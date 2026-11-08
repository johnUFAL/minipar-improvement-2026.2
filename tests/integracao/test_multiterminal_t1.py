from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class MultiterminalT1IntegrationTests(unittest.TestCase):
    def _run_t1(self, operation: str, value1: str, value2: str) -> str:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "run_multiterminal.py"),
                "--operacao",
                operation,
                "--v1",
                value1,
                "--v2",
                value2,
                "--timeout",
                "20",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=120,
        )

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        return output

    def test_t1_client_and_server_add(self) -> None:
        output = self._run_t1("+", "12", "30")
        self.assertIn("Servidor recebeu: + 12.0 30.0", output)
        self.assertIn("Resultado: 42.0", output)

    def test_t1_division_by_zero_returns_error_without_crashing_server(self) -> None:
        output = self._run_t1("/", "5", "0")
        self.assertIn("Erro: divisao por zero.", output)
        self.assertIn("servidor retornou 0", output)

    def test_t1_division_uses_fractional_semantics(self) -> None:
        output = self._run_t1("/", "7", "2")
        self.assertIn("Resultado: 3.5", output)


if __name__ == "__main__":
    unittest.main()
