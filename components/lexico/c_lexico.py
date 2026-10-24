from __future__ import annotations

from collections import deque

from erros import Diagnostic, DiagnosticBag

from .token import KEYWORDS, Token, TokenType

# Gramática 2026.2: 4 espaços por nível de indentação.
INDENT_WIDTH = 4

_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}

_TWO_CHAR_OPS = {
    "==": TokenType.EQ,
    "!=": TokenType.NEQ,
    "<=": TokenType.LTE,
    ">=": TokenType.GTE,
    "+=": TokenType.PLUS_ASSIGN,
    "-=": TokenType.MINUS_ASSIGN,
    "*=": TokenType.STAR_ASSIGN,
    "/=": TokenType.SLASH_ASSIGN,
    "->": TokenType.ARROW,
}

_ONE_CHAR_OPS = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "%": TokenType.MOD,
    "=": TokenType.ASSIGN,
    "<": TokenType.LT,
    ">": TokenType.GT,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    ".": TokenType.DOT,
    ",": TokenType.COMMA,
    ":": TokenType.COLON,
}

_CLOSERS = {")": "(", "]": "["}

# Quem vem do 2026.1 recebe a dica da
# forma nova em vez de um genérico "caractere inválido".
_HINTS = {
    "{": "blocos são delimitados por indentação",
    "}": "blocos são delimitados por indentação",
    ";": "instruções terminam em quebra de linha",
    "!": "use 'not' ou '!='",
    "&": "use 'and'",
    "|": "use 'or'",
}


def _is_digit(ch: str) -> bool:
    # str.isdigit() aceita dígitos Unicode ("²", "٣"), que int() trata de forma
    # diferente; a gramática define digito = "0".."9".
    return "0" <= ch <= "9"


def _is_ident_start(ch: str) -> bool:
    # Gramática: letra = A-Z | a-z. Acentos valem em strings e comentários,
    # não em identificadores.
    return ch == "_" or (ch.isascii() and ch.isalpha())


def _is_ident_part(ch: str) -> bool:
    return _is_ident_start(ch) or _is_digit(ch)


