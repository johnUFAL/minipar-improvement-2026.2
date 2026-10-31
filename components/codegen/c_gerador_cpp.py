from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from .driver_gcc import DriverGCC


_FUNCTION = re.compile(
    r"func\s+([A-Za-z_]\w*)\((.*?)\)(?:\s*->\s*([\w<>*]+))?:"
)
_ASSIGNMENT = re.compile(r"([A-Za-z_]\w*)(?::([\w<>*]+))?\s*=\s*(.+)")
_ARRAY_ASSIGNMENT = re.compile(r"([A-Za-z_]\w*)\[(.+)\]\s*=\s*(.+)")


@dataclass
class _Function:
    name: str
    parameters: list[tuple[str, str]]
    return_type: str | None
    lines: list[tuple[str, int | None]]


class CppCodeGenerator:
    """Translates textual TAC into C++ without consulting the source AST."""

    @staticmethod
    def _split(text: str) -> list[str]:
        values: list[str] = []
        start = depth = 0
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
                values.append(text[start:index].strip())
                start = index + 1
        values.append(text[start:].strip())
        return [value for value in values if value]

    @staticmethod
    def _cpp_type(type_name: str | None) -> str:
        if not type_name:
            return "std::int64_t"
        aliases = {
            "int": "std::int64_t",
            "integer": "std::int64_t",
            "int64": "std::int64_t",
            "int64_t": "std::int64_t",
            "float": "double",
            "double": "double",
            "bool": "bool",
            "string": "std::string",
            "void": "void",
            "c_channel": "std::shared_ptr<MiniParChannel>",
            "channel": "std::shared_ptr<MiniParChannel>",
            "Canal*": "std::shared_ptr<MiniParChannel>",
            "canal*": "std::shared_ptr<MiniParChannel>",
            "list": "std::vector<std::int64_t>",
            "matrix": "std::vector<std::vector<double>>",
        }
        if type_name.startswith("list<") and type_name.endswith(">"):
            element = CppCodeGenerator._cpp_type(type_name[5:-1])
            return f"std::vector<{element}>"
        return aliases.get(type_name, f"std::shared_ptr<{type_name}>")

    @staticmethod
    def _literal_type(expression: str) -> str | None:
        text = expression.strip()
        if text in ("true", "false"):
            return "bool"
        if text.startswith(("'", '"')):
            return "string"
        if re.fullmatch(r"[+-]?\d+", text):
            return "int"
        if re.fullmatch(r"[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?", text):
            return "float"
        return None

    @staticmethod
    def _expression(expression: str, result_type: str | None = None) -> str:
        text = expression.strip()
        if text.startswith("'") or text.startswith('"'):
            try:
                value = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                value = text[1:-1]
            if isinstance(value, str):
                return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'
        if text.startswith("[") and text.endswith("]"):
            elements = CppCodeGenerator._split(text[1:-1])
            values = ", ".join(CppCodeGenerator._expression(item) for item in elements)
            element_type = "double" if any("." in item for item in elements) else "std::int64_t"
            return f"std::vector<{element_type}>{{{values}}}"
        binary = re.fullmatch(r"(.+?)\s+([+\-*/%])\s+(.+)", text)
        if binary:
            left, operator, right = binary.groups()
            left_cpp = CppCodeGenerator._expression(left)
            right_cpp = CppCodeGenerator._expression(right)
            if operator == "+" and result_type == "string":
                return f"__minipar_concat({left_cpp}, {right_cpp})"
            if operator == "/":
                return f"__minipar_divide({left_cpp}, {right_cpp})"
            return f"({left_cpp} {operator} {right_cpp})"
        text = re.sub(r"\btrue\b", "true", text)
        text = re.sub(r"\bfalse\b", "false", text)
        text = re.sub(r"\band\b", "&&", text)
        text = re.sub(r"\bor\b", "||", text)
        text = re.sub(r"\bnot\b", "!", text)
        text = re.sub(r"(?<![=!<>])=(?!=)", "==", text) if "if " in text else text
        text = re.sub(r"\blen\(", "__minipar_len(", text)
        text = re.sub(r"\bto_number\(", "__minipar_to_float(", text)
        text = re.sub(r"\binput\(", "input(", text)
        text = re.sub(r"\bc_channel\(", "std::make_shared<MiniParChannel>(", text)
        text = re.sub(r"\bmatrix\(", "__make_matrix(", text)
        text = re.sub(r"\b([A-Za-z_]\w*)\[([^\[\]]+)\]", r"__minipar_array_at(\1, \2)", text)
        return text

    @staticmethod
    def _rename_identifiers(text: str, names: dict[str, str]) -> str:
        result: list[str] = []
        index = 0
        quote: str | None = None
        escaped = False
        while index < len(text):
            character = text[index]
            if quote:
                result.append(character)
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
                index += 1
                continue
            if character in ("'", '"'):
                quote = character
                result.append(character)
                index += 1
                continue
            identifier = re.match(r"[A-Za-z_]\w*", text[index:])
            if identifier:
                word = identifier.group()
                result.append(names.get(word, word))
                index += len(word)
            else:
                result.append(character)
                index += 1
        return "".join(result)

    @staticmethod
    def _parse(tac: str) -> tuple[list[_Function], list[tuple[str, int | None]], dict[str, list[str]]]:
        functions: list[_Function] = []
        main: list[tuple[str, int | None]] = []
        classes: dict[str, list[str]] = {}
        current_function: _Function | None = None
        source_line: int | None = None
        in_main = False

        for raw_line in tac.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                source_match = re.fullmatch(r"#\s*source:\s*(\d+)", line)
                if source_match:
                    source_line = int(source_match.group(1))
                class_match = re.fullmatch(r"#\s*class\s+([A-Za-z_]\w*):\s*(.*)", line)
                if class_match:
                    classes[class_match.group(1)] = (
                        CppCodeGenerator._split(class_match.group(2))
                    )
                continue
            header = _FUNCTION.fullmatch(line)
            if header:
                name, parameter_text, return_type = header.groups()
                parameters = []
                for parameter in CppCodeGenerator._split(parameter_text):
                    pieces = parameter.split(":", 1)
                    parameters.append((pieces[0].strip(), pieces[1].strip() if len(pieces) > 1 else ""))
                current_function = _Function(name, parameters, return_type, [])
                functions.append(current_function)
                source_line = None
                continue
            if line == "endfunc":
                current_function = None
                source_line = None
                continue
            if line == "MAIN:":
                in_main = True
                source_line = None
                continue
            if current_function is not None:
                current_function.lines.append((line, source_line))
            elif in_main or not functions:
                if line != "goto MAIN":
                    main.append((line, source_line))
        return functions, main, classes

    @classmethod
    def _infer_types(
        cls, lines: list[tuple[str, int | None]], parameters: list[tuple[str, str]],
        functions: dict[str, _Function], classes: dict[str, list[str]],
    ) -> tuple[dict[str, str], list[tuple[str, str]], str]:
        types = {name: type_name for name, type_name in parameters if type_name}
        for line, _ in lines:
            assignment = _ASSIGNMENT.fullmatch(line)
            if assignment and assignment.group(2):
                types[assignment.group(1)] = assignment.group(2)

        def expression_type(expression: str) -> str | None:
            expression = expression.strip()
            if expression in types:
                return types[expression]
            literal = cls._literal_type(expression)
            if literal:
                return literal
            if expression.startswith("["):
                elements = cls._split(expression[1:-1])
                if elements and all(cls._literal_type(item) == "float" for item in elements):
                    return "list<float>"
                if elements and cls._literal_type(elements[0]) == "string":
                    return "list<string>"
                return "list<int>"
            index = re.fullmatch(r"([A-Za-z_]\w*)\[(.+)\]", expression)
            if index:
                collection_type = types.get(index.group(1), "")
                if collection_type.startswith("list<"):
                    return collection_type[5:-1]
                return "int"
            call = re.fullmatch(r"call\s+([\w.]+)\s*,\s*\d+", expression)
            if call and call.group(1) in functions:
                return functions[call.group(1)].return_type
            if expression.startswith("alloc "):
                return expression[6:].strip()
            if expression.startswith("c_channel("):
                return "c_channel"
            if expression.startswith(("input(", "recv ")):
                return "string"
            if expression.startswith("getfield "):
                operands = cls._split(expression[len("getfield "):])
                if len(operands) == 2:
                    class_type = types.get(operands[0], "")
                    fields = classes.get(class_type.removeprefix("shared_ptr<").removesuffix(">"), [])
                    try:
                        return fields[int(operands[1])]
                    except (ValueError, IndexError):
                        return None
            operands = re.split(r"\s+(?:\+|-|\*|/|%)\s+", expression)
            if len(operands) > 1:
                operand_types = [expression_type(item) for item in operands]
                if "string" in operand_types and "+" in expression:
                    return "string"
                if "float" in operand_types or "/" in expression:
                    return "float"
                if all(item is not None for item in operand_types):
                    return "int"
            return None

        def function_calls() -> list[tuple[str, list[str]]]:
            calls: list[tuple[str, list[str]]] = []
            for body in [function.lines for function in functions.values()] + [lines]:
                pending: list[str] = []
                for line, _ in body:
                    if line.startswith("param "):
                        pending.append(line[6:].strip())
                    else:
                        call = re.search(r"call\s+([\w.]+)\s*,\s*(\d+)", line)
                        if call:
                            count = int(call.group(2))
                            calls.append((call.group(1), pending[-count:] if count else []))
                            if count:
                                del pending[-count:]
                        elif not line.startswith("#"):
                            pending.clear()
            return calls

        # Propagate types from call sites so unannotated TAC parameters remain typed.
        for _ in range(max(1, len(functions) + 1)):
            changed = False
            for function_name, arguments in function_calls():
                function = functions.get(function_name)
                if function is None:
                    continue
                for index, expression in enumerate(arguments):
                    if index < len(function.parameters) and not function.parameters[index][1]:
                        inferred = expression_type(expression)
                        if inferred and function.parameters[index][1] != inferred:
                            function.parameters[index] = (function.parameters[index][0], inferred)
                            changed = True
            for body, parameters in [(function.lines, function.parameters) for function in functions.values()] + [(lines, [])]:
                local_types = dict(types)
                local_types.update({name: kind for name, kind in parameters if kind})
                for line, _ in body:
                    assignment = _ASSIGNMENT.fullmatch(line)
                    if assignment:
                        destination, explicit_type, expression = assignment.groups()
                        inferred = explicit_type or expression_type(expression)
                        if inferred and local_types.get(destination) != inferred:
                            local_types[destination] = inferred
                            changed = True
                types.update(local_types)
            for function in functions.values():
                if function.return_type:
                    continue
                returns = [
                    expression_type(match.group(1))
                    for line, _ in function.lines
                    if (match := re.fullmatch(r"ret\s+(.+)", line))
                ]
                inferred_return = next((item for item in returns if item), None)
                if inferred_return:
                    function.return_type = inferred_return
                    changed = True
            if not changed:
                break

        for function in functions.values():
            function.return_type = function.return_type or (
                "void" if not any(line.startswith("ret ") for line, _ in function.lines)
                else "int"
            )
        return types, parameters, "void"

    @classmethod
    def _render_body(
        cls, lines: list[tuple[str, int | None]], parameters: list[tuple[str, str]],
        functions: dict[str, _Function], classes: dict[str, list[str]],
        declare_variables: bool = True,
    ) -> tuple[list[str], str]:
        types, _, _ = cls._infer_types(lines, parameters, functions, classes)
        variables: set[str] = set()
        for line, _ in lines:
            assignment = _ASSIGNMENT.fullmatch(line)
            if assignment:
                variables.add(assignment.group(1))
            array_assignment = _ARRAY_ASSIGNMENT.fullmatch(line)
            if array_assignment:
                variables.add(array_assignment.group(1))
        parameter_names = {name for name, _ in parameters}
        local_declarations = (
            [
                f"    [[maybe_unused]] {cls._cpp_type(types.get(name))} {name}{{}};"
                for name in sorted(variables - parameter_names)
            ]
            if declare_variables
            else []
        )
        fork_blocks: dict[
            int,
            tuple[
                str, list[tuple[str, int | None]], dict[str, str],
                dict[str, str], dict[str, str],
            ],
        ] = {}
        excluded: set[int] = set()
        for fork_index, (fork_line, _) in enumerate(lines):
            if not fork_line.startswith("fork "):
                continue
            fork = re.fullmatch(
                r"fork\s+(\w+)\s*,\s*\w+\s*,\s*.*?,\s*(\w+)", fork_line
            )
            if fork is None:
                raise ValueError(f"Instrucao fork TAC invalida: {fork_line}")
            task_name, branch_label = fork.groups()
            label_index = next(
                (
                    index for index in range(fork_index + 1, len(lines))
                    if lines[index][0] == f"{branch_label}:"
                ),
                None,
            )
            if label_index is None:
                raise ValueError(f"Rotulo fork TAC nao definido: {branch_label}")
            join_index = next(
                (
                    index for index in range(label_index + 1, len(lines))
                    if lines[index][0].startswith("join ")
                    and task_name in cls._split(lines[index][0][5:])
                ),
                None,
            )
            if join_index is None:
                raise ValueError(f"join TAC nao encontrado para tarefa {task_name}")
            branch_body = lines[label_index + 1:join_index]
            branch_types, _, _ = cls._infer_types(
                branch_body, parameters, functions, classes
            )
            assigned: set[str] = set()
            for branch_line, _ in branch_body:
                assignment = _ASSIGNMENT.fullmatch(branch_line)
                if assignment:
                    assigned.add(assignment.group(1))
                array_assignment = _ARRAY_ASSIGNMENT.fullmatch(branch_line)
                if array_assignment:
                    assigned.add(array_assignment.group(1))
                if branch_line.startswith("setfield "):
                    operands = cls._split(branch_line[len("setfield "):])
                    if operands and re.fullmatch(r"[A-Za-z_]\w*", operands[0]):
                        assigned.add(operands[0])
            for name in assigned:
                if not branch_types.get(name):
                    branch_types[name] = types.get(name, "")
            untyped_assignments = sorted(
                name for name in assigned if not branch_types.get(name)
            )
            if untyped_assignments:
                raise ValueError(
                    "Tipo nao inferido para variavel(is) atribuida(s) "
                    "em ramo PAR: " + ", ".join(untyped_assignments)
                )
            local_names = {
                name: f"_minipar_local_{fork_index}_{name}"
                for name in sorted(assigned)
            }
            result_names = {
                name: f"_minipar_result_{fork_index}_{name}"
                for name in local_names
            }
            type_names = {
                name: branch_types[name] for name in local_names
            }
            fork_blocks[fork_index] = (
                task_name, branch_body, local_names, result_names, type_names
            )
            excluded.update(range(label_index, join_index + 1))

        output = local_declarations
        if declare_variables and fork_blocks:
            output.append("    std::vector<std::function<void()>> _minipar_tasks;")
            for _, _, _, result_names, type_names in fork_blocks.values():
                for name, result_name in result_names.items():
                    output.append(
                        f"    [[maybe_unused]] {cls._cpp_type(type_names[name])} "
                        f"{result_name}{{}};"
                    )
        pending_parameters: list[str] = []
        pending_forks: list[int] = []
        index = 0
        while index < len(lines):
            if index in excluded:
                index += 1
                continue
            line, source_line = lines[index]
            if source_line is not None:
                output.append(f"    // MiniPar line {source_line}")
            if index in fork_blocks:
                _, branch_body, local_names, result_names, _ = fork_blocks[index]
                renamed_body = [
                    (cls._rename_identifiers(branch_line, local_names), line_number)
                    for branch_line, line_number in branch_body
                ]
                rendered_branch_body, _ = cls._render_body(
                    renamed_body, parameters, functions, classes,
                    declare_variables=False,
                )
                result_captures = ", ".join(
                    f"&{result_name}" for result_name in result_names.values()
                )
                capture_clause = (
                    f"[=, {result_captures}]" if result_captures else "[=]"
                )
                output.append(
                    f"    _minipar_tasks.emplace_back({capture_clause}() mutable {{"
                )
                output.extend(
                    f"        auto {local_name} = {original_name};"
                    for original_name, local_name in local_names.items()
                )
                output.extend(f"    {item}" for item in rendered_branch_body)
                output.extend(
                    f"        {result_names[name]} = {local_names[name]};"
                    for name in local_names
                )
                output.append("    });")
                pending_forks.append(index)
                index += 1
                continue
            if line.startswith("param "):
                pending_parameters.append(line[6:].strip())
                index += 1
                continue
            if line.startswith("print "):
                print_values = [
                    cls._expression(value)
                    for value in cls._split(line[6:])
                ]
                output.append(f"    minipar_print({', '.join(print_values)});")
                index += 1
                continue
            assignment = _ASSIGNMENT.fullmatch(line)
            array_assignment = _ARRAY_ASSIGNMENT.fullmatch(line)
            if assignment:
                destination, _, expression = assignment.groups()
                call = re.fullmatch(r"call\s+([\w.]+)\s*,\s*(\d+)", expression)
                allocation = re.fullmatch(r"alloc\s+(.+)", expression)
                getfield = re.fullmatch(r"getfield\s+(.+)", expression)
                if call:
                    count = int(call.group(2))
                    args = pending_parameters[-count:] if count else []
                    if count:
                        del pending_parameters[-count:]
                    output.append(f"    {destination} = {call.group(1)}({', '.join(cls._expression(item) for item in args)});")
                elif allocation:
                    allocation_type = types.get(destination, "")
                    if allocation_type.startswith("shared_ptr<"):
                        allocation_type = allocation_type[11:-1]
                    output.append(f"    {destination} = std::make_shared<{allocation_type}>();")
                elif getfield:
                    base, offset = cls._split(getfield.group(1))
                    output.append(f"    {destination} = {cls._expression(base)}->field_{offset};")
                elif expression.startswith("recv "):
                    channel = cls._split(expression[5:])[0]
                    receive_type = cls._cpp_type(types.get(destination, "string"))
                    output.append(
                        f"    {destination} = {cls._expression(channel)}"
                        f"->receber<{receive_type}>();"
                    )
                else:
                    output.append(
                        f"    {destination} = "
                        f"{cls._expression(expression, types.get(destination))};"
                    )
            elif array_assignment:
                array_name, array_index, value = array_assignment.groups()
                output.append(f"    __minipar_array_set({array_name}, {cls._expression(array_index)}, {cls._expression(value)});")
            elif line.startswith("setfield "):
                base, offset, value = cls._split(line[len("setfield "):])
                output.append(f"    {cls._expression(base)}->field_{offset} = {cls._expression(value)};")
            elif line.startswith("send "):
                channel, message = cls._split(line[5:])
                output.append(
                    f"    {cls._expression(channel)}->sendData("
                    f"__to_string({cls._expression(message)}));"
                )
            elif line.startswith("send_typed "):
                arguments = cls._split(line[len("send_typed "):])
                channel, messages = arguments[0], arguments[1:]
                if not messages:
                    raise ValueError(f"Instrucao send_typed TAC invalida: {line}")
                values = ", ".join(cls._expression(message) for message in messages)
                output.append(
                    f"    {cls._expression(channel)}->enviar({values});"
                )
            elif line.startswith("recv "):
                arguments = cls._split(line[5:])
                if len(arguments) < 2:
                    raise ValueError(f"Instrucao recv TAC invalida: {line}")
                channel, destinations = arguments[0], arguments[1:]
                if len(destinations) == 1:
                    destination = destinations[0]
                    output.append(
                        f"    {destination} = {cls._expression(channel)}"
                        f"->receber<decltype({destination})>();"
                    )
                else:
                    receive_types = ", ".join(
                        f"decltype({destination})"
                        for destination in destinations
                    )
                    output.append(
                        f"    std::tie({', '.join(destinations)}) = "
                        f"{cls._expression(channel)}->receber<{receive_types}>();"
                    )
            elif line.startswith("ifFalse "):
                conditional = re.fullmatch(
                    r"ifFalse\s+(.+?)\s+goto\s+(\w+)", line
                )
                if conditional is None:
                    raise ValueError(f"Instrucao ifFalse TAC invalida: {line}")
                condition, label = conditional.groups()
                output.append(f"    if (!({cls._expression(condition)})) goto {label};")
            elif line.startswith("if "):
                conditional = re.fullmatch(
                    r"if\s+(.+?)\s+goto\s+(\w+)", line
                )
                if conditional is None:
                    raise ValueError(f"Instrucao if TAC invalida: {line}")
                condition, label = conditional.groups()
                output.append(f"    if ({cls._expression(condition)}) goto {label};")
            elif line.startswith("goto "):
                output.append(f"    goto {line[5:].strip()};")
            elif line.endswith(":"):
                output.append(f"{line[:-1]}: ;")
            elif line == "ret":
                output.append("    return;")
            elif line.startswith("ret "):
                output.append(f"    return {cls._expression(line[4:])};")
            elif re.fullmatch(r"call\s+[\w.]+\s*,\s*\d+", line):
                call = re.fullmatch(
                    r"call\s+([\w.]+)\s*,\s*(\d+)", line
                )
                if call is None:
                    raise ValueError(f"Instrucao call TAC invalida: {line}")
                function_name, count_text = call.groups()
                count = int(count_text)
                args = pending_parameters[-count:] if count else []
                if count:
                    del pending_parameters[-count:]
                output.append(
                    f"    {function_name}({', '.join(cls._expression(item) for item in args)});"
                )
            elif line.startswith("fork "):
                raise ValueError(f"Instrucao fork TAC nao associada a bloco: {line}")
            elif line.startswith("join"):
                output.append("    minipar_parallel(_minipar_tasks);")
                output.append("    _minipar_tasks.clear();")
                for fork_index in pending_forks:
                    _, _, _, result_names, _ = fork_blocks[fork_index]
                    output.extend(
                        f"    {name} = {result_name};"
                        for name, result_name in result_names.items()
                    )
                pending_forks.clear()
            elif line in ("par_begin", "par_end") or line.startswith("par_begin "):
                pass
            else:
                raise ValueError(f"Instrucao TAC nao suportada pelo codegen: {line}")
            index += 1
        return output, types.get("__return__", "void")

    @classmethod
    def _generate_cpp(cls, tac: str) -> str:
        functions, main_lines, classes = cls._parse(tac)
        function_map = {function.name: function for function in functions}
        for function in functions:
            cls._infer_types(function.lines, function.parameters, function_map, classes)

        cpp = ['#include "minipar_rt.hpp"', "", "#include <memory>", "#include <string>", "#include <vector>", ""]
        for class_name, fields in classes.items():
            cpp.append(f"struct {class_name} {{")
            for index, field_type in enumerate(fields):
                cpp.append(f"    {cls._cpp_type(field_type)} field_{index}{{}};")
            cpp.extend(["};", ""])

        signatures: dict[str, str] = {}
        for function in functions:
            ret = cls._cpp_type(function.return_type)
            args = ", ".join(
                f"[[maybe_unused]] {cls._cpp_type(kind)} {name}"
                for name, kind in function.parameters
            )
            signatures[function.name] = f"{ret} {function.name}({args})"
        for signature in signatures.values():
            cpp.append(f"{signature};")
        if signatures:
            cpp.append("")

        for function in functions:
            signature = signatures[function.name]
            cpp.append(f"{signature} {{")
            body, _ = cls._render_body(function.lines, function.parameters, function_map, classes)
            cpp.extend(body)
            if function.return_type != "void" and not any(line.startswith("ret ") for line, _ in function.lines):
                cpp.append("    return {};")
            cpp.extend(["}", ""])

        cpp.extend([
            "int main(int argc, char** argv) {",
            "    minipar_init_console();",
            "    try {",
            "        minipar_init(argc, argv);",
        ])
        body, _ = cls._render_body(main_lines, [], function_map, classes)
        cpp.extend("    " + line for line in body)
        cpp.extend([
            "    } catch (const std::exception& error) {",
            '        std::cerr << "Erro de execucao: " << error.what() << std::endl;',
            "        return 1;",
            "    }",
            "    return 0;",
            "}",
            "",
        ])
        return "\n".join(cpp)

    def generate(
        self,
        tac: str,
        output_name: str,
        nivel_otimizacao: str = "O2",
    ) -> bool:
        if not isinstance(tac, str):
            raise TypeError("CppCodeGenerator.generate espera TAC textual")
        cpp_code = self._generate_cpp(tac)
        output_dir = Path(__file__).resolve().parents[2] / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        cpp_path = output_dir / f"{output_name}.cpp"
        cpp_path.write_text(cpp_code, encoding="utf-8")
        print(
            f"[CODEGEN] Compilando via g++ com -std=c++17 "
            f"-{nivel_otimizacao} -Wall..."
        )
        return DriverGCC().compile(cpp_path, optimization_level=nivel_otimizacao)
