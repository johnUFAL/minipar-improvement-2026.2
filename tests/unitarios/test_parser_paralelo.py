from __future__ import annotations

import unittest

from components.lexico import Lexer
from components.sintatico.ast import (
    Assignment,
    ChannelDecl,
    ForkStmt,
    IdentifierExpr,
    JoinStmt,
    MethodCall,
    NumberExpr,
    ParBlock,
    Program,
    SeqBlock,
    StringExpr,
)
from components.sintatico.c_sintatico import Parser


def parse(source: str) -> tuple[Program, Parser]:
    parser = Parser(Lexer(source))
    return parser.parse(), parser


class ParallelParserTests(unittest.TestCase):
    def test_client_server_channel_and_method_calls_parse(self) -> None:
        source = (
            "c_channel calculadora computador_1 computador_2\n"
            "SEQ\n"
            "    calculadora.send(a, b, c)\n"
            "    calculadora.receive(a, b, c)\n"
        )

        program, parser = parse(source)

        self.assertFalse(parser.diagnostics)
        channel = program.statements[0]
        self.assertIsInstance(channel, ChannelDecl)
        self.assertEqual(channel.name, "calculadora")
        self.assertEqual(channel.first_host, "computador_1")
        self.assertEqual(channel.second_host, "computador_2")

        root = program.statements[1]
        self.assertIsInstance(root, SeqBlock)
        self.assertEqual(len(root.statements), 2)
        for statement, method_name in zip(root.statements, ("send", "receive")):
            self.assertIsInstance(statement, MethodCall)
            self.assertEqual(statement.method_name, method_name)
            self.assertIsInstance(statement.object, IdentifierExpr)
            self.assertEqual(statement.object.name, "calculadora")
            self.assertEqual(
                tuple(argument.name for argument in statement.arguments),
                ("a", "b", "c"),
            )

    def test_parallel_block_contains_sequential_thread_blocks(self) -> None:
        program, parser = parse(
            "PAR\n"
            "    SEQ\n"
            "        fatorial = 120\n"
            "    SEQ\n"
            "        fibonacci = 21\n"
        )

        self.assertFalse(parser.diagnostics)
        root = program.statements[0]
        self.assertIsInstance(root, ParBlock)
        self.assertEqual(len(root.statements), 2)
        for block, variable, value in zip(
            root.statements,
            ("fatorial", "fibonacci"),
            ("120", "21"),
        ):
            self.assertIsInstance(block, SeqBlock)
            assignment = block.statements[0]
            self.assertIsInstance(assignment, Assignment)
            self.assertEqual(assignment.name, variable)
            self.assertIsInstance(assignment.value, NumberExpr)
            self.assertEqual(assignment.value.value, value)

    def test_parallel_and_sequential_blocks_can_be_nested_either_way(self) -> None:
        program, parser = parse(
            "SEQ\n"
            "    PAR\n"
            "        SEQ\n"
            "            inner = 1\n"
            "    after = 2\n"
        )

        self.assertFalse(parser.diagnostics)
        root = program.statements[0]
        self.assertIsInstance(root, SeqBlock)
        parallel = root.statements[0]
        self.assertIsInstance(parallel, ParBlock)
        nested_seq = parallel.statements[0]
        self.assertIsInstance(nested_seq, SeqBlock)
        self.assertIsInstance(nested_seq.statements[0], Assignment)
        self.assertIsInstance(root.statements[1], Assignment)

        program, parser = parse(
            "PAR\n"
            "    SEQ\n"
            "        inner = 1\n"
            "        PAR\n"
            "            SEQ\n"
            "                deepest = 3\n"
            "    SEQ\n"
            "        other = 2\n"
        )

        self.assertFalse(parser.diagnostics)
        root = program.statements[0]
        self.assertIsInstance(root, ParBlock)
        first_seq = root.statements[0]
        self.assertIsInstance(first_seq, SeqBlock)
        nested_par = first_seq.statements[1]
        self.assertIsInstance(nested_par, ParBlock)
        deepest_seq = nested_par.statements[0]
        self.assertIsInstance(deepest_seq, SeqBlock)
        deepest_assignment = deepest_seq.statements[0]
        self.assertIsInstance(deepest_assignment, Assignment)
        self.assertEqual(deepest_assignment.name, "deepest")
        self.assertIsInstance(root.statements[1], SeqBlock)

    def test_fork_core_and_host_targets_and_orphan_join_parse(self) -> None:
        program, parser = parse(
            "SEQ\n"
            "    fork worker_core em core(2):\n"
            "        print(1)\n"
            "    fork worker_host em host(\"computador_2\"):\n"
            "        print(2)\n"
            "    join worker_core, worker_host\n"
            "    join sem_fork\n"
        )

        self.assertFalse(parser.diagnostics)
        root = program.statements[0]
        self.assertIsInstance(root, SeqBlock)
        core_fork = root.statements[0]
        self.assertIsInstance(core_fork, ForkStmt)
        self.assertEqual(core_fork.task_name, "worker_core")
        self.assertEqual(core_fork.target_kind, "core")
        self.assertIsInstance(core_fork.target, NumberExpr)
        self.assertEqual(core_fork.target.value, "2")
        self.assertIsInstance(core_fork.body, SeqBlock)

        host_fork = root.statements[1]
        self.assertIsInstance(host_fork, ForkStmt)
        self.assertEqual(host_fork.task_name, "worker_host")
        self.assertEqual(host_fork.target_kind, "host")
        self.assertIsInstance(host_fork.target, StringExpr)
        self.assertEqual(host_fork.target.value, "computador_2")

        join = root.statements[2]
        self.assertIsInstance(join, JoinStmt)
        self.assertEqual(join.task_names, ("worker_core", "worker_host"))
        orphan_join = root.statements[3]
        self.assertIsInstance(orphan_join, JoinStmt)
        self.assertEqual(orphan_join.task_names, ("sem_fork",))


if __name__ == "__main__":
    unittest.main()
