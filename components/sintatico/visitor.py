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
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ASTNode):
                        self.visit(item)
