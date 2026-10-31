from __future__ import annotations

from dataclasses import fields, is_dataclass
from pathlib import Path

from ..sintatico.ast import (
    Assignment,
    ASTNode,
    BinaryExpr,
    BoolExpr,
    BreakStmt,
    CChannelExpr,
    ChannelDecl,
    ClassDecl,
    ContinueStmt,
    DoWhileStmt,
    ForStmt,
    FuncCallExpr,
    FuncDecl,
    ForkStmt,
    IdentifierExpr,
    IfStmt,
    IndexAssign,
    IndexExpr,
    InputExpr,
    JoinStmt,
    ListLiteral,
    MatrixCreateExpr,
    MethodCall,
    NewExpr,
    NumberExpr,
    ParBlock,
    PrintStmt,
    Program,
    PropertyAccess,
    PropertyAssign,
    ReceiveExpr,
    ReturnStmt,
    SendStmt,
    SeqBlock,
    StringExpr,
    ThisExpr,
    UnaryExpr,
    VarDecl,
    WhileStmt,
)


class TACGenerator:
    """Converte a AST MiniPar para uma representação textual de TAC."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.temp_count = 0
        self.label_count = 0
        self.break_stack: list[str] = []
        self.continue_stack: list[str] = []
        self.variable_types: dict[str, str] = {}
        self.functions: dict[str, FuncDecl] = {}
        self.classes: dict[str, ClassDecl] = {}
        self.class_fields: dict[str, dict[str, tuple[int, str, ASTNode | None]]] = {}
        self.class_methods: dict[str, dict[str, tuple[str, FuncDecl]]] = {}
        self.current_class: str | None = None
        self.parameter_types: dict[str, tuple[str, ...]] = {}

    def _temp(self, type_: str | None = None) -> str:
        name = f"t{self.temp_count}"
        self.temp_count += 1
        return f"{name}:{type_}" if type_ else name

    def _label(self, prefix: str) -> str:
        name = f"{prefix}_{self.label_count}"
        self.label_count += 1
        return name

    def _emit(self, line: str = "") -> None:
        self.lines.append(line)

    def _type_of(self, node: ASTNode | None) -> str | None:
        if node is None:
            return None
        if node.tipo_inferido and node.tipo_inferido not in ("unknown", "var"):
            return node.tipo_inferido
        if isinstance(node, NumberExpr):
            return "float" if "." in node.value else "int"
        if isinstance(node, StringExpr):
            return "string"
        if isinstance(node, BoolExpr):
            return "bool"
        if isinstance(node, ListLiteral):
            return "list"
        if isinstance(node, NewExpr):
            return node.class_name
        if isinstance(node, IdentifierExpr):
            return self.variable_types.get(node.name)
        if isinstance(node, PropertyAccess):
            class_name = self._class_of(node.object)
            field = self._field(class_name, node.property_name)
            return field[1] if field else None
        if isinstance(node, MethodCall):
            class_name = self._class_of(node.object)
            method = self._method(class_name, node.method_name)
            if method:
                declaration = method[1]
                return declaration.return_type
        if isinstance(node, UnaryExpr):
            return "bool" if node.op in ("!", "not") else self._type_of(node.operand)
        if isinstance(node, BinaryExpr):
            if node.op in (
                "==", "!=", "<", ">", "<=", ">=", "and", "or", "&&", "||"
            ):
                return "bool"
            left, right = self._type_of(node.left), self._type_of(node.right)
            if left == "float" or right == "float":
                return "float"
            if left == right == "int":
                return "int"
        if isinstance(node, FuncCallExpr):
            if node.name in self.functions:
                return self.functions[node.name].return_type
        if isinstance(node, InputExpr):
            return "string"
        return None

    def _class_of(self, node: ASTNode | None) -> str | None:
        if isinstance(node, ThisExpr):
            return self.current_class
        if isinstance(node, IdentifierExpr):
            return self.variable_types.get(node.name)
        if isinstance(node, NewExpr):
            return node.class_name
        if isinstance(node, PropertyAccess):
            return self._type_of(node)
        if isinstance(node, (FuncCallExpr, MethodCall)):
            return self._type_of(node)
        return None

    def _field(
        self, class_name: str | None, field_name: str
    ) -> tuple[int, str, ASTNode | None] | None:
        if class_name is None:
            return None
        return self.class_fields.get(class_name, {}).get(field_name)

    def _method(
        self, class_name: str | None, method_name: str
    ) -> tuple[str, FuncDecl] | None:
        if class_name is None:
            return None
        return self.class_methods.get(class_name, {}).get(method_name)

    def _build_class_layouts(self, declarations: list[ClassDecl]) -> None:
        self.classes = {declaration.name: declaration for declaration in declarations}
        self.class_fields = {}
        self.class_methods = {}
        building: set[str] = set()

        def build(class_name: str) -> None:
            if class_name in self.class_fields:
                return
            if class_name in building:
                raise ValueError(f"Ciclo de heranca TAC em '{class_name}'")
            declaration = self.classes[class_name]
            building.add(class_name)
            fields: dict[str, tuple[int, str, ASTNode | None]] = {}
            methods: dict[str, tuple[str, FuncDecl]] = {}
            if declaration.superclass:
                if declaration.superclass not in self.classes:
                    raise ValueError(
                        f"Classe base TAC nao definida: {declaration.superclass}"
                    )
                build(declaration.superclass)
                fields.update(self.class_fields[declaration.superclass])
                methods.update(self.class_methods[declaration.superclass])
            for attribute in declaration.attributes:
                offset = len(fields)
                field_type = attribute.type
                if field_type == "var":
                    field_type = self._type_of(attribute.init_value) or field_type
                fields[attribute.name] = (
                    offset,
                    field_type,
                    attribute.init_value,
                )
            for method in declaration.methods:
                methods[method.name] = (class_name, method)
            self.class_fields[class_name] = fields
            self.class_methods[class_name] = methods
            building.remove(class_name)

        for class_name in self.classes:
            build(class_name)

    def _new_temp(self, node: ASTNode | None, expression: str) -> str:
        target = self._temp(self._type_of(node))
        self._emit(f"{target} = {expression}")
        return target.split(":", 1)[0]

    @staticmethod
    def _literal(node: ASTNode | None) -> str:
        if isinstance(node, NumberExpr):
            return node.value
        if isinstance(node, StringExpr):
            return repr(node.value)
        if isinstance(node, BoolExpr):
            return "true" if node.value else "false"
        return "0"

    def _expr(self, node: ASTNode | None) -> str:
        if node is None:
            return "0"
        if isinstance(node, (NumberExpr, StringExpr, BoolExpr)):
            return self._literal(node)
        if isinstance(node, IdentifierExpr):
            return node.name
        if isinstance(node, ThisExpr):
            return "self"
        if isinstance(node, UnaryExpr):
            value = self._expr(node.operand)
            operator = "not " if node.op in ("!", "not") else node.op
            return self._new_temp(node, f"{operator}{value}")
        if isinstance(node, BinaryExpr):
            if node.op in ("and", "or", "&&", "||"):
                return self._logical_expr(node)
            left = self._expr(node.left)
            right = self._expr(node.right)
            return self._new_temp(node, f"{left} {node.op} {right}")
        if isinstance(node, ListLiteral):
            values = ", ".join(self._expr(item) for item in node.elements)
            return self._new_temp(node, f"[{values}]")
        if isinstance(node, MatrixCreateExpr):
            rows, cols, value = (
                self._expr(node.rows),
                self._expr(node.cols),
                self._expr(node.init_value),
            )
            return self._new_temp(node, f"matrix({rows}, {cols}, {value})")
        if isinstance(node, IndexExpr):
            array, index = self._expr(node.object), self._expr(node.index)
            return self._new_temp(node, f"{array}[{index}]")
        if isinstance(node, PropertyAccess):
            class_name = self._class_of(node.object)
            field = self._field(class_name, node.property_name)
            if field is None:
                raise ValueError(
                    f"Campo TAC nao definido: {class_name}.{node.property_name}"
                )
            target = self._temp(self._type_of(node))
            self._emit(
                f"{target} = getfield {self._expr(node.object)}, {field[0]}"
            )
            return target.split(":", 1)[0]
        if isinstance(node, FuncCallExpr):
            if node.name == "receive":
                if len(node.arguments) != 1:
                    raise ValueError("receive TAC espera exatamente um canal")
                target = self._temp(self._type_of(node))
                self._emit(f"{target} = recv {self._expr(node.arguments[0])}")
                return target.split(":", 1)[0]
            if node.name == "send":
                if len(node.arguments) != 2:
                    raise ValueError("send TAC espera canal e mensagem")
                self._emit(
                    f"send {self._expr(node.arguments[0])}, "
                    f"{self._expr(node.arguments[1])}"
                )
                return "0"
            if node.name == "to_number":
                if len(node.arguments) != 1:
                    raise ValueError("to_number TAC espera exatamente um argumento")
                return self._new_temp(
                    node, f"to_number({self._expr(node.arguments[0])})"
                )
            function = self.functions.get(node.name)
            function_arguments: list[ASTNode | None] = list(node.arguments)
            if function:
                function_arguments.extend(
                    parameter.default_value
                    for parameter in function.params[len(function_arguments):]
                )
            for argument in function_arguments:
                self._emit(f"param {self._expr(argument)}")
            call = f"call {node.name}, {len(function_arguments)}"
            if function and (
                function.return_type or self._function_return_type(function.body)
            ) == "void":
                self._emit(call)
                return "0"
            return self._new_temp(node, call)
        if isinstance(node, MethodCall):
            if node.method_name in ("send", "receive"):
                receiver = self._expr(node.object)
                if node.method_name == "send":
                    for argument in node.arguments:
                        self._emit(f"send {receiver}, {self._expr(argument)}")
                    return "0"
                target = self._temp(self._type_of(node))
                self._emit(f"{target} = recv {receiver}")
                return target.split(":", 1)[0]
            class_name = self._class_of(node.object)
            method = self._method(class_name, node.method_name)
            if method is None:
                raise ValueError(
                    f"Metodo TAC nao definido: {class_name}.{node.method_name}"
                )
            owner, declaration = method
            receiver = self._expr(node.object)
            method_arguments: list[ASTNode | None] = list(node.arguments)
            method_arguments.extend(
                parameter.default_value
                for parameter in declaration.params[len(method_arguments):]
            )
            self._emit(f"param {receiver}")
            for argument in method_arguments:
                self._emit(f"param {self._expr(argument)}")
            call_name = f"{owner}_{node.method_name}"
            call = f"call {call_name}, {len(method_arguments) + 1}"
            if (
                declaration.return_type
                or self._function_return_type(declaration.body)
            ) == "void":
                self._emit(call)
                return "0"
            return self._new_temp(node, call)
        if isinstance(node, NewExpr):
            if node.class_name not in self.class_fields:
                raise ValueError(f"Classe TAC nao definida: {node.class_name}")
            object_name = self._temp(node.class_name)
            self._emit(f"{object_name} = alloc {len(self.class_fields[node.class_name])}")
            object_value = object_name.split(":", 1)[0]
            for _, (offset, _, default_value) in enumerate(
                self.class_fields[node.class_name].values()
            ):
                if default_value is not None:
                    self._emit(
                        f"setfield {object_value}, {offset}, "
                        f"{self._expr(default_value)}"
                    )
            initializer = self._method(node.class_name, "init")
            if initializer is not None:
                owner, declaration = initializer
                constructor_arguments: list[ASTNode | None] = list(node.arguments)
                constructor_arguments.extend(
                    parameter.default_value
                    for parameter in declaration.params[len(constructor_arguments):]
                )
                self._emit(f"param {object_value}")
                for argument in constructor_arguments:
                    self._emit(f"param {self._expr(argument)}")
                self._emit(
                    f"call {owner}_init, {len(constructor_arguments) + 1}"
                )
            elif node.arguments:
                raise ValueError(
                    f"Construtor TAC de '{node.class_name}' nao aceita argumentos"
                )
            return object_value
        if isinstance(node, CChannelExpr):
            return self._new_temp(
                node, f"c_channel({self._expr(node.ip)}, {self._expr(node.port)})"
            )
        if isinstance(node, ReceiveExpr):
            target = self._temp(self._type_of(node))
            self._emit(f"{target} = recv {self._expr(node.channel)}")
            return target.split(":", 1)[0]
        if isinstance(node, InputExpr):
            prompt = self._expr(node.prompt) if node.prompt else ""
            return self._new_temp(node, f"input({prompt})")
        raise NotImplementedError(
            f"Expressao sem lowering TAC: {type(node).__name__}"
        )

    def _logical_expr(self, node: BinaryExpr) -> str:
        result = self._temp("bool")
        result_name = result.split(":", 1)[0]
        end = self._label("LOGICAL_END")
        is_and = node.op in ("and", "&&")
        short_value = "false" if is_and else "true"
        left = self._expr(node.left)
        self._emit(f"{result} = {short_value if is_and else 'false'}")
        branch = self._label("LOGICAL_RHS")
        self._emit(f"if {left} goto {branch}" if is_and else f"ifFalse {left} goto {branch}")
        self._emit(f"{result_name} = {short_value}")
        self._emit(f"goto {end}")
        self._emit(f"{branch}:")
        right = self._expr(node.right)
        self._emit(f"{result_name} = {right}")
        self._emit(f"{end}:")
        return result_name

    def _assign_type(
        self, name: str, node: ASTNode | None, declared: str = "var"
    ) -> None:
        inferred = self._type_of(node)
        if declared != "var":
            inferred = declared
        if inferred:
            self.variable_types[name] = inferred

    def _emit_function(
        self,
        declaration: FuncDecl,
        name: str,
        class_name: str | None = None,
    ) -> None:
        parameter_types = self.parameter_types.get(name, ())
        previous_types = self.variable_types
        previous_class = self.current_class
        self.variable_types = {
            parameter.name: (
                parameter.type
                if parameter.type != "var"
                else parameter_types[index]
                if index < len(parameter_types)
                else "int"
            )
            for index, parameter in enumerate(declaration.params)
        }
        if class_name:
            self.variable_types["self"] = class_name
        self.current_class = class_name
        parameters = (["self:" + (class_name or "var")] if class_name else []) + [
            f"{parameter.name}:{parameter.type if parameter.type != 'var' else parameter_types[index] if index < len(parameter_types) else 'int'}"
            for index, parameter in enumerate(declaration.params)
        ]
        return_type = declaration.return_type or self._function_return_type(
            declaration.body
        )
        self._emit(f"# source: {declaration.line}")
        self._emit(
            f"func {name}({', '.join(parameters)}) -> {return_type}:"
        )
        self._stmt(declaration.body)
        self._emit("endfunc")
        self.variable_types = previous_types
        self.current_class = previous_class

    def _function_return_type(self, node: ASTNode | None) -> str:
        return_types: list[str] = []

        def visit(value: object) -> None:
            if isinstance(value, ReturnStmt) and value.value is not None:
                inferred = self._type_of(value.value)
                if inferred and inferred not in ("unknown", "var"):
                    return_types.append(inferred)
            if is_dataclass(value):
                for field in fields(value):
                    child = getattr(value, field.name)
                    if isinstance(child, tuple):
                        for item in child:
                            visit(item)
                    elif is_dataclass(child):
                        visit(child)

        visit(node)
        if return_types:
            return return_types[0]
        if any(isinstance(value, ReturnStmt) and value.value is not None for value in self._walk(node)):
            return "int"
        return "void"

    @staticmethod
    def _walk(node: object) -> tuple[object, ...]:
        values: list[object] = []

        def visit(value: object) -> None:
            if is_dataclass(value):
                values.append(value)
                for field in fields(value):
                    child = getattr(value, field.name)
                    if isinstance(child, tuple):
                        for item in child:
                            visit(item)
                    elif is_dataclass(child):
                        visit(child)

        visit(node)
        return tuple(values)

    def _prepare_parameter_types(self, program: Program) -> None:
        declarations = {
            statement.name: statement
            for statement in program.statements
            if isinstance(statement, FuncDecl)
        }
        for statement in program.statements:
            if isinstance(statement, ClassDecl):
                declarations.update(
                    {
                        f"{statement.name}_{method.name}": method
                        for method in statement.methods
                    }
                )
        source_types: dict[str, str] = {}
        calls: dict[str, list[tuple[ASTNode | None, ...]]] = {}

        def visit(node: object) -> None:
            if isinstance(node, ClassDecl):
                previous_class = self.current_class
                self.current_class = node.name
                for attribute in node.attributes:
                    visit(attribute)
                for method in node.methods:
                    visit(method)
                self.current_class = previous_class
                return
            if isinstance(node, VarDecl) and node.init_value is not None:
                source_types[node.name] = self._type_of(node.init_value) or node.type
            if isinstance(node, FuncCallExpr):
                calls.setdefault(node.name, []).append(node.arguments)
            if isinstance(node, MethodCall):
                calls.setdefault(node.method_name, []).append(node.arguments)
            if is_dataclass(node):
                for field in fields(node):
                    child = getattr(node, field.name)
                    if isinstance(child, tuple):
                        for item in child:
                            visit(item)
                    elif is_dataclass(child):
                        visit(child)

        visit(program)
        self.parameter_types = {}
        for name, declaration in declarations.items():
            inferred: list[str] = []
            call_arguments = calls.get(name, [])
            if not call_arguments and "_" in name:
                call_arguments = calls.get(name.rsplit("_", 1)[1], [])
            for index, parameter in enumerate(declaration.params):
                if parameter.type != "var":
                    inferred.append(parameter.type)
                    continue
                argument_type = None
                for arguments in call_arguments:
                    if index >= len(arguments):
                        continue
                    argument = arguments[index]
                    argument_type = self._type_of(argument)
                    if argument_type in ("unknown", "var"):
                        argument_type = None
                    if argument_type is None and isinstance(argument, IdentifierExpr):
                        argument_type = source_types.get(argument.name)
                    if argument_type:
                        break
                inferred.append(argument_type or "int")
            self.parameter_types[name] = tuple(inferred)

    def _stmt(self, node: ASTNode | None) -> None:
        if node is None:
            return
        self._emit(f"# source: {node.line}")
        if isinstance(node, VarDecl):
            self._assign_type(node.name, node.init_value, node.type)
            declared_type = node.type if node.type != "var" else self.variable_types.get(node.name)
            suffix = f":{declared_type}" if declared_type else ""
            self._emit(f"{node.name}{suffix} = {self._expr(node.init_value)}")
        elif isinstance(node, Assignment):
            self._assign_type(node.name, node.value)
            declared_type = self.variable_types.get(node.name)
            suffix = f":{declared_type}" if declared_type else ""
            self._emit(f"{node.name}{suffix} = {self._expr(node.value)}")
        elif isinstance(node, PropertyAssign):
            class_name = self._class_of(node.object)
            field = self._field(class_name, node.property_name)
            if field is None:
                raise ValueError(
                    f"Campo TAC nao definido: {class_name}.{node.property_name}"
                )
            self._emit(
                f"setfield {self._expr(node.object)}, {field[0]}, "
                f"{self._expr(node.value)}"
            )
        elif isinstance(node, IndexAssign):
            if not isinstance(node.target, IndexExpr):
                raise NotImplementedError("Atribuicao indexada TAC requer IndexExpr")
            array = self._expr(node.target.object)
            index = self._expr(node.target.index)
            value = self._expr(node.value)
            self._emit(f"{array}[{index}] = {value}")
        elif isinstance(node, PrintStmt):
            arguments = [self._expr(argument) for argument in node.arguments]
            self._emit(f"print {', '.join(arguments)}")
        elif isinstance(node, SendStmt):
            self._emit(f"send {self._expr(node.channel)}, {self._expr(node.message)}")
        elif isinstance(node, ChannelDecl):
            self._emit(
                f"{node.name} = c_channel({node.first_host!r}, "
                f"{node.second_host!r})"
            )
        elif isinstance(node, ParBlock):
            parallel_id = self._label("PAR")
            end = self._label("PAREND")
            task_names = [
                f"__{parallel_id}_branch_{index}"
                for index in range(len(node.statements))
            ]
            branch_labels = [
                self._label(f"{parallel_id}_BRANCH")
                for _ in node.statements
            ]
            self._emit(f"par_begin {len(node.statements)}")
            for task_name, branch_label in zip(task_names, branch_labels):
                self._emit(f"fork {task_name}, simulated, 0, {branch_label}")
            self._emit(f"join {', '.join(task_names)}")
            self._emit(f"goto {end}")
            for statement, task_name, branch_label in zip(
                node.statements, task_names, branch_labels
            ):
                self._emit(f"{branch_label}:")
                self._stmt(statement)
                self._emit(f"join {task_name}")
            self._emit(f"{end}:")
            self._emit("par_end")
        elif isinstance(node, ForkStmt):
            branch_label = self._label("FORK")
            end = self._label("ENDFORK")
            target = self._expr(node.target) if node.target else "0"
            target_kind = node.target_kind or "core"
            self._emit(
                f"fork {node.task_name}, {target_kind}, {target}, {branch_label}"
            )
            self._emit(f"goto {end}")
            self._emit(f"{branch_label}:")
            self._stmt(node.body)
            self._emit(f"join {node.task_name}")
            self._emit(f"{end}:")
        elif isinstance(node, JoinStmt):
            self._emit(f"join {', '.join(node.task_names)}")
        elif isinstance(node, SeqBlock):
            for statement in node.statements:
                self._stmt(statement)
        elif isinstance(node, IfStmt):
            end = self._label("ENDIF")
            else_label = self._label("ELSE") if node.else_branch else end
            self._emit(f"ifFalse {self._expr(node.condition)} goto {else_label}")
            self._stmt(node.then_branch)
            if node.else_branch:
                self._emit(f"goto {end}")
                self._emit(f"{else_label}:")
                self._stmt(node.else_branch)
            self._emit(f"{end}:")
        elif isinstance(node, WhileStmt):
            start, end = self._label("WHILE"), self._label("ENDWHILE")
            self.break_stack.append(end)
            self.continue_stack.append(start)
            self._emit(f"{start}:")
            self._emit(f"ifFalse {self._expr(node.condition)} goto {end}")
            self._stmt(node.body)
            self._emit(f"goto {start}")
            self._emit(f"{end}:")
            self.break_stack.pop()
            self.continue_stack.pop()
        elif isinstance(node, DoWhileStmt):
            start = self._label("DO")
            condition, end = self._label("DO_CONDITION"), self._label("ENDDO")
            self.break_stack.append(end)
            self.continue_stack.append(condition)
            self._emit(f"{start}:")
            self._stmt(node.body)
            self._emit(f"{condition}:")
            self._emit(f"if {self._expr(node.condition)} goto {start}")
            self._emit(f"{end}:")
            self.break_stack.pop()
            self.continue_stack.pop()
        elif isinstance(node, ForStmt):
            if node.iterator_name:
                iterable = self._expr(node.iterable)
                index = self._temp("int")
                index_name = index.split(":", 1)[0]
                sequence = self._temp("list")
                sequence_name = sequence.split(":", 1)[0]
                self._emit(f"{sequence} = {iterable}")
                self._emit(f"{index} = 0")
                start, step, end = (
                    self._label("FOR"),
                    self._label("FOR_STEP"),
                    self._label("ENDFOR"),
                )
                self.break_stack.append(end)
                self.continue_stack.append(step)
                self._emit(f"{start}:")
                self._emit(f"if {index_name} >= len({sequence_name}) goto {end}")
                self._emit(
                    f"{node.iterator_name} = {sequence_name}[{index_name}]"
                )
                self._stmt(node.body)
                self._emit(f"{step}:")
                self._emit(f"{index_name} = {index_name} + 1")
                self._emit(f"goto {start}")
                self._emit(f"{end}:")
                self.break_stack.pop()
                self.continue_stack.pop()
                return
            start, step, end = (
                self._label("FOR"),
                self._label("FOR_STEP"),
                self._label("ENDFOR"),
            )
            self._stmt(node.initializer)
            self.break_stack.append(end)
            self.continue_stack.append(step)
            self._emit(f"{start}:")
            if node.condition:
                self._emit(f"ifFalse {self._expr(node.condition)} goto {end}")
            self._stmt(node.body)
            self._emit(f"{step}:")
            self._stmt(node.increment)
            self._emit(f"goto {start}")
            self._emit(f"{end}:")
            self.break_stack.pop()
            self.continue_stack.pop()
        elif isinstance(node, BreakStmt):
            if not self.break_stack:
                raise ValueError("break fora de loop")
            self._emit(f"goto {self.break_stack[-1]}")
        elif isinstance(node, ContinueStmt):
            if not self.continue_stack:
                raise ValueError("continue fora de loop")
            self._emit(f"goto {self.continue_stack[-1]}")
        elif isinstance(node, ReturnStmt):
            self._emit(f"ret {self._expr(node.value)}" if node.value else "ret")
        elif isinstance(node, (FuncCallExpr, MethodCall)):
            self._expr(node)
        elif isinstance(node, ClassDecl):
            for method in node.methods:
                self._emit_function(
                    method, f"{node.name}_{method.name}", node.name
                )
        elif isinstance(node, FuncDecl):
            self._emit_function(node, node.name)
        else:
            raise NotImplementedError(
                f"Instrucao sem lowering TAC: {type(node).__name__}"
            )

    def generate_text(self, program: Program) -> str:
        self.lines = []
        self.temp_count = 0
        self.label_count = 0
        self.break_stack = []
        self.continue_stack = []
        self.variable_types = {}
        self.functions = {
            statement.name: statement
            for statement in program.statements
            if isinstance(statement, FuncDecl)
        }
        class_declarations = [
            statement for statement in program.statements
            if isinstance(statement, ClassDecl)
        ]
        self._build_class_layouts(class_declarations)
        self._prepare_parameter_types(program)
        for class_name, fields_by_name in self.class_fields.items():
            field_types = ", ".join(
                field_type
                for _, field_type, _ in fields_by_name.values()
            )
            self._emit(f"# class {class_name}: {field_types}")
        functions = [
            statement for statement in program.statements
            if isinstance(statement, (FuncDecl, ClassDecl))
        ]
        main_statements = [
            statement for statement in program.statements
            if not isinstance(statement, (FuncDecl, ClassDecl))
        ]
        if functions:
            self._emit("goto MAIN")
            for function in functions:
                self._stmt(function)
            self._emit("MAIN:")
        for statement in main_statements:
            self._stmt(statement)
        return "\n".join(self.lines) + ("\n" if self.lines else "")

    def imprimir_tac(self, program: Program) -> str:
        return self.generate_text(program)

    def generate(self, program: Program, output_name: str) -> str:
        output_dir = Path(__file__).resolve().parents[2] / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        tac_path = output_dir / f"{output_name}.tac"
        tac_path.write_text(self.generate_text(program), encoding="utf-8")
        return str(tac_path)


def imprimir_tac(tac: str | Program) -> str:
    """Devolve o TAC em formato textual legível."""
    if isinstance(tac, Program):
        return TACGenerator().generate_text(tac)
    return tac
