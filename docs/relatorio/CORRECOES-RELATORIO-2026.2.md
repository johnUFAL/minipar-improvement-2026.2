# Correções aplicadas ao `RELATORIO-2026.2.md`

**Data:** 09/11/2026
**Escopo:** correções factuais e de consistência no relatório principal, com base na auditoria do código-fonte.
**Arquivo editado:** `docs/relatorio/RELATORIO-2026.2.md`
**Cópia integral corrigida:** `docs/relatorio/RELATORIO-2026.2-revisado.md`

Este documento registra cada alteração feita no relatório, com o texto anterior, o texto corrigido e a evidência no código.

---

## 1. Sintaxe de `seq`/`par`

**Seção:** §2 (linha 110) e §2.1 (linha 138)

**Antes:** o relatório afirmava que `SEQ`/`PAR` eram maiúsculos e **sem `:`**.

**Corrigido:** o relatório agora informa que `seq`/`par` são aceitos (inclusive em maiúsculas) e que o bloco aceita suíte indentada após `:` ou bloco entre `{ }`.

**Evidência:**
- `components/sintatico/c_sintatico.py:112-119` (`_match_block_keyword` aceita `seq`/`par` minúsculos).
- `components/sintatico/c_sintatico.py:121-126` (`_at_root_block`).
- `components/sintatico/c_sintatico.py:164-180` (`_suite` aceita `{ }`).
- Programas de aceitação usam `seq {`/`par {` (ex.: `programas_teste/t02_fatorial_fibonacci_par.mp:15-16`).

Também foram ajustadas as menções em §1 e a linha de aliases em §2.1, que passou a listar `SEQ`/`seq` e `PAR`/`par`.

---

## 2. Pseudocódigo do parser: assinatura de `Program`

**Seção:** §4 (linha 291)

**Antes:** `construir Program(declarations, bloco_raiz)`

**Corrigido:** `construir Program(statements) com declarações e bloco raiz`

**Evidência:**
- `components/sintatico/ast.py:309` — `Program` só possui `statements`.
- `components/sintatico/c_sintatico.py:904` — `Program(statements=tuple(statements))`.
- A tabela do próprio §4 já dizia `Program(statements)`; a correção elimina a contradição interna.

---

## 3. `parse_ints` / `list`: remoção da falsa correção

**Seções:** §8 (linha 484), §11.2 (linha 680) e §13 (linha 780)

**Antes:** o relatório afirmava que `parse_ints` foi corrigido para `vector<int64_t>` e que `list` era `vector<int64_t>`.

**Corrigido:** o relatório agora registra que `__parse_ints` retorna `std::vector<double>`, que `list` mapeia para `std::vector<double>` e que a correção para `int64_t` **está pendente**.

**Evidência:**
- `runtime/minipar_rt.hpp:488-496` — `inline std::vector<double> __parse_ints(...)`.
- `components/codegen/c_gerador_cpp.py:108` — `list` → `std::vector<double>`.
- `tests/unitarios/test_codegen.py:134-145` — verifica apenas `t0 = __parse_ints(texto);`, não o tipo de retorno.

---

## 4. Notas do UML em §10.1

**Seção:** §10.1 (linhas 596 e 598)

**Antes:** o relatório chamava as notas de "honestas" e repetia que os concretos não implementam os contratos e que o `DiagnosticBag` não está ligado ao semântico.

**Corrigido:** o relatório agora aponta explicitamente que `classes.puml` está defasado, lista os `TokenType` antigos, registra que `TabelaSimbolos` implementa `ITabelaSimbolos` e que `DiagnosticBag` está ligado ao `SemanticAnalyzer`. Também foi adicionada nota sobre a assinatura desatualizada de `CppCodeGenerator` em `tac_runtime.puml`.

**Evidência:**
- `docs/uml/classes.puml` — `TokenType` com `NUMBER`, `FUNC`, `THIS`, `SEND`, `RECEIVE`, `MATRIX`, `SEMICOLON`.
- `components/tabela_simbolos/c_tabela_simbolos.py:88` — `class TabelaSimbolos(ITabelaSimbolos)`.
- `components/semantico/c_semantico.py:342-343` — `self._diagnostics.report(diagnostic)`.
- `components/codegen/c_gerador_cpp.py:1036-1051` — `generate(tac, output_name, nivel_otimizacao="O2")`.

---

## 5. Narrativa de testes e revalidação

**Seção:** §11 (linha 606)

**Antes:** o relatório misturava a execução original com a revalidação de outra branch e apresentava as falhas de T1/assets CDN como se valessem para o checkout atual.

