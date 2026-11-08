from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import run_testes_2026_2 as runner

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "programas_teste" / "t05_recomendacao.mp"
EXPECTED = (
    ROOT
    / "tests"
    / "integracao"
    / "expected_results"
    / "t05_recomendacao.expected.txt"
)
INPUTS = [
    "1", "0", "0", "0", "0", "1", "0", "0",
    "0", "1", "0", "0", "1", "0", "0", "0",
]
RECOMMENDATIONS = [
    "Laptop",
    "Tablet",
    "Fones de ouvido",
    "Camisa",
    "Jaqueta",
    "Sapatos",
    "Geladeira",
    "Máquina de lavar",
    "Ar condicionado",
    "Não-ficção",
    "Ficção científica",
    "Fantasia",
]
RECOMMENDATION_LINE = re.compile(
    r"^(.+) probabilidade:\s*"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)$",
    re.MULTILINE,
)
PROMPT_LINE = re.compile(r"^(.+) - comprou\? \(0/1\):$", re.MULTILINE)


class TestT05(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temp_dir.name)
        cls.executable = runner.build_program(SOURCE, cls.work, "O2")
        if not cls.executable.is_file():
            alternative = cls.executable.with_suffix(".exe")
            if alternative.is_file():
                cls.executable = alternative
        cls.stdout = cls._run()

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    @classmethod
    def _run(cls) -> str:
        result = subprocess.run(
            [str(cls.executable)],
            input=("\n".join(INPUTS) + "\n").encode("utf-8"),
            capture_output=True,
            check=False,
            cwd=str(cls.work),
            timeout=60,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr.decode("utf-8", errors="replace"))
        return result.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")

    def test_output_matches_golden_file(self) -> None:
        expected = EXPECTED.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(self.stdout, expected)

    def test_has_exactly_twelve_recommendations_in_order(self) -> None:
        found = RECOMMENDATION_LINE.findall(self.stdout)
        self.assertEqual([name for name, _ in found], RECOMMENDATIONS)
        self.assertEqual(len(found), 12)

    def test_accents_are_correct(self) -> None:
        self.assertNotIn("\ufffd", self.stdout)
        for wrong in (
            "Maquina de lavar",
            "Ficcao",
            "Nao-ficcao",
            "Ficcao cientifica",
        ):
            self.assertNotIn(wrong, self.stdout)
        for right in (
            "Máquina de lavar",
            "Ficção",
            "Não-ficção",
            "Ficção científica",
        ):
            self.assertIn(right, self.stdout)

    def test_reads_sixteen_product_prompts(self) -> None:
        prompts = PROMPT_LINE.findall(self.stdout)
        self.assertEqual(len(prompts), 16)
        self.assertEqual(prompts[0], "Smartphone")
        self.assertEqual(prompts[-1], "Fantasia")


if __name__ == "__main__":
    unittest.main()
