from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_multiterminal.py"


class TestT01(unittest.TestCase):
    def test_calculator_all_operations_and_errors(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RUNNER), "--scenario", "all", "--timeout", "30"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=180,
        )
        output = result.stdout + result.stderr

        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Resultado: 42.0", output)  # + 12 30 e * 6 7
        self.assertIn("Resultado: 18.0", output)  # - 30 12
        self.assertIn("Resultado: 3.5", output)  # / 7 2
        self.assertIn("ERRO: divisao por zero", output)  # / 5 0
        self.assertIn("ERRO: operacao invalida", output)  # % 2 3
        self.assertIn("Servidor encerrando.", output)
        self.assertIn("Cliente encerrando.", output)
        self.assertEqual(output.count("Resultado: 42.0"), 3)
        self.assertIn("servidor recebeu todas as requisicoes", output)


if __name__ == "__main__":
    unittest.main()
