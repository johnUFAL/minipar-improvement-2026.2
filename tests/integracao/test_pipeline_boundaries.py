from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from components.codegen.c_gerador_cpp import CppCodeGenerator
from components.codegen.driver_gcc import DriverGCC
from components.lexico.c_lexico import Lexer
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser
from components.tac.c_gerador_tac import TACGenerator
from erros.diagnosticos import DiagnosticBag


class PipelineBoundaryIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which(os.environ.get("CXX", "g++").strip('"')),
        "g++ is required for end-to-end component boundary tests",
    )
    def test_source_crosses_frontend_tac_codegen_and_native_runtime(self) -> None:
        source = "SEQ\n    var total = 20 + 22\n    print(total)\n"
        diagnostics = DiagnosticBag(source)
        tokens = Lexer(source, diagnostics).tokenize()
        self.assertTrue(tokens)

        program = Parser(Lexer(source, diagnostics), diagnostics).parse()
        self.assertTrue(SemanticAnalyzer(diagnostics).analyze(program))
        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())

        tac = TACGenerator().generate_text(program)
        self.assertIn("print", tac)
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


if __name__ == "__main__":
    unittest.main()
