import json
import unittest

from components.lexico.c_lexico import Lexer
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser
from components.tabela_simbolos import Symbol, TabelaSimbolos


class SymbolTableTests(unittest.TestCase):
    def test_define_lookup_and_duplicate_in_current_scope(self):
        table = TabelaSimbolos()
        global_symbol = Symbol("item", "int")

        self.assertTrue(table.define(global_symbol))
        self.assertIs(table.lookup("item"), global_symbol)
        self.assertFalse(table.define(Symbol("item", "string")))

    def test_nested_scope_shadows_and_restores_parent_symbol(self):
        table = TabelaSimbolos()
        global_symbol = Symbol("item", "int")
        local_symbol = Symbol("item", "string")
        table.define(global_symbol)

        table.enter_scope()
        self.assertIs(table.lookup("item"), global_symbol)
        self.assertTrue(table.define(local_symbol))
        shadowed_symbol = table.lookup("item")
        assert shadowed_symbol is not None
        self.assertEqual(shadowed_symbol.type, "string")
        self.assertEqual(shadowed_symbol.scope, "global/block")

        table.exit_scope()
        self.assertIs(table.lookup("item"), global_symbol)

    def test_exit_scope_keeps_root_scope(self):
        table = TabelaSimbolos()
        root_symbol = Symbol("item", "int")

        table.define(root_symbol)
        table.exit_scope()

        self.assertIs(table.lookup("item"), root_symbol)
        self.assertIsNone(table.lookup("missing"))

    def test_local_lookup_does_not_search_parent_scopes(self):
        table = TabelaSimbolos()
        global_symbol = Symbol("item", "int")
        table.define(global_symbol)

        table.enter_scope("function:work")

        self.assertIsNone(table.lookup_local("item"))
        self.assertIs(table.lookup("item"), global_symbol)

    def test_export_is_json_serializable_and_includes_scope_metadata(self):
        table = TabelaSimbolos()
        table.enter_scope("function:work")
        symbol = Symbol(
            "value",
            "int",
            category="parameter",
            line=4,
        )
        table.define(symbol)

        encoded = json.dumps(table.export())
        exported = json.loads(encoded)
        function_scope = exported["scopes"][1]

        self.assertEqual(function_scope["name"], "function:work")
        self.assertEqual(function_scope["symbols"][0]["category"], "parameter")
        self.assertEqual(function_scope["symbols"][0]["line"], 4)
        self.assertEqual(function_scope["symbols"][0]["scope"], function_scope["path"])

    def test_method_lookup_follows_superclass(self):
        table = TabelaSimbolos()
        base = Symbol(
            "Base",
            "Base",
            category="class",
            methods={"run": ("value",)},
        )
        child = Symbol(
            "Child",
            "Child",
            category="class",
            parent_class="Base",
        )
        table.define(base)
        table.enter_scope("class:Base")
        table.register_class_scope("Base", table.current_scope_path)
        method = Symbol(
            "run",
            "unknown",
            category="method",
            params=("value",),
            line=3,
        )
        table.define(method)
        table.exit_scope()
        table.define(child)
        table.enter_scope("class:Child")
        table.register_class_scope("Child", table.current_scope_path)
        table.exit_scope()

        inherited_method = table.lookup_method("Child", "run")
        assert inherited_method is not None
        self.assertEqual(inherited_method.name, method.name)
        self.assertEqual(inherited_method.scope, "global/class:Base")

    def test_semantic_analyzer_reports_duplicate_in_same_scope_only(self):
        same_scope = Parser(
            Lexer(
                "SEQ\n"
                "    value: int = 1\n"
                "    value: int = 2\n"
            )
        ).parse()
        analyzer = SemanticAnalyzer()

        self.assertFalse(analyzer.analyze(same_scope))
        self.assertTrue(
            any("ja declarado neste escopo" in item.message for item in analyzer.diagnostics)
        )

        nested_scopes = Parser(
            Lexer(
                "SEQ\n"
                "    value: int = 1\n"
                "    SEQ\n"
                "        value: int = 2\n"
            )
        ).parse()
        nested_analyzer = SemanticAnalyzer()

        self.assertTrue(nested_analyzer.analyze(nested_scopes))

    def test_semantic_analyzer_accepts_inherited_method_call(self):
        program = Parser(
            Lexer(
                "class Parent:\n"
                "    def run(value):\n"
                "        return value\n"
                "class Child extends Parent:\n"
                "    own: int = 1\n"
                "SEQ\n"
                "    child: Child = new Child()\n"
                "    child.run(1)\n"
            )
        ).parse()
        analyzer = SemanticAnalyzer()

        self.assertTrue(analyzer.analyze(program), analyzer.diagnostics)


if __name__ == "__main__":
    unittest.main()
