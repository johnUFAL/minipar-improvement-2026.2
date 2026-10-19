import unittest
from contextlib import redirect_stderr
from dataclasses import FrozenInstanceError
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import components.sintatico.ast as ast_module
from components.codegen.driver_gcc import DriverGCC
from components.lexico.c_lexico import Lexer
from components.lexico.token import TokenType
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser
from components.tac.c_gerador_tac import TACGenerator
from components.tac.executor_tac import TACExecutor


class ComponentTests(unittest.TestCase):
    def test_lexer_preserves_token_position(self):
        tokens = Lexer("var total = 12;").tokenize()
        self.assertEqual(tokens[0].type, TokenType.VAR)
        self.assertEqual((tokens[0].line, tokens[0].column), (1, 1))
        self.assertEqual(tokens[-1].type, TokenType.END_OF_FILE)

    def test_semantic_analyzer_accepts_declared_variable(self):
        program = Parser(Lexer("var answer = 42; print(answer);").tokenize()).parse()
        self.assertTrue(SemanticAnalyzer().analyze(program))

    def test_ast_nodes_and_collections_are_immutable(self):
        program = Parser(
            Lexer("seq { var values = [1, 2]; print(values); }").tokenize()
        ).parse()
        block = program.statements[0]
        declaration = block.statements[0]
        literal = declaration.init_value

        with self.assertRaises(FrozenInstanceError):
            program.statements = ()  # type: ignore[misc]
        with self.assertRaises(AttributeError):
            block.statements.append(declaration)  # type: ignore[attr-defined]
        with self.assertRaises(AttributeError):
            literal.elements.append(literal.elements[0])  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            literal.elements[0].value = "changed"  # type: ignore[misc]

    def test_every_ast_dataclass_is_frozen(self):
        ast_types = [
            value
            for value in vars(ast_module).values()
            if isinstance(value, type)
            and getattr(value, "__module__", None) == ast_module.__name__
        ]
        ast_node_types = [
            ast_type
            for ast_type in ast_types
            if issubclass(ast_type, ast_module.ASTNode)
        ]
        self.assertTrue(ast_node_types)
        self.assertTrue(
            all(ast_type.__dataclass_params__.frozen for ast_type in ast_node_types)
        )

    def test_tac_executor_runs_assignments_and_branches(self):
        program = """count = 0
LOOP:
count = count + 1
ifFalse count < 3 goto END
print count
goto LOOP
END:
"""
        variables, output = TACExecutor().execute(program)
        self.assertEqual(variables["count"], 3)
        self.assertEqual(output, ["1", "2"])

    def test_quicksort_tac_matches_existing_golden_file(self):
        root = Path(__file__).resolve().parents[2]
        source_path = root / "programas_teste" / "t07_quicksort_iterativo_tac.mp"
        expected_path = (
            root
            / "tests"
            / "integracao"
            / "expected_results"
            / "t07_quicksort_iterativo_tac.expected.tac"
        )
        program = Parser(
            Lexer(source_path.read_text(encoding="utf-8")).tokenize()
        ).parse()
        self.assertEqual(
            TACGenerator().generate_text(program),
            expected_path.read_text(encoding="utf-8"),
        )

    @patch("components.codegen.driver_gcc.shutil.which", return_value=None)
    def test_missing_cpp_compiler_fails_without_traceback(self, _which):
        stderr = StringIO()
        with redirect_stderr(stderr):
            result = DriverGCC().compile("program.cpp")
        self.assertFalse(result)
        self.assertIn("Compilador C++", stderr.getvalue())
        self.assertIn("nao encontrado", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
