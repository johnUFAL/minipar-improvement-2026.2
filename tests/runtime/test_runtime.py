from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_TEST = Path(__file__).with_name("runtime_test.cpp")


class CppRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = os.environ.get("CXX", "g++").strip('"')
        compiler_path = shutil.which(compiler)
        if compiler_path is None:
            raise unittest.SkipTest(f"Compilador C++ nao encontrado: {compiler}")

        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.executable = Path(cls.temp_dir.name) / (
            "runtime_test.exe" if os.name == "nt" else "runtime_test"
        )
        result = subprocess.run(
            [
                compiler_path,
                "-std=c++20",
                str(RUNTIME_TEST),
                "-I",
                str(ROOT / "runtime"),
                "-o",
                str(cls.executable),
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise AssertionError(result.stderr.decode(errors="replace"))

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def test_builtins_and_utf8_output(self) -> None:
        result = subprocess.run(
            [str(self.executable)], capture_output=True, check=False
        )

        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(
            result.stdout.replace(b"\r\n", b"\n"),
            "Máquina de lavar\nLinha adicional\n".encode("utf-8"),
        )

    def test_invalid_array_index_exits_with_clear_error(self) -> None:
        result = subprocess.run(
            [str(self.executable), "bounds"], capture_output=True, check=False
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"indice 2 fora dos limites", result.stderr)

    def test_division_by_zero_exits_with_clear_error(self) -> None:
        result = subprocess.run(
            [str(self.executable), "division"], capture_output=True, check=False
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"divisao por zero", result.stderr)


if __name__ == "__main__":
    unittest.main()
