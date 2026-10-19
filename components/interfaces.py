from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from components.lexico.token import Token
from components.sintatico.ast import ASTNode, Program
from erros.diagnosticos import Diagnostic


class ILexico(ABC):
    @abstractmethod
    def initialize(self, source: str) -> None:
        """Carrega o código-fonte e reinicia a leitura."""

    @abstractmethod
    def next_token(self) -> Token:
        """Devolve o próximo token
        O parser puxa tokens por aqui, me vez de receber uma lista pronta.
        """


class ISintatico(ABC):
    @abstractmethod
    def parse(self, lexer: ILexico, semantic_analyzer: ISemantico) -> Program:
        """Constrói a ASI puxando tokens de lexico e chamando semantico."""


class ISemantico(ABC):
    @abstractmethod
    def verify(self, node: ASTNode) -> None:
        """Valida um nó: chamado pelo parse durante a análise sentiática."""

    @property
    @abstractmethod
    def diagnostics(self) -> Sequence[Diagnostic]:
        """Erros semânticos acumulados."""


class ITabelaSimbolos(ABC):
    @abstractmethod
    def enter_scope(self) -> None:
        """Abre um novo escopo."""

    @abstractmethod
    def exit_scope(self) -> None:
        """Fecha o escopo atual."""

    @abstractmethod
    def define(self, name: str, symbol: object) -> bool:
        """Define no escopo atual. False se já exister nele."""

    @abstractmethod
    def lookup(self, name: str) -> object | None:
        """Procura um nó: chamado pelo parser durante a análise sintática."""


class IGeradorTAC(ABC):
    @abstractmethod
    def generate(self, program: Program, output_name: str) -> str:
        """Gera o código de três endereços e devolve o caminho do arquivo."""


class IGeradorCpp(ABC):
    @abstractmethod
    def generate(self, program: Program, output_name: str) -> bool:
        """Gera e compila o C++ se o executável foi produzido."""


class IControle(ABC):
    @abstractmethod
    def compile(self, source: str, output_name: str) -> bool:
        """Orquestra as fasessobre o texto-fonte: True se todas passarem."""
