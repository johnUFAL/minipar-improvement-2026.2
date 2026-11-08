from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import run_testes_2026_2 as runner

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "programas_teste" / "t02_fatorial_fibonacci_par.mp"
FIBONACCI_EXPECTED = ["0", "1", "1", "2", "3", "5", "8", "13", "21", "34"]
FLOAT = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"


class TestT02(unittest.TestCase):
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

    def _run_once(self) -> str:
        result = subprocess.run(
            [str(self.executable)],
            cwd=str(self.work),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def _marker(self, stdout: str, name: str) -> float:
        match = re.search(rf"^{name}\s+{FLOAT}$", stdout, re.MULTILINE)
        self.assertIsNotNone(match, f"Marcador {name} ausente:\n{stdout}")
        assert match is not None
        return float(match.group(1))

    def test_recursive_values_and_overlap_20_times(self) -> None:
        for run in range(1, 21):
            stdout = self._run_once()
            self.assertIn("Fatorial de 10: 3628800", stdout, f"execucao {run}")
            fibonacci = re.findall(r"^FIBONACCI\s+(\d+)$", stdout, re.MULTILINE)
            self.assertEqual(fibonacci, FIBONACCI_EXPECTED, f"execucao {run}")

            fat_inicio = self._marker(stdout, "FATORIAL_INICIO")
            fat_fim = self._marker(stdout, "FATORIAL_FIM")
            fib_inicio = self._marker(stdout, "FIBONACCI_INICIO")
            fib_fim = self._marker(stdout, "FIBONACCI_FIM")

            inicio_comum = max(fat_inicio, fib_inicio)
            fim_comum = min(fat_fim, fib_fim)
            self.assertLess(
                inicio_comum,
                fim_comum,
                f"sem sobreposicao na execucao {run}:\n{stdout}",
            )


if __name__ == "__main__":
    unittest.main()
