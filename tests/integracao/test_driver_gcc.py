from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from components.codegen import driver_gcc
from components.codegen.c_gerador_cpp import CppCodeGenerator
from components.lexico.c_lexico import Lexer
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser
from components.tac.c_gerador_tac import TACGenerator


ROOT = Path(__file__).resolve().parents[2]


class DriverGCCIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which(os.environ.get("CXX", "g++").strip('"')),
        "g++ is required for native channel code generation",
    )
    def test_declared_channel_generates_compilable_cpp(self) -> None:
        source = 'c_channel dados pc1 pc2\nSEQ\n    print("ok")\n'
        program = Parser(Lexer(source)).parse()
        analyzer = SemanticAnalyzer()
        self.assertTrue(analyzer.analyze(program), analyzer.diagnostics)
        tac = TACGenerator().generate_text(program)
        generated_cpp = CppCodeGenerator._generate_cpp(tac)

        with tempfile.TemporaryDirectory() as temp_dir:
            cpp_path = Path(temp_dir) / "channel.cpp"
            cpp_path.write_text(generated_cpp, encoding="utf-8")
            executable = Path(temp_dir) / "channel"
            self.assertTrue(
                driver_gcc.DriverGCC().compile(
                    cpp_path, executable, optimization_level="O0"
                )
            )

    def test_compiler_diagnostics_map_generated_cpp_to_minipar_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cpp_path = Path(temp_dir) / "broken.cpp"
            cpp_path.write_text(
                "int main() {\n"
                "    // MiniPar line 12\n"
                "    return unknown_symbol;\n"
                "}\n",
                encoding="utf-8",
            )
            compiler_error = (
                f"{cpp_path}:3:12: error: 'unknown_symbol' was not declared"
            )
            stderr = StringIO()
            with (
                patch.object(driver_gcc.shutil, "which", return_value="g++"),
                patch.object(
                    driver_gcc.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess(
                        args=[], returncode=1, stdout="", stderr=compiler_error
                    ),
                ),
                redirect_stderr(stderr),
            ):
                succeeded = driver_gcc.compilar(cpp_path, Path(temp_dir) / "broken")

        self.assertFalse(succeeded)
        self.assertIn("broken.mp:12:", stderr.getvalue())
        self.assertIn("(C++ gerado: linha 3)", stderr.getvalue())

    def test_compiler_uses_optimization_and_platform_flags(self) -> None:
        self.assertEqual(driver_gcc._platform_link_flags("linux", "posix"), ["-pthread"])
        self.assertEqual(driver_gcc._platform_link_flags("win32", "nt"), ["-lws2_32"])
        self.assertEqual(driver_gcc._platform_link_flags("darwin", "posix"), [])

        with tempfile.TemporaryDirectory() as temp_dir:
            cpp_path = Path(temp_dir) / "program.cpp"
            cpp_path.write_text("int main() { return 0; }\n", encoding="utf-8")
            output_path = Path(temp_dir) / "program"

            def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                Path(command[command.index("-o") + 1]).touch()
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            with (
                patch.object(driver_gcc.shutil, "which", return_value="g++"),
                patch.object(driver_gcc.subprocess, "run", side_effect=fake_run) as run,
                patch.object(driver_gcc.sys, "platform", "linux"),
            ):
                succeeded = driver_gcc.compilar(cpp_path, output_path, "O0")

        self.assertTrue(succeeded)
        command = run.call_args.args[0]
        self.assertIn("-std=c++17", command)
        self.assertIn("-O0", command)
        self.assertIn("-pthread", command)
        self.assertNotIn("-lws2_32", command)

    def test_invalid_optimization_level_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "O0, O1, O2 ou O3"):
            driver_gcc.compilar("program.cpp", "program", "O4")

    def test_execute_captures_stdout_and_exit_code(self) -> None:
        result = subprocess.CompletedProcess(
            args=["program"], returncode=7, stdout="program output\n", stderr=""
        )
        with patch.object(driver_gcc.subprocess, "run", return_value=result) as run:
            actual = driver_gcc.executar("program")

        self.assertEqual(actual.stdout, "program output\n")
        self.assertEqual(actual.returncode, 7)
        self.assertTrue(run.call_args.kwargs["capture_output"])
        self.assertTrue(run.call_args.kwargs["text"])

    @unittest.skipUnless(
        shutil.which(os.environ.get("CXX", "g++").strip('"')),
        "g++ is required for the native optimization integration test",
    )
    def test_test_7_compiles_and_runs_equally_with_o0_and_o3(self) -> None:
        source = (ROOT / "programas_teste" / "t07_quicksort_iterativo_tac.mp").read_text(
            encoding="utf-8"
        )
        program = Parser(Lexer(source)).parse()
        self.assertTrue(SemanticAnalyzer().analyze(program))
        tac = TACGenerator().generate_text(program)
        generated_cpp = CppCodeGenerator._generate_cpp(tac)
        expected = (
            ROOT
            / "tests"
            / "integracao"
            / "expected_results"
            / "t07_quicksort_iterativo_tac.expected.txt"
        ).read_text(encoding="utf-8").strip()
        outputs: list[str] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            cpp_path = Path(temp_dir) / "t07.cpp"
            cpp_path.write_text(generated_cpp, encoding="utf-8")
            driver = driver_gcc.DriverGCC()
            for level in ("O0", "O3"):
                executable = Path(temp_dir) / f"t07-{level}"
                self.assertTrue(
                    driver.compile(cpp_path, executable, optimization_level=level)
                )
                result = driver.executar(executable)
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append(result.stdout.strip())

        self.assertEqual(outputs, [expected, expected])


if __name__ == "__main__":
    unittest.main()
