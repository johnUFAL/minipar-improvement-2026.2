from __future__ import annotations

import sys
from collections.abc import Sequence

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
    ForkStmt,
    FuncCallExpr,
    FuncDecl,
    IdentifierExpr,
    IfStmt,
    JoinStmt,
    IndexAssign,
    IndexExpr,
    InputExpr,
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
from ..tabela_simbolos.c_tabela_simbolos import Symbol, TabelaSimbolos
from ..interfaces import ITabelaSimbolos
from erros.diagnosticos import Diagnostic, DiagnosticBag, Phase


_EXPRESSION_NODES = (
    NumberExpr,
    StringExpr,
    BoolExpr,
    IdentifierExpr,
    BinaryExpr,
    UnaryExpr,
    FuncCallExpr,
    MethodCall,
    PropertyAccess,
    NewExpr,
    ThisExpr,
    CChannelExpr,
    ReceiveExpr,
    InputExpr,
    ListLiteral,
    MatrixCreateExpr,
    IndexExpr,
)


class SemanticAnalyzer:
    def __init__(
        self,
        diagnostics: DiagnosticBag | None = None,
        symbol_table: ITabelaSimbolos | None = None,
    ) -> None:
        self._symbol_table = (
            symbol_table if symbol_table is not None else TabelaSimbolos()
        )
        self._has_errors = False
        self._diagnostics = diagnostics
        self._reported_diagnostics: list[Diagnostic] = []
        self._current_function: str | None = None
        self._current_class: str | None = None
        self._current_return_type: str | None = None
        self._loop_depth = 0
        self._class_declarations: dict[str, ClassDecl] = {}
        self._concurrent_scope_paths: list[str] = []
        self._fork_scopes: list[dict[str, ForkStmt]] = []
        self._channel_calls: dict[
            str,
            dict[str, list[tuple[tuple[str, ...], MethodCall | FuncCallExpr]]],
        ] = {}

    def _enter_scope(self) -> None: self._symbol_table.enter_scope()

    def _exit_scope(self) -> None:
        self._symbol_table.exit_scope()

    def _get_context(self) -> str:
        return f" (Funcao: {self._current_function})" if self._current_function else ""

    def _define_symbol(
        self,
        name: str,
        type_: str,
        line: int,
        category: str = "variable",
        params: tuple[str, ...] | None = None,
        column: int | None = None,
        parameter_types: tuple[str, ...] = (),
        required_params: int | None = None,
    ) -> None:
        symbol = Symbol(
            name,
            type_,
            params=params or (),
            category=category,
            line=line,
            parameter_types=parameter_types,
            required_params=required_params,
        )
        if not self._symbol_table.define(symbol):
            self._report(
                line,
                f"Identificador '{name}' ja declarado neste escopo.",
                column,
            )

    def _lookup(self, name: str) -> Symbol | None:
        return self._symbol_table.lookup(name)

    def _concurrent_write_is_external(self, symbol: Symbol) -> bool:
        return any(
            symbol.scope != scope_path
            and not symbol.scope.startswith(f"{scope_path}/")
            for scope_path in self._concurrent_scope_paths
        )

    def _check_concurrent_write(
        self, name: str, line: int, column: int | None
    ) -> None:
        symbol = self._lookup(name)
        if (
            symbol is not None
            and symbol.category not in ("channel", "function", "class", "task")
            and self._concurrent_write_is_external(symbol)
        ):
            self._report(
                line,
                f"Ramo concorrente nao pode escrever na variavel externa "
                f"'{name}'.",
                column,
            )

    def _check_write_target(self, target: ASTNode | None) -> None:
        while isinstance(target, (PropertyAccess, IndexExpr)):
            target = target.object
        if isinstance(target, IdentifierExpr):
            self._check_concurrent_write(
                target.name, target.line, target.column
            )

    def _record_channel_call(
        self,
        channel_name: str,
        direction: str,
        signature: tuple[str, ...],
        call: MethodCall | FuncCallExpr,
    ) -> None:
        self._channel_calls.setdefault(
            channel_name, {"send": [], "receive": []}
        )[direction].append((signature, call))

    def _finish_fork_scope(self) -> None:
        if not self._fork_scopes:
            return
        scope = self._fork_scopes.pop()
        for task_name, fork in scope.items():
            self._report(
                fork.line,
                f"Fork '{task_name}' nao possui join neste escopo.",
                fork.column,
            )

    @property
    def symbol_table(self) -> ITabelaSimbolos:
        return self._symbol_table

    def _class_symbol(self, name: str) -> Symbol | None:
        symbol = self._symbol_table.lookup(name)
        return symbol if symbol is not None and symbol.category == "class" else None

    def _is_subclass(self, candidate: str, expected: str) -> bool:
        visited: set[str] = set()
        current = candidate
        while current not in visited:
            if current == expected:
                return True
            visited.add(current)
            class_symbol = self._class_symbol(current)
            if class_symbol is None or class_symbol.parent_class is None:
                return False
            current = class_symbol.parent_class
        return False

    def _function_symbol(self, name: str) -> Symbol | None:
        symbol = self._symbol_table.lookup(name)
        return symbol if symbol is not None and symbol.category == "function" else None

    def _report(
        self, line: int, message: str, column: int | None = None
    ) -> None:
        contextual_message = f"{message}{self._get_context()}"
        diagnostic = Diagnostic(
            Phase.SEMANTIC, contextual_message, line, column
        )
        self._reported_diagnostics.append(diagnostic)
        if self._diagnostics is not None:
            self._diagnostics.report(diagnostic)
        else:
            print(
                f"[ERRO SEMANTICO] Linha {line}: {contextual_message}",
                file=sys.stderr,
            )
        self._has_errors = True

    @property
    def diagnostics(self) -> Sequence[Diagnostic]:
        return tuple(self._reported_diagnostics)

    def set_diagnostic_collector(self, diagnostics: DiagnosticBag) -> None:
        self._diagnostics = diagnostics

    def _infer_type(self, node: ASTNode | None) -> str:
        inferred_type = self._infer_type_impl(node)
        if isinstance(node, _EXPRESSION_NODES):
            node.definir_tipo_inferido(inferred_type)
        return inferred_type

    def _infer_type_impl(self, node: ASTNode | None) -> str:
        if node is None:
            return "unknown"
        if isinstance(node, NumberExpr):
            return "float" if "." in node.value else "int"
        if isinstance(node, StringExpr):
            return "string"
        if isinstance(node, BoolExpr):
            return "bool"
        if isinstance(node, InputExpr):
            return "string"
        if isinstance(node, CChannelExpr):
            return "c_channel"
        if isinstance(node, ReceiveExpr):
            return "string"
        if isinstance(node, ListLiteral):
            return "list"
        if isinstance(node, MatrixCreateExpr):
            return "matrix"
        if isinstance(node, NewExpr):
            return node.class_name
        if isinstance(node, ThisExpr):
            return self._current_class or "unknown"
        if isinstance(node, IdentifierExpr):
            sym = self._lookup(node.name)
            return sym.type if sym else "unknown"
        if isinstance(node, UnaryExpr):
            return "bool" if node.op in ("!", "not") else self._infer_type(node.operand)
        if isinstance(node, BinaryExpr):
            lt, rt = self._infer_type(node.left), self._infer_type(node.right)
            if node.op in (
                "==",
                "!=",
                "<",
                ">",
                "<=",
                ">=",
                "and",
                "or",
                "&&",
                "||",
            ):
                return "bool"
            if node.op == "+" and lt == rt == "string":
                return "string"
            if node.op == "+" and lt == rt == "list":
                return "list"
            if lt in ("int", "float") and rt in ("int", "float"):
                return "float" if "float" in (lt, rt) or node.op == "/" else "int"
            return "unknown"
        if isinstance(node, PropertyAccess):
            obj_type = self._infer_type(node.object)
            attribute = self._symbol_table.lookup_attribute(
                obj_type, node.property_name
            )
            if attribute is not None:
                return attribute.type
            return "unknown"
        if isinstance(node, MethodCall):
            object_type = self._infer_type(node.object)
            method = self._symbol_table.lookup_method(object_type, node.method_name)
            if method is not None:
                return method.type
            return {
                ("string", "split"): "list",
                ("string", "strip"): "string",
                ("list", "append"): "void",
                ("list", "pop"): "unknown",
                ("c_channel", "send"): "void",
                ("c_channel", "receive"): "string",
            }.get((object_type, node.method_name), "unknown")
        if isinstance(node, FuncCallExpr):
            function = self._function_symbol(node.name)
            if function is not None:
                return function.type
            if node.name == "c_channel":
                return "c_channel"
            if node.name in ("random", "exp", "float", "to_number", "clock", "inf"):
                return "float"
            if node.name == "receive":
                return "string"
            if node.name == "send":
                return "void"
            if node.name in ("int", "len", "parse_ints", "str", "format_float"):
                return "string" if node.name in ("str", "format_float") else (
                    "list" if node.name == "parse_ints" else "int"
                )
            if node.name in ("range",):
                return "list"
            if node.name in ("is_number",):
                return "bool"
            return "unknown"
        if isinstance(node, IndexExpr):
            object_type = self._infer_type(node.object)
            if object_type == "string":
                return "string"
            return "unknown"
        return "unknown"

    def _types_compatible(self, declared: str, actual: str) -> bool:
        if declared in ("var", "unknown") or actual in ("var", "unknown"):
            return True
        if declared == "float" and actual == "int":
            return True
        if self._class_symbol(declared) and self._class_symbol(actual):
            return self._is_subclass(actual, declared)
        return declared == actual

    @staticmethod
    def _is_numeric(type_: str) -> bool:
        return type_ in ("int", "float", "var", "unknown")

    def _check_condition(self, node: ASTNode | None) -> None:
        condition_type = self._infer_type(node)
        if condition_type not in ("bool", "unknown", "var"):
            self._report(
                node.line if node is not None else 1,
                f"Condicao deve ser bool, recebeu {condition_type}.",
                node.column if node is not None else None,
            )

    def _always_returns(self, node: ASTNode | None) -> bool:
        if isinstance(node, ReturnStmt):
            return True
        if isinstance(node, SeqBlock):
            return any(self._always_returns(statement) for statement in node.statements)
        if isinstance(node, IfStmt):
            return (
                node.else_branch is not None
                and self._always_returns(node.then_branch)
                and self._always_returns(node.else_branch)
            )
        return False

    def _check_call_arguments(
        self,
        node: FuncCallExpr | MethodCall | NewExpr,
        parameter_types: tuple[str, ...],
        required_params: int,
        name: str,
    ) -> None:
        count = len(node.arguments)
        if count < required_params or count > len(parameter_types):
            expected = (
                f"{required_params} a {len(parameter_types)}"
                if required_params != len(parameter_types)
                else str(len(parameter_types))
            )
            self._report(
                node.line,
                f"'{name}' espera {expected} argumento(s), recebeu {count}.",
                node.column,
            )
        for index, (argument, expected_type) in enumerate(
            zip(node.arguments, parameter_types)
        ):
            actual_type = self._infer_type(argument)
            if not self._types_compatible(expected_type, actual_type):
                self._report(
                    argument.line,
                    f"Tipo incompativel no argumento {index + 1} de '{name}': "
                    f"esperado {expected_type}, recebido {actual_type}.",
                    argument.column,
                )

    def _parameter_types(self, function: FuncDecl) -> tuple[str, ...]:
        return tuple(
            param.type
            if param.type != "var" or param.default_value is None
            else self._infer_type(param.default_value)
            for param in function.params
        )

    def _check_builtin_call(self, node: FuncCallExpr) -> None:
        signatures: dict[str, tuple[tuple[str, ...], int]] = {
            "exp": (("float",), 1),
            "random": ((), 0),
            "range": (("int", "int", "int"), 1),
            "len": (("var",), 1),
            "to_number": (("string",), 1),
            "parse_ints": (("string",), 1),
            "str": (("var",), 1),
            "int": (("var",), 1),
            "float": (("var",), 1),
            "inf": ((), 0),
            "clock": ((), 0),
            "format_float": (("float", "int"), 2),
            "is_number": (("string",), 1),
            "receive": (("c_channel",), 1),
            "send": (("c_channel",) + ("var",) * 7, 2),
            "c_channel": (("string", "int"), 2),
        }
        signature = signatures.get(node.name)
        if signature is not None:
            parameter_types, required_params = signature
            self._check_call_arguments(
                node, parameter_types, required_params, node.name
            )

    def _collect_declarations(self, program: Program) -> None:
        classes: list[ClassDecl] = []
        self._class_declarations = {}
        for stmt in program.statements:
            if isinstance(stmt, ChannelDecl):
                self._define_symbol(
                    stmt.name,
                    "c_channel",
                    stmt.line,
                    "channel",
                    column=stmt.column,
                )
            elif isinstance(stmt, FuncDecl):
                self._define_symbol(
                    stmt.name,
                    stmt.return_type or "unknown",
                    stmt.line,
                    category="function",
                    params=tuple(param.name for param in stmt.params),
                    column=stmt.column,
                    parameter_types=self._parameter_types(stmt),
                    required_params=sum(
                        param.default_value is None for param in stmt.params
                    ),
                )
            elif isinstance(stmt, ClassDecl):
                attrs = {a.name: a.type for a in stmt.attributes}
                methods = {
                    method.name: tuple(param.name for param in method.params)
                    for method in stmt.methods
                }
                symbol = Symbol(
                    stmt.name,
                    stmt.name,
                    attributes=attrs,
                    methods=methods,
                    category="class",
                    line=stmt.line,
                    parent_class=stmt.superclass,
                )
                if not self._symbol_table.define(symbol):
                    self._report(
                        stmt.line,
                        f"Classe '{stmt.name}' ja declarada neste escopo.",
                        stmt.column,
                    )
                else:
                    classes.append(stmt)
                    self._class_declarations[stmt.name] = stmt

        for class_decl in classes:
            self._symbol_table.enter_scope(f"class:{class_decl.name}")
            self._symbol_table.register_class_scope(
                class_decl.name, self._symbol_table.current_scope_path
            )
            for attribute in class_decl.attributes:
                self._define_symbol(
                    attribute.name,
                    attribute.type,
                    attribute.line,
                    category="attribute",
                    column=attribute.column,
                )
            for method in class_decl.methods:
                self._define_symbol(
                    method.name,
                    method.return_type or "unknown",
                    method.line,
                    category="method",
                    params=tuple(param.name for param in method.params),
                    column=method.column,
                    parameter_types=self._parameter_types(method),
                    required_params=sum(
                        param.default_value is None for param in method.params
                    ),
                )
            self._symbol_table.exit_scope()

        self._check_inheritance_cycles(classes)
        self._check_method_overrides(classes)

    def _check_inheritance_cycles(self, classes: list[ClassDecl]) -> None:
        visited: set[str] = set()
        active: list[str] = []

        def visit(class_name: str) -> None:
            if class_name in visited:
                return
            if class_name in active:
                cycle_start = active.index(class_name)
                cycle = active[cycle_start:] + [class_name]
                declaration = self._class_declarations[class_name]
                self._report(
                    declaration.line,
                    "Heranca circular detectada: " + " -> ".join(cycle) + ".",
                    declaration.column,
                )
                return

            active.append(class_name)
            declaration = self._class_declarations[class_name]
            parent = declaration.superclass
            if parent in self._class_declarations:
                visit(parent)
            active.pop()
            visited.add(class_name)

        for declaration in classes:
            visit(declaration.name)

    def _check_method_overrides(self, classes: list[ClassDecl]) -> None:
        for declaration in classes:
            parent = declaration.superclass
            if parent is None:
                continue
            for method in declaration.methods:
                inherited = self._symbol_table.lookup_method(parent, method.name)
                if inherited is None:
                    continue
                parameter_types = self._parameter_types(method)
                required_params = sum(
                    parameter.default_value is None for parameter in method.params
                )
                parameters_match = (
                    len(parameter_types) == len(inherited.parameter_types)
                    and required_params == (inherited.required_params or 0)
                    and all(
                        declared == inherited_type
                        or "unknown" in (declared, inherited_type)
                        or "var" in (declared, inherited_type)
                        for declared, inherited_type in zip(
                            parameter_types, inherited.parameter_types
                        )
                    )
                )
                return_type = method.return_type or "unknown"
                return_matches = (
                    return_type == inherited.type
                    or return_type in ("unknown", "var")
                    or inherited.type in ("unknown", "var")
                )
                if not parameters_match or not return_matches:
                    self._report(
                        method.line,
                        f"Assinatura incompativel ao sobrescrever o metodo "
                        f"'{method.name}' de '{parent}'.",
                        method.column,
                    )

    def validate_node(self, node: ASTNode | None) -> None:
        if node is None:
            return
        if isinstance(node, _EXPRESSION_NODES):
            self._infer_type(node)

        if isinstance(node, VarDecl):
            if node.init_value is not None:
                self.validate_node(node.init_value)

            actual_type = self._infer_type(node.init_value)
            declared_type = actual_type if node.type == "var" and actual_type != "unknown" else node.type
            if not self._types_compatible(declared_type, actual_type):
                self._report(
                    node.line,
                    f"Tipo incompativel em '{node.name}': esperado {declared_type}, "
                    f"recebido {actual_type}.",
                    node.column,
                )
            self._define_symbol(
                node.name, declared_type, node.line, column=node.column
            )

        elif isinstance(node, Assignment):
            sym = self._lookup(node.name)
            self._check_concurrent_write(node.name, node.line, node.column)
            if sym is None:
                self._define_symbol(
                    node.name,
                    self._infer_type(node.value),
                    node.line,
                    column=node.column,
                )

            if node.value is not None:
                self.validate_node(node.value)

            if sym and not self._types_compatible(
                sym.type, self._infer_type(node.value)
            ):
                self._report(
                    node.line,
                    f"Tipo incompativel em atribuicao de '{node.name}'.",
                    node.column,
                )

        elif isinstance(node, PrintStmt):
            for arg in node.arguments:
                self.validate_node(arg)
        elif isinstance(node, SendStmt):
            self.validate_node(node.channel)
            self.validate_node(node.message)
        elif isinstance(node, CChannelExpr):
            self.validate_node(node.ip)
            self.validate_node(node.port)
        elif isinstance(node, ReceiveExpr):
            self.validate_node(node.channel)
        elif isinstance(node, ListLiteral):
            for e in node.elements:
                self.validate_node(e)
        elif isinstance(node, MatrixCreateExpr):
            self.validate_node(node.rows)
            self.validate_node(node.cols)
            self.validate_node(node.init_value)
        elif isinstance(node, IndexExpr):
            self.validate_node(node.object)
            self.validate_node(node.index)
        elif isinstance(node, IndexAssign):
            self._check_write_target(node.target)
            self.validate_node(node.target)
            self.validate_node(node.value)
        elif isinstance(node, IdentifierExpr):
            if self._lookup(node.name) is None:
                self._report(
                    node.line,
                    f"Variavel '{node.name}' nao declarada.",
                    node.column,
                )
        elif isinstance(node, BinaryExpr):
            self.validate_node(node.left)
            self.validate_node(node.right)
            left_type = self._infer_type(node.left)
            right_type = self._infer_type(node.right)
            if node.op in ("+", "-", "*", "/", "%"):
                valid = (
                    self._is_numeric(left_type) and self._is_numeric(right_type)
                ) or left_type in ("var", "unknown") or right_type in (
                    "var", "unknown"
                )
                if node.op == "+":
                    valid = valid or (
                        left_type == right_type and left_type in ("string", "list")
                    )
                if not valid:
                    self._report(
                        node.line,
                        f"Operandos incompativeis para '{node.op}': "
                        f"{left_type} e {right_type}.",
                        node.column,
                    )
            elif node.op in ("and", "or", "&&", "||"):
                if left_type not in ("bool", "var", "unknown") or right_type not in (
                    "bool", "var", "unknown"
                ):
                    self._report(
                        node.line,
                        f"Operador '{node.op}' exige operandos bool.",
                        node.column,
                    )
            elif node.op in ("<", ">", "<=", ">="):
                compatible = (
                    self._is_numeric(left_type) and self._is_numeric(right_type)
                ) or (
                    left_type == right_type and left_type in ("string", "var", "unknown")
                ) or left_type in ("var", "unknown") or right_type in (
                    "var", "unknown"
                )
                if not compatible:
                    self._report(
                        node.line,
                        f"Operandos incompativeis para comparacao: "
                        f"{left_type} e {right_type}.",
                        node.column,
                    )
            elif node.op in ("==", "!=") and not (
                self._types_compatible(left_type, right_type)
                or self._types_compatible(right_type, left_type)
            ):
                self._report(
                    node.line,
                    f"Operandos incompativeis para '{node.op}': "
                    f"{left_type} e {right_type}.",
                    node.column,
                )
        elif isinstance(node, UnaryExpr):
            self.validate_node(node.operand)
            operand_type = self._infer_type(node.operand)
            expected = (
                ("bool", "var", "unknown")
                if node.op in ("!", "not")
                else ("int", "float", "var", "unknown")
            )
            if operand_type not in expected:
                self._report(
                    node.line,
                    f"Operador unario '{node.op}' incompativel com {operand_type}.",
                    node.column,
                )
        elif isinstance(node, SeqBlock):
            self._enter_scope()
            self._fork_scopes.append({})
            for stmt in node.statements:
                self.validate_node(stmt)
            self._finish_fork_scope()
            self._exit_scope()
        elif isinstance(node, ParBlock):
            self._enter_scope()
            for stmt in node.statements:
                self._enter_scope()
                self._concurrent_scope_paths.append(
                    self._symbol_table.current_scope_path
                )
                self._fork_scopes.append({})
                self.validate_node(stmt)
                self._finish_fork_scope()
                self._concurrent_scope_paths.pop()
                self._exit_scope()
            self._exit_scope()
        elif isinstance(node, ChannelDecl):
            if node.first_host == node.second_host:
                self._report(
                    node.line,
                    f"Canal '{node.name}' deve ligar computadores distintos.",
                    node.column,
                )
        elif isinstance(node, ForkStmt):
            if node.target is not None:
                self.validate_node(node.target)
            if not self._fork_scopes:
                self._fork_scopes.append({})
            current_forks = self._fork_scopes[-1]
            if node.task_name in current_forks:
                self._report(
                    node.line,
                    f"Fork '{node.task_name}' duplicado neste escopo.",
                    node.column,
                )
            else:
                current_forks[node.task_name] = node
            self._define_symbol(
                node.task_name, "task", node.line, "task", column=node.column
            )
            self._enter_scope()
            self._concurrent_scope_paths.append(
                self._symbol_table.current_scope_path
            )
            self._fork_scopes.append({})
            self.validate_node(node.body)
            self._finish_fork_scope()
            self._concurrent_scope_paths.pop()
            self._exit_scope()
        elif isinstance(node, JoinStmt):
            for task_name in node.task_names:
                if not self._fork_scopes or task_name not in self._fork_scopes[-1]:
                    self._report(
                        node.line,
                        f"Join '{task_name}' nao referencia um fork anterior "
                        "neste escopo.",
                        node.column,
                    )
                else:
                    del self._fork_scopes[-1][task_name]
        elif isinstance(node, IfStmt):
            self.validate_node(node.condition)
            self._check_condition(node.condition)
            self.validate_node(node.then_branch)
            if node.else_branch is not None:
                self.validate_node(node.else_branch)
        elif isinstance(node, WhileStmt):
            self.validate_node(node.condition)
            self._check_condition(node.condition)
            self._loop_depth += 1
            self.validate_node(node.body)
            self._loop_depth -= 1
        elif isinstance(node, DoWhileStmt):
            self._loop_depth += 1
            self.validate_node(node.body)
            self._loop_depth -= 1
            self.validate_node(node.condition)
            self._check_condition(node.condition)
        elif isinstance(node, ForStmt):
            self._enter_scope()
            if node.iterator_name:
                if node.iterable is not None:
                    self.validate_node(node.iterable)
                self._define_symbol(
                    node.iterator_name, "var", node.line, column=node.column
                )
            else:
                if node.initializer is not None:
                    self.validate_node(node.initializer)
                if node.condition is not None:
                    self.validate_node(node.condition)
                    self._check_condition(node.condition)
                if node.increment is not None:
                    self.validate_node(node.increment)
            self._loop_depth += 1
            self.validate_node(node.body)
            self._loop_depth -= 1
            self._exit_scope()
        elif isinstance(node, (BreakStmt, ContinueStmt)):
            if self._loop_depth == 0:
                self._report(
                    node.line,
                    f"'{node.__class__.__name__.replace('Stmt', '').lower()}' usado"
                    " fora de laco.",
                    node.column,
                )
        elif isinstance(node, ClassDecl):
            if node.superclass and self._class_symbol(node.superclass) is None:
                self._report(
                    node.line,
                    f"Superclasse '{node.superclass}' nao declarada.",
                    node.column,
                )
            self._symbol_table.enter_scope(f"class:{node.name}", reuse=True)
            old_class = self._current_class
            self._current_class = node.name
            for attr in node.attributes:
                if attr.init_value is not None:
                    self.validate_node(attr.init_value)
                    actual_type = self._infer_type(attr.init_value)
                    if not self._types_compatible(attr.type, actual_type):
                        self._report(
                            attr.line,
                            f"Tipo incompativel em '{attr.name}': esperado "
                            f"{attr.type}, recebido {actual_type}.",
                            attr.column,
                        )
            for method in node.methods:
                self.validate_node(method)
            self._current_class = old_class
            self._exit_scope()
        elif isinstance(node, FuncDecl):
            scope_name = (
                f"method:{node.name}"
                if self._current_class is not None
                else f"function:{node.name}"
            )
            self._symbol_table.enter_scope(scope_name)
            old_function = self._current_function
            old_return_type = self._current_return_type
            self._current_function = node.name
            self._current_return_type = node.return_type
            for parameter in node.params:
                parameter_type = parameter.type
                if parameter_type == "var" and parameter.default_value is not None:
                    parameter_type = self._infer_type(parameter.default_value)
                self._define_symbol(
                    parameter.name,
                    parameter_type,
                    parameter.line,
                    "parameter",
                    column=parameter.column,
                )
                if parameter.default_value is not None:
                    self.validate_node(parameter.default_value)
                    default_type = self._infer_type(parameter.default_value)
                    if not self._types_compatible(parameter_type, default_type):
                        self._report(
                            parameter.line,
                            f"Valor padrao incompativel para '{parameter.name}': "
                            f"esperado {parameter_type}, recebido {default_type}.",
                            parameter.column,
                        )
            if node.body is not None:
                self.validate_node(node.body)
            if (
                node.return_type not in (None, "void")
                and not self._always_returns(node.body)
            ):
                self._report(
                    node.line,
                    f"Funcao '{node.name}' pode terminar sem retornar "
                    f"{node.return_type}.",
                    node.column,
                )
            self._current_function = old_function
            self._current_return_type = old_return_type
            self._exit_scope()
        elif isinstance(node, ReturnStmt):
            if self._current_function is None:
                self._report(
                    node.line,
                    "'return' usado fora de funcao.",
                    node.column,
                )
            if node.value is not None:
                self.validate_node(node.value)
            actual_type = self._infer_type(node.value)
            expected_type = self._current_return_type
            if expected_type == "void" and node.value is not None:
                self._report(
                    node.line,
                    f"Funcao '{self._current_function}' declarada void nao pode "
                    "retornar valor.",
                    node.column,
                )
            elif expected_type not in (None, "void") and node.value is None:
                self._report(
                    node.line,
                    f"Funcao '{self._current_function}' deve retornar "
                    f"{expected_type}.",
                    node.column,
                )
            elif expected_type not in (None, "void") and not self._types_compatible(
                expected_type, actual_type
            ):
                self._report(
                    node.line,
                    f"Tipo de retorno incompativel: esperado {expected_type}, "
                    f"recebido {actual_type}.",
                    node.column,
                )
        elif isinstance(node, MethodCall):
            obj_type = self._infer_type(node.object)
            inherited_method = self._symbol_table.lookup_method(
                obj_type, node.method_name
            )
            if node.method_name in ("send", "receive"):
                if not isinstance(node.object, IdentifierExpr):
                    self._report(
                        node.line,
                        f"'{node.method_name}' so pode ser usado em variavel "
                        "declarada como c_channel.",
                        node.column,
                    )
                else:
                    channel_symbol = self._lookup(node.object.name)
                    if (
                        channel_symbol is None
                        or channel_symbol.category != "channel"
                    ):
                        self._report(
                            node.line,
                            f"'{node.method_name}' so pode ser usado em variavel "
                            "declarada como c_channel.",
                            node.column,
                        )
                    elif node.method_name == "receive" and not node.arguments:
                        self._record_channel_call(
                            node.object.name, "receive", ("string",), node
                        )
                    else:
                        signature = tuple(
                            self._infer_type(argument) for argument in node.arguments
                        )
                        self._record_channel_call(
                            node.object.name, node.method_name, signature, node
                        )
            if self._class_symbol(obj_type) and inherited_method is None:
                self._report(
                    node.line,
                    f"Metodo '{node.method_name}' nao declarado em '{obj_type}'.",
                    node.column,
                )
            self.validate_node(node.object)
            for arg in node.arguments:
                self.validate_node(arg)
            if inherited_method is not None:
                self._check_call_arguments(
                    node,
                    inherited_method.parameter_types,
                    inherited_method.required_params or 0,
                    node.method_name,
                )
        elif isinstance(node, FuncCallExpr):
            function = self._function_symbol(node.name)
            if function is None and node.name not in (
                "exp", "random", "range", "len", "to_number", "parse_ints",
                "str", "int", "float", "inf", "clock", "format_float",
                "is_number", "receive", "send", "c_channel",
            ):
                self._report(
                    node.line,
                    f"Funcao '{node.name}' nao declarada.",
                    node.column,
                )
            if node.name in ("send", "receive"):
                channel_arg = node.arguments[0] if node.arguments else None
                if not isinstance(channel_arg, IdentifierExpr):
                    self._report(
                        node.line,
                        f"'{node.name}' exige como primeiro argumento uma "
                        "variavel declarada como c_channel.",
                        node.column,
                    )
                else:
                    channel_symbol = self._lookup(channel_arg.name)
                    if (
                        channel_symbol is None
                        or channel_symbol.category != "channel"
                    ):
                        self._report(
                            node.line,
                            f"'{node.name}' exige como primeiro argumento uma "
                            "variavel declarada como c_channel.",
                            node.column,
                        )
                    elif node.name == "receive":
                        self._record_channel_call(
                            channel_arg.name, "receive", ("string",), node
                        )
                    else:
                        signature = tuple(
                            self._infer_type(argument)
                            for argument in node.arguments[1:]
                        )
                        self._record_channel_call(
                            channel_arg.name, "send", signature, node
                        )
            for arg in node.arguments:
                self.validate_node(arg)
            if function is not None:
                self._check_call_arguments(
                    node,
                    function.parameter_types,
                    function.required_params or 0,
                    node.name,
                )
            elif node.name in (
                "exp", "random", "range", "len", "to_number", "parse_ints",
                "str", "int", "float", "inf", "clock", "format_float",
                "is_number", "receive", "send", "c_channel",
            ):
                self._check_builtin_call(node)
        elif isinstance(node, PropertyAccess):
            self.validate_node(node.object)
            obj_type = self._infer_type(node.object)
            attribute = self._symbol_table.lookup_attribute(
                obj_type, node.property_name
            )
            if self._class_symbol(obj_type) and attribute is None:
                self._report(
                    node.line,
                    f"Atributo '{node.property_name}' nao declarado em '{obj_type}'.",
                    node.column,
                )
        elif isinstance(node, PropertyAssign):
            self._check_write_target(node.object)
            self.validate_node(node.object)
            self.validate_node(node.value)
            obj_type = self._infer_type(node.object)
            attribute = self._symbol_table.lookup_attribute(
                obj_type, node.property_name
            )
            if self._class_symbol(obj_type) and attribute is None:
                self._report(
                    node.line,
                    f"Atributo '{node.property_name}' nao declarado em '{obj_type}'.",
                    node.column,
                )
            elif attribute is not None and not self._types_compatible(
                attribute.type, self._infer_type(node.value)
            ):
                self._report(
                    node.line,
                    f"Tipo incompativel em atribuicao de '{node.property_name}': "
                    f"esperado {attribute.type}, recebido "
                    f"{self._infer_type(node.value)}.",
                    node.column,
                )
        elif isinstance(node, NewExpr):
            class_symbol = self._class_symbol(node.class_name)
            if class_symbol is None:
                self._report(
                    node.line,
                    f"Classe '{node.class_name}' nao declarada.",
                    node.column,
                )
            for arg in node.arguments:
                self.validate_node(arg)
            if class_symbol is not None:
                declaration = self._class_declarations.get(node.class_name)
                constructor = (
                    next(
                        (
                            method
                            for method in declaration.methods
                            if method.name == "init"
                        ),
                        None,
                    )
                    if declaration is not None
                    else None
                )
                if constructor is None:
                    if node.arguments:
                        self._report(
                            node.line,
                            f"Construtor de '{node.class_name}' nao aceita "
                            f"argumentos; recebeu {len(node.arguments)}.",
                            node.column,
                        )
                else:
                    self._check_call_arguments(
                        node,
                        self._parameter_types(constructor),
                        sum(
                            parameter.default_value is None
                            for parameter in constructor.params
                        ),
                        f"{node.class_name}.init",
                    )
        elif isinstance(node, ThisExpr):
            if self._current_class is None or self._current_function is None:
                self._report(
                    node.line,
                    "'self' so pode ser usado dentro de metodos.",
                    node.column,
                )
        elif isinstance(node, InputExpr):
            if node.prompt is not None:
                self.validate_node(node.prompt)

    def analyze(self, program: Program) -> bool:
        self._concurrent_scope_paths.clear()
        self._fork_scopes.clear()
        self._channel_calls.clear()
        self._collect_declarations(program)
        for stmt in program.statements:
            self.validate_node(stmt)
        self._validate_channel_signatures()
        return not self._has_errors

    def _validate_channel_signatures(self) -> None:
        for channel_name, directions in self._channel_calls.items():
            sends = directions["send"]
            receives = directions["receive"]
            signatures = sends + receives
            for index, (signature, call) in enumerate(signatures):
                for other_signature, other_call in signatures[index + 1:]:
                    if len(signature) != len(other_signature):
                        self._report(
                            other_call.line,
                            f"Aridade inconsistente no canal '{channel_name}': "
                            f"{len(signature)} e {len(other_signature)}.",
                            other_call.column,
                        )
                        continue
                    for argument_index, (first_type, second_type) in enumerate(
                        zip(signature, other_signature), start=1
                    ):
                        if not (
                            self._types_compatible(first_type, second_type)
                            or self._types_compatible(second_type, first_type)
                        ):
                            self._report(
                                other_call.line,
                                f"Tipo inconsistente no argumento "
                                f"{argument_index} do canal '{channel_name}': "
                                f"{first_type} e {second_type}.",
                                other_call.column,
                            )
