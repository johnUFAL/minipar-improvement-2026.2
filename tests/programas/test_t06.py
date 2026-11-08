from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import run_testes_2026_2 as runner

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "programas_teste" / "t06_quicksort_classes.mp"
EXPECTED = (
    ROOT
    / "tests"
    / "integracao"
    / "expected_results"
    / "t06_quicksort_classes.expected.txt"
)


class TestT06(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temp_dir.name)
        cls.executable = runner.build_program(SOURCE, cls.work, "O2")
        if not cls.executable.is_file():
            alternative = cls.executable.with_suffix(".exe")
            if alternative.is_file():
                cls.executable = alternative

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def _run(self, stdin: str) -> str:
        result = subprocess.run(
            [str(self.executable)],
            input=stdin.encode("utf-8"),
            capture_output=True,
            check=False,
            cwd=str(self.work),
            timeout=60,
        )
        self.assertEqual(
            result.returncode,
            0,
            result.stderr.decode("utf-8", errors="replace"),
        )
        return result.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")

    def _sorted_line(self, stdout: str) -> str:
        matches = re.findall(
            r"^Vetor ordenado: (\[.*\])$", stdout, re.MULTILINE
        )
        self.assertTrue(matches, stdout)
        return matches[-1]

    def test_pdf_input_matches_golden_file(self) -> None:
        stdout = self._run("10 -3 -40 80 70 -100\n")
        expected = EXPECTED.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(stdout, expected)

    def test_invalid_token_reprompts_and_then_sorts(self) -> None:
        stdout = self._run("1 a 3\n10 -3 -40 80 70 -100\n")
        self.assertIn("Entrada invalida", stdout)
        self.assertEqual(stdout.count("Entrada invalida"), 1)
        self.assertEqual(self._sorted_line(stdout), "[-100, -40, -3, 10, 70, 80]")
        self.assertNotIn("Traceback", stdout)

    def test_empty_input_reprompts_and_single_value_is_sorted(self) -> None:
        stdout = self._run("\n5\n")
        self.assertIn("Entrada invalida", stdout)
        self.assertEqual(self._sorted_line(stdout), "[5]")

    def test_single_element_vector(self) -> None:
        stdout = self._run("7\n")
        self.assertNotIn("Entrada invalida", stdout)
        self.assertEqual(self._sorted_line(stdout), "[7]")

    def test_negative_and_zero_values(self) -> None:
        stdout = self._run("-5 0 5\n")
        self.assertEqual(self._sorted_line(stdout), "[-5, 0, 5]")

    def test_float_token_is_rejected(self) -> None:
        stdout = self._run("1.5 2\n3 2 1\n")
        self.assertIn("Entrada invalida", stdout)
        self.assertEqual(self._sorted_line(stdout), "[1, 2, 3]")


if __name__ == "__main__":
    unittest.main()
