from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any

from .ast import ASTNode


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


def para_dict(node: ASTNode) -> dict[str, object]:
    result: dict[str, object] = {"tipo": type(node).__name__}
    for field in fields(node):
        value = getattr(node, field.name)
        if isinstance(value, ASTNode):
            result[field.name] = para_dict(value)
        elif isinstance(value, (tuple, list)):
            result[field.name] = [
                para_dict(item) if isinstance(item, ASTNode) else item
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
