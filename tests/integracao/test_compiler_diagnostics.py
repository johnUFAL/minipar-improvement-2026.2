from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from components.controle.c_controle import compile_file
from erros.diagnosticos import DiagnosticBag


class CompilerDiagnosticsIntegrationTests(unittest.TestCase):
    def test_compiler_collects_lexical_syntax_and_semantic_errors(self) -> None:
        source = (
            "var good = 0;\n"
            "var broken = @;\n"
            "print(2;\n"
            "var good = 3;\n"
            "print(missing);\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "invalid.mp"
            source_path.write_text(source, encoding="utf-8")
            diagnostics = DiagnosticBag(source)

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                succeeded = compile_file(source_path, "invalid", diagnostics)

        self.assertFalse(succeeded)
        self.assertGreaterEqual(len(diagnostics), 4)
        self.assertTrue(diagnostics.has_errors)
        rendered = diagnostics.format_text()
        self.assertIn("erro léxico [2:14]", rendered)
        self.assertIn("erro sintático", rendered)
        self.assertIn("erro semântico [4]", rendered)
        self.assertIn("erro semântico [5]", rendered)
        self.assertIn("^", rendered)

        serialized = diagnostics.to_dict()
        self.assertTrue(serialized["has_errors"])
        self.assertGreaterEqual(len(serialized["diagnostics"]), 4)
        self.assertTrue(
            all(item["source_line"] is not None for item in serialized["diagnostics"])
        )


if __name__ == "__main__":
    unittest.main()
