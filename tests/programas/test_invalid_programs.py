from __future__ import annotations

import unittest
from pathlib import Path

from components.lexico.c_lexico import Lexer
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser
from erros.diagnosticos import DiagnosticBag

INVALID_PROGRAMS = Path(__file__).with_name("invalidos")
EXPECTED_DIAGNOSTICS = {
    "01_caractere_invalido.mp": "caractere inválido",
    "02_numero_malformado.mp": "número mal formado",
    "03_instrucao_sem_parenteses.mp": "Esperado '('",
    "04_variavel_nao_declarada.mp": "nao declarada",
    "05_tipo_incompativel.mp": "Tipo incompativel",
    "06_break_fora_de_laco.mp": "fora de laco",
    "07_return_fora_de_funcao.mp": "fora de funcao",
    "08_canal_mesmo_host.mp": "computadores distintos",
    "09_fork_sem_join.mp": "nao possui join",
    "10_join_sem_fork.mp": "nao referencia um fork",
}


class InvalidProgramIntegrationTests(unittest.TestCase):
    def test_invalid_programs_report_the_expected_diagnostic(self) -> None:
        self.assertEqual(len(EXPECTED_DIAGNOSTICS), 10)
        for filename, expected in EXPECTED_DIAGNOSTICS.items():
            with self.subTest(program=filename):
                source = (INVALID_PROGRAMS / filename).read_text(encoding="utf-8")
                diagnostics = DiagnosticBag(source)
                program = Parser(Lexer(source, diagnostics), diagnostics).parse()
                SemanticAnalyzer(diagnostics).analyze(program)

                self.assertTrue(diagnostics.has_errors, filename)
                self.assertIn(expected, diagnostics.format_text())


if __name__ == "__main__":
    unittest.main()
