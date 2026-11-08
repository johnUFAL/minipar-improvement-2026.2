from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import run_testes_2026_2 as runner

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "programas_teste" / "t03_neuronio.mp"
EXPECTED = (
    ROOT
    / "tests"
    / "integracao"
    / "expected_results"
    / "t03_neuronio.expected.txt"
)


def parse_blocks(text: str) -> dict[int, list[str]]:
    blocks: dict[int, list[str]] = {}
    current: int | None = None
    for line in text.splitlines():
        match = re.fullmatch(r"#### Iteração: (\d+)", line)
        if match:
            current = int(match.group(1))
            blocks[current] = [line]
            continue
        if current is None:
            continue
        if line.startswith("✅") or line.startswith("Valor desejado:"):
            current = None
            continue
        blocks[current].append(line)
    return blocks


class TestT03(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temp_dir.name)
        cls.executable = runner.build_program(SOURCE, cls.work, "O2")
        if not cls.executable.is_file():
            alternative = cls.executable.with_suffix(".exe")
            if alternative.is_file():
                cls.executable = alternative
        cls.expected = parse_blocks(EXPECTED.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def test_convergencia_formato_e_blocos_do_pdf(self) -> None:
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

        self.assertIn("Entrada: 1 | Saída desejada: 0", stdout)
        self.assertEqual(stdout.count("#### Iteração:"), 51)
        self.assertIn("✅ Parabéns! O neurônio aprendeu.", stdout)
        self.assertIn("Valor desejado: 0", stdout)

        blocks = parse_blocks(stdout)
        for number in (1, 2, 3, 4, 49, 50, 51):
            self.assertIn(number, blocks, f"bloco {number} ausente")
            self.assertEqual(
                blocks[number],
                self.expected[number],
                f"bloco {number} diferente do PDF",
            )

        for old_label in (
            "Iteracao:",
            "Soma ponderada:",
            "Peso entrada:",
            "Peso bias:",
            "Neuronio aprendeu dinamicamente.",
        ):
            self.assertNotIn(old_label, stdout)


if __name__ == "__main__":
    unittest.main()
