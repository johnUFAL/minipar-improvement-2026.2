from __future__ import annotations

import unittest
from pathlib import Path

from components.lexico import Lexer
from components.sintatico.ast import (
    ClassDecl,
    MethodCall,
    MethodDecl,
    NewExpr,
    PropertyAccess,
    PropertyAssign,
    SeqBlock,
    ThisExpr,
    VarDecl,
)
from components.sintatico.c_sintatico import Parser
from erros.diagnosticos import DiagnosticBag


def parse(source: str):
    diagnostics = DiagnosticBag(source)
    program = Parser(Lexer(source, diagnostics), diagnostics).parse()
    return program, diagnostics


class ObjectOrientedParserTests(unittest.TestCase):
    def test_acceptance_programs_parse(self) -> None:
        test_programs = Path(__file__).parents[2] / "programas_teste"
        for name in (
            "t03_neuronio.mp",
            "t04_rede_neural_xor.mp",
            "t05_recomendacao.mp",
            "t06_quicksort_classes.mp",
        ):
            with self.subTest(program=name):
                source = (test_programs / name).read_text(encoding="utf-8")
                _, diagnostics = parse(source)
                self.assertFalse(diagnostics.has_errors, diagnostics.format_text())

    def test_class_inheritance_constructor_parameters_and_chained_access(self) -> None:
        source = (
            "class Neuronio extends Base {\n"
            "    var ativacao: float = 0.0;\n"
            "    func init(valor: float) {\n"
            "        this.ativacao = valor;\n"
            "    }\n"
            "    func obter() -> float {\n"
            "        return self.normalizar().valor;\n"
            "    }\n"
            "}\n"
            "seq {\n"
            "    var n = new Neuronio(1.0);\n"
            "    n.obter();\n"
            "}\n"
        )

        program, diagnostics = parse(source)

        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        declaration = program.statements[0]
        assert isinstance(declaration, ClassDecl)
        self.assertEqual(declaration.superclass, "Base")
        attribute = declaration.attributes[0]
        self.assertEqual(attribute.name, "ativacao")
        initializer = declaration.methods[0]
        assert isinstance(initializer, MethodDecl)
        self.assertEqual(initializer.name, "init")
        self.assertEqual(initializer.params[0].name, "valor")
        self.assertEqual(initializer.params[0].type, "float")
        method = declaration.methods[1]
        self.assertEqual(method.return_type, "float")
        return_statement = method.body.statements[0]
        chained_access = return_statement.value
        assert isinstance(chained_access, PropertyAccess)
        assert isinstance(chained_access.object, MethodCall)
        assert isinstance(chained_access.object.object, ThisExpr)

        root = program.statements[1]
        assert isinstance(root, SeqBlock)
        instance = root.statements[0]
        assert isinstance(instance, VarDecl)
        assert isinstance(instance.init_value, NewExpr)
        self.assertEqual(instance.init_value.class_name, "Neuronio")

    def test_missing_method_parenthesis_reports_unexpected_closing_brace(self) -> None:
        source = "seq {\n    objeto.metodo(\n        1\n}\n"

        _, diagnostics = parse(source)

        missing_parenthesis = [
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.phase == "syntax" and "Esperado ')'" in diagnostic.message
        ]
        self.assertTrue(missing_parenthesis, diagnostics.format_text())
        self.assertEqual(
            (missing_parenthesis[0].line, missing_parenthesis[0].column),
            (4, 1),
        )

    def test_property_assignment_supports_chained_receiver(self) -> None:
        program, diagnostics = parse(
            "seq {\n"
            "    objeto.fabrica().campo = new Valor(3);\n"
            "}\n"
        )

        self.assertFalse(diagnostics.has_errors, diagnostics.format_text())
        root = program.statements[0]
        assert isinstance(root, SeqBlock)
        assignment = root.statements[0]
        assert isinstance(assignment, PropertyAssign)
        assert isinstance(assignment.object, MethodCall)
        self.assertEqual(assignment.object.method_name, "fabrica")


if __name__ == "__main__":
    unittest.main()
