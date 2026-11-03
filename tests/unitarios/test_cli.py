from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from components.codegen.driver_gcc import DriverGCC
from interfaces.command_line import run
import main as legacy_main


ROOT = Path(__file__).resolve().parents[2]
VALID_SOURCE = "SEQ\n    print(1)\n"


class CommandLineTests(unittest.TestCase):
    def _source(self, directory: str, source: str = VALID_SOURCE) -> Path:
        path = Path(directory) / "program.mp"
        path.write_text(source, encoding="utf-8")
        return path

    def test_tac_prints_output_without_compiling_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = self._source(temp_dir)
            output = Path(temp_dir) / "program"
            stdout = StringIO()
            with patch.object(DriverGCC, "compile") as compile_program:
                with redirect_stdout(stdout), redirect_stderr(StringIO()):
                    result = run(
                        ["compilar", str(source), "--tac", "-o", str(output)]
                    )

            self.assertEqual(result, 0)
            self.assertIn("print", stdout.getvalue())
            self.assertTrue(output.with_suffix(".tac").is_file())
            self.assertFalse(output.with_suffix(".cpp").exists())
            self.assertFalse(output.with_suffix(".exe").exists())
            compile_program.assert_not_called()

    def test_build_options_are_passed_to_driver(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = self._source(temp_dir)
            output = Path(temp_dir) / "compiled"
            with patch.object(DriverGCC, "compile", return_value=True) as compile_program:
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    result = run(
                        ["compilar", str(source), "-O2", "-o", str(output)]
                    )

            self.assertEqual(result, 0)
            self.assertEqual(
                compile_program.call_args.args,
                (output.with_suffix(".cpp"), output, "O2"),
            )
            self.assertTrue(output.with_suffix(".cpp").is_file())

    def test_execute_option_runs_compiled_program_and_returns_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = self._source(temp_dir)
            output = Path(temp_dir) / "compiled"
            completed = subprocess.CompletedProcess(
                args=["compiled"], returncode=0, stdout="ok\n", stderr=""
            )
            with (
                patch.object(DriverGCC, "compile", return_value=True),
                patch.object(DriverGCC, "executar", return_value=completed) as execute,
                redirect_stdout(StringIO()) as stdout,
                redirect_stderr(StringIO()),
            ):
                result = run(
                    ["compilar", str(source), "-o", str(output), "--executar"]
                )

            self.assertEqual(result, 0)
            self.assertEqual(stdout.getvalue(), "ok\n")
            execute.assert_called_once_with(output)

    def test_program_failure_uses_execution_phase_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = self._source(temp_dir)
            completed = subprocess.CompletedProcess(
                args=["compiled"], returncode=1, stdout="", stderr="runtime failure\n"
            )
            with (
                patch.object(DriverGCC, "compile", return_value=True),
                patch.object(DriverGCC, "executar", return_value=completed),
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                result = run(["run", str(source)])

        self.assertEqual(result, 7)

    def test_no_arguments_still_starts_legacy_terminal_menu(self) -> None:
        with (
            patch.object(legacy_main, "start_interactive") as start_interactive,
            patch.object(legacy_main.sys, "argv", ["main.py"]),
        ):
            result = legacy_main.main()

        self.assertEqual(result, 0)
        start_interactive.assert_called_once_with()

    def test_each_frontend_phase_has_a_distinct_exit_code(self) -> None:
        invalid_sources = (
            ("SEQ\n    print(@)\n", 2),
            ("SEQ\n    print(1 2)\n", 3),
            ("SEQ\n    print(missing)\n", 4),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            for index, (source_text, expected_code) in enumerate(invalid_sources):
                source = Path(temp_dir) / f"invalid-{index}.mp"
                source.write_text(source_text, encoding="utf-8")
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    result = run(["compilar", str(source)])
                self.assertEqual(result, expected_code)

    def test_cli_executes_test_7_and_matches_expected_output(self) -> None:
        compiler = os.environ.get("CXX", "g++").strip('"')
        if shutil.which(compiler) is None:
            self.skipTest("g++ is required for the CLI integration test")
        source = ROOT / "programas_teste" / "t07_quicksort_iterativo_tac.mp"
        expected = (
            ROOT
            / "tests"
            / "integracao"
            / "expected_results"
            / "t07_quicksort_iterativo_tac.expected.txt"
        ).read_text(encoding="utf-8").strip()
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "t07"
            stdout = StringIO()
            with redirect_stdout(stdout), redirect_stderr(StringIO()):
                result = run(
                    ["run", str(source), "-O2", "-o", str(output)]
                )

        self.assertEqual(result, 0)
        self.assertTrue(stdout.getvalue().strip().endswith(expected))


if __name__ == "__main__":
    unittest.main()
