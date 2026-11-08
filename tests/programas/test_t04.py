from __future__ import annotations

import math
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import run_testes_2026_2 as runner

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "programas_teste" / "t04_rede_neural_xor.mp"
PREDICTION = re.compile(
    r"Input: \[(\d), (\d)\], Predicted Output:\s*"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
)


class TestT04(unittest.TestCase):
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

    def test_xor_outputs_are_in_expected_ranges(self) -> None:
        result = subprocess.run(
            [str(self.executable)],
            cwd=str(self.work),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=60,
        )
        stdout = result.stdout
        self.assertEqual(result.returncode, 0, result.stderr)

        predictions = {
            (int(x1), int(x2)): float(value)
            for x1, x2, value in PREDICTION.findall(stdout)
        }
        self.assertEqual(
            set(predictions),
            {(0, 0), (0, 1), (1, 0), (1, 1)},
            stdout,
        )

        self.assertLess(predictions[(0, 0)], 0.1, stdout)
        self.assertGreater(predictions[(0, 1)], 0.9, stdout)
        self.assertGreater(predictions[(1, 0)], 0.9, stdout)
        self.assertLess(predictions[(1, 1)], 0.1, stdout)

        for value in predictions.values():
            self.assertTrue(math.isfinite(value))
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)


if __name__ == "__main__":
    unittest.main()