**Corrigido:**
- a soma dos tempos passou de ~2 min 34 s para ~1 min 34 s, coerente com o JSON versionado;
- a execução original `216 passed / 245,57 s` foi qualificada como **sem artefato versionado que a comprove**;
- a revalidação `247 passed, 8 failed, 8 skipped, 89 subtests, 81,03%` foi atribuída explicitamente à branch **`fix/quest_docs_minipar_2026`**, não à `main`;
- foi registrado que a `main` atual tem os assets do CodeMirror versionados localmente, de modo que a falha de CDN não se aplica a este checkout.

**Evidência:**
- `ANALISE-ISSUES-E-PLANO.md:3-15` — os números pertencem à branch `fix/quest_docs_minipar_2026`.
- `interfaces/web/frontend/static/vendor/codemirror/5.65.13/` — assets locais presentes.
- `docs/relatorio/resultados/testes_2026_2/testes_2026_2.json` — tempos versionados.

---

## 6. Tempos da tabela do §11

**Seção:** §11 (linhas 608-620)

**Antes:** tempos de 23,99 s a 14,84 s, somando ~2 min 34 s, sem correspondência com o JSON.

**Corrigido:** a coluna passou a usar os valores de `elapsed` do JSON versionado.

| Teste | Antes | Depois |
|---|---:|---:|
| T1 | 23,99 s | 15,30 s |
| T2 | 12,69 s | 7,61 s |
| T3 | 12,33 s | 7,30 s |
| T4 | 13,41 s | 7,31 s |
| T5 | 11,70 s | 7,48 s |
| T6 | 13,68 s | 7,35 s |
| T7 | 11,94 s | 7,49 s |
| T8 | 13,82 s | 8,18 s |
| T9 | 14,84 s | 8,57 s |
| T10 | 12,98 s | 8,77 s |
| T11 | 12,78 s | 9,12 s |

**Evidência:** `docs/relatorio/resultados/testes_2026_2/testes_2026_2.json` (campo `elapsed` de cada teste).

---

## 7. Entrada fixa do T5

**Seção:** §11 (linha 622)

**Antes:** a sequência tinha **19 valores**, embora o texto dissesse "16 linhas".

**Corrigido:** a sequência passou a ter os **16 valores** usados pelos testes:
`1 0 0 0 0 1 0 0 0 1 0 0 1 0 0 0`.

**Evidência:** `tests/programas/test_t05.py:20-23`.

---

## 8. Evidência do T1

**Seção:** §11.1 (linha 633)

**Antes:** `Servidor calculou: 12.0`

**Corrigido:** `Servidor respondeu: OK 12.0`

**Evidência:**
- `programas_teste/t01_multiterminal/t01_calculadora_servidor.mp:61` — saída atual do servidor.
- `docs/relatorio/resultados/testes_2026_2/t1.log:10` — log antigo, que ainda contém `Servidor calculou`.

---

## 9. Parágrafo de "correções necessárias no backend" (§11.2)

**Seção:** §11.2 (linha 680)

**Antes:** dizia que `parse_ints` foi corrigido e que ambas as correções estavam cobertas por `test_codegen.py`.

**Corrigido:** o item de `this.array[i]` permanece como corrigido; o item de `parse_ints` foi marcado como **pendente**, com a observação de que o teste existente verifica apenas o nome do helper.

---

## 10. Conclusão

**Seção:** §13 (linha 780)

**Antes:** "correções de backend registradas".

**Corrigido:** "correções de backend registradas (uma pendente: tipo de `parse_ints`)".

---

## Itens identificados na auditoria que **não** foram alterados neste arquivo

Estes pontos estão fora do `RELATORIO-2026.2.md`, mas continuam pendentes para consistência global:

1. `docs/relatorio/RELATORIO-TESTES-2026.2.md` §3.2 — descreve a resposta do T1 como `("", 0.0, 0.0, resultado)`; o protocolo real é `(status, resultado, 0.0, 0.0)`.
2. `docs/relatorio/RELATORIO-TESTES-2026.2.md` §5.1 — diz que não há cobertura mínima; §5.4 e o CI exigem 80%.
3. `components/controle/c_controle.py:122` — imprime `"Chamada do GCC (-O3)"`, mas o driver usa `-O2` por padrão.
4. `docs/uml/classes.puml` e `docs/uml/tac_runtime.puml` — fontes PlantUML continuam defasadas; o relatório agora as sinaliza, mas os arquivos não foram regenerados.
5. `.github/workflows/ci.yml:30` verifica `g++ -std=c++20`, enquanto o código gerado é compilado com C++17; convém explicar a diferença ou alinhar.

---

## Resumo

- **15 alterações** aplicadas em `RELATORIO-2026.2.md`.
- **Cópia integral corrigida** em `RELATORIO-2026.2-revisado.md`.
- Nenhuma alteração foi feita em código-fonte, testes, configuração ou nos demais documentos.
