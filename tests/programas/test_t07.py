from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from components.lexico import Lexer
from components.sintatico.c_sintatico import Parser
from components.tac import TACExecutor, TACGenerator
from scripts import run_testes_2026_2 as runner

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "programas_teste" / "t07_quicksort_iterativo_tac.mp"
EXPECTED = (
    ROOT
    / "tests"
    / "integracao"
    / "expected_results"
    / "t07_quicksort_iterativo_tac.expected.txt"
)
REFERENCE_TAC = (
    ROOT
    / "tests"
    / "integracao"
    / "expected_results"
    / "t07_quicksort_iterativo_tac.expected.tac"
)
SORTED = "Array ordenado: [5, 12, 33, 61, 98]"


def parse(source: str):
    return Parser(Lexer(source)).parse()


class TestT07(unittest.TestCase):
    """Aceitacao do T7: fonte -> TAC -> executavel.

    O TAC do PDF usa os rotulos ``LOOP``, ``PARTITION_LOOP``, ``SWAP``,
    ``PARTITION_END`` e ``END``. O gerador atual emite rotulos genericos
    (``WHILE_n``/``ENDWHILE_m``) e o ``SWAP`` fica inline no ``if`` de troca.
    A comparacao com o PDF e por equivalencia de execucao, conforme a #17.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.tac = TACGenerator().generate_text(parse(cls.source))
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

    def _run_binary(self) -> str:
        result = subprocess.run(
            [str(self.executable)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            cwd=str(self.work),
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.replace("\r\n", "\n").strip()

    def test_binary_output_matches_golden_file(self) -> None:
        expected = EXPECTED.read_text(encoding="utf-8").strip()
        self.assertEqual(self._run_binary(), expected)

    def test_tac_executor_sorts_the_array(self) -> None:
        variables, output = TACExecutor().execute(self.tac)

        self.assertEqual(variables["ordenado"], [5, 12, 33, 61, 98])
        self.assertEqual(output[-1], SORTED)

    def test_tac_and_binary_agree(self) -> None:
        _, output = TACExecutor().execute(self.tac)

        self.assertEqual(output[-1], self._run_binary().splitlines()[-1])

    def test_generated_tac_has_loop_partition_and_end_labels(self) -> None:
        while_labels = re.findall(r"(?m)^WHILE_\d+:$", self.tac)

        self.assertGreaterEqual(len(while_labels), 2)
        self.assertRegex(self.tac, r"(?m)^ENDWHILE_\d+:$")
        self.assertIn("stack[sp] =", self.tac)
        self.assertRegex(self.tac, r"(?m)^t\d+:int = sp \+ 1$")
        self.assertRegex(self.tac, r"(?m)^sp:int = t\d+$")
        self.assertIn("call len, 1", self.tac)
        self.assertIn("call quicksort_iterativo, 1", self.tac)
        self.assertIn("ret arr", self.tac)
        self.assertNotIn("alloc ", self.tac)

    def test_generated_tac_is_deterministic(self) -> None:
        again = TACGenerator().generate_text(parse(self.source))

        self.assertEqual(self.tac, again)

    def test_reference_tac_from_pdf_has_expected_labels(self) -> None:
        reference = REFERENCE_TAC.read_text(encoding="utf-8", errors="replace")

        for label in ("LOOP:", "PARTITION_LOOP:", "PARTITION_END:", "END:"):
            self.assertIn(label, reference)


if __name__ == "__main__":
    unittest.main()
