from __future__ import annotations

import unittest

from components.lexico import Lexer
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser


def analyze(source: str) -> SemanticAnalyzer:
    program = Parser(Lexer(source)).parse()
    analyzer = SemanticAnalyzer()
    analyzer.analyze(program)
    return analyzer


class ParallelSemanticAnalyzerTests(unittest.TestCase):
    def test_parallel_branches_cannot_write_outer_variable(self) -> None:
        analyzer = analyze(
            "SEQ\n"
            "    shared: int = 0\n"
            "    PAR\n"
            "        SEQ\n"
            "            shared = 1\n"
            "        SEQ\n"
            "            shared = 2\n"
        )

        messages = [diagnostic.message for diagnostic in analyzer.diagnostics]
        self.assertEqual(
            sum("nao pode escrever na variavel externa 'shared'" in message
                for message in messages),
            2,
        )

    def test_parallel_branches_can_write_local_variables(self) -> None:
        analyzer = analyze(
            "PAR\n"
            "    SEQ\n"
            "        local_a: int = 1\n"
            "        local_a = 2\n"
            "    SEQ\n"
            "        local_b: int = 3\n"
            "        local_b = 4\n"
        )

        self.assertFalse(analyzer.diagnostics, analyzer.diagnostics)

    def test_fork_cannot_write_outer_variable(self) -> None:
        analyzer = analyze(
            "SEQ\n"
            "    shared: int = 0\n"
            "    fork worker:\n"
            "        shared = 1\n"
            "    join worker\n"
        )

        self.assertTrue(
            any("nao pode escrever na variavel externa 'shared'"
                in diagnostic.message for diagnostic in analyzer.diagnostics),
            analyzer.diagnostics,
        )

    def test_channel_send_and_receive_signatures_must_match(self) -> None:
        analyzer = analyze(
            "c_channel dados pc1 pc2\n"
            "SEQ\n"
            "    first: int = 0\n"
            "    second: int = 0\n"
            "    third: int = 0\n"
            "    fourth: int = 0\n"
            "    dados.send(1, 2, 3)\n"
            "    dados.receive(first, second, third, fourth)\n"
        )

        self.assertTrue(
            any("Aridade inconsistente no canal 'dados'" in diagnostic.message
                for diagnostic in analyzer.diagnostics),
            analyzer.diagnostics,
        )

    def test_channel_argument_types_must_match(self) -> None:
        analyzer = analyze(
            "c_channel dados pc1 pc2\n"
            "SEQ\n"
            "    text: string = \"\"\n"
            "    count: int = 0\n"
            "    dados.send(1, \"value\")\n"
            "    dados.receive(text, count)\n"
        )

        self.assertTrue(
            any("Tipo inconsistente no argumento 1 do canal 'dados'"
                in diagnostic.message for diagnostic in analyzer.diagnostics),
            analyzer.diagnostics,
        )

    def test_declared_channel_accepts_matching_send_and_receive(self) -> None:
        analyzer = analyze(
            "c_channel dados pc1 pc2\n"
            "SEQ\n"
            "    text: string = \"\"\n"
            "    dados.send(\"value\")\n"
            "    dados.receive(text)\n"
        )

        self.assertFalse(analyzer.diagnostics, analyzer.diagnostics)

    def test_send_and_receive_require_declared_channel(self) -> None:
        analyzer = analyze(
            "SEQ\n"
            "    value: int = 1\n"
            "    value.send(1)\n"
        )

        self.assertTrue(
            any("so pode ser usado em variavel declarada como c_channel"
                in diagnostic.message for diagnostic in analyzer.diagnostics),
            analyzer.diagnostics,
        )

    def test_function_style_send_and_receive_require_channel_variable(self) -> None:
        analyzer = analyze(
            "SEQ\n"
            "    send(1, \"value\")\n"
            "    receive(1)\n"
        )

        self.assertEqual(
            sum("exige como primeiro argumento uma variavel declarada como c_channel"
                in diagnostic.message for diagnostic in analyzer.diagnostics),
            2,
            analyzer.diagnostics,
        )

    def test_channel_must_connect_distinct_computers(self) -> None:
        analyzer = analyze(
            "c_channel local pc1 pc1\n"
            "SEQ\n"
            "    print(1)\n"
        )

        self.assertTrue(
            any("deve ligar computadores distintos" in diagnostic.message
                for diagnostic in analyzer.diagnostics),
            analyzer.diagnostics,
        )

    def test_join_must_follow_fork_in_same_scope(self) -> None:
        analyzer = analyze(
            "SEQ\n"
            "    join worker\n"
            "    fork worker:\n"
            "        print(1)\n"
            "    join worker\n"
        )

        messages = [diagnostic.message for diagnostic in analyzer.diagnostics]
        self.assertEqual(
            sum("nao referencia um fork anterior neste escopo" in message
                for message in messages),
            1,
        )
        self.assertFalse(
            any("nao possui join neste escopo" in message for message in messages),
            messages,
        )

    def test_fork_must_be_joined_in_its_own_scope(self) -> None:
        analyzer = analyze(
            "SEQ\n"
            "    SEQ\n"
            "        fork worker:\n"
            "            print(1)\n"
            "    join worker\n"
        )

        messages = [diagnostic.message for diagnostic in analyzer.diagnostics]
        self.assertTrue(
            any("nao possui join neste escopo" in message for message in messages),
            messages,
        )
        self.assertTrue(
            any("nao referencia um fork anterior neste escopo" in message
                for message in messages),
            messages,
        )

    def test_fork_and_join_in_same_scope_are_valid(self) -> None:
        analyzer = analyze(
            "SEQ\n"
            "    fork worker:\n"
            "        print(1)\n"
            "    join worker\n"
        )

        self.assertFalse(analyzer.diagnostics, analyzer.diagnostics)


if __name__ == "__main__":
    unittest.main()
