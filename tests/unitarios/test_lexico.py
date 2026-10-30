import unittest
from pathlib import Path

from components.lexico import Lexer, Token, TokenType
from erros import DiagnosticBag

T = TokenType


def lex(source: str) -> tuple[list[Token], DiagnosticBag]:
    bag = DiagnosticBag()
    return Lexer(source, bag).tokenize(), bag


def kinds(source: str) -> list[TokenType]:
    return [t.type for t in lex(source)[0]]


def errors(source: str) -> list[str]:
    return [str(d) for d in lex(source)[1].diagnostics]


class StructureTests(unittest.TestCase):
    def test_indent_dedent_and_newline(self):
        self.assertEqual(
            kinds("SEQ\n    x = 1\ny = 2\n"),
            [T.SEQ, T.NEWLINE, T.INDENT, T.IDENTIFIER, T.ASSIGN, T.INT_LITERAL,
             T.NEWLINE, T.DEDENT, T.IDENTIFIER, T.ASSIGN, T.INT_LITERAL,
             T.NEWLINE, T.END_OF_FILE],
        )

    def test_multiple_dedents_at_once(self):
        ks = kinds("a:\n    b:\n        c\nd\n")
        i = ks.index(T.DEDENT)
        self.assertEqual(ks[i:i + 2], [T.DEDENT, T.DEDENT])

    def test_eof_closes_open_blocks_and_last_line_without_newline(self):
        ks = kinds("SEQ\n    x")
        self.assertEqual(ks[-3:], [T.NEWLINE, T.DEDENT, T.END_OF_FILE])

    def test_blank_and_comment_lines_do_not_affect_indentation(self):
        ks = kinds("SEQ\n    a\n\n        # nada\n    b\n")
        self.assertEqual(ks.count(T.INDENT), 1)
        self.assertEqual(ks.count(T.DEDENT), 1)
        self.assertEqual(ks.count(T.NEWLINE), 3)

    def test_trailing_spaces_at_eof(self):
        self.assertEqual(kinds("SEQ\n    a\n    ")[-2:], [T.DEDENT, T.END_OF_FILE])

    def test_newline_ignored_inside_brackets(self):
        ks = kinds("x = [1,\n  2,\n        3]\ny\n")
        self.assertEqual(ks.count(T.NEWLINE), 2)
        self.assertNotIn(T.INDENT, ks)

    def test_crlf_and_bom(self):
        tokens, bag = lex("\ufeffSEQ\r\n    x\r\n\r\n")
        self.assertFalse(bag.has_errors)
        self.assertEqual(tokens[0].type, T.SEQ)
        self.assertEqual((tokens[0].line, tokens[0].col), (1, 1))


class IndentationErrorTests(unittest.TestCase):
    def test_wrong_indent_size(self):
        tokens, bag = lex("SEQ\n  x\n")
        self.assertEqual(len(bag.diagnostics), 1)
        self.assertEqual(bag.diagnostics[0].line, 2)
        self.assertEqual(sum(t.type is T.INDENT for t in tokens), 1)
        self.assertEqual(sum(t.type is T.DEDENT for t in tokens), 1)

    def test_dedent_to_unknown_level_reports_once_and_stays_balanced(self):
        tokens, bag = lex("SEQ\n    if x:\n        a\n      b\n      c\n")
        self.assertEqual(len(bag.diagnostics), 1)
        self.assertEqual(bag.diagnostics[0].line, 4)
        self.assertEqual(
            sum(t.type is T.INDENT for t in tokens),
            sum(t.type is T.DEDENT for t in tokens),
        )

    def test_tab_is_an_error_without_cascade(self):
        tokens, bag = lex("SEQ\n\tx\n")
        self.assertEqual(len(bag.diagnostics), 1)
        self.assertEqual((bag.diagnostics[0].line, bag.diagnostics[0].column), (2, 1))
        self.assertIn(T.INDENT, [t.type for t in tokens])

    def test_tab_inside_a_line_is_whitespace(self):
        self.assertEqual(errors("x\t=\t1\n"), [])


