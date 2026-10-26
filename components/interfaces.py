from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING

from components.lexico.token import Token
from components.sintatico.ast import Program
from erros.diagnosticos import Diagnostic

if TYPE_CHECKING:
    from components.tabela_simbolos.c_tabela_simbolos import Symbol


class ILexico(ABC):
    @abstractmethod
    def initialize(self, source: str) -> None:
        """Carrega o código-fonte e reinicia a leitura."""

    @abstractmethod
    def next_token(self) -> Token:
        """Devolve o próximo token sob demanda."""


class ISintatico(ABC):
    @abstractmethod
    def parse(
        self,
        lexer: ILexico | None = None,
        semantic_analyzer: ISemantico | None = None,
    ) -> Program:
        """Constrói a AST consumindo tokens do léxico sob demanda."""


class ISemantico(ABC):
    @abstractmethod
    def analyze(self, program: Program) -> bool:
        """Valida a AST completa depois da análise sintática."""

    @property
    @abstractmethod
    def diagnostics(self) -> Sequence[Diagnostic]:
        """Erros semânticos acumulados."""


class ITabelaSimbolos(ABC):
    @property
    @abstractmethod
    def current_scope_path(self) -> str:
        """Caminho estável do escopo ativo."""

    @abstractmethod
    def enter_scope(self, name: str | None = None, *, reuse: bool = False) -> None:
        """Abre um novo escopo."""

    @abstractmethod
    def exit_scope(self) -> None:
        """Fecha o escopo atual."""

    @abstractmethod
    def define(self, symbol: Symbol) -> bool:
        """Define no escopo atual. False se já exister nele."""

    @abstractmethod
    def lookup(self, name: str) -> Symbol | None:
        """Procura no escopo atual e nos escopos pais."""

    @abstractmethod
    def lookup_local(self, name: str) -> Symbol | None:
        """Procura somente no escopo atual."""

    @abstractmethod
    def register_class_scope(self, class_name: str, scope_path: str) -> None:
        """Associa uma classe ao escopo persistente de seus membros."""

    @abstractmethod
    def lookup_member(self, class_name: str, name: str) -> Symbol | None:
        """Procura um membro na classe e em suas superclasses."""

    @abstractmethod
    def lookup_method(self, class_name: str, name: str) -> Symbol | None:
        """Procura um método na classe e em suas superclasses."""

    @abstractmethod
    def lookup_attribute(self, class_name: str, name: str) -> Symbol | None:
        """Procura um atributo na classe e em suas superclasses."""

    @abstractmethod
    def export(self) -> dict[str, object]:
        """Devolve uma representação serializável da tabela."""


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
