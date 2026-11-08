from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from components.codegen.c_gerador_cpp import CppCodeGenerator
from components.codegen.driver_gcc import DriverGCC


class ParallelCodegenIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = os.environ.get("CXX", "g++").strip('"')
        if shutil.which(compiler) is None:
            raise unittest.SkipTest(f"Compilador C++ nao encontrado: {compiler}")

        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.executable = Path(cls.temp_dir.name) / (
            "parallel_error.exe" if os.name == "nt" else "parallel_error"
        )
        cpp_path = Path(cls.temp_dir.name) / "parallel_error.cpp"
        tac = """goto MAIN
MAIN:
counter:int = 0
par_begin 1
fork worker, simulated, 0, BRANCH
join worker
goto END
BRANCH:
counter:int = 10 / 0
join worker
END:
par_end
"""
        cpp_path.write_text(CppCodeGenerator._generate_cpp(tac), encoding="utf-8")
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as errors:
            compiled = DriverGCC().compilar(cpp_path, cls.executable, "O0")
        if not compiled:
            raise AssertionError(f"Falha ao compilar C++ de integracao:\n{errors.getvalue()}")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def test_branch_error_is_reported_by_generated_main(self) -> None:
        result = subprocess.run(
            [str(self.executable)],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Erro de execucao: divisao por zero.", result.stderr)

    @unittest.skipUnless(
        shutil.which(os.environ.get("CXX", "g++").strip('"')),
        "g++ is required for recursive parallel benchmark integration",
    )
    def test_t2_recursive_work_runs_with_overlapping_intervals(self) -> None:
        from scripts import run_multiterminal, run_testes_2026_2

        source = run_testes_2026_2.PROGRAMS / "t02_fatorial_fibonacci_par.mp"
        with tempfile.TemporaryDirectory() as directory:
            executable = run_multiterminal.build_program(source, Path(directory))
            for _ in range(20):
                result = subprocess.run(
                    [str(executable)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Fatorial de 10: 3628800", result.stdout)
                fibonacci_values = [
                    line.removeprefix("FIBONACCI ")
                    for line in result.stdout.splitlines()
                    if line.startswith("FIBONACCI ")
                    and not line.startswith("FIBONACCI_INICIO")
                    and not line.startswith("FIBONACCI_FIM")
                ]
                self.assertEqual(
                    fibonacci_values, ["0", "1", "1", "2", "3", "5", "8", "13", "21", "34"]
                )

                intervals: dict[str, dict[str, float]] = {
                    "FATORIAL": {},
                    "FIBONACCI": {},
                }
                for line in result.stdout.splitlines():
                    fields = line.split()
                    if len(fields) == 2 and fields[0] in (
                        "FATORIAL_INICIO",
                        "FATORIAL_FIM",
                        "FIBONACCI_INICIO",
                        "FIBONACCI_FIM",
                    ):
                        task, marker = fields[0].split("_")
                        intervals[task][marker] = float(fields[1])

                starts = [intervals[task]["INICIO"] for task in intervals]
                ends = [intervals[task]["FIM"] for task in intervals]
                self.assertLess(max(starts), min(ends), result.stdout)


if __name__ == "__main__":
    unittest.main()
