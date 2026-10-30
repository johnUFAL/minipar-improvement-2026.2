from __future__ import annotations

import unittest
from collections.abc import Sequence

from components.interfaces import ISemantico
from components.lexico import Lexer
from components.sintatico.ast import (
    Assignment,
    BinaryExpr,
    ForStmt,
    FuncCallExpr,
    FuncDecl,
    IfStmt,
    IndexAssign,
    IndexExpr,
    NumberExpr,
    Program,
    SeqBlock,
    UnaryExpr,
    WhileStmt,
)
from components.sintatico.c_sintatico import Parser
from erros.diagnosticos import Diagnostic, DiagnosticBag


def parse(source: str) -> tuple[Program, DiagnosticBag]:
    diagnostics = DiagnosticBag(source)
    program = Parser(Lexer(source, diagnostics), diagnostics).parse()
    return program, diagnostics


class RecordingSemanticAnalyzer(ISemantico):
    def __init__(self) -> None:
        self.programs: list[Program] = []

    def analyze(self, program: Program) -> bool:
        self.programs.append(program)
        return True

    @property
    def diagnostics(self) -> Sequence[Diagnostic]:
        return ()


class ExpressionParserTests(unittest.TestCase):
    def test_multiplication_has_higher_precedence_than_addition(self) -> None:
        program, diagnostics = parse("SEQ\n    result = 2 + 3 * 4\n")

        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        root = program.statements[0]
        assert isinstance(root, SeqBlock)
        assignment = root.statements[0]
        assert isinstance(assignment, Assignment)
        assert isinstance(assignment.value, BinaryExpr)
        self.assertEqual(assignment.value.op, "+")
        assert isinstance(assignment.value.right, BinaryExpr)
        self.assertEqual(assignment.value.right.op, "*")

    def test_subtraction_associates_to_the_left(self) -> None:
        program, diagnostics = parse("SEQ\n    result = 10 - 3 - 2\n")

        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        root = program.statements[0]
        assert isinstance(root, SeqBlock)
        assignment = root.statements[0]
        assert isinstance(assignment, Assignment)
        expression = assignment.value
        assert isinstance(expression, BinaryExpr)
        self.assertEqual(expression.op, "-")
        assert isinstance(expression.left, BinaryExpr)
        self.assertEqual(expression.left.op, "-")
        assert isinstance(expression.right, NumberExpr)
        self.assertEqual(expression.right.value, "2")

    def test_function_calls_and_indexed_assignment(self) -> None:
        program, diagnostics = parse(
            "SEQ\n"
            "    values[index] = calculate(2 + 3)\n"
        )

        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        root = program.statements[0]
        assert isinstance(root, SeqBlock)
        assignment = root.statements[0]
        assert isinstance(assignment, IndexAssign)
        assert isinstance(assignment.target, IndexExpr)
        assert isinstance(assignment.value, FuncCallExpr)
        self.assertEqual(assignment.value.name, "calculate")

    def test_logical_comparison_unary_and_modulo_precedence(self) -> None:
        program, diagnostics = parse(
            "SEQ\n"
            "    result = not ready or active and (count >= -7 % 3)\n"
        )

        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        root = program.statements[0]
        assert isinstance(root, SeqBlock)
        assignment = root.statements[0]
        assert isinstance(assignment, Assignment)
        expression = assignment.value
        assert isinstance(expression, BinaryExpr)
        self.assertEqual(expression.op, "or")
        assert isinstance(expression.left, UnaryExpr)
        self.assertEqual(expression.left.op, "not")
        assert isinstance(expression.right, BinaryExpr)
        self.assertEqual(expression.right.op, "and")
        grouped = expression.right.right
        assert isinstance(grouped, BinaryExpr)
        self.assertEqual(grouped.op, ">=")
        assert isinstance(grouped.right, BinaryExpr)
        self.assertEqual(grouped.right.op, "%")
        assert isinstance(grouped.right.left, UnaryExpr)
        self.assertEqual(grouped.right.left.op, "-")


class StatementParserTests(unittest.TestCase):
    def test_functions_factorial_and_fibonacci_parse_recursively(self) -> None:
        source = (
            "def factorial(n):\n"
            "    if n <= 1:\n"
            "        return 1\n"
            "    return n * factorial(n - 1)\n"
            "\n"
            "def fibonacci(n):\n"
            "    if n <= 1:\n"
            "        return n\n"
            "    return fibonacci(n - 1) + fibonacci(n - 2)\n"
            "\n"
            "SEQ\n"
            "    fact = factorial(5)\n"
            "    fib = fibonacci(8)\n"
        )

        program, diagnostics = parse(source)

        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        factorial = program.statements[0]
        fibonacci = program.statements[1]
        root = program.statements[2]
        assert isinstance(factorial, FuncDecl)
        assert isinstance(fibonacci, FuncDecl)
        assert isinstance(root, SeqBlock)
        self.assertEqual(factorial.name, "factorial")
        self.assertEqual(fibonacci.name, "fibonacci")

    def test_conditionals_and_loops_parse_into_their_ast_nodes(self) -> None:
        source = (
            "SEQ\n"
            "    if ready:\n"
            "        total = 0\n"
            "    else:\n"
            "        total = 1\n"
            "    while total < 3:\n"
            "        total += 1\n"
            "    for item in values:\n"
            "        print(item)\n"
        )

        program, diagnostics = parse(source)

        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        root = program.statements[0]
        assert isinstance(root, SeqBlock)
        statements = root.statements
        assert isinstance(statements[0], IfStmt)
        assert isinstance(statements[1], WhileStmt)
        assert isinstance(statements[2], ForStmt)
        self.assertIsNotNone(statements[0].else_branch)

    def test_parser_analyzes_complete_program_once_when_semantic_is_supplied(self) -> None:
        diagnostics = DiagnosticBag()
        semantic_analyzer = RecordingSemanticAnalyzer()
        lexer = Lexer("SEQ\n    x = 1\n", diagnostics)

        program = Parser(lexer, diagnostics).parse(
            semantic_analyzer=semantic_analyzer
        )

        self.assertEqual(semantic_analyzer.programs, [program])

    def test_parser_skips_semantic_pass_after_syntax_errors(self) -> None:
        diagnostics = DiagnosticBag()
        semantic_analyzer = RecordingSemanticAnalyzer()
        lexer = Lexer("SEQ\n    x =\n    y = 1\n", diagnostics)

        Parser(lexer, diagnostics).parse(semantic_analyzer=semantic_analyzer)

        self.assertTrue(diagnostics.has_errors)
        self.assertEqual(semantic_analyzer.programs, [])


class ParserRecoveryTests(unittest.TestCase):
    def test_reports_a_second_error_after_synchronizing_at_newline(self) -> None:
        source = "SEQ\n    first =\n    second =\n    valid = 3\n"

        program, diagnostics = parse(source)

        syntax_errors = [
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.phase == "syntax"
        ]
        self.assertEqual(len(syntax_errors), 2, diagnostics.format_text())
        self.assertEqual(
            [diagnostic.line for diagnostic in syntax_errors],
            [2, 3],
        )
        root = program.statements[0]
        assert isinstance(root, SeqBlock)
        self.assertEqual(len(root.statements), 1)
        statement = root.statements[0]
        assert isinstance(statement, Assignment)
        self.assertEqual(statement.name, "valid")


if __name__ == "__main__":
    unittest.main()
