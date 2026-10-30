from __future__ import annotations

import unittest

from components.lexico.c_lexico import Lexer
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.ast import Program
from components.sintatico.c_sintatico import Parser


def analyze(source: str) -> tuple[SemanticAnalyzer, Program]:
    program = Parser(Lexer(source)).parse()
    analyzer = SemanticAnalyzer()
    analyzer.analyze(program)
    return analyzer, program


class SemanticAnalyzerTests(unittest.TestCase):
    def test_incompatible_string_addition_reports_line_and_column(self) -> None:
        analyzer, _ = analyze('SEQ\n    print("a" + 1)\n')

        self.assertTrue(analyzer.diagnostics)
        diagnostic = analyzer.diagnostics[0]
        self.assertEqual(diagnostic.line, 2)
        self.assertIsNotNone(diagnostic.column)
        self.assertIn("incompativeis", diagnostic.message)

    def test_recursive_function_and_forward_call_pass(self) -> None:
        analyzer, _ = analyze(
            "def first(value: int) -> int:\n"
            "    if value <= 1:\n"
            "        return 1\n"
            "    else:\n"
            "        return value * factorial(value - 1)\n"
            "def factorial(value: int) -> int:\n"
            "    if value <= 1:\n"
            "        return 1\n"
            "    else:\n"
            "        return value * factorial(value - 1)\n"
            "def later() -> int:\n"
            "    return 7\n"
            "SEQ\n"
            "    print(first(5))\n"
            "    print(later())\n"
        )

        self.assertFalse(analyzer.diagnostics, analyzer.diagnostics)

    def test_integer_plus_float_infers_float(self) -> None:
        _, program = analyze("SEQ\n    print(1 + 1.5)\n")
        expression = program.statements[0].statements[0].arguments[0]

        self.assertEqual(expression.tipo_inferido, "float")

    def test_float_to_int_is_rejected_but_int_to_float_is_allowed(self) -> None:
        analyzer, _ = analyze(
            "SEQ\n"
            "    whole: int = 1.5\n"
            "    decimal: float = 2\n"
        )

        self.assertTrue(
            any("Tipo incompativel" in diagnostic.message
                for diagnostic in analyzer.diagnostics)
        )
        self.assertFalse(
            any("'decimal'" in diagnostic.message
                for diagnostic in analyzer.diagnostics)
        )

    def test_calls_check_arity_argument_types_and_return_type(self) -> None:
        analyzer, program = analyze(
            "def value(argument: string) -> int:\n"
            "    return 1\n"
            "SEQ\n"
            "    answer: string = value(3)\n"
            "    print(value())\n"
            "    print(missing_function(1))\n"
        )

        messages = [diagnostic.message for diagnostic in analyzer.diagnostics]
        self.assertTrue(any("argumento 1" in message for message in messages))
        self.assertTrue(any("espera 1 argumento(s), recebeu 0" in message
                            for message in messages))
        self.assertTrue(any("Funcao 'missing_function' nao declarada" in message
                            for message in messages))
        self.assertTrue(any("'answer'" in message for message in messages))
        call = program.statements[1].statements[0].init_value
        self.assertEqual(call.tipo_inferido, "int")

    def test_non_void_function_must_return_on_all_paths(self) -> None:
        analyzer, _ = analyze(
            "def maybe(flag: bool) -> int:\n"
            "    if flag:\n"
            "        return 1\n"
            "SEQ\n"
            "    print(1)\n"
        )

        self.assertTrue(
            any("pode terminar sem retornar" in diagnostic.message
                for diagnostic in analyzer.diagnostics)
        )

    def test_method_call_checks_parameter_types_and_infers_return(self) -> None:
        analyzer, program = analyze(
            "class Box:\n"
            "    def get(offset: int) -> float:\n"
            "        return offset\n"
            "SEQ\n"
            "    box: Box = new Box()\n"
            "    print(box.get(\"wrong\"))\n"
        )
        call = program.statements[1].statements[1].arguments[0]

        self.assertTrue(
            any("Tipo incompativel no argumento 1" in diagnostic.message
                for diagnostic in analyzer.diagnostics)
        )
        self.assertEqual(call.tipo_inferido, "float")

    def test_condition_and_undeclared_variable_are_rejected(self) -> None:
        analyzer, _ = analyze(
            "SEQ\n"
            "    if 1:\n"
            "        print(missing)\n"
        )

        messages = [diagnostic.message for diagnostic in analyzer.diagnostics]
        self.assertTrue(any("Condicao deve ser bool" in message for message in messages))
        self.assertTrue(any("nao declarada" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
