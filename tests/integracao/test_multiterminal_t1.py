from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class MultiterminalT1IntegrationTests(unittest.TestCase):
    def test_t1_server_and_client_exchange_messages(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "run_multiterminal.py"),
                "--operacao",
                "+",
                "--v1",
                "7",
                "--v2",
                "5",
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
        self.assertIn("Servidor recebeu: + 7.0 5.0", output)
        self.assertIn("Resultado: 12.0", output)


if __name__ == "__main__":
    unittest.main()