class PositionTests(unittest.TestCase):
    def test_line_and_column_multiline(self):
        tokens, _ = lex('SEQ\n    x = 10\n    y = "hi"\n')
        self.assertEqual(
            [(t.type, t.lexeme, t.line, t.col) for t in tokens],
            [
                (T.SEQ, "SEQ", 1, 1),
                (T.NEWLINE, "", 1, 4),
                (T.INDENT, "", 2, 5),
                (T.IDENTIFIER, "x", 2, 5),
                (T.ASSIGN, "=", 2, 7),
                (T.INT_LITERAL, "10", 2, 9),
                (T.NEWLINE, "", 2, 11),
                (T.IDENTIFIER, "y", 3, 5),
                (T.ASSIGN, "=", 3, 7),
                (T.STRING_LITERAL, '"hi"', 3, 9),
                (T.NEWLINE, "", 3, 13),
                (T.DEDENT, "", 4, 1),
                (T.END_OF_FILE, "", 4, 1),
            ],
        )

    def test_comments_count_lines(self):
        tokens, _ = lex("# a\n# b\nx = 1  # c\ny\n")
        xs = [t for t in tokens if t.type is T.IDENTIFIER]
        self.assertEqual([(t.lexeme, t.line, t.col) for t in xs], [("x", 3, 1), ("y", 4, 1)])


class LiteralTests(unittest.TestCase):
    def test_numbers(self):
        tokens, bag = lex("42 3.14 0.5\n")
        self.assertFalse(bag.has_errors)
        self.assertEqual([t.value for t in tokens[:3]], [42, 3.14, 0.5])
        self.assertEqual([t.type for t in tokens[:3]], [T.INT_LITERAL, T.FLOAT_LITERAL, T.FLOAT_LITERAL])

    def test_dot_without_digit_is_not_float(self):
        self.assertEqual(kinds("1.foo\n")[:3], [T.INT_LITERAL, T.DOT, T.IDENTIFIER])

    def test_malformed_number(self):
        tokens, bag = lex("12abc 1_500\n")
        self.assertEqual(len(bag.diagnostics), 2)
        self.assertEqual([t.type for t in tokens[:2]], [T.UNKNOWN, T.UNKNOWN])

    def test_bool_values(self):
        tokens, _ = lex("true false\n")
        self.assertEqual([(t.type, t.value) for t in tokens[:2]],
                         [(T.BOOL_LITERAL, True), (T.BOOL_LITERAL, False)])

    def test_accents_preserved_in_strings(self):
        tokens, bag = lex('print("Máquina de lavar", "Ficção científica")\n')
        self.assertFalse(bag.has_errors)
        strings = [t.value for t in tokens if t.type is T.STRING_LITERAL]
        self.assertEqual(strings, ["Máquina de lavar", "Ficção científica"])

    def test_escapes(self):
        tokens, bag = lex(r'"a\nb\t\"c\\"' + "\n")
        self.assertFalse(bag.has_errors)
        self.assertEqual(tokens[0].value, 'a\nb\t"c\\')
        self.assertEqual(tokens[0].lexeme, r'"a\nb\t\"c\\"')

    def test_invalid_escape(self):
        tokens, bag = lex(r'"a\qb"' + "\n")
        self.assertEqual(len(bag.diagnostics), 1)
        self.assertEqual(bag.diagnostics[0].column, 3)
        self.assertEqual(tokens[0].value, "a\\qb")

    def test_unterminated_string_does_not_stop_lexing(self):
        tokens, bag = lex('x = "abc\ny = 2\n')
        self.assertEqual(len(bag.diagnostics), 1)
        self.assertEqual((bag.diagnostics[0].line, bag.diagnostics[0].column), (1, 5))
        self.assertIn("y", [t.lexeme for t in tokens])

    def test_unterminated_string_with_trailing_backslash(self):
        self.assertEqual(len(errors('"abc\\')), 1)
        self.assertEqual(len(errors('"abc\\\n')), 1)


