from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from components.compilador import CompiladorMiniPar
from components.controle.c_controle import CControle
from components.interfaces import IControle, ILexico, ISemantico
from components.lexico.token import TokenType
from tests.unitarios.falsos import (
    AlternateFakeLexer,
    FakeCppGenerator,
    FakeLexer,
    FakeParser,
    FakeSemanticAnalyzer,
    FakeSymbolTable,
    FakeTACGenerator,
)
from erros.diagnosticos import Diagnostic


def build_pipeline(lexer: ILexico) -> tuple[CompiladorMiniPar, ISemantico]:
    semantic_analyzer = FakeSemanticAnalyzer(FakeSymbolTable())
    controller = CControle(
        lexer,
        FakeParser(),
        semantic_analyzer,
        FakeTACGenerator(),
        FakeCppGenerator(),
    )
    return CompiladorMiniPar(controller), semantic_analyzer


class PipelineTests(unittest.TestCase):
    def test_complete_pipeline_runs_with_stubs(self) -> None:
        compiler, semantic_analyzer = build_pipeline(FakeLexer())
        self.assertTrue(compiler.compile_text("var x = 1", "output"))
        self.assertEqual(semantic_analyzer.verified_nodes, 4)

    def test_component_can_be_replaced_without_other_changes(self) -> None:
        lexer = AlternateFakeLexer()
        compiler, _ = build_pipeline(lexer)
        self.assertTrue(compiler.compile_text("1 2 3", "output"))
        lexer.initialize("7")
        self.assertIs(lexer.next_token().type, TokenType.INT_LITERAL)

    def test_interfaces_cannot_be_instantiated(self) -> None:
        with self.assertRaises(TypeError):
            ILexico()  # type: ignore[abstract]
        with self.assertRaises(TypeError):
            IControle()  # type: ignore[abstract]

    def test_tokens_are_immutable(self) -> None:
        token = FakeLexer()
        token.initialize("identifier")
        with self.assertRaises(FrozenInstanceError):
            token.next_token().lexeme = "changed"  # type: ignore[misc]

    def test_diagnostics_are_immutable(self) -> None:
        diagnostic = Diagnostic("parser", "Unexpected token", 2, 4)
        with self.assertRaises(FrozenInstanceError):
            diagnostic.message = "changed"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
