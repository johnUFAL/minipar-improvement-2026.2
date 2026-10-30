from __future__ import annotations

from pathlib import Path

from ..sintatico.ast import (
    Assignment,
    ASTNode,
    BinaryExpr,
    BoolExpr,
    BreakStmt,
    CChannelExpr,
    ClassDecl,
    ContinueStmt,
    DoWhileStmt,
    ForStmt,
    FuncCallExpr,
    FuncDecl,
    IdentifierExpr,
    IfStmt,
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
        if node.tipo_inferido:
            return node.tipo_inferido
        if isinstance(node, NumberExpr):
            return "float" if "." in node.value else "int"
        if isinstance(node, StringExpr):
            return "string"
        if isinstance(node, BoolExpr):
            return "bool"
        if isinstance(node, ListLiteral):
            return "list"
        if isinstance(node, IdentifierExpr):
            return self.variable_types.get(node.name)
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
        if isinstance(node, (FuncCallExpr, MethodCall)):
            if isinstance(node, FuncCallExpr) and node.name in self.functions:
                return self.functions[node.name].return_type
        if isinstance(node, InputExpr):
            return "string"
        return None

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
            return "this"
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
            return self._new_temp(
                node, f"{self._expr(node.object)}.{node.property_name}"
            )
        if isinstance(node, FuncCallExpr):
            function = self.functions.get(node.name)
            arguments: list[ASTNode | None] = list(node.arguments)
            if function:
                arguments.extend(
                    parameter.default_value
                    for parameter in function.params[len(arguments):]
                )
            for argument in arguments:
                self._emit(f"param {self._expr(argument)}")
            return self._new_temp(
                node, f"call {node.name}, {len(arguments)}"
            )
        if isinstance(node, MethodCall):
            for argument in node.arguments:
                self._emit(f"param {self._expr(argument)}")
            target = f"{self._expr(node.object)}.{node.method_name}"
            return self._new_temp(node, f"call {target}, {len(node.arguments)}")
        if isinstance(node, NewExpr):
            args = ", ".join(self._expr(arg) for arg in node.arguments)
            return self._new_temp(node, f"new {node.class_name}({args})")
        if isinstance(node, CChannelExpr):
            return self._new_temp(
                node, f"c_channel({self._expr(node.ip)}, {self._expr(node.port)})"
            )
        if isinstance(node, ReceiveExpr):
            return self._new_temp(node, f"receive {self._expr(node.channel)}")
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

    def _stmt(self, node: ASTNode | None) -> None:
        if node is None:
            return
        if isinstance(node, VarDecl):
            self._assign_type(node.name, node.init_value, node.type)
            self._emit(f"{node.name} = {self._expr(node.init_value)}")
        elif isinstance(node, Assignment):
            self._assign_type(node.name, node.value)
            self._emit(f"{node.name} = {self._expr(node.value)}")
        elif isinstance(node, PropertyAssign):
            self._emit(
                f"{self._expr(node.object)}.{node.property_name} = "
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
            for argument in node.arguments:
                self._emit(f"print {self._expr(argument)}")
        elif isinstance(node, SendStmt):
            self._emit(f"send {self._expr(node.channel)}, {self._expr(node.message)}")
        elif isinstance(node, (SeqBlock, ParBlock)):
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
                self._stmt(method)
        elif isinstance(node, FuncDecl):
            self._emit(
                f"func {node.name}({', '.join(p.name for p in node.params)}):"
            )
            old_types = self.variable_types
            self.variable_types = {p.name: p.type for p in node.params if p.type != "var"}
            self._stmt(node.body)
            self._emit("endfunc")
            self.variable_types = old_types
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
        functions = [
            statement for statement in program.statements
            if isinstance(statement, FuncDecl)
        ]
        main_statements = [
            statement for statement in program.statements
            if not isinstance(statement, FuncDecl)
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
