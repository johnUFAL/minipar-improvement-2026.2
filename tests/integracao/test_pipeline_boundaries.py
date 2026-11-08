from __future__ import annotations

import os
import shutil
import tempfile
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from components.codegen.c_gerador_cpp import CppCodeGenerator
from components.codegen.driver_gcc import DriverGCC
from components.controle.c_controle import compile_file
from components.lexico.c_lexico import Lexer
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser
from components.tac.c_gerador_tac import TACGenerator
from erros.diagnosticos import DiagnosticBag

ROOT = Path(__file__).resolve().parents[2]
INVALIDOS = ROOT / "tests" / "programas" / "invalidos"
ACCEPTANCE = (
    "t02_fatorial_fibonacci_par.mp",
    "t03_neuronio.mp",
    "t04_rede_neural_xor.mp",
    "t05_recomendacao.mp",
    "t06_quicksort_classes.mp",
    "t07_quicksort_iterativo_tac.mp",
)
GCC_AVAILABLE = shutil.which(os.environ.get("CXX", "g++").strip('"')) is not None


def _frontend(source: str):
    diagnostics = DiagnosticBag(source)
    program = Parser(Lexer(source, diagnostics), diagnostics).parse()
    SemanticAnalyzer(diagnostics).analyze(program)
    return program, diagnostics


class PipelineBoundaryIntegrationTests(unittest.TestCase):
    def _invalid(self, name: str) -> str:
        return (INVALIDOS / name).read_text(encoding="utf-8")

    def test_lexer_to_parser_positive(self) -> None:
        source = "SEQ\n    var total = 20 + 22\n    print(total)\n"
        diagnostics = DiagnosticBag(source)
        tokens = Lexer(source, diagnostics).tokenize()
        self.assertTrue(tokens)

        program = Parser(Lexer(source, diagnostics), diagnostics).parse()

        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        self.assertTrue(program.statements)

    def test_lexer_to_parser_negative(self) -> None:
        source = self._invalid("01_caractere_invalido.mp")
        diagnostics = DiagnosticBag(source)

        Parser(Lexer(source, diagnostics), diagnostics).parse()

        self.assertTrue(diagnostics.has_errors)
        self.assertIn("caractere inválido", diagnostics.format_text())

    def test_parser_to_semantic_positive(self) -> None:
        source = "SEQ\n    var total: int = 20 + 22\n    print(total)\n"

        program, diagnostics = _frontend(source)

        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        self.assertTrue(program.statements)

    def test_parser_to_semantic_negative(self) -> None:
        source = self._invalid("04_variavel_nao_declarada.mp")

        _, diagnostics = _frontend(source)

        self.assertTrue(diagnostics.has_errors)
        self.assertIn("nao declarada", diagnostics.format_text())

    def test_semantic_to_tac_positive(self) -> None:
        source = "SEQ\n    var total = 20 + 22\n    print(total)\n"
        program, diagnostics = _frontend(source)
        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())

        tac = TACGenerator().generate_text(program)

        self.assertIn("print", tac)
        self.assertIn("20 + 22", tac)

    def test_semantic_to_tac_negative_stops_before_tac(self) -> None:
        source = self._invalid("05_tipo_incompativel.mp")
        output_name = f"pipeline_invalido_{uuid.uuid4().hex}"
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "invalido.mp"
            source_path.write_text(source, encoding="utf-8")
            diagnostics = DiagnosticBag(source)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                succeeded = compile_file(source_path, output_name, diagnostics)

        self.assertFalse(succeeded)
        self.assertTrue(diagnostics.has_errors)
        self.assertFalse((ROOT / "output" / f"{output_name}.tac").exists())

    def test_tac_to_cpp_positive(self) -> None:
        source = "SEQ\n    var total = 20 + 22\n    print(total)\n"
        program, diagnostics = _frontend(source)
        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        tac = TACGenerator().generate_text(program)

        cpp = CppCodeGenerator().generate_source(tac)

        self.assertIn("int main", cpp)
        self.assertIn("minipar_print", cpp)

    def test_tac_to_cpp_negative(self) -> None:
        with self.assertRaises(ValueError) as context:
            CppCodeGenerator._generate_cpp("goto MAIN\nMAIN:\nfoobar x\n")

        self.assertIn(
            "Instrucao TAC nao suportada pelo codegen",
            str(context.exception),
        )

    @unittest.skipUnless(GCC_AVAILABLE, "g++ is required for boundary tests")
    def test_cpp_to_gcc_positive(self) -> None:
        source = "SEQ\n    var total = 20 + 22\n    print(total)\n"
        program, diagnostics = _frontend(source)
        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        tac = TACGenerator().generate_text(program)
        cpp = CppCodeGenerator().generate_source(tac)

        with tempfile.TemporaryDirectory() as temp_dir:
            cpp_path = Path(temp_dir) / "pipeline.cpp"
            cpp_path.write_text(cpp, encoding="utf-8")
            executable = Path(temp_dir) / "pipeline"
            self.assertTrue(
                DriverGCC().compile(cpp_path, executable, optimization_level="O0")
            )
            result = DriverGCC().executar(executable)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "42")

    @unittest.skipUnless(GCC_AVAILABLE, "g++ is required for boundary tests")
    def test_cpp_to_gcc_negative(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cpp_path = Path(temp_dir) / "broken.cpp"
            cpp_path.write_text(
                "int main() { return missing; }\n", encoding="utf-8"
            )
            executable = Path(temp_dir) / "broken"
            errors = StringIO()
            with redirect_stderr(errors):
                compiled = DriverGCC().compile(
                    cpp_path, executable, optimization_level="O0"
                )

        self.assertFalse(compiled)
        self.assertIn("error", errors.getvalue().lower())

    def test_acceptance_programs_cross_frontend_tac_and_codegen(self) -> None:
        for name in ACCEPTANCE:
            with self.subTest(program=name):
                source = (ROOT / "programas_teste" / name).read_text(
                    encoding="utf-8"
                )
                program, diagnostics = _frontend(source)
                self.assertFalse(
                    diagnostics.has_errors, diagnostics.format_text()
                )
                tac = TACGenerator().generate_text(program)
                self.assertTrue(tac.strip())
                cpp = CppCodeGenerator().generate_source(tac)
                self.assertIn("int main", cpp)

    @unittest.skipUnless(GCC_AVAILABLE, "g++ is required for boundary tests")
    def test_representative_program_runs_end_to_end(self) -> None:
        source = (
            ROOT / "programas_teste" / "t07_quicksort_iterativo_tac.mp"
        ).read_text(encoding="utf-8")
        program, diagnostics = _frontend(source)
        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        tac = TACGenerator().generate_text(program)
        cpp = CppCodeGenerator().generate_source(tac)

        with tempfile.TemporaryDirectory() as temp_dir:
            cpp_path = Path(temp_dir) / "t07.cpp"
            cpp_path.write_text(cpp, encoding="utf-8")
            executable = Path(temp_dir) / "t07"
            self.assertTrue(
                DriverGCC().compile(cpp_path, executable, optimization_level="O0")
            )
            result = DriverGCC().executar(executable)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Array ordenado: [5, 12, 33, 61, 98]", result.stdout)


if __name__ == "__main__":
    unittest.main()