class OperatorAndKeywordTests(unittest.TestCase):
    def test_operators(self):
        src = "+ - * / % = == != < > <= >= += -= *= /= -> ( ) [ ] . , :\n"
        self.assertEqual(
            kinds(src)[:-2],
            [T.PLUS, T.MINUS, T.STAR, T.SLASH, T.MOD, T.ASSIGN, T.EQ, T.NEQ,
             T.LT, T.GT, T.LTE, T.GTE, T.PLUS_ASSIGN, T.MINUS_ASSIGN,
             T.STAR_ASSIGN, T.SLASH_ASSIGN, T.ARROW, T.LPAREN, T.RPAREN,
             T.LBRACKET, T.RBRACKET, T.DOT, T.COMMA, T.COLON],
        )

    def test_logical_operator_aliases_are_normalized(self):
        tokens, bag = lex("true && false || true\n")
        self.assertFalse(bag.has_errors)
        self.assertEqual(
            [(token.type, token.lexeme) for token in tokens[:5]],
            [
                (T.BOOL_LITERAL, "true"),
                (T.AND, "and"),
                (T.BOOL_LITERAL, "false"),
                (T.OR, "or"),
                (T.BOOL_LITERAL, "true"),
            ],
        )

    def test_keywords(self):
        src = ("SEQ PAR fork join em core host c_channel class extends new self "
               "def return print input if elif else while for in break continue "
               "and or not\n")
        ks = kinds(src)[:-2]
        self.assertNotIn(T.IDENTIFIER, ks)
        self.assertEqual(len(ks), 27)

    def test_types_and_builtins(self):
        tokens, _ = lex("int float string bool list void print input\n")
        self.assertEqual([t.type for t in tokens[:6]], [T.TYPE] * 6)
        self.assertEqual([t.type for t in tokens[6:8]], [T.PRINT, T.INPUT])

    def test_keywords_are_case_sensitive(self):
        self.assertEqual(kinds("seq Par\n")[:2], [T.IDENTIFIER, T.IDENTIFIER])


class ErrorRecoveryTests(unittest.TestCase):
    def test_invalid_chars_collected_and_lexing_continues(self):
        tokens, bag = lex("a @ b $ c\n")
        self.assertEqual(len(bag.diagnostics), 2)
        self.assertEqual([t.lexeme for t in tokens if t.type is T.IDENTIFIER], ["a", "b", "c"])
        self.assertEqual(sum(t.type is T.UNKNOWN for t in tokens), 2)

    def test_hints_for_unsupported_operators(self):
        for ch, hint in [("!", "not"), ("&", "and"), ("|", "or")]:
            with self.subTest(ch=ch):
                self.assertIn(hint, errors(f"a {ch} b\n")[0])

    def test_brace_blocks_and_semicolon_statement_terminators(self):
        tokens, bag = lex("seq { x = 1; }\n")
        self.assertFalse(bag.has_errors)
        self.assertEqual(
            [token.type for token in tokens],
            [
                T.IDENTIFIER,
                T.LBRACE,
                T.IDENTIFIER,
                T.ASSIGN,
                T.INT_LITERAL,
                T.NEWLINE,
                T.RBRACE,
                T.NEWLINE,
                T.END_OF_FILE,
            ],
        )

    def test_accented_identifier_is_rejected(self):
        self.assertEqual(len(errors("ação = 1\n")), 1)

    def test_bracket_errors(self):
        self.assertEqual(len(errors("x)\n")), 1)
        self.assertIn("não corresponde", errors("(1]\n")[0])
        _, bag = lex("f(1,\n")
        self.assertEqual(len(bag.diagnostics), 1)
        self.assertEqual((bag.diagnostics[0].line, bag.diagnostics[0].column), (1, 2))

    def test_diagnostic_format(self):
        diagnostic = lex("@\n")[1].diagnostics[0]
        self.assertEqual(diagnostic.phase, "lexical")
        self.assertEqual((diagnostic.line, diagnostic.column), (1, 1))

    def test_creates_own_bag_when_none_given(self):
        lexer = Lexer("@\n")
        lexer.tokenize()
        self.assertTrue(lexer.diagnostics.has_errors)

    def test_diagnostic_collector_can_be_replaced(self):
        lexer = Lexer("@\n")
        collector = DiagnosticBag()
        lexer.set_diagnostic_collector(collector)
        lexer.tokenize()
        self.assertEqual(len(collector.diagnostics), 1)

    def test_initialize_resets_source_and_scanner_state(self):
        lexer = Lexer("old\n")
        self.assertEqual(lexer.next_token().lexeme, "old")
        lexer.initialize("new\n")
        token = lexer.next_token()
        self.assertEqual((token.lexeme, token.line, token.col), ("new", 1, 1))


