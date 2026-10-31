from __future__ import annotations

import ast
import operator
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class _HeapObject:
    fields: list[Any]


@dataclass
class _Channel:
    messages: list[Any] = field(default_factory=list)


@dataclass
class _ExecutionContext:
    pc: int
    variables: dict[str, Any]
    task_name: str | None = None
    pending_parameters: list[Any] = field(default_factory=list)
    frames: list[tuple[int, dict[str, Any], str | None]] = field(default_factory=list)
    waiting_for: tuple[str, ...] | None = None
    parent_variables: dict[str, Any] | None = None
    initial_variables: dict[str, Any] = field(default_factory=dict)
    done: bool = False


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
    _function_header = re.compile(
        r"func\s+(\w+)\((.*?)\)(?:\s*->\s*[\w<>]+)?:"
    )
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

    def _evaluate(
        self,
        expression: str,
        variables: dict[str, Any],
        channels: dict[tuple[Any, ...], _Channel] | None = None,
    ) -> Any:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as error:
            raise ValueError(f"Expressao TAC invalida: {expression}") from error
        return self._evaluate_node(
            tree.body, variables, channels if channels is not None else {}
        )

    def _evaluate_node(
        self,
        node: ast.AST,
        variables: dict[str, Any],
        channels: dict[tuple[Any, ...], _Channel],
    ) -> Any:
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
            return [
                self._evaluate_node(item, variables, channels) for item in node.elts
            ]
        if isinstance(node, ast.Subscript):
            container = self._evaluate_node(node.value, variables, channels)
            index = self._evaluate_node(node.slice, variables, channels)
            return container[index]
        if isinstance(node, ast.UnaryOp):
            value = self._evaluate_node(node.operand, variables, channels)
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
                    self._evaluate_node(node.left, variables, channels),
                    self._evaluate_node(node.right, variables, channels),
                )
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for value in node.values:
                    result = self._evaluate_node(value, variables, channels)
                    if not result:
                        return result
                return result
            for value in node.values:
                result = self._evaluate_node(value, variables, channels)
                if result:
                    return result
            return result
        if isinstance(node, ast.Compare):
            left = self._evaluate_node(node.left, variables, channels)
            for operation_node, comparator in zip(node.ops, node.comparators):
                operation = self._compare_ops.get(type(operation_node))
                right = self._evaluate_node(comparator, variables, channels)
                if operation is None or not operation(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            arguments = [
                self._evaluate_node(argument, variables, channels)
                for argument in node.args
            ]
            if node.func.id == "len" and len(arguments) == 1:
                return len(arguments[0])
            if node.func.id == "to_number" and len(arguments) == 1:
                value = str(arguments[0]).strip()
                try:
                    number = float(value)
                except ValueError as error:
                    raise ValueError(f"Valor numerico TAC invalido: {value}") from error
                return int(number) if re.fullmatch(r"[+-]?\d+", value) else number
            if node.func.id == "c_channel" and len(arguments) == 2:
                key = tuple(arguments)
                return channels.setdefault(key, _Channel())
        raise ValueError(f"Expressao TAC nao suportada: {ast.dump(node)}")

    @staticmethod
    def _split_operands(text: str) -> list[str]:
        operands: list[str] = []
        start = 0
        depth = 0
        quote: str | None = None
        escaped = False
        for index, character in enumerate(text):
            if escaped:
                escaped = False
            elif quote and character == "\\":
                escaped = True
            elif quote and character == quote:
                quote = None
            elif not quote and character in ("'", '"'):
                quote = character
            elif not quote and character in "([{":
                depth += 1
            elif not quote and character in ")]}":
                depth -= 1
            elif not quote and depth == 0 and character == ",":
                operands.append(text[start:index].strip())
                start = index + 1
        operands.append(text[start:].strip())
        return operands

    @staticmethod
    def _finish_context(context: _ExecutionContext) -> None:
        context.done = True
        if context.parent_variables is None:
            return
        for name, value in context.variables.items():
            if (
                name not in context.initial_variables
                or value is not context.initial_variables[name]
                and value != context.initial_variables[name]
            ):
                context.parent_variables[name] = value

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
                    item.strip().split(":", 1)[0]
                    for item in parameter_text.split(",")
                    if item.strip()
                )
                if name in functions:
                    raise ValueError(f"Funcao TAC duplicada: {name}")
                functions[name] = (index + 1, parameters)

        variables: dict[str, Any] = {}
        output: list[str] = []
        input_values = iter(inputs)
        channels: dict[tuple[Any, ...], _Channel] = {}
        main = _ExecutionContext(0, variables)
        contexts = [main]
        tasks: dict[str, _ExecutionContext] = {}
        steps = 0

        while any(not context.done for context in contexts):
            progressed = False
            for context in list(contexts):
                if context.done:
                    continue
                if context.waiting_for is not None:
                    if not all(
                        name in tasks and tasks[name].done
                        for name in context.waiting_for
                    ):
                        continue
                    context.waiting_for = None
                steps += 1
                if steps > self.max_steps:
                    raise RuntimeError(
                        f"Limite de execucao TAC ({self.max_steps}) excedido"
                    )
                if self._step(
                    context,
                    lines,
                    labels,
                    functions,
                    input_values,
                    output,
                    channels,
                    tasks,
                    contexts,
                ):
                    progressed = True
            if not progressed and any(not context.done for context in contexts):
                blocked = [
                    context.task_name or "main"
                    for context in contexts
                    if not context.done
                ]
                raise RuntimeError(
                    "Execucao TAC bloqueada sem progresso: " + ", ".join(blocked)
                )

        return main.variables, output

    def _step(
        self,
        context: _ExecutionContext,
        lines: list[str],
        labels: dict[str, int],
        functions: dict[str, tuple[int, tuple[str, ...]]],
        input_values: Iterator[Any],
        output: list[str],
        channels: dict[tuple[Any, ...], _Channel],
        tasks: dict[str, _ExecutionContext],
        contexts: list[_ExecutionContext],
    ) -> bool:
        if context.pc >= len(lines):
            self._finish_context(context)
            return True
        line_index = context.pc
        line = lines[line_index]
        context.pc += 1
        variables = context.variables
        if not line or line.endswith(":") or self._function_header.fullmatch(line):
            return True
        if line in ("par_begin", "par_end") or line.startswith("par_begin "):
            return True
        if line == "endfunc":
            if context.frames:
                return_pc, caller_variables, destination = context.frames.pop()
                context.variables = caller_variables
                if destination:
                    caller_variables[destination] = None
                context.pc = return_pc
            else:
                self._finish_context(context)
            return True

        jump = re.fullmatch(r"goto\s+(\w+)", line)
        if jump:
            context.pc = self._label_pc(labels, jump.group(1))
            return True

        conditional = re.fullmatch(r"if(False)?\s+(.+?)\s+goto\s+(\w+)", line)
        if conditional:
            condition = bool(self._evaluate(conditional.group(2), variables, channels))
            should_jump = not condition if conditional.group(1) else condition
            if should_jump:
                context.pc = self._label_pc(labels, conditional.group(3))
            return True

        if line.startswith("param "):
            context.pending_parameters.append(
                self._evaluate(line[6:].strip(), variables, channels)
            )
            return True

        return_match = re.fullmatch(r"(?:ret|return)(?:\s+(.+))?", line)
        if return_match:
            expression = return_match.group(1) or ""
            value = (
                self._evaluate(expression, variables, channels) if expression else None
            )
            if context.frames:
                return_pc, caller_variables, destination = context.frames.pop()
                context.variables = caller_variables
                if destination:
                    caller_variables[destination] = value
                context.pc = return_pc
            else:
                self._finish_context(context)
            return True

        print_match = re.fullmatch(r"print\s+(.+)", line)
        if print_match:
            values = (
                self._evaluate(operand, variables, channels)
                for operand in self._split_operands(print_match.group(1))
            )
            output.append(" ".join(map(str, values)))
            return True

        send = re.fullmatch(r"send\s+(.+)", line)
        if send:
            operands = self._split_operands(send.group(1))
            if len(operands) != 2:
                raise ValueError(f"Instrucao send TAC invalida: {line}")
            channel = self._evaluate(operands[0], variables, channels)
            if not isinstance(channel, _Channel):
                raise TypeError("send TAC requer um canal")
            channel.messages.append(
                self._evaluate(operands[1], variables, channels)
            )
            return True

        typed_send = re.fullmatch(r"send_typed\s+(.+)", line)
        if typed_send:
            operands = self._split_operands(typed_send.group(1))
            if len(operands) < 2:
                raise ValueError(f"Instrucao send_typed TAC invalida: {line}")
            channel = self._evaluate(operands[0], variables, channels)
            if not isinstance(channel, _Channel):
                raise TypeError("send_typed TAC requer um canal")
            channel.messages.extend(
                self._evaluate(operand, variables, channels)
                for operand in operands[1:]
            )
            return True

        typed_receive = re.fullmatch(r"recv\s+(.+)", line)
        if typed_receive:
            operands = self._split_operands(typed_receive.group(1))
            if len(operands) < 2:
                raise ValueError(f"Instrucao recv TAC invalida: {line}")
            channel = self._evaluate(operands[0], variables, channels)
            if not isinstance(channel, _Channel):
                raise TypeError("recv TAC requer um canal")
            if len(channel.messages) < len(operands) - 1:
                context.pc = line_index
                return False
            for destination in operands[1:]:
                if not re.fullmatch(r"[A-Za-z_]\w*", destination):
                    raise ValueError(f"Destino recv TAC invalido: {destination}")
                variables[destination] = channel.messages.pop(0)
            return True

        array_assignment = re.fullmatch(
            r"([A-Za-z_]\w*)\[(.+)\]\s*=\s*(.+)", line
        )
        if array_assignment:
            array_name, index_expression, value_expression = (
                array_assignment.groups()
            )
            if array_name not in variables:
                raise NameError(f"Variavel TAC nao definida: {array_name}")
            index = self._evaluate(index_expression, variables, channels)
            value = self._evaluate(value_expression, variables, channels)
            array = variables[array_name]
            if isinstance(array, list) and isinstance(index, int) and index >= 0:
                if index >= len(array):
                    array.extend([None] * (index + 1 - len(array)))
            array[index] = value
            return True

        assignment = self._assignment.fullmatch(line)
        if assignment:
            destination, expression = assignment.groups()
            call = re.fullmatch(r"call\s+([\w.]+)\s*,\s*(\d+)", expression)
            if call:
                function_name, count_text = call.groups()
                context.variables = self._call_function(
                    function_name,
                    int(count_text),
                    destination,
                    context.pc,
                    variables,
                    functions,
                    context.pending_parameters,
                    context.frames,
                )
                context.pc = functions[function_name][0]
                return True
            allocation = re.fullmatch(r"alloc\s+(.+)", expression)
            if allocation:
                size = int(self._evaluate(allocation.group(1), variables, channels))
                if size < 0:
                    raise ValueError("Tamanho de alloc TAC nao pode ser negativo")
                variables[destination] = _HeapObject([None] * size)
                return True
            getfield = re.fullmatch(r"getfield\s+(.+)", expression)
            if getfield:
                operands = self._split_operands(getfield.group(1))
                if len(operands) != 2:
                    raise ValueError(f"Instrucao getfield TAC invalida: {line}")
                obj = self._evaluate(operands[0], variables, channels)
                offset = int(self._evaluate(operands[1], variables, channels))
                if not isinstance(obj, _HeapObject):
                    raise TypeError("getfield TAC requer um objeto alocado")
                if offset < 0 or offset >= len(obj.fields):
                    raise IndexError(f"Offset getfield TAC invalido: {offset}")
                variables[destination] = obj.fields[offset]
                return True
            receive = re.fullmatch(r"(?:recv|receive)\s+(.+)", expression)
            if receive:
                channel = self._evaluate(receive.group(1), variables, channels)
                if not isinstance(channel, _Channel):
                    raise TypeError("recv TAC requer um canal")
                if not channel.messages:
                    context.pc = line_index
                    return False
                variables[destination] = channel.messages.pop(0)
                return True
            input_match = re.fullmatch(r"input(?:\((.*)\))?", expression)
            if input_match:
                try:
                    variables[destination] = next(input_values)
                except StopIteration as error:
                    raise EOFError("Entrada TAC esgotada") from error
                return True
            variables[destination] = self._evaluate(expression, variables, channels)
            return True

        setfield = re.fullmatch(r"setfield\s+(.+)", line)
        if setfield:
            operands = self._split_operands(setfield.group(1))
            if len(operands) != 3:
                raise ValueError(f"Instrucao setfield TAC invalida: {line}")
            obj = self._evaluate(operands[0], variables, channels)
            offset = int(self._evaluate(operands[1], variables, channels))
            value = self._evaluate(operands[2], variables, channels)
            if not isinstance(obj, _HeapObject):
                raise TypeError("setfield TAC requer um objeto alocado")
            if offset < 0 or offset >= len(obj.fields):
                raise IndexError(f"Offset setfield TAC invalido: {offset}")
            obj.fields[offset] = value
            return True

        fork = re.fullmatch(
            r"fork\s+(\w+)\s*,\s*(core|host|simulated)\s*,\s*(.*?)\s*,\s*(\w+)",
            line,
        )
        if fork:
            task_name, _, _, label = fork.groups()
            if task_name in tasks and not tasks[task_name].done:
                raise ValueError(f"Tarefa TAC duplicada: {task_name}")
            task = _ExecutionContext(
                self._label_pc(labels, label),
                dict(variables),
                task_name=task_name,
                parent_variables=variables,
                initial_variables=dict(variables),
            )
            tasks[task_name] = task
            contexts.append(task)
            return True

        join = re.fullmatch(r"join(?:\s+(.+))?", line)
        if join:
            task_names = tuple(
                item.strip()
                for item in self._split_operands(join.group(1) or "")
                if item.strip()
            )
            if context.task_name and context.task_name in task_names:
                self._finish_context(context)
                return True
            if not task_names:
                task_names = tuple(tasks)
            unknown = [name for name in task_names if name not in tasks]
            if unknown:
                raise ValueError(f"Tarefa TAC nao definida: {', '.join(unknown)}")
            if not all(tasks[name].done for name in task_names):
                context.pc = line_index
                context.waiting_for = task_names
                return False
            return True

        call = re.fullmatch(r"call\s+([\w.]+)\s*,\s*(\d+)", line)
        if call:
            function_name, count_text = call.groups()
            context.variables = self._call_function(
                function_name,
                int(count_text),
                None,
                context.pc,
                variables,
                functions,
                context.pending_parameters,
                context.frames,
            )
            context.pc = functions[function_name][0]
            return True

        raise ValueError(f"Instrucao TAC nao suportada: {line}")

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
