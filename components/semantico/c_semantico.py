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
        self._loop_depth = 0

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
    ) -> None:
        symbol = Symbol(
            name,
            type_,
            params=params or (),
            category=category,
            line=line,
        )
        if not self._symbol_table.define(symbol):
            self._report(line, f"Identificador '{name}' ja declarado neste escopo.")

    def _lookup(self, name: str) -> Symbol | None:
        return self._symbol_table.lookup(name)

    @property
    def symbol_table(self) -> ITabelaSimbolos:
        return self._symbol_table

    def _class_symbol(self, name: str) -> Symbol | None:
        symbol = self._symbol_table.lookup(name)
        return symbol if symbol is not None and symbol.category == "class" else None

    def _function_symbol(self, name: str) -> Symbol | None:
        symbol = self._symbol_table.lookup(name)
        return symbol if symbol is not None and symbol.category == "function" else None

    def _report(self, line: int, message: str) -> None:
        contextual_message = f"{message}{self._get_context()}"
        diagnostic = Diagnostic(Phase.SEMANTIC, contextual_message, line)
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
        if node is None:
            return "unknown"
        if isinstance(node, NumberExpr):
            return "number"
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
            return "bool" if node.op == "!" else self._infer_type(node.operand)
        if isinstance(node, BinaryExpr):
            lt, rt = self._infer_type(node.left), self._infer_type(node.right)
            if node.op in ("==", "!=", "<", ">", "<=", ">=", "&&", "||"):
                return "bool"
            if node.op == "+" and (lt == "string" or rt == "string"):
                return "string"
            if node.op == "+" and (lt == "list" or rt == "list"):
                return "list"
            return "number"
        if isinstance(node, PropertyAccess):
            obj_type = self._infer_type(node.object)
            attribute = self._symbol_table.lookup_attribute(
                obj_type, node.property_name
            )
            if attribute is not None:
                return attribute.type
            return "unknown"
        if isinstance(node, MethodCall):
            return "unknown"
        if isinstance(node, FuncCallExpr):
            if node.name in ("random", "exp"):
                return "number"
            if node.name in ("range", "parse_ints"):
                return "list"
            return "unknown"
        if isinstance(node, IndexExpr):
            return "unknown"
        return "unknown"

    def _types_compatible(self, declared: str, actual: str) -> bool:
        if declared in ("var", "unknown") or actual == "unknown":
            return True
        if declared == "int" and actual == "number":
            return True
        if declared == "number" and actual == "int":
            return True
        return declared == actual

    def _collect_declarations(self, program: Program) -> None:
        classes: list[ClassDecl] = []
        for stmt in program.statements:
            if isinstance(stmt, FuncDecl):
                self._define_symbol(
                    stmt.name,
                    "function",
                    stmt.line,
                    category="function",
                    params=stmt.params,
                )
            elif isinstance(stmt, ClassDecl):
                attrs = {a.name: a.type for a in stmt.attributes}
                methods = {m.name: tuple(m.params) for m in stmt.methods}
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
                    )
                else:
                    classes.append(stmt)

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
                )
            for method in class_decl.methods:
                self._define_symbol(
                    method.name,
                    "unknown",
                    method.line,
                    category="method",
                    params=method.params,
                )
            self._symbol_table.exit_scope()

    def validate_node(self, node: ASTNode | None) -> None:
        if node is None:
            return

        if isinstance(node, VarDecl):
            if node.init_value is not None:
                self.validate_node(node.init_value)

            actual_type = self._infer_type(node.init_value)
            declared_type = actual_type if node.type == "var" and actual_type != "unknown" else node.type
            if not self._types_compatible(declared_type, actual_type):
                self._report(
                    node.line,
                    f"Tipo incompativel em '{node.name}': esperado {declared_type}, "
                    f"recebido {actual_type}."
                )
            self._define_symbol(node.name, declared_type, node.line)

        elif isinstance(node, Assignment):
            sym = self._lookup(node.name)
            if sym is None:
                self._define_symbol(
                    node.name, self._infer_type(node.value), node.line
                )

            if node.value is not None:
                self.validate_node(node.value)

            if sym and not self._types_compatible(
                sym.type, self._infer_type(node.value)
            ):
                self._report(
                    node.line,
                    f"Tipo incompativel em atribuicao de '{node.name}'."
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
            self.validate_node(node.target)
            self.validate_node(node.value)
        elif isinstance(node, IdentifierExpr):
            if self._lookup(node.name) is None:
                self._report(node.line, f"Variavel '{node.name}' nao declarada.")
        elif isinstance(node, BinaryExpr):
            self.validate_node(node.left)
            self.validate_node(node.right)
            if node.op in ("+", "-", "*", "/", "%"):
                lt, rt = self._infer_type(node.left), self._infer_type(node.right)
                if node.op != "+" and (
                    lt not in ("number", "int", "var", "unknown") or rt not in (
                        "number", "int", "var", "unknown"
                    )
                ):
                    self._report(
                        node.line, f"Operador '{node.op}' exige operandos numericos."
                    )
        elif isinstance(node, UnaryExpr):
            self.validate_node(node.operand)
        elif isinstance(node, (SeqBlock, ParBlock)):
            self._enter_scope()
            for stmt in node.statements:
                self.validate_node(stmt)
            self._exit_scope()
        elif isinstance(node, ChannelDecl):
            self._define_symbol(node.name, "c_channel", node.line, "channel")
        elif isinstance(node, ForkStmt):
            if node.target is not None:
                self.validate_node(node.target)
            self._define_symbol(node.task_name, "task", node.line, "task")
            self.validate_node(node.body)
        elif isinstance(node, JoinStmt):
            for task_name in node.task_names:
                if self._lookup(task_name) is None:
                    self._report(node.line, f"Tarefa '{task_name}' não declarada.")
        elif isinstance(node, IfStmt):
            self.validate_node(node.condition)
            self.validate_node(node.then_branch)
            if node.else_branch is not None:
                self.validate_node(node.else_branch)
        elif isinstance(node, WhileStmt):
            self.validate_node(node.condition)
            self._loop_depth += 1
            self.validate_node(node.body)
            self._loop_depth -= 1
        elif isinstance(node, DoWhileStmt):
            self._loop_depth += 1
            self.validate_node(node.body)
            self._loop_depth -= 1
            self.validate_node(node.condition)
        elif isinstance(node, ForStmt):
            self._enter_scope()
            if node.iterator_name:
                if node.iterable is not None:
                    self.validate_node(node.iterable)
                self._define_symbol(node.iterator_name, "var", node.line)
            else:
                if node.initializer is not None:
                    self.validate_node(node.initializer)
                if node.condition is not None:
                    self.validate_node(node.condition)
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
                    " fora de laco."
                )
        elif isinstance(node, ClassDecl):
            if node.superclass and self._class_symbol(node.superclass) is None:
                self._report(
                    node.line, f"Superclasse '{node.superclass}' nao declarada."
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
            self._current_function = node.name
            for p in node.params:
                self._define_symbol(p, "var", node.line, "parameter")
            if node.body is not None:
                self.validate_node(node.body)
            self._current_function = old_function
            self._exit_scope()
        elif isinstance(node, ReturnStmt):
            if node.value is not None:
                self.validate_node(node.value)
        elif isinstance(node, MethodCall):
            obj_type = self._infer_type(node.object)
            inherited_method = self._symbol_table.lookup_method(
                obj_type, node.method_name
            )
            if self._class_symbol(obj_type) and inherited_method is None:
                self._report(
                    node.line,
                    f"Metodo '{node.method_name}' nao declarado em '{obj_type}'."
                )
            elif inherited_method is not None and len(
                inherited_method.params
            ) != len(node.arguments):
                self._report(
                    node.line,
                    f"Metodo '{node.method_name}' espera "
                    f"{len(inherited_method.params)} "
                    f"argumento(s), recebeu {len(node.arguments)}."
                )

            self.validate_node(node.object)
            for arg in node.arguments:
                self.validate_node(arg)
        elif isinstance(node, FuncCallExpr):
            function = self._function_symbol(node.name)
            if function is None and node.name not in (
                "exp", "random", "range", "len", "to_number", "parse_ints"
            ):
                self._report(node.line, f"Funcao '{node.name}' nao declarada.")
            elif function is not None and len(function.params) != len(node.arguments):
                self._report(
                    node.line,
                    f"Funcao '{node.name}' espera {len(function.params)} "
                    f"argumento(s), recebeu {len(node.arguments)}."
                    )
            for arg in node.arguments:
                self.validate_node(arg)
        elif isinstance(node, PropertyAccess):
            self.validate_node(node.object)
            obj_type = self._infer_type(node.object)
            attribute = self._symbol_table.lookup_attribute(
                obj_type, node.property_name
            )
            if self._class_symbol(obj_type) and attribute is None:
                self._report(
                    node.line,
                    f"Atributo '{node.property_name}' nao declarado em '{obj_type}'."
                )
        elif isinstance(node, PropertyAssign):
            self.validate_node(node.object)
            self.validate_node(node.value)
            obj_type = self._infer_type(node.object)
            attribute = self._symbol_table.lookup_attribute(
                obj_type, node.property_name
            )
            if self._class_symbol(obj_type) and attribute is None:
                self._report(
                    node.line,
                    f"Atributo '{node.property_name}' nao declarado em '{obj_type}'."
                )
        elif isinstance(node, NewExpr):
            if self._class_symbol(node.class_name) is None:
                self._report(node.line, f"Classe '{node.class_name}' nao declarada.")
            for arg in node.arguments:
                self.validate_node(arg)
        elif isinstance(node, ThisExpr):
            pass
        elif isinstance(node, InputExpr):
            if node.prompt is not None:
                self.validate_node(node.prompt)

    def analyze(self, program: Program) -> bool:
        self._collect_declarations(program)
        for stmt in program.statements:
            self.validate_node(stmt)
        return not self._has_errors
