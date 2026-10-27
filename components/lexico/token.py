from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class TokenType(Enum):
    # Estrutura
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    END_OF_FILE = auto()

    # Identificador e literais
    IDENTIFIER = auto()
    INT_LITERAL = auto()
    FLOAT_LITERAL = auto()
    STRING_LITERAL = auto()
    BOOL_LITERAL = auto()

    # Palavras reservadas
    SEQ = auto()
    PAR = auto()
    FORK = auto()
    JOIN = auto()
    EM = auto()
    CORE = auto()
    HOST = auto()
    C_CHANNEL = auto()
    CLASS = auto()
    EXTENDS = auto()
    NEW = auto()
    SELF = auto()
    DEF = auto()
    VAR = auto()
    RETURN = auto()
    PRINT = auto()
    INPUT = auto()
    IF = auto()
    ELIF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    IN = auto()
    BREAK = auto()
    CONTINUE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    TYPE = auto()

    # Operadores
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    MOD = auto()
    ASSIGN = auto()
    PLUS_ASSIGN = auto()
    MINUS_ASSIGN = auto()
    STAR_ASSIGN = auto()
    SLASH_ASSIGN = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()
    ARROW = auto()

    # Delimitadores
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    DOT = auto()
    COMMA = auto()
    COLON = auto()

    # Caractere inválido
    UNKNOWN = auto()


KEYWORDS: dict[str, TokenType] = {
    "SEQ": TokenType.SEQ,
    "PAR": TokenType.PAR,
    "fork": TokenType.FORK,
    "join": TokenType.JOIN,
    "em": TokenType.EM,
    "core": TokenType.CORE,
    "host": TokenType.HOST,
    "c_channel": TokenType.C_CHANNEL,
    "class": TokenType.CLASS,
    "extends": TokenType.EXTENDS,
    "new": TokenType.NEW,
    "self": TokenType.SELF,
    "this": TokenType.SELF,
    "def": TokenType.DEF,
    "func": TokenType.DEF,
    "var": TokenType.VAR,
    "return": TokenType.RETURN,
    "print": TokenType.PRINT,
    "input": TokenType.INPUT,
    "if": TokenType.IF,
    "elif": TokenType.ELIF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "for": TokenType.FOR,
    "in": TokenType.IN,
    "break": TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "true": TokenType.BOOL_LITERAL,
    "false": TokenType.BOOL_LITERAL,
    "bool": TokenType.TYPE,
    "int": TokenType.TYPE,
    "float": TokenType.TYPE,
    "string": TokenType.TYPE,
    "list": TokenType.TYPE,
    "void": TokenType.TYPE,
}


@dataclass(frozen=True, init=False)
class Token:
    """Unidade léxica imutável: o léxico a produz, o parser só a lê."""
    type: TokenType
    lexeme: str
    line: int
    column: int
    value: Any = None

    def __init__(
        self,
        type: TokenType,
        lexeme: str,
        line: int,
        column: int | None = None,
        value: Any = None,
        *,
        col: int | None = None,
    ) -> None:
        resolved_column = column if column is not None else col
        if resolved_column is None:
            raise TypeError("Token exige 'column' (ou o alias 'col')")
        object.__setattr__(self, "type", type)
        object.__setattr__(self, "lexeme", lexeme)
        object.__setattr__(self, "line", line)
        object.__setattr__(self, "column", resolved_column)
        object.__setattr__(self, "value", value)

    @property
    def col(self) -> int:
        """Alias curto mantido para clientes que usam a nomenclatura portuguesa."""
        return self.column
