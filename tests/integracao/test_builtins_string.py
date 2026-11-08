from __future__ import annotations

import os
import shutil
import subprocess
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


PROGRAM = """\
seq {
    var texto = "MiniPar 2026.2"
    var primeira = char_at(texto, 0)
    var segunda = texto[1]
    var pedaco = substring(texto, 0, 7)
    var digito = '7'
    var letra = 'M'
    var espaco = ' '
    var numero = is_number("123.5")
    var nao_numero = is_number("12a")
    var pedacos = dividir("10 -3 40")
    var inteiro = eh_inteiro("-42")
    var nao_inteiro = eh_inteiro("4.2")

    print("primeira:", primeira)
    print("segunda:", segunda)
    print("pedaco:", pedaco)
    print("digito:", is_digit(digito))
    print("letra:", is_alpha(letra))
    print("espaco:", is_space(espaco))
    print("numero:", numero, nao_numero)
    print("pedacos:", pedacos)
    print("inteiro:", inteiro, nao_inteiro)

    var status = write_file("builtins_teste.txt", texto + "|" + pedaco)
    print("write_file:", status)
}
"""


class BuiltinsStringIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = os.environ.get("CXX", "g++").strip('"')
        if shutil.which(compiler) is None:
            raise unittest.SkipTest(f"Compilador C++ nao encontrado: {compiler}")

        cls.temp_dir = tempfile.TemporaryDirectory()
        work = Path(cls.temp_dir.name)
        cls.arquivo = work / "builtins_teste.txt"
        source = PROGRAM

        diagnostics = DiagnosticBag(source)
        lexer = Lexer(source, diagnostics)
        program = Parser(lexer, diagnostics).parse()
        SemanticAnalyzer(diagnostics).analyze(program)
        if diagnostics.has_errors:
            raise AssertionError(diagnostics.format_text())

        tac = TACGenerator().generate_text(program)
        cpp_path = work / "builtins.cpp"
        cpp_path.write_text(CppCodeGenerator().generate_source(tac), encoding="utf-8")
        cls.executable = work / "builtins.exe"
        if not DriverGCC().compile(cpp_path, cls.executable, "O2"):
            raise AssertionError("Falha ao compilar o programa de builtins de string")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def test_builtins_execute_and_write_file(self) -> None:
        result = subprocess.run(
            [str(self.executable)],
            capture_output=True,
            check=False,
            text=True,
            timeout=120,
            cwd=Path(self.temp_dir.name),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("primeira: M", result.stdout)
        self.assertIn("segunda: i", result.stdout)
        self.assertIn("pedaco: MiniPar", result.stdout)
        self.assertIn("digito: 1", result.stdout)
        self.assertIn("letra: 1", result.stdout)
        self.assertIn("espaco: 1", result.stdout)
        self.assertIn("numero: 1 0", result.stdout)
        self.assertIn("pedacos: [10, -3, 40]", result.stdout)
        self.assertIn("inteiro: 1 0", result.stdout)
        self.assertIn("write_file: 0", result.stdout)
        self.assertTrue(self.arquivo.exists())
        self.assertEqual(
            self.arquivo.read_text(encoding="utf-8"), "MiniPar 2026.2|MiniPar"
        )


if __name__ == "__main__":
    unittest.main()