class TokenTests(unittest.TestCase):
    def test_column_field_and_short_alias(self):
        token = Token(T.IDENTIFIER, "nome", 3, column=7)
        self.assertEqual(token.column, 7)
        self.assertEqual(token.col, 7)
        self.assertEqual(Token(T.IDENTIFIER, "nome", 3, col=7).column, 7)

    def test_column_is_required(self):
        with self.assertRaisesRegex(TypeError, "exige 'column'"):
            Token(T.IDENTIFIER, "nome", 3)


class OnDemandTests(unittest.TestCase):
    def test_next_and_peek(self):
        lexer = Lexer("a = 1\n")
        self.assertEqual(lexer.peek().lexeme, "a")
        self.assertEqual(lexer.peek(2).lexeme, "1")
        self.assertEqual(lexer.next_token().lexeme, "a")
        self.assertEqual(lexer.next_token().type, T.ASSIGN)
        self.assertEqual(lexer.peek().type, T.INT_LITERAL)

    def test_eof_is_sticky_and_peek_clamps(self):
        lexer = Lexer("")
        self.assertEqual(lexer.next_token().type, T.END_OF_FILE)
        self.assertEqual(lexer.next_token().type, T.END_OF_FILE)
        self.assertEqual(lexer.peek(10).type, T.END_OF_FILE)

    def test_portuguese_aliases(self):
        lexer = Lexer("x\n")
        self.assertEqual(lexer.espiar().lexeme, "x")
        self.assertEqual(lexer.proximo_token().lexeme, "x")

    def test_is_lazy(self):
        lexer = Lexer('a\n"aberta\n')
        lexer.next_token()
        self.assertFalse(lexer.diagnostics.has_errors)

    def test_parser_reads_from_lexer_only_as_needed(self):
        from components.sintatico.c_sintatico import Parser

        lexer = Lexer("a\nb\n")
        parser = Parser(lexer)
        self.assertEqual(parser._peek().lexeme, "a")
        self.assertEqual(len(parser._tokens), 1)
        self.assertEqual(parser._advance().lexeme, "a")
        self.assertEqual(parser._peek().type, T.NEWLINE)
        self.assertEqual(len(parser._tokens), 2)


class ProgramTests(unittest.TestCase):
    def test_channel_program_shape(self):
        src = (
            "c_channel calculadora computador_1 computador_2\n"
            "SEQ\n"
            "    op = input()\n"
            "    if op == \"+\":\n"
            "        calculadora.send(op, v1, v2)\n"
            "    elif op == \"-\":\n"
            "        x -= 1\n"
        )
        tokens, bag = lex(src)
        self.assertFalse(bag.has_errors)
        self.assertEqual(tokens[0].type, T.C_CHANNEL)
        self.assertEqual(
            sum(t.type is T.INDENT for t in tokens), sum(t.type is T.DEDENT for t in tokens)
        )

    def test_fork_join_program(self):
        src = (
            "SEQ\n"
            "    fork prof em core(1):\n"
            "        corrigir(1)\n"
            "    fork m em host(\"pc2\"):\n"
            "        corrigir(2)\n"
            "    join prof, m\n"
        )
        tokens, bag = lex(src)
        self.assertFalse(bag.has_errors)
        self.assertEqual(sum(t.type is T.FORK for t in tokens), 2)
        self.assertEqual(sum(t.type is T.JOIN for t in tokens), 1)

    def test_all_legacy_programs_are_scanned_to_eof(self):
        files = sorted(
            (Path(__file__).resolve().parents[2] / "programas_teste").glob("*.mp")
        )
        if not files:
            self.fail("programas_teste/ não contém os programas de aceitação .mp")
        for path in files:
            with self.subTest(programa=path.name):
                tokens, _ = lex(path.read_text(encoding="utf-8"))
                self.assertEqual(tokens[-1].type, T.END_OF_FILE)


if __name__ == "__main__":
    unittest.main()
