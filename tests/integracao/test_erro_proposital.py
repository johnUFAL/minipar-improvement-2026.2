from __future__ import annotations

import unittest
from pathlib import Path

from interfaces.web.api import app

ROOT = Path(__file__).resolve().parents[2]


class ErroPropositalInterfaceTests(unittest.TestCase):
    def test_fibonacci_error_keeps_tokens_and_ast_but_reports_diagnostic(self) -> None:
        source = (ROOT / "programas_teste" / "t02_fibonacci_erro_proposital.mp").read_text(
            encoding="utf-8"
        )
        client = app.test_client()

        response = client.post("/api/compilar", json={"code": source})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertFalse(result["success"])
        self.assertTrue(result["tokens"])
        self.assertEqual(result["ast"]["tipo"], "Program")
        self.assertEqual(result["tac"], "")
        self.assertEqual(result["cpp"], "")
        self.assertTrue(
            any(
                diagnostic["line"] == 35
                and "Tipo incompativel" in diagnostic["message"]
                for diagnostic in result["diagnosticos"]
            ),
            result["diagnosticos"],
        )


if __name__ == "__main__":
    unittest.main()
