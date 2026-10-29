from __future__ import annotations

import ast
import operator
import re
from collections.abc import Iterable
from typing import Any, ClassVar


class TACExecutor:
    """Interpreta instruções TAC e mantém quadros independentes para chamadas."""

    _binary_ops: ClassVar = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
    }
    _compare_ops: ClassVar = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }
    _function_header = re.compile(r"func\s+(\w+)\((.*?)\):")
    _assignment = re.compile(r"([A-Za-z_]\w*)(?::\w+)?\s*=\s*(.+)")

    def __init__(self, max_steps: int = 100_000) -> None:
        self.max_steps = max_steps

    @staticmethod
    def _strip_comment(line: str) -> str:
        quote: str | None = None
        escaped = False
        for index, character in enumerate(line):
            if escaped:
                escaped = False
            elif character == "\\" and quote:
                escaped = True
            elif quote and character == quote:
                quote = None
            elif not quote and character in ("'", '"'):
                quote = character
            elif not quote and character == "#":
                return line[:index].strip()
        return line.strip()

    def _evaluate(self, expression: str, variables: dict[str, Any]) -> Any:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as error:
            raise ValueError(f"Expressao TAC invalida: {expression}") from error
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
            container = self._evaluate_node(node.value, variables)
            index = self._evaluate_node(node.slice, variables)
            return container[index]
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
            if operation is not None:
                return operation(
                    self._evaluate_node(node.left, variables),
                    self._evaluate_node(node.right, variables),
                )
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for value in node.values:
                    result = self._evaluate_node(value, variables)
                    if not result:
                        return result
                return result
            for value in node.values:
                result = self._evaluate_node(value, variables)
                if result:
                    return result
            return result
        if isinstance(node, ast.Compare):
            left = self._evaluate_node(node.left, variables)
            for operation_node, comparator in zip(node.ops, node.comparators):
                operation = self._compare_ops.get(type(operation_node))
                right = self._evaluate_node(comparator, variables)
                if operation is None or not operation(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            arguments = [
                self._evaluate_node(argument, variables) for argument in node.args
            ]
            if node.func.id == "len" and len(arguments) == 1:
                return len(arguments[0])
        raise ValueError(f"Expressao TAC nao suportada: {ast.dump(node)}")

    def execute(
        self, tac: str, inputs: Iterable[Any] = ()
    ) -> tuple[dict[str, Any], list[str]]:
        lines = [self._strip_comment(line) for line in tac.splitlines()]
        labels: dict[str, int] = {}
        functions: dict[str, tuple[int, tuple[str, ...]]] = {}
        for index, line in enumerate(lines):
            if line.endswith(":"):
                label = line[:-1]
                if label in labels:
                    raise ValueError(f"Rotulo TAC duplicado: {label}")
                labels[label] = index
            header = self._function_header.fullmatch(line)
            if header:
                name, parameter_text = header.groups()
                parameters = tuple(
                    item.strip() for item in parameter_text.split(",") if item.strip()
                )
                if name in functions:
                    raise ValueError(f"Funcao TAC duplicada: {name}")
                functions[name] = (index + 1, parameters)

        variables: dict[str, Any] = {}
        output: list[str] = []
        input_values = iter(inputs)
        pending_parameters: list[Any] = []
        frames: list[tuple[int, dict[str, Any], str | None]] = []
        pc = 0
        steps = 0

        def finish_function(value: Any) -> bool:
            nonlocal pc, variables
            if not frames:
                return False
            return_pc, caller_variables, destination = frames.pop()
            variables = caller_variables
            if destination:
                variables[destination] = value
            pc = return_pc
            return True

        while pc < len(lines):
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError(
                    f"Limite de execucao TAC ({self.max_steps}) excedido"
                )
            line = lines[pc]
            pc += 1
            if not line or line.endswith(":") or self._function_header.fullmatch(line):
                continue
            if line == "endfunc":
                if not finish_function(None):
                    break
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

            if line.startswith("param "):
                pending_parameters.append(self._evaluate(line[6:].strip(), variables))
                continue

            return_match = re.fullmatch(r"(?:ret|return)(?:\s+(.+))?", line)
            if return_match:
                expression = return_match.group(1) or ""
                value = self._evaluate(expression, variables) if expression else None
                if not finish_function(value):
                    break
                continue

            print_match = re.fullmatch(r"print\s+(.+)", line)
            if print_match:
                output.append(str(self._evaluate(print_match.group(1), variables)))
                continue

            array_assignment = re.fullmatch(
                r"([A-Za-z_]\w*)\[(.+)\]\s*=\s*(.+)", line
            )
            if array_assignment:
                array_name, index_expression, value_expression = (
                    array_assignment.groups()
                )
                if array_name not in variables:
                    raise NameError(f"Variavel TAC nao definida: {array_name}")
                index = self._evaluate(index_expression, variables)
                value = self._evaluate(value_expression, variables)
                array = variables[array_name]
                if isinstance(array, list) and isinstance(index, int) and index >= 0:
                    if index >= len(array):
                        array.extend([None] * (index + 1 - len(array)))
                array[index] = value
                continue

            call = re.fullmatch(r"call\s+([\w.]+)\s*,\s*(\d+)", line)
            assignment = self._assignment.fullmatch(line)
            if assignment:
                destination, expression = assignment.groups()
                call = re.fullmatch(r"call\s+([\w.]+)\s*,\s*(\d+)", expression)
                if call:
                    function_name, count_text = call.groups()
                    variables = self._call_function(
                        function_name,
                        int(count_text),
                        destination,
                        pc,
                        variables,
                        functions,
                        pending_parameters,
                        frames,
                    )
                    pc = functions[function_name][0]
                    continue
                input_match = re.fullmatch(r"input(?:\((.*)\))?", expression)
                if input_match:
                    try:
                        variables[destination] = next(input_values)
                    except StopIteration as error:
                        raise EOFError("Entrada TAC esgotada") from error
                    continue
                variables[destination] = self._evaluate(expression, variables)
                continue

            if call:
                function_name, count_text = call.groups()
                variables = self._call_function(
                    function_name,
                    int(count_text),
                    None,
                    pc,
                    variables,
                    functions,
                    pending_parameters,
                    frames,
                )
                pc = functions[function_name][0]
                continue

            raise ValueError(f"Instrucao TAC nao suportada: {line}")

        return variables, output

    def _call_function(
        self,
        function_name: str,
        argument_count: int,
        destination: str | None,
        return_pc: int,
        caller_variables: dict[str, Any],
        functions: dict[str, tuple[int, tuple[str, ...]]],
        pending_parameters: list[Any],
        frames: list[tuple[int, dict[str, Any], str | None]],
    ) -> dict[str, Any]:
        if function_name not in functions:
            raise ValueError(f"Funcao TAC nao definida: {function_name}")
        if len(pending_parameters) < argument_count:
            raise ValueError("Quantidade insuficiente de parametros TAC")
        arguments = pending_parameters[-argument_count:] if argument_count else []
        if argument_count:
            del pending_parameters[-argument_count:]
        parameters = functions[function_name][1]
        if len(arguments) != len(parameters):
            raise ValueError(
                f"Funcao {function_name} esperava {len(parameters)} argumentos, "
                f"recebeu {len(arguments)}"
            )
        active = dict(caller_variables)
        active.update(zip(parameters, arguments))
        frames.append((return_pc, caller_variables, destination))
        return active

    @staticmethod
    def _label_pc(labels: dict[str, int], label: str) -> int:
        if label not in labels:
            raise ValueError(f"Rotulo TAC nao definido: {label}")
        return labels[label]
