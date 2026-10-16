from __future__ import annotations

from dataclasses import dataclass, field


class ASTNode:
    line: int = 1


@dataclass
class NumberExpr(ASTNode):
    value: str = ""
    line: int = 1


@dataclass
class StringExpr(ASTNode):
    value: str = ""
    line: int = 1


@dataclass
class BoolExpr(ASTNode):
    value: bool = False
    line: int = 1


@dataclass
class IdentifierExpr(ASTNode):
    name: str = ""
    line: int = 1


@dataclass
class BinaryExpr(ASTNode):
    op: str = ""
    left: ASTNode | None = None
    right: ASTNode | None = None
    line: int = 1


@dataclass
class UnaryExpr(ASTNode):
    op: str = ""
    operand: ASTNode | None = None
    line: int = 1


@dataclass
class VarDecl(ASTNode):
    name: str = ""
    init_value: ASTNode | None = None
    type: str = "var"
    line: int = 1


@dataclass
class Assignment(ASTNode):
    name: str = ""
    value: ASTNode | None = None
    line: int = 1


@dataclass
class PrintStmt(ASTNode):
    arguments: list[ASTNode] = field(default_factory=list)
    line: int = 1


@dataclass
class SeqBlock(ASTNode):
    statements: list[ASTNode] = field(default_factory=list)
    line: int = 1


@dataclass
class ParBlock(ASTNode):
    statements: list[ASTNode] = field(default_factory=list)
    line: int = 1


@dataclass
class IfStmt(ASTNode):
    condition: ASTNode | None = None
    then_branch: ASTNode | None = None
    else_branch: ASTNode | None = None
    line: int = 1


@dataclass
class WhileStmt(ASTNode):
    condition: ASTNode | None = None
    body: ASTNode | None = None
    line: int = 1


@dataclass
class DoWhileStmt(ASTNode):
    body: ASTNode | None = None
    condition: ASTNode | None = None
    line: int = 1


@dataclass
class ForStmt(ASTNode):
    initializer: ASTNode | None = None
    condition: ASTNode | None = None
    increment: ASTNode | None = None
    body: ASTNode | None = None
    iterator_name: str | None = None
    iterable: ASTNode | None = None
    line: int = 1


@dataclass
class BreakStmt(ASTNode):
    line: int = 1


@dataclass
class ContinueStmt(ASTNode):
    line: int = 1


@dataclass
class ClassDecl(ASTNode):
    name: str = ""
    superclass: str | None = None
    attributes: list[VarDecl] = field(default_factory=list)
    methods: list[FuncDecl] = field(default_factory=list)
    line: int = 1


@dataclass
class FuncDecl(ASTNode):
    name: str = ""
    params: list[str] = field(default_factory=list)
    body: ASTNode | None = None
    line: int = 1


@dataclass
class ReturnStmt(ASTNode):
    value: ASTNode | None = None
    line: int = 1


@dataclass
class MethodCall(ASTNode):
    object: ASTNode | None = None
    method_name: str = ""
    arguments: list[ASTNode] = field(default_factory=list)
    line: int = 1


@dataclass
class FuncCallExpr(ASTNode):
    name: str = ""
    arguments: list[ASTNode] = field(default_factory=list)
    line: int = 1


@dataclass
class PropertyAccess(ASTNode):
    object: ASTNode | None = None
    property_name: str = ""
    line: int = 1


@dataclass
class PropertyAssign(ASTNode):
    object: ASTNode | None = None
    property_name: str = ""
    value: ASTNode | None = None
    line: int = 1


@dataclass
class NewExpr(ASTNode):
    class_name: str = ""
    arguments: list[ASTNode] = field(default_factory=list)
    line: int = 1


@dataclass
class ThisExpr(ASTNode):
    line: int = 1


@dataclass
class CChannelExpr(ASTNode):
    ip: ASTNode | None = None
    port: ASTNode | None = None
    line: int = 1


@dataclass
class SendStmt(ASTNode):
    channel: ASTNode | None = None
    message: ASTNode | None = None
    line: int = 1


@dataclass
class ReceiveExpr(ASTNode):
    channel: ASTNode | None = None
    line: int = 1


@dataclass
class InputExpr(ASTNode):
    prompt: ASTNode | None = None
    line: int = 1


@dataclass
class ListLiteral(ASTNode):
    elements: list[ASTNode] = field(default_factory=list)
    line: int = 1


@dataclass
class MatrixCreateExpr(ASTNode):
    rows: ASTNode | None = None
    cols: ASTNode | None = None
    init_value: ASTNode | None = None
    line: int = 1


@dataclass
class IndexExpr(ASTNode):
    object: ASTNode | None = None
    index: ASTNode | None = None
    line: int = 1


@dataclass
class IndexAssign(ASTNode):
    target: ASTNode | None = None
    value: ASTNode | None = None
    line: int = 1


@dataclass
class Program(ASTNode):
    statements: list[ASTNode] = field(default_factory=list)
    line: int = 1
