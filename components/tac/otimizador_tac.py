from __future__ import annotations

import ast
import operator
import re
from collections.abc import Callable
from typing import Any


_ASSIGNMENT = re.compile(r"([A-Za-z_]\w*)(:\w+)?\s*=\s*(.+)")
_TEMPORARY = re.compile(r"t\d+")
_JUMP = re.compile(r"goto\s+(\w+)")
_CONDITIONAL = re.compile(r"(ifFalse|if)\s+(.+?)\s+goto\s+(\w+)")

_BINARY_OPERATORS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}
_COMPARISON_OPERATORS: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


class _ExpressionOptimizer(ast.NodeTransformer):
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def visit_Name(self, node: ast.Name) -> ast.AST:
        replacement = self.values.get(node.id)
        if replacement is None or replacement == node.id:
            return node
        try:
            replacement_node = ast.parse(replacement, mode="eval").body
        except SyntaxError:
            return node
        return ast.copy_location(replacement_node, node)

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        updated = self.generic_visit(node)
        if not isinstance(updated, ast.BinOp):
            return updated
        operation = _BINARY_OPERATORS.get(type(updated.op))
        left, right = _constant_value(updated.left), _constant_value(updated.right)
        if operation is None or left is _NOT_CONSTANT or right is _NOT_CONSTANT:
            return node
        if not _is_foldable_scalar(left) or not _is_foldable_scalar(right):
            return node
        try:
            result = operation(left, right)
        except (ArithmeticError, TypeError, ValueError):
            return node
        return _constant_node(result, updated)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        updated = self.generic_visit(node)
        if not isinstance(updated, ast.UnaryOp):
            return updated
        value = _constant_value(updated.operand)
        if value is _NOT_CONSTANT or not _is_foldable_scalar(value):
            return node
        try:
            if isinstance(updated.op, ast.UAdd):
                result = +value
            elif isinstance(updated.op, ast.USub):
                result = -value
            elif isinstance(updated.op, ast.Not):
                result = not value
            else:
                return updated
        except (ArithmeticError, TypeError, ValueError):
            return updated
        return _constant_node(result, updated)

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        updated = self.generic_visit(node)
        if not isinstance(updated, ast.Compare) or len(updated.ops) != 1:
            return updated
        operation = _COMPARISON_OPERATORS.get(type(updated.ops[0]))
        left, right = _constant_value(updated.left), _constant_value(updated.comparators[0])
        if operation is None or left is _NOT_CONSTANT or right is _NOT_CONSTANT:
            return node
        if not _is_foldable_scalar(left) or not _is_foldable_scalar(right):
            return updated
        try:
            return _constant_node(operation(left, right), updated)
        except (ArithmeticError, TypeError, ValueError):
            return updated

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        updated = self.generic_visit(node)
        if not isinstance(updated, ast.BoolOp):
            return updated
        values = [_constant_value(value) for value in updated.values]
        if any(value is _NOT_CONSTANT or not isinstance(value, bool) for value in values):
            return updated
        result = all(values) if isinstance(updated.op, ast.And) else any(values)
        return _constant_node(result, updated)


_NOT_CONSTANT = object()


def _is_foldable_scalar(value: Any) -> bool:
    return isinstance(value, (int, float, bool, str))


def _constant_value(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant) and _is_foldable_scalar(node.value):
        return node.value
    if isinstance(node, ast.Name) and node.id in ("true", "false"):
        return node.id == "true"
    return _NOT_CONSTANT


def _constant_node(value: Any, source: ast.AST) -> ast.AST:
    if isinstance(value, bool):
        node: ast.AST = ast.Name(id="true" if value else "false", ctx=ast.Load())
    else:
        node = ast.Constant(value=value)
    return ast.copy_location(node, source)


def _parse_pure_expression(expression: str) -> ast.Expression | None:
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None

    allowed_nodes = (
        ast.Expression,
        ast.Constant,
        ast.Name,
        ast.BinOp,
        ast.UnaryOp,
        ast.Compare,
        ast.BoolOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.UAdd,
        ast.USub,
        ast.Not,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.And,
        ast.Or,
        ast.Load,
    )
    if any(not isinstance(node, allowed_nodes) for node in ast.walk(parsed)):
        return None
    return parsed


def _format_expression(expression: ast.Expression) -> str:
    return ast.unparse(expression.body)


def _is_scalar_literal(expression: str) -> bool:
    try:
        parsed = ast.parse(expression, mode="eval").body
    except SyntaxError:
        return False
    return _constant_value(parsed) is not _NOT_CONSTANT


def _is_copy(expression: str) -> str | None:
    try:
        parsed = ast.parse(expression, mode="eval").body
    except SyntaxError:
        return None
    return parsed.id if isinstance(parsed, ast.Name) else None


def _resolved_values(values: dict[str, str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for name in values:
        replacement = values[name]
        seen = {name}
        while replacement in values and replacement not in seen:
            seen.add(replacement)
            replacement = values[replacement]
        resolved[name] = replacement
    return resolved


def _is_discardable_expression(expression: str) -> bool:
    parsed = _parse_pure_expression(expression)
    if parsed is None:
        return False
    optimized = _ExpressionOptimizer({}).visit(parsed)
    return _constant_value(optimized.body) is not _NOT_CONSTANT


def _remove_redundant_jumps(lines: list[str]) -> list[str]:
    result: list[str] = []
    for index, line in enumerate(lines):
        jump = _JUMP.fullmatch(line.strip())
        if jump:
            next_index = index + 1
            while next_index < len(lines):
                candidate = lines[next_index].strip()
                if (
                    not candidate
                    or candidate.startswith("#")
                    or candidate.startswith("//")
                ):
                    next_index += 1
                    continue
                if candidate == f"{jump.group(1)}:":
                    break
                next_index = len(lines)
            if next_index < len(lines):
                continue
        result.append(line)
    return result


def _remove_dead_temporaries(lines: list[str]) -> list[str]:
    optimized = lines
    while True:
        used: set[str] = set()
        for line in optimized:
            assignment = _ASSIGNMENT.fullmatch(line.strip())
            expression = assignment.group(3) if assignment else line
            used.update(_TEMPORARY.findall(expression))

        updated: list[str] = []
        removed = False
        for line in optimized:
            assignment = _ASSIGNMENT.fullmatch(line.strip())
            if assignment:
                target, type_annotation, expression = assignment.groups()
                if (
                    _TEMPORARY.fullmatch(target)
                    and target not in used
                    and _is_discardable_expression(expression)
                ):
                    removed = True
                    continue
            updated.append(line)
        if not removed:
            return optimized
        optimized = updated


class TACOptimizer:
    """Aplica otimizações locais conservadoras sobre TAC textual."""

    @staticmethod
    def instruction_count(tac: str) -> int:
        return sum(
            1
            for line in tac.splitlines()
            if line.strip()
            and not line.strip().endswith(":")
            and not line.strip().startswith(("#", "//"))
        )

    def optimize(self, tac: str) -> str:
        lines = tac.splitlines()
        values: dict[str, str] = {}
        optimized: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                optimized.append(line)
                continue

            if stripped.endswith(":") or stripped.startswith("func "):
                values.clear()
                optimized.append(line)
                continue

            conditional = _CONDITIONAL.fullmatch(stripped)
            if conditional:
                kind, expression, label = conditional.groups()
                parsed = _parse_pure_expression(expression)
                if parsed is not None:
                    rewritten = _ExpressionOptimizer(
                        _resolved_values(values)
                    ).visit(parsed)
                    ast.fix_missing_locations(rewritten)
                    expression = _format_expression(rewritten)
                optimized.append(f"{kind} {expression} goto {label}")
                values.clear()
                continue

            if _JUMP.fullmatch(stripped) or stripped in ("ret", "return", "endfunc"):
                optimized.append(line)
                values.clear()
                continue

            assignment = _ASSIGNMENT.fullmatch(stripped)
            if assignment:
                target, type_annotation, expression = assignment.groups()
                parsed = _parse_pure_expression(expression)
                if parsed is None:
                    optimized.append(line)
                    values.clear()
                    continue

                rewritten = _ExpressionOptimizer(_resolved_values(values)).visit(
                    parsed
                )
                ast.fix_missing_locations(rewritten)
                expression = _format_expression(rewritten)
                annotation = type_annotation or ""
                optimized.append(f"{target}{annotation} = {expression}")

                resolved_values = _resolved_values(values)
                values = {
                    name: value
                    for name, value in values.items()
                    if name != target and resolved_values[name] != target
                }
                if _is_scalar_literal(expression):
                    values[target] = expression
                else:
                    copied_name = _is_copy(expression)
                    if copied_name is not None:
                        values[target] = copied_name
                continue

            if stripped.startswith(("print ", "param ", "ret ", "return ")):
                prefix, expression = stripped.split(" ", 1)
                parsed = _parse_pure_expression(expression)
                if parsed is not None:
                    rewritten = _ExpressionOptimizer(
                        _resolved_values(values)
                    ).visit(parsed)
                    ast.fix_missing_locations(rewritten)
                    optimized.append(f"{prefix} {_format_expression(rewritten)}")
                else:
                    optimized.append(line)
                values.clear()
                continue

            optimized.append(line)
            values.clear()

        optimized = _remove_redundant_jumps(optimized)
        optimized = _remove_dead_temporaries(optimized)
        return "\n".join(optimized) + ("\n" if tac.endswith("\n") else "")


__all__ = ["TACOptimizer"]
