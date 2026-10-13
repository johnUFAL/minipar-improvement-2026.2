from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING_LITERAL = auto()
    BOOL_LITERAL = auto()
    CLASS = auto()
    EXTENDS = auto()
    NEW = auto()
    FUNC = auto()
    VAR = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    DO = auto()
    FOR = auto()
    IN = auto()
    BREAK = auto()
    CONTINUE = auto()
    RETURN = auto()
    SEQ = auto()
    PAR = auto()
    THIS = auto()
    C_CHANNEL = auto()
    SEND = auto()
    RECEIVE = auto()
    INPUT = auto()
    PRINT = auto()
    MATRIX = auto()
    TYPE = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    MOD = auto()
    ASSIGN = auto()
    EQ = auto()
    NEQ = auto()
    NOT = auto()
    AND = auto()
    OR = auto()
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    DOT = auto()
    SEMICOLON = auto()
    COMMA = auto()
    END_OF_FILE = auto()
    UNKNOWN = auto()


KEYWORDS: dict[str, TokenType] = {
    "class": TokenType.CLASS,
    "extends": TokenType.EXTENDS,
    "new": TokenType.NEW,
    "seq": TokenType.SEQ,
    "par": TokenType.PAR,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "do": TokenType.DO,
    "for": TokenType.FOR,
    "in": TokenType.IN,
    "break": TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "return": TokenType.RETURN,
    "func": TokenType.FUNC,
    "var": TokenType.VAR,
    "print": TokenType.PRINT,
    "this": TokenType.THIS,
    "c_channel": TokenType.C_CHANNEL,
    "send": TokenType.SEND,
    "receive": TokenType.RECEIVE,
    "input": TokenType.INPUT,
    "matrix": TokenType.MATRIX,
    "true": TokenType.BOOL_LITERAL,
    "false": TokenType.BOOL_LITERAL,
    "number": TokenType.TYPE,
    "int": TokenType.TYPE,
    "string": TokenType.TYPE,
    "bool": TokenType.TYPE,
    "void": TokenType.TYPE,
    "list": TokenType.TYPE,
    "dict": TokenType.TYPE,
}


@dataclass
class Token:
    type: TokenType
    lexeme: str
    line: int
    col: int