class Lexer:
    """Analisador léxico por autômato escrito à mão.

    O parser consome tokens sob demanda via ``next_token()`` / ``peek()``.
    Erros léxicos vão para o ``DiagnosticBag`` e a varredura continua, para que
    uma única execução reporte todos os problemas do arquivo.
    """

    PHASE = "lexical"

    def __init__(
        self, source_code: str = "", diagnostics: DiagnosticBag | None = None
    ) -> None:
        self.diagnostics = diagnostics if diagnostics is not None else DiagnosticBag()
        self.initialize(source_code)

    def initialize(self, source: str) -> None:
        """Carrega uma nova fonte e reinicia o estado de varredura."""
        self._src = source.removeprefix("\ufeff")
        self._pos = 0
        self._line = 1
        self._col = 1

        self._indents = [0]
        self._open: list[tuple[str, int, int]] = []
        self._at_line_start = True
        self._line_has_tokens = False
        self._finished = False
        self._buffer: deque[Token] = deque()

    def set_diagnostic_collector(self, diagnostics: DiagnosticBag) -> None:
        self.diagnostics = diagnostics

    # ------------------------------------------------------------------
    # API pública (consumo sob demanda)
    # ------------------------------------------------------------------

    def next_token(self) -> Token:
        """Consome e devolve o próximo token. Após o fim, repete END_OF_FILE."""
        self._fill(1)
        token = self._buffer[0]
        if token.type is not TokenType.END_OF_FILE:
            self._buffer.popleft()
        return token

    def peek(self, ahead: int = 0) -> Token:
        """Espia o token ``ahead`` posições à frente sem consumi-lo."""
        self._fill(ahead + 1)
        return self._buffer[min(ahead, len(self._buffer) - 1)]

    def tokenize(self) -> list[Token]:
        """Esgota o fonte e devolve todos os tokens restantes (inclui o EOF)."""
        tokens: list[Token] = []
        while True:
            token = self.next_token()
            tokens.append(token)
            if token.type is TokenType.END_OF_FILE:
                return tokens

    proximo_token = next_token
    espiar = peek

    # ------------------------------------------------------------------
    # Infraestrutura
    # ------------------------------------------------------------------

    def _fill(self, count: int) -> None:
        # Uma linha física pode gerar vários tokens, então o
        # buffer é preenchido até ter o que o chamador pediu.
        while len(self._buffer) < count and not self._finished:
            self._scan_step()

    def _peek_char(self, offset: int = 0) -> str:
        index = self._pos + offset
        return self._src[index] if index < len(self._src) else ""

    def _advance(self) -> str:
        ch = self._src[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _emit(
        self, type_: TokenType, lexeme: str, line: int, col: int, value: object = None
    ) -> None:
        self._buffer.append(Token(type_, lexeme, line, col, value))

    def _error(self, message: str, line: int, col: int) -> None:
        self.diagnostics.report(Diagnostic(self.PHASE, message, line, col))

    # ------------------------------------------------------------------
    # Varredura
    # ------------------------------------------------------------------

    def _scan_step(self) -> None:
        if self._at_line_start and not self._open:
            self._scan_indentation()
            # Linha em branco/comentário ou fim do
            # arquivo: nada mais a fazer neste passo.
            if self._at_line_start or self._finished:
                return
        self._scan_token()

    def _scan_indentation(self) -> None:
        width = 0
        while True:
            ch = self._peek_char()
            if ch == " ":
                self._advance()
                width += 1
            elif ch == "\t":
                # Tabulação é erro. Conta como um nível
                # para a recuperação não gerar um segundo erro em cascata.
                self._error(
                    "tabulação na indentação não é permitida (use 4 espaços)",
                    self._line,
                    self._col,
                )
                self._advance()
                width += INDENT_WIDTH
            elif ch == "\r":
                self._advance()
            else:
                break

        ch = self._peek_char()
        if ch == "":
            self._finish()
        elif ch == "\n":
            self._advance()
        elif ch == "#":
            self._skip_comment()
        else:
            self._apply_indentation(width)
            self._at_line_start = False

    def _apply_indentation(self, width: int) -> None:
        line, col = self._line, self._col
        top = self._indents[-1]
        if width > top:
            if width - top != INDENT_WIDTH:
                self._error(
                    f"indentação inconsistente: esperados {INDENT_WIDTH} espaços "
                    f"por nível, encontrados {width - top}",
                    line,
                    col,
                )
            self._indents.append(width)
            self._emit(TokenType.INDENT, "", line, col)
        elif width < top:
            while self._indents[-1] > width:
                self._indents.pop()
                self._emit(TokenType.DEDENT, "", line, col)
            if self._indents[-1] != width:
                self._error(
                    "recuo não corresponde a nenhum nível de indentação anterior",
                    line,
                    col,
                )
                self._indents[-1] = width

    def _skip_comment(self) -> None:
        while self._peek_char() not in ("", "\n"):
            self._advance()

    def _scan_token(self) -> None:
        ch = self._peek_char()
        if ch == "":
            self._finish()
        elif ch in (" ", "\t", "\r"):
            self._advance()
        elif ch == "\n":
            self._scan_newline()
        elif ch == "#":
            self._skip_comment()
        elif _is_ident_start(ch) or ch.isalpha():
            self._scan_word()
        elif _is_digit(ch):
            self._scan_number()
        elif ch == '"':
            self._scan_string()
        else:
            self._scan_operator()

    def _scan_newline(self) -> None:
        # Dentro de ( ) ou [ ] a quebra de linha é ignorada.
        if not self._open:
            if self._line_has_tokens:
                self._emit(TokenType.NEWLINE, "", self._line, self._col)
            self._at_line_start = True
            self._line_has_tokens = False
        self._advance()

    def _scan_word(self) -> None:
        line, col = self._line, self._col
        chars = []
        # Letras não-ASCII entram na palavra para o erro sair uma vez só
        # e não um por caractere com a palavra picotada.
        while _is_ident_part(self._peek_char()) or self._peek_char().isalpha():
            chars.append(self._advance())
        lexeme = "".join(chars)
        if not lexeme.isascii():
            self._error(
                f"identificador inválido '{lexeme}': use apenas letras ASCII, "
                "dígitos e '_' (acentos só em strings e comentários)",
                line,
                col,
            )
            self._emit(TokenType.UNKNOWN, lexeme, line, col)
            self._line_has_tokens = True
            return
        type_ = KEYWORDS.get(lexeme, TokenType.IDENTIFIER)
        value = (lexeme == "true") if type_ is TokenType.BOOL_LITERAL else None
        self._emit(type_, lexeme, line, col, value)
        self._line_has_tokens = True

    def _scan_digits(self) -> str:
        digits = []
        while _is_digit(self._peek_char()):
            digits.append(self._advance())
        return "".join(digits)

    def _scan_number(self) -> None:
        line, col = self._line, self._col
        lexeme = self._scan_digits()
        is_float = False
        if self._peek_char() == "." and _is_digit(self._peek_char(1)):
            self._advance()
            lexeme += "." + self._scan_digits()
            is_float = True

        if _is_ident_start(self._peek_char()):
            # "12abc" / "1_500": sem isto viraria INT + IDENT e o parser daria
            # uma mensagem confusa sobre a coisa errada.
            while _is_ident_part(self._peek_char()):
                lexeme += self._advance()
            self._error(f"número mal formado: '{lexeme}'", line, col)
            self._emit(TokenType.UNKNOWN, lexeme, line, col)
        elif is_float:
            self._emit(TokenType.FLOAT_LITERAL, lexeme, line, col, float(lexeme))
        else:
            self._emit(TokenType.INT_LITERAL, lexeme, line, col, int(lexeme))
        self._line_has_tokens = True

    def _scan_string(self) -> None:
        line, col = self._line, self._col
        start = self._pos
        self._advance()
        chars: list[str] = []
        closed = False
        while True:
            ch = self._peek_char()
            if ch in ("", "\n", "\r"):
                break
            if ch == '"':
                self._advance()
                closed = True
                break
            if ch == "\\":
                esc_line, esc_col = self._line, self._col
                self._advance()
                nxt = self._peek_char()
                if nxt in ("", "\n", "\r"):
                    break
                self._advance()
                if nxt in _ESCAPES:
                    chars.append(_ESCAPES[nxt])
                else:
                    self._error(
                        f"sequência de escape inválida: '\\{nxt}'", esc_line, esc_col
                    )
                    chars.append("\\" + nxt)
            else:
                chars.append(self._advance())

        if not closed:
            self._error("string não fechada", line, col)
        self._emit(
            TokenType.STRING_LITERAL, self._src[start : self._pos], line, col, "".join(chars)
        )
        self._line_has_tokens = True

    def _scan_operator(self) -> None:
        line, col = self._line, self._col
        ch = self._peek_char()
        two = ch + self._peek_char(1)

        if two in _TWO_CHAR_OPS:
            self._advance()
            self._advance()
            self._emit(_TWO_CHAR_OPS[two], two, line, col)
        elif ch in _ONE_CHAR_OPS:
            self._advance()
            self._emit(_ONE_CHAR_OPS[ch], ch, line, col)
            self._track_delimiter(ch, line, col)
        else:
            self._advance()
            message = f"caractere inválido: {ch!r}"
            if ch in _HINTS:
                message += f" ({_HINTS[ch]})"
            self._error(message, line, col)
            self._emit(TokenType.UNKNOWN, ch, line, col)
        self._line_has_tokens = True

    def _track_delimiter(self, ch: str, line: int, col: int) -> None:
        if ch in ("(", "["):
            self._open.append((ch, line, col))
        elif ch in _CLOSERS:
            if not self._open:
                self._error(f"'{ch}' sem delimitador de abertura", line, col)
                return
            opener, o_line, o_col = self._open.pop()
            if opener != _CLOSERS[ch]:
                self._error(
                    f"'{ch}' não corresponde ao '{opener}' aberto na linha "
                    f"{o_line}, coluna {o_col}",
                    line,
                    col,
                )

    def _finish(self) -> None:
        # Fecha a última linha lógica e todos os blocos ainda abertos, para o
        # parser nunca ver um bloco sem DEDENT.
        if self._line_has_tokens:
            self._emit(TokenType.NEWLINE, "", self._line, self._col)
            self._line_has_tokens = False
        while len(self._indents) > 1:
            self._indents.pop()
            self._emit(TokenType.DEDENT, "", self._line, self._col)
        for opener, o_line, o_col in self._open:
            self._error(f"'{opener}' não foi fechado", o_line, o_col)
        self._open.clear()
        self._emit(TokenType.END_OF_FILE, "", self._line, self._col)
        self._finished = True