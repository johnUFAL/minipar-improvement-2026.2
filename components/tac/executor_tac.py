from __future__ import annotations

import ast
import operator
import re
from collections.abc import Iterable
from typing import Any


class TACExecutor:
    """Executa TAC com expressões, desvios, atribuições simples e print."""

    _binary_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
    }
    _compare_ops = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }

    def __init__(self, max_steps: int = 100_000) -> None:
        self.max_steps = max_steps

    def _evaluate(self, expression: str, variables: dict[str, Any]) -> Any:
        tree = ast.parse(expression, mode="eval")
        return self._evaluate_node(tree.body, variables)

    def _evaluate_node(self, node: ast.AST, variables: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id == "true":
                return True
            if node.id == "false":
                return False
            if node.id not in variables:
                raise NameError(f"Variavel TAC nao definida: {node.id}")
            return variables[node.id]
        if isinstance(node, ast.List):
            return [self._evaluate_node(item, variables) for item in node.elts]
        if isinstance(node, ast.Subscript):
            return self._evaluate_node(node.value, variables)[
                self._evaluate_node(node.slice, variables)
            ]
        if isinstance(node, ast.UnaryOp):
            value = self._evaluate_node(node.operand, variables)
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return +value
            if isinstance(node.op, ast.Not):
                return not value
        if isinstance(node, ast.BinOp):
            operation = self._binary_ops.get(type(node.op))
            if operation:
                return operation(
                    self._evaluate_node(node.left, variables),
                    self._evaluate_node(node.right, variables),
                )
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for value in node.values:
                    if not self._evaluate_node(value, variables):
                        return False
                return True
            for value in node.values:
                if self._evaluate_node(value, variables):
                    return True
            return False
        if isinstance(node, ast.Compare):
            left = self._evaluate_node(node.left, variables)
            for operation_node, comparator in zip(node.ops, node.comparators):
                operation = self._compare_ops.get(type(operation_node))
                right = self._evaluate_node(comparator, variables)
                if operation is None or not operation(left, right):
                    return False
                left = right
            return True
        raise ValueError(f"Expressao TAC nao suportada: {ast.dump(node)}")

    def execute(
        self, tac: str, inputs: Iterable[str] = ()
    ) -> tuple[dict[str, Any], list[str]]:
        lines = [line.strip() for line in tac.splitlines()]
        labels = {
            line[:-1]: index
            for index, line in enumerate(lines)
            if line.endswith(":")
        }
        variables: dict[str, Any] = {}
        output: list[str] = []
        input_values = iter(inputs)
        pc = 0
        steps = 0

        while pc < len(lines):
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError(f"Limite de execucao TAC ({self.max_steps}) excedido")

            line = lines[pc]
            pc += 1
            if not line or line.startswith("#") or line.endswith(":"):
                continue

            jump = re.fullmatch(r"goto\s+(\w+)", line)
            if jump:
                pc = self._label_pc(labels, jump.group(1))
                continue

            conditional = re.fullmatch(r"if(False)?\s+(.+?)\s+goto\s+(\w+)", line)
            if conditional:
                condition = bool(self._evaluate(conditional.group(2), variables))
                should_jump = not condition if conditional.group(1) else condition
                if should_jump:
                    pc = self._label_pc(labels, conditional.group(3))
                continue

            print_match = re.fullmatch(r"print\s+(.+)", line)
            if print_match:
                output.append(str(self._evaluate(print_match.group(1), variables)))
                continue

            assignment = re.fullmatch(r"([A-Za-z_]\w*)\s*=\s*(.+)", line)
            if assignment:
                target, expression = assignment.groups()
                if expression.startswith("input(") and expression.endswith(")"):
                    try:
                        variables[target] = next(input_values)
                    except StopIteration as error:
                        raise EOFError("Entrada TAC esgotada") from error
                else:
                    variables[target] = self._evaluate(expression, variables)
                continue

            raise ValueError(f"Instrucao TAC nao suportada: {line}")

        return variables, output

    @staticmethod
    def _label_pc(labels: dict[str, int], label: str) -> int:
        if label not in labels:
            raise ValueError(f"Rotulo TAC nao definido: {label}")
        return labels[label]
