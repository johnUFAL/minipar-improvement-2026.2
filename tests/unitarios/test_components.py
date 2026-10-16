import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

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
        self.assertEqual((tokens[0].line, tokens[0].col), (1, 1))
        self.assertEqual(tokens[-1].type, TokenType.END_OF_FILE)

    def test_semantic_analyzer_accepts_declared_variable(self):
        program = Parser(Lexer("var answer = 42; print(answer);").tokenize()).parse()
        self.assertTrue(SemanticAnalyzer().analyze(program))

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
