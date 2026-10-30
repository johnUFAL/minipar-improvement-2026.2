from __future__ import annotations

import unittest

from components.lexico import Lexer
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser
from erros.diagnosticos import DiagnosticBag


def analyze(source: str) -> SemanticAnalyzer:
    diagnostics = DiagnosticBag(source)
    program = Parser(Lexer(source, diagnostics), diagnostics).parse()
    if diagnostics.has_errors:
        raise AssertionError(diagnostics.format_text())
    analyzer = SemanticAnalyzer(diagnostics)
    analyzer.analyze(program)
    return analyzer


class SemanticObjectOrientedTests(unittest.TestCase):
    def test_resolves_inherited_attributes_and_methods_by_static_type(self) -> None:
        analyzer = analyze(
            "class Parent {\n"
            "    var value: int = 1;\n"
            "    func answer(argument: int) -> int {\n"
            "        return argument;\n"
            "    }\n"
            "    func getValue() -> int {\n"
            "        return this.value;\n"
            "    }\n"
            "}\n"
            "class Child extends Parent {\n"
            "    func answer(argument: int) -> int {\n"
            "        return argument;\n"
            "    }\n"
            "}\n"
            "seq {\n"
            "    var child = new Child();\n"
            "    var parent: Parent = new Child();\n"
            "    print(child.value);\n"
            "    print(parent.answer(1));\n"
            "    print(child.getValue());\n"
            "}\n"
        )

        self.assertFalse(analyzer.diagnostics, analyzer.diagnostics)

    def test_missing_method_reports_semantic_error(self) -> None:
        analyzer = analyze(
            "class Box {\n"
            "    var value: int = 1;\n"
            "}\n"
            "seq {\n"
            "    var box = new Box();\n"
            "    box.missing();\n"
            "}\n"
        )

        self.assertTrue(
            any("Metodo 'missing' nao declarado em 'Box'" in item.message
                for item in analyzer.diagnostics)
        )

    def test_circular_inheritance_reports_semantic_error(self) -> None:
        analyzer = analyze(
            "class A extends B {\n"
            "    var a: int = 1;\n"
            "}\n"
            "class B extends A {\n"
            "    var b: int = 1;\n"
            "}\n"
            "seq {\n"
            "    print(1);\n"
            "}\n"
        )

        self.assertTrue(
            any("Heranca circular detectada" in item.message
                for item in analyzer.diagnostics)
        )

    def test_constructor_checks_arity_and_argument_types(self) -> None:
        analyzer = analyze(
            "class Box {\n"
            "    func init(value: int) {\n"
            "        print(value);\n"
            "    }\n"
            "}\n"
            "seq {\n"
            "    var missing = new Box();\n"
            "    var wrong_type = new Box(\"text\");\n"
            "    var valid = new Box(1);\n"
            "}\n"
        )
        messages = [item.message for item in analyzer.diagnostics]

        self.assertTrue(any("espera 1 argumento(s), recebeu 0" in msg
                            for msg in messages))
        self.assertTrue(any("Tipo incompativel no argumento 1" in msg
                            for msg in messages))

    def test_self_is_only_valid_inside_class_methods(self) -> None:
        analyzer = analyze(
            "seq {\n"
            "    print(self);\n"
            "}\n"
        )

        self.assertTrue(
            any("'self' so pode ser usado dentro de metodos" in item.message
                for item in analyzer.diagnostics)
        )

    def test_incompatible_method_override_is_rejected(self) -> None:
        analyzer = analyze(
            "class Parent {\n"
            "    func answer(argument: int) -> int {\n"
            "        return argument;\n"
            "    }\n"
            "}\n"
            "class Child extends Parent {\n"
            "    func answer(argument: string) -> string {\n"
            "        return argument;\n"
            "    }\n"
            "}\n"
            "seq {\n"
            "    print(1);\n"
            "}\n"
        )

        self.assertTrue(
            any("Assinatura incompativel ao sobrescrever" in item.message
                for item in analyzer.diagnostics)
        )


if __name__ == "__main__":
    unittest.main()
