import json
import unittest

from erros import ColetorDiagnosticos, Diagnostico, Fase, Severidade

FONTE = "x = 1\nif (x > 0 else\n    y = @\nprint(z\n"


class DiagnosticosTests(unittest.TestCase):
    def test_formato_do_exemplo_da_issue(self):
        c = ColetorDiagnosticos("a\nb\nif (x > 0 else\n")
        c.erro(Fase.SINTATICO, "esperado ')' mas encontrou 'else'", 3, 12, 4)
        saida = c.formatar_texto().splitlines()
        self.assertEqual(
            saida[0], "erro sintático [3:12]: esperado ')' mas encontrou 'else'"
        )
        self.assertEqual(saida[1], "  3 | if (x > 0 else")
        self.assertEqual(saida[2], "    |            ^~~~")  # caret sob o 'e' de else

    def test_tres_erros_de_fases_diferentes_juntos(self):
        c = ColetorDiagnosticos(FONTE)
        c.erro(Fase.LEXICO, "caractere inesperado '@'", 3, 9)
        c.erro(Fase.SINTATICO, "esperado ')' mas encontrou 'else'", 2, 12, 4)
        c.erro(Fase.SEMANTICO, "variável 'z' não declarada", 4, 7)
        self.assertEqual(len(c), 3)
        self.assertTrue(c.tem_erros())
        texto = c.formatar_texto()
        for trecho in ("erro léxico [3:9]", "erro sintático [2:12]", "erro semântico [4:7]"):
            self.assertIn(trecho, texto)
        self.assertTrue(texto.endswith("3 erro(s), 0 aviso(s)"))
        # ordem de inserção preservada
        self.assertEqual([d.fase for d in c], [Fase.LEXICO, Fase.SINTATICO, Fase.SEMANTICO])

    def test_json_estavel_para_a_api(self):
        c = ColetorDiagnosticos(FONTE)
        c.erro(Fase.SINTATICO, "esperado ')'", 2, 12, 4)
        dados = json.loads(c.para_json())
        self.assertTrue(dados["tem_erros"])
        self.assertEqual(
            dados["diagnosticos"][0],
            {
                "fase": "sintático",
                "severidade": "erro",
                "linha": 2,
                "coluna": 12,
                "comprimento": 4,
                "mensagem": "esperado ')'",
                "trecho": "if (x > 0 else",
            },
        )

    def test_aviso_nao_conta_como_erro(self):
        c = ColetorDiagnosticos()
        c.adicionar(Diagnostico(Fase.SEMANTICO, "variável não usada", 1, 1,
                                severidade=Severidade.AVISO))
        self.assertFalse(c.tem_erros())
        self.assertEqual(len(c), 1)

    def test_sem_fonte_ou_linha_fora_do_arquivo_nao_quebra(self):
        c = ColetorDiagnosticos("so uma linha")
        c.erro(Fase.SINTATICO, "fim inesperado", 9, 1)  # EOF além da última linha
        c.erro(Fase.EXECUCAO, "divisão por zero")       # sem posição
        texto = c.formatar_texto()
        self.assertIn("erro sintático [9:1]: fim inesperado", texto)
        self.assertIn("erro execução: divisão por zero", texto)
        self.assertNotIn("^", texto)

    def test_caret_preserva_tab_no_recuo(self):
        c = ColetorDiagnosticos("\tx = @")
        c.erro(Fase.LEXICO, "caractere inesperado", 1, 6)
        self.assertIn("|\t", c.formatar_texto().splitlines()[1].replace("| ", "|"))

    def test_coletor_vazio(self):
        c = ColetorDiagnosticos()
        self.assertFalse(c.tem_erros())
        self.assertEqual(c.formatar_texto(), "")


if __name__ == "__main__":
    unittest.main()