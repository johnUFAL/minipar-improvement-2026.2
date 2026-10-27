import unittest
from contextlib import redirect_stderr
from dataclasses import FrozenInstanceError
import json
from io import StringIO
from unittest.mock import patch

import components.sintatico.ast as ast_module
from components.codegen.driver_gcc import DriverGCC
from components.lexico.c_lexico import Lexer
from components.lexico.token import TokenType
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.ast import ASTNode
from components.sintatico.ast import BinaryExpr, ForkStmt, IfStmt, JoinStmt
from components.sintatico.c_sintatico import Parser
from components.sintatico.visitor import ASTPrinter, ASTVisitor, para_dict
from components.tac.executor_tac import TACExecutor


class ComponentTests(unittest.TestCase):
    def test_ast_visitor_traverses_tuple_children(self):
        program = Parser(
            Lexer("SEQ\n    print(42)\n")
        ).parse()
        visited: list[type[ASTNode]] = []

        class RecordingVisitor(ASTVisitor):
            def generic_visit(self, node: ASTNode) -> None:
                visited.append(type(node))
                super().generic_visit(node)

        RecordingVisitor().visit(program)

        self.assertEqual(
            visited,
            [
                type(program),
                type(program.statements[0]),
                type(program.statements[0].statements[0]),
                type(program.statements[0].statements[0].arguments[0]),
            ],
        )

    def test_ast_visitor_and_printer_cover_every_node_type(self):
        node_types = [
            value
            for value in vars(ast_module).values()
            if isinstance(value, type)
            and value is not ASTNode
            and getattr(value, "__module__", None) == ast_module.__name__
            and issubclass(value, ASTNode)
        ]
        program = ast_module.Program(
            statements=tuple(node_type() for node_type in node_types)
        )
        visited: list[type[ASTNode]] = []

        class RecordingVisitor(ASTVisitor):
            def generic_visit(self, node: ASTNode) -> None:
                visited.append(type(node))
                super().generic_visit(node)

        RecordingVisitor().visit(program)

        self.assertEqual(set(visited), set(node_types) | {ast_module.Program})
        printed = ASTPrinter().format(program).splitlines()
        self.assertEqual(len(printed), len(node_types) + 1)
        printed_node_names = {line.strip() for line in printed}
        self.assertTrue(
            all(node_type.__name__ in printed_node_names for node_type in node_types)
        )

    def test_ast_para_dict_matches_stable_snapshot(self):
        program = ast_module.Program(
            statements=(
                ast_module.SeqBlock(
                    statements=(
                        ast_module.PrintStmt(
                            arguments=(ast_module.NumberExpr(value="7"),)
                        ),
                    )
                ),
            )
        )

        snapshot = json.dumps(para_dict(program), separators=(",", ":"))

        self.assertEqual(
            snapshot,
            '{"tipo":"Program","line":1,"column":1,"tipo_inferido":null,'
            '"statements":[{"tipo":"SeqBlock","line":1,"column":1,'
            '"tipo_inferido":null,"statements":[{"tipo":"PrintStmt","line":1,'
            '"column":1,"tipo_inferido":null,"arguments":[{"tipo":"NumberExpr",'
            '"line":1,"column":1,"tipo_inferido":null,"value":"7"}]}]}]}',
        )

    def test_parser_preserves_columns_and_semantic_inferred_types(self):
        program = Parser(
            Lexer("SEQ\n    answer: int = 42\n    print(answer)\n")
        ).parse()
        declaration = program.statements[0].statements[0]
        literal = declaration.init_value
        printed_identifier = program.statements[0].statements[1].arguments[0]

        self.assertEqual((declaration.line, declaration.column), (2, 5))
        self.assertEqual((literal.line, literal.column), (2, 19))
        self.assertEqual((printed_identifier.line, printed_identifier.column), (3, 11))
        self.assertTrue(SemanticAnalyzer().analyze(program))
        self.assertEqual(literal.tipo_inferido, "int")
        self.assertEqual(printed_identifier.tipo_inferido, "int")
        with self.assertRaises(FrozenInstanceError):
            literal.column = 3  # type: ignore[misc]

    def test_parser_builds_typed_parameter_attribute_and_method_nodes(self):
        source = (
            "def scale(value: float = 1.5) -> float:\n"
            "    return value\n"
            "class Box:\n"
            "    value: int = 0\n"
            "    def get(offset: int) -> int:\n"
            "        return self.value\n"
            "SEQ\n"
            "    print(1)\n"
        )
        parser = Parser(Lexer(source))
        program = parser.parse()

        self.assertFalse(parser.diagnostics)
        function = program.statements[0]
        parameter = function.params[0]
        self.assertEqual(parameter.name, "value")
        self.assertEqual(parameter.type, "float")
        self.assertIsInstance(parameter.default_value, ast_module.NumberExpr)
        self.assertEqual(function.return_type, "float")
        class_decl = program.statements[1]
        self.assertIsInstance(class_decl.attributes[0], ast_module.AttributeDecl)
        method = class_decl.methods[0]
        self.assertIsInstance(method, ast_module.MethodDecl)
        self.assertEqual(method.params[0].name, "offset")
        self.assertEqual(method.return_type, "int")

    def test_semantic_diagnostics_include_ast_column(self):
        program = Parser(Lexer("SEQ\n    print(missing)\n")).parse()
        analyzer = SemanticAnalyzer()

        self.assertFalse(analyzer.analyze(program))
        self.assertEqual(analyzer.diagnostics[0].column, 11)

    def test_semantic_inference_marks_boolean_operator_nodes(self):
        program = Parser(
            Lexer("SEQ\n    print(not true and false)\n")
        ).parse()
        expression = program.statements[0].statements[0].arguments[0]

        self.assertTrue(SemanticAnalyzer().analyze(program))
        self.assertEqual(expression.tipo_inferido, "bool")
        self.assertEqual(expression.left.tipo_inferido, "bool")

    def test_lexer_preserves_token_position(self):
        tokens = Lexer("total: int = 12\n").tokenize()
        self.assertEqual(tokens[0].type, TokenType.IDENTIFIER)
        self.assertEqual((tokens[0].line, tokens[0].column), (1, 1))
        self.assertEqual(tokens[-1].type, TokenType.END_OF_FILE)

    def test_semantic_analyzer_accepts_declared_variable(self):
        program = Parser(
            Lexer("SEQ\n    answer: int = 42\n    print(answer)\n")
        ).parse()
        self.assertTrue(SemanticAnalyzer().analyze(program))

    def test_ast_nodes_and_collections_are_immutable(self):
        program = Parser(
            Lexer("SEQ\n    values: list = [1, 2]\n    print(values)\n")
        ).parse()
        block = program.statements[0]
        declaration = block.statements[0]
        literal = declaration.init_value

        with self.assertRaises(FrozenInstanceError):
            program.statements = ()  # type: ignore[misc]
        with self.assertRaises(AttributeError):
            block.statements.append(declaration)  # type: ignore[attr-defined]
        with self.assertRaises(AttributeError):
            literal.elements.append(literal.elements[0])  # type: ignore[attr-defined]
        with self.assertRaises(FrozenInstanceError):
            literal.elements[0].value = "changed"  # type: ignore[misc]

    def test_every_ast_dataclass_is_frozen(self):
        ast_types = [
            value
            for value in vars(ast_module).values()
            if isinstance(value, type)
            and getattr(value, "__module__", None) == ast_module.__name__
        ]
        ast_node_types = [
            ast_type
            for ast_type in ast_types
            if issubclass(ast_type, ast_module.ASTNode)
        ]
        self.assertTrue(ast_node_types)
        self.assertTrue(
            all(ast_type.__dataclass_params__.frozen for ast_type in ast_node_types)
        )

    def test_tac_executor_runs_assignments_and_branches(self):
        program = """count = 0
LOOP:
count = count + 1
ifFalse count < 3 goto END
print count
goto LOOP
END:
"""
        variables, output = TACExecutor().execute(program)
        self.assertEqual(variables["count"], 3)
        self.assertEqual(output, ["1", "2"])

    def test_parser_consumes_tokens_lazily(self):
        lexer = Lexer("SEQ\n    x = 1\n")
        program = Parser(lexer).parse()
        self.assertEqual(len(program.statements), 1)
        self.assertIsInstance(program.statements[0], ast_module.SeqBlock)

    def test_parser_uses_operator_precedence_and_builds_elif_chain(self):
        source = (
            "SEQ\n"
            "    if a:\n"
            "        print(1)\n"
            "    elif b:\n"
            "        print(2)\n"
            "    elif c:\n"
            "        print(3)\n"
            "    else:\n"
            "        print(4)\n"
            "    print(1 + 2 * 3)\n"
        )
        lexer = Lexer(source)
        parser = Parser(lexer)
        program = parser.parse()

        self.assertFalse(parser.diagnostics)
        block = program.statements[0]
        self.assertIsInstance(block, ast_module.SeqBlock)
        conditional = block.statements[0]
        self.assertIsInstance(conditional, IfStmt)
        self.assertIsInstance(conditional.else_branch, IfStmt)
        self.assertIsInstance(conditional.else_branch.else_branch, IfStmt)
        printed = block.statements[1].arguments[0]
        self.assertIsInstance(printed, BinaryExpr)
        self.assertEqual(printed.op, "+")
        self.assertIsInstance(printed.right, BinaryExpr)
        self.assertEqual(printed.right.op, "*")

    def test_parser_builds_fork_and_join_nodes(self):
        source = (
            "SEQ\n"
            "    fork worker em core(2):\n"
            "        print(1)\n"
            "    join worker\n"
        )
        parser = Parser(Lexer(source))
        program = parser.parse()

        self.assertFalse(parser.diagnostics)
        block = program.statements[0]
        self.assertIsInstance(block.statements[0], ForkStmt)
        self.assertEqual(block.statements[0].task_name, "worker")
        self.assertIsInstance(block.statements[1], JoinStmt)
        self.assertEqual(block.statements[1].task_names, ("worker",))

    @patch("components.codegen.driver_gcc.shutil.which", return_value=None)
    def test_missing_cpp_compiler_fails_without_traceback(self, _which):
        stderr = StringIO()
        with redirect_stderr(stderr):
            result = DriverGCC().compile("program.cpp")
        self.assertFalse(result)
        self.assertIn("Compilador C++", stderr.getvalue())
        self.assertIn("nao encontrado", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
