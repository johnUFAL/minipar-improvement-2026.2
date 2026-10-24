from __future__ import annotations

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

    def enter_scope(self) -> None:
        self._scopes.append({})

    def exit_scope(self) -> None:
        if len(self._scopes) > 1:
            self._scopes.pop()

    def define(self, name: str, symbol: object) -> bool:
        if name in self._scopes[-1]:
            return False
        self._scopes[-1][name] = symbol
        return True

    def lookup(self, name: str) -> object | None:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None


class FakeSemanticAnalyzer(ISemantico):
    def __init__(self, symbol_table: ITabelaSimbolos) -> None:
        self._symbol_table = symbol_table
        self.verified_nodes = 0

    def verify(self, node: ASTNode) -> None:
        self.verified_nodes += 1

    @property
    def diagnostics(self) -> Sequence[Diagnostic]:
        return ()


class FakeParser(ISintatico):
    def parse(self, lexer: ILexico, semantic_analyzer: ISemantico) -> Program:
        statements: list[ASTNode] = []
        while lexer.next_token().type is not TokenType.END_OF_FILE:
            node = ASTNode()
            semantic_analyzer.verify(node)
            statements.append(node)
        return Program(statements=tuple(statements))


class FakeTACGenerator(IGeradorTAC):
    def generate(self, program: Program, output_name: str) -> str:
        return f"{output_name}.tac"


class FakeCppGenerator(IGeradorCpp):
    def generate(self, program: Program, output_name: str) -> bool:
        return True
