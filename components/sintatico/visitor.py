from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any

from .ast import ASTNode


_CATEGORIA_DECLARACAO = frozenset({
    "Program",
    "VarDecl",
    "AttributeDecl",
    "Parameter",
    "FuncDecl",
    "MethodDecl",
    "ClassDecl",
})

_CATEGORIA_EXPRESSAO = frozenset({
    "NumberExpr",
    "StringExpr",
    "BoolExpr",
    "IdentifierExpr",
    "BinaryExpr",
    "UnaryExpr",
    "PropertyAccess",
    "MethodCall",
    "FuncCallExpr",
    "NewExpr",
    "ThisExpr",
    "InputExpr",
    "ListLiteral",
    "MatrixCreateExpr",
    "IndexExpr",
})

_CATEGORIA_CONTROLE = frozenset({
    "SeqBlock",
    "IfStmt",
    "WhileStmt",
    "DoWhileStmt",
    "ForStmt",
    "BreakStmt",
    "ContinueStmt",
    "ReturnStmt",
    "PrintStmt",
    "Assignment",
    "PropertyAssign",
    "IndexAssign",
})

_CATEGORIA_PARALELO = frozenset({
    "ParBlock",
    "ForkStmt",
    "JoinStmt",
    "SendStmt",
    "ReceiveExpr",
    "ChannelDecl",
    "CChannelExpr",
})


def categoria_ast(node: ASTNode) -> str:
    tipo = type(node).__name__
    if tipo in _CATEGORIA_PARALELO:
        return "paralelo"
    if tipo in ("FuncCallExpr", "MethodCall"):
        nome = getattr(node, "name", None) or getattr(node, "method_name", None)
        if nome in ("send", "receive"):
            return "paralelo"
    if tipo in _CATEGORIA_DECLARACAO:
        return "declaracao"
    if tipo in _CATEGORIA_EXPRESSAO:
        return "expressao"
    if tipo in _CATEGORIA_CONTROLE:
        return "controle"
    return "controle"


class ASTVisitor:
    def visit(self, node: ASTNode | None) -> Any:
        if node is None:
            return None
        method = getattr(self, f"visit_{type(node).__name__}", self.generic_visit)
        return method(node)

    def generic_visit(self, node: ASTNode) -> None:
        if not is_dataclass(node):
            return
        for field in fields(node):
            value = getattr(node, field.name)
            if isinstance(value, ASTNode):
                self.visit(value)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, ASTNode):
                        self.visit(item)


def para_dict(
    node: ASTNode, *, incluir_categoria: bool = False
) -> dict[str, object]:
    result: dict[str, object] = {"tipo": type(node).__name__}
    if incluir_categoria:
        result["categoria"] = categoria_ast(node)
    for field in fields(node):
        value = getattr(node, field.name)
        if isinstance(value, ASTNode):
            result[field.name] = para_dict(
                value, incluir_categoria=incluir_categoria
            )
        elif isinstance(value, (tuple, list)):
            result[field.name] = [
                para_dict(item, incluir_categoria=incluir_categoria)
                if isinstance(item, ASTNode)
                else item
                for item in value
            ]
        else:
            result[field.name] = value
    return result


class ASTPrinter(ASTVisitor):
    def __init__(self) -> None:
        self._lines: list[str] = []
        self._depth = 0

    def format(self, node: ASTNode) -> str:
        self._lines.clear()
        self._depth = 0
        self.visit(node)
        return "\n".join(self._lines)

    def generic_visit(self, node: ASTNode) -> None:
        self._lines.append(f"{'  ' * self._depth}{type(node).__name__}")
        self._depth += 1
        try:
            super().generic_visit(node)
        finally:
            self._depth -= 1
