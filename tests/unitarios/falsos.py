from __future__ import annotations

from pathlib import Path

from collections.abc import Sequence

from components.interfaces import (
    IGeradorCpp,
    IGeradorTAC,
    ILexico,
    ISemantico,
    ISintatico,
    ITabelaSimbolos,
)
from components.lexico.token import Token, TokenType
from components.sintatico.ast import ASTNode, Program
from components.tabela_simbolos import Symbol
from erros.diagnosticos import Diagnostic


class FakeLexer(ILexico):
    def __init__(self) -> None:
        self._tokens: list[Token] = []

    def initialize(self, source: str) -> None:
        self._tokens = [
            Token(TokenType.IDENTIFIER, part, 1, index + 1)
            for index, part in enumerate(source.split())
        ]

    def next_token(self) -> Token:
        if self._tokens:
            return self._tokens.pop(0)
        return Token(TokenType.END_OF_FILE, "", 1, 1)


class AlternateFakeLexer(FakeLexer):
    """Outro léxico: tudo vira NUMERO. Usado no teste de substituição."""

    def initialize(self, source: str) -> None:
        self._tokens = [
            Token(TokenType.INT_LITERAL, part, 1, index + 1)
            for index, part in enumerate(source.split())
        ]


class FakeSymbolTable(ITabelaSimbolos):
    def __init__(self) -> None:
        self._scopes: list[dict[str, object]] = [{}]

    @property
    def current_scope_path(self) -> str:
        return "fake"

    def enter_scope(self, name: str | None = None, *, reuse: bool = False) -> None:
        self._scopes.append({})

    def exit_scope(self) -> None:
        if len(self._scopes) > 1:
            self._scopes.pop()

    def define(self, symbol: Symbol) -> bool:
        if symbol.name in self._scopes[-1]:
            return False
        self._scopes[-1][symbol.name] = symbol
        return True

    def lookup(self, name: str) -> Symbol | None:
        for scope in reversed(self._scopes):
            if name in scope:
                symbol = scope[name]
                return symbol if isinstance(symbol, Symbol) else None
        return None

    def lookup_local(self, name: str) -> Symbol | None:
        symbol = self._scopes[-1].get(name)
        return symbol if isinstance(symbol, Symbol) else None

    def register_class_scope(self, class_name: str, scope_path: str) -> None:
        pass

    def lookup_member(self, class_name: str, name: str) -> Symbol | None:
        return None

    def lookup_method(self, class_name: str, name: str) -> Symbol | None:
        return None

    def lookup_attribute(self, class_name: str, name: str) -> Symbol | None:
        return None

    def export(self) -> dict[str, object]:
        return {"scopes": []}


class FakeSemanticAnalyzer(ISemantico):
    def __init__(self, symbol_table: ITabelaSimbolos) -> None:
        self._symbol_table = symbol_table
        self.verified_nodes = 0

    def analyze(self, program: Program) -> bool:
        self.verified_nodes += len(program.statements)
        return True

    @property
    def diagnostics(self) -> Sequence[Diagnostic]:
        return ()


class FakeParser(ISintatico):
    def parse(
        self,
        lexer: ILexico | None = None,
        semantic_analyzer: ISemantico | None = None,
    ) -> Program:
        if lexer is None or semantic_analyzer is None:
            raise ValueError("FakeParser requer léxico e analisador semântico")
        statements: list[ASTNode] = []
        while lexer.next_token().type is not TokenType.END_OF_FILE:
            statements.append(ASTNode())
        program = Program(statements=tuple(statements))
        semantic_analyzer.analyze(program)
        return program


class FakeTACGenerator(IGeradorTAC):
    def generate(self, program: Program, output_name: str) -> str:
        path = Path(f"{output_name}.tac")
        path.write_text("", encoding="utf-8")
        return str(path)


class FakeCppGenerator(IGeradorCpp):
    def generate(self, tac: str, output_name: str) -> bool:
        Path(f"{output_name}.tac").unlink(missing_ok=True)
        return True
