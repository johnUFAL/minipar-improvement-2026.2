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

ROOT = Path(__file__).resolve().parents[2]
PROGRAMS = ROOT / "programas_teste"


def build_program(source_path: Path, work: Path, optimization: str = "O2") -> Path:
    source = source_path.read_text(encoding="utf-8")
    diagnostics = DiagnosticBag(source)
    program = Parser(Lexer(source, diagnostics), diagnostics).parse()
    SemanticAnalyzer(diagnostics).analyze(program)
    if diagnostics.has_errors:
        raise AssertionError(diagnostics.format_text())

    tac = TACGenerator().generate_text(program)
    cpp_path = work / (source_path.stem + ".cpp")
    cpp_path.write_text(CppCodeGenerator().generate_source(tac), encoding="utf-8")
    executable = work / source_path.stem
    if not DriverGCC().compile(cpp_path, executable, optimization):
        raise AssertionError(f"Falha ao compilar {source_path.name}")
    return executable


class TestesOitoANoveIntegracao(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = os.environ.get("CXX", "g++").strip('"')
        if shutil.which(compiler) is None:
            raise unittest.SkipTest(f"Compilador C++ nao encontrado: {compiler}")

    def _run(self, filename: str, expected: list[str]) -> str:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            executable = build_program(PROGRAMS / filename, work)
            result = subprocess.run(
                [str(executable)],
                capture_output=True,
                check=False,
                timeout=180,
            )
            stdout = result.stdout.decode("utf-8", errors="replace")
            stderr = result.stderr.decode("utf-8", errors="replace")
            self.assertEqual(result.returncode, 0, stderr)
            for text in expected:
                self.assertIn(text, stdout)
            return stdout

    def test_teste_8_avaliacao_em_quatro_nucleos(self) -> None:
        self._run(
            "t08_avaliacao_4_nucleos.mp",
            [
                "Total de Atividades a Avaliar: 160",
                "[Professor] Concluiu 160 atividades",
                "BENCHMARK DE DESEMPENHO",
                "Nucleos Utilizados (Paralelo) : 4",
            ],
        )

    def test_teste_9_cinco_nucleos_com_mandelbrot(self) -> None:
        self._run(
            "t09_5_nucleos_4_avaliadores_1_fractal.mp",
            [
                "FRACTAL DE MANDELBROT",
                "Nucleos Utilizados (Paralelo) : 5",
                "[Monitor 3] Concluiu 40 atividades",
            ],
        )

    def test_teste_10_seis_nucleos_com_dois_fractais(self) -> None:
        self._run(
            "t10_6_nucleos_avaliacao_2_fractais.mp",
            [
                "FRACTAL DE MANDELBROT",
                "TAPETE DE SIERPINSKI",
                "Nucleos Utilizados (Paralelo) : 6",
            ],
        )


class TesteOnzeIntegracao(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = os.environ.get("CXX", "g++").strip('"')
        if shutil.which(compiler) is None:
            raise unittest.SkipTest(f"Compilador C++ nao encontrado: {compiler}")

        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temp_dir.name)
        cls.executable = build_program(
            PROGRAMS / "t11_minicompilador_arm.mp", cls.work, "O0"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def test_minicompilador_gera_resultados_e_arquivos_arm(self) -> None:
        (self.work / "programas_teste" / "teste11").mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [str(self.executable)],
            cwd=self.work,
            capture_output=True,
            check=False,
            timeout=120,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")

        self.assertEqual(result.returncode, 0, stderr)
        self.assertIn("t1 = 2 + 4", stdout)
        self.assertIn("t4 = t2 - t3", stdout)
        self.assertIn("SUB    r8, r4, r7", stdout)
        self.assertEqual(stdout.count("➡️  22.0"), 2)
        self.assertIn("➡️  -84.0", stdout)
        self.assertIn("[NUMERO: '2']", stdout)

        for name in ("expr1.arm", "expr2.arm", "expr3.arm"):
            arm = (self.work / "programas_teste" / "teste11" / name).read_text(
                encoding="utf-8"
            )
            self.assertIn(".global _start", arm)
            self.assertIn(".text", arm)
            self.assertIn("_start:", arm)
            self.assertIn("b .", arm)

        expr1 = (self.work / "programas_teste" / "teste11" / "expr1.arm").read_text(
            encoding="utf-8"
        )
        self.assertIn("ADD    r2, r0, r1", expr1)
        self.assertIn("MUL    r4, r2, r3", expr1)
        self.assertIn("SUB    r8, r4, r7", expr1)

        expr2 = (self.work / "programas_teste" / "teste11" / "expr2.arm").read_text(
            encoding="utf-8"
        )
        self.assertIn("SUB    r4, r0, r3", expr2)
        self.assertIn("MUL    r8, r6, r7", expr2)

    def test_arm_files_assemble_for_armv7_when_clang_is_available(self) -> None:
        clang = shutil.which("clang")
        if clang is None:
            self.skipTest("clang nao encontrado")
        (self.work / "programas_teste" / "teste11").mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [str(self.executable)],
            cwd=self.work,
            capture_output=True,
            check=False,
            timeout=120,
        )
        for name in ("expr1.arm", "expr2.arm", "expr3.arm"):
            arm = self.work / "programas_teste" / "teste11" / name
            object_file = self.work / (name + ".o")
            result = subprocess.run(
                [
                    clang,
                    "--target=armv7-none-eabi",
                    "-x",
                    "assembler",
                    "-c",
                    str(arm),
                    "-o",
                    str(object_file),
                ],
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                result.stderr.decode("utf-8", errors="replace"),
            )
            self.assertTrue(object_file.is_file())


if __name__ == "__main__":
    unittest.main()
