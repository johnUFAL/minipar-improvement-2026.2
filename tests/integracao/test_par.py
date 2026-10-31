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


if __name__ == "__main__":
    unittest.main()
