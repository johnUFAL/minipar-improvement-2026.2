from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ASTNode:
    """Base de todos os nós da AST."""
    line: int = 1


@dataclass(frozen=True)
class NumberExpr(ASTNode):
    value: str = ""
    line: int = 1


@dataclass(frozen=True)
class StringExpr(ASTNode):
    value: str = ""
    line: int = 1


@dataclass(frozen=True)
class BoolExpr(ASTNode):
    value: bool = False
    line: int = 1


@dataclass(frozen=True)
class IdentifierExpr(ASTNode):
    name: str = ""
    line: int = 1


@dataclass(frozen=True)
class BinaryExpr(ASTNode):
    op: str = ""
    left: ASTNode | None = None
    right: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class UnaryExpr(ASTNode):
    op: str = ""
    operand: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class VarDecl(ASTNode):
    name: str = ""
    init_value: ASTNode | None = None
    type: str = "var"
    line: int = 1


@dataclass(frozen=True)
class Assignment(ASTNode):
    name: str = ""
    value: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class PrintStmt(ASTNode):
    arguments: tuple[ASTNode, ...] = ()
    line: int = 1


@dataclass(frozen=True)
class SeqBlock(ASTNode):
    statements: tuple[ASTNode, ...] = ()
    line: int = 1


@dataclass(frozen=True)
class ParBlock(ASTNode):
    statements: tuple[ASTNode, ...] = ()
    line: int = 1


@dataclass(frozen=True)
class IfStmt(ASTNode):
    condition: ASTNode | None = None
    then_branch: ASTNode | None = None
    else_branch: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class WhileStmt(ASTNode):
    condition: ASTNode | None = None
    body: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class DoWhileStmt(ASTNode):
    body: ASTNode | None = None
    condition: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class ForStmt(ASTNode):
    initializer: ASTNode | None = None
    condition: ASTNode | None = None
    increment: ASTNode | None = None
    body: ASTNode | None = None
    iterator_name: str | None = None
    iterable: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class BreakStmt(ASTNode):
    line: int = 1


@dataclass(frozen=True)
class ContinueStmt(ASTNode):
    line: int = 1


@dataclass(frozen=True)
class ClassDecl(ASTNode):
    name: str = ""
    superclass: str | None = None
    attributes: tuple[VarDecl, ...] = ()
    methods: tuple[FuncDecl, ...] = ()
    line: int = 1


@dataclass(frozen=True)
class ChannelDecl(ASTNode):
    name: str = ""
    first_host: str = ""
    second_host: str = ""
    line: int = 1


@dataclass(frozen=True)
class ForkStmt(ASTNode):
    task_name: str = ""
    target_kind: str | None = None
    target: ASTNode | None = None
    body: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class JoinStmt(ASTNode):
    task_names: tuple[str, ...] = ()
    line: int = 1


@dataclass(frozen=True)
class FuncDecl(ASTNode):
    name: str = ""
    params: tuple[str, ...] = ()
    body: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class ReturnStmt(ASTNode):
    value: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class MethodCall(ASTNode):
    object: ASTNode | None = None
    method_name: str = ""
    arguments: tuple[ASTNode, ...] = ()
    line: int = 1


@dataclass(frozen=True)
class FuncCallExpr(ASTNode):
    name: str = ""
    arguments: tuple[ASTNode, ...] = ()
    line: int = 1


@dataclass(frozen=True)
class PropertyAccess(ASTNode):
    object: ASTNode | None = None
    property_name: str = ""
    line: int = 1


@dataclass(frozen=True)
class PropertyAssign(ASTNode):
    object: ASTNode | None = None
    property_name: str = ""
    value: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class NewExpr(ASTNode):
    class_name: str = ""
    arguments: tuple[ASTNode, ...] = ()
    line: int = 1


@dataclass(frozen=True)
class ThisExpr(ASTNode):
    line: int = 1


@dataclass(frozen=True)
class CChannelExpr(ASTNode):
    ip: ASTNode | None = None
    port: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class SendStmt(ASTNode):
    channel: ASTNode | None = None
    message: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class ReceiveExpr(ASTNode):
    channel: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class InputExpr(ASTNode):
    prompt: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class ListLiteral(ASTNode):
    elements: tuple[ASTNode, ...] = ()
    line: int = 1


@dataclass(frozen=True)
class MatrixCreateExpr(ASTNode):
    rows: ASTNode | None = None
    cols: ASTNode | None = None
    init_value: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class IndexExpr(ASTNode):
    object: ASTNode | None = None
    index: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class IndexAssign(ASTNode):
    target: ASTNode | None = None
    value: ASTNode | None = None
    line: int = 1


@dataclass(frozen=True)
class Program(ASTNode):
    statements: tuple[ASTNode, ...] = ()
    line: int = 1
