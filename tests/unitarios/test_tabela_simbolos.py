import unittest

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
        self.assertIs(table.lookup("item"), local_symbol)

        table.exit_scope()
        self.assertIs(table.lookup("item"), global_symbol)

    def test_exit_scope_keeps_root_scope(self):
        table = TabelaSimbolos()
        root_symbol = Symbol("item", "int")

        table.define(root_symbol)
        table.exit_scope()

        self.assertIs(table.lookup("item"), root_symbol)
        self.assertIsNone(table.lookup("missing"))


if __name__ == "__main__":
    unittest.main()
