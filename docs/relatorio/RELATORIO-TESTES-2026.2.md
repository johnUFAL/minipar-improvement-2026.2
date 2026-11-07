# Relatório de execução — 11 testes do MiniPar 2026.2

**Branch:** `testes`  
**Data da execução:** 06/11/2026  
**Ambiente:** Windows 10, Python 3.11.15, GCC 16.2.0 (MSYS2 UCRT64), clang 23.1.4  
**Escopo:** Testes 1 a 11 do compilador MiniPar. A interface didática **não** faz parte deste relatório.

---

## 1. Resultado geral

```text
11/11 testes passaram.
```

| Teste | Descrição | Modo | Tempo |
|---|---|---|---|
| T1 | Calculadora cliente-servidor | 2 processos, canal lógico | 23,99 s |
| T2 | Fatorial e Fibonacci em `par` | local | 12,69 s |
| T3 | Neurônio com classes | local | 12,33 s |
| T4 | Rede neural XOR | local | 13,41 s |
| T5 | Sistema de recomendação | local, 16 entradas | 11,70 s |
| T6 | Quicksort com classes | local, 1 entrada | 13,68 s |
| T7 | Quicksort iterativo | local | 11,94 s |
| T8 | Avaliação em 4 núcleos | local, `fork/core` | 13,82 s |
| T9 | 5 núcleos com Mandelbrot | local, `fork/core` | 14,84 s |
| T10 | 6 núcleos com dois fractais | local, `fork/core` | 12,98 s |
| T11 | Minicompilador ARMv7 | local | 12,78 s |

Os tempos incluem compilação e execução. A soma é de aproximadamente 2 min 34 s.

### 1.1 Suíte automatizada

```text
216 passed, 1 skipped, 40 subtests passed in 245.57s
```

O único teste ignorado é o de `taskset`, específico de Linux. A suíte inclui
os testes unitários, T1 multi-terminal, T8–T11 e os testes de integração do
compilador.

---

## 2. Como reproduzir

```powershell
# todos os 11 testes
.\.venv\Scripts\python.exe scripts\run_testes_2026_2.py

# apenas alguns
.\.venv\Scripts\python.exe scripts\run_testes_2026_2.py --only t1,t11

# somente o T1 multi-terminal
.\.venv\Scripts\python.exe scripts\run_multiterminal.py --operacao + --v1 7 --v2 5

# suíte pytest
.\.venv\Scripts\python.exe -m pytest -q
```

Logs por teste: `docs/relatorio/resultados/testes_2026_2/`  
Resumo JSON: `docs/relatorio/resultados/testes_2026_2/testes_2026_2.json`

---

## 3. Teste 1 — calculadora multi-terminal

### 3.1 Problema encontrado

O menu interativo do MiniPar (`python main.py` → opção 1) cria uma sessão e
mostra o progresso dos participantes, mas **apenas o terminal iniciador
compila e executa** o binário. Ele não inicia o segundo processo nem passa
`--como`/`--hosts`. Além disso, o `t01_calculadora.mp` original usa
`c_channel("127.0.0.1", 5101)`, que no runtime cria um **cliente**; o bloco
`par` chama `receive` em um canal que nunca chamou `ouvir`.

### 3.2 Solução

O T1 foi separado em dois programas em `programas_teste/t01_multiterminal/`:

- `t01_calculadora_servidor.mp` — executado com `--como computador_2`;
- `t01_calculadora_cliente.mp` — executado com `--como computador_1`.

O canal é único e bidirecional:

```minipar
c_channel dados computador_1 computador_2
```

O payload tem sempre quatro campos `(string, float, float, float)` para manter
aridade e tipos iguais nas duas direções. O servidor inicia primeiro e fica em
`LISTENING`; o cliente conecta e envia `(op, v1, v2, 0.0)`; o servidor responde
`("", 0.0, 0.0, resultado)`.

O runner `scripts/run_multiterminal.py`:

1. compila os dois programas;
2. aloca uma porta livre e escreve `minipar.hosts`;
3. inicia o servidor;
4. espera a porta entrar em `LISTENING` (sem consumir o `accept`);
5. executa o cliente com as entradas;
6. valida as duas saídas e encerra os processos.

### 3.3 Evidência

```text
===== SAIDA DO SERVIDOR =====
==== T1 Calculadora - servidor (computador_2) ====
Servidor recebeu: + 7.0 5.0
Servidor calculou: 12.0
Servidor enviou a resposta.

===== SAIDA DO CLIENTE =====
==== T1 Calculadora - cliente (computador_1) ====
Cliente enviou: + 7.0 5.0
Resultado: 12.0
```

---

## 4. Correções necessárias no compilador

Para os 11 testes passarem na branch `testes`, foram necessárias duas correções
no backend C++:

### 4.1 `parse_ints` retornava `vector<double>`

O tipo `list` é `std::vector<std::int64_t>`, mas `__parse_ints` retornava
`std::vector<double>`, quebrando o T6 na atribuição. A função passou a retornar
`std::vector<std::int64_t>` e a ler `std::int64_t`.

### 4.2 Atribuição em array de atributo de classe

O TAC de `this.array[i] = valor` gera:

```text
t0:list = getfield self, 0
t0[i] = valor
```

O codegen copiava `self->field_0` para `t0` e alterava a cópia, sem refletir no
objeto. Agora o codegen rastreia `getfield` e emite
`__minipar_array_set(self->field_0, i, valor)` diretamente. Isso corrigiu o
Quicksort com classes (T6).

Ambas as correções têm testes unitários em `tests/unitarios/test_codegen.py`.

---

## 5. Entradas fixas

| Teste | Entrada |
|---|---|
| T1 | `+`, `7`, `5` |
| T5 | `1 1 1 1 1 1 1 1 0 0 0 0 0 0 0 0` (16 linhas) |
| T6 | `10 -3 -40 80 70 -100` |
| T2, T3, T4, T7, T8–T11 | sem entrada |

As saídas de T2–T7 foram congeladas em
`tests/integracao/expected_results/` e são comparadas após normalização de
CRLF.

---

## 6. T8–T10 — fork/join em núcleos

- **T8:** 160 atividades em 4 núcleos; imprime benchmark e speedup.
- **T9:** 4 avaliadores + Mandelbrot ASCII no 5º núcleo.
- **T10:** 4 avaliadores + Mandelbrot + tapete de Sierpinski no 6º núcleo.

O runner não compara tempos exatos (variam por máquina); valida os marcos de
saída: total de atividades, cabeçalho do benchmark, número de núcleos e presença
dos fractais.

---

## 7. T11 — minicompilador ARMv7

O T11 gera tokens, AST, TAC, Assembly ARMv7, tabela de símbolos e resultados.
Saídas esperadas:

| Expressão | Resultado |
|---|---|
| `((2+4)*7)-(5*4)` | `22.0` |
| `((10 -8*7)+4)*2` | `-84.0` |
| `((2+4)*7)-(5*4)` | `22.0` |

Os três arquivos estão em `programas_teste/teste11/`:

- `expr1.arm`
- `expr2.arm`
- `expr3.arm`

Validação automática:

```bash
clang --target=armv7-none-eabi -x assembler -c programas_teste/teste11/expr1.arm -o expr1.o
```

Os três montam sem erro. A execução no CPUlator permanece manual: colar o
`.arm`, executar e conferir `r8` (22, -84, 22).

---

## 8. Limitações e pendências

1. **CPUlator manual:** a validação automática usa `clang`; falta o screenshot
   da execução no CPUlator.
2. **Speedup variável:** T8–T10 dependem do número de CPUs disponíveis; o
   runner valida a estrutura, não os valores exatos.
3. **Menu multi-terminal:** continua sendo um monitor de sessão. O runner
   scriptado é a forma recomendada para T1. O menu agora avisa e não tenta
   executar testes multi-terminal sozinho.
4. **Teste em duas máquinas reais:** o runner valida dois processos em
   `localhost`; para duas máquinas, basta apontar `computador_2` para o IP do
   servidor e liberar a porta no firewall.
5. **T1 original:** `t01_calculadora.mp` permanece como referência histórica,
   mas não é executável sozinho; o par em `t01_multiterminal/` é a versão
   válida.

---

## 9. Checklist

- [x] T1 multi-terminal com dois processos reais.
- [x] T2–T7 locais com entradas fixas e saídas esperadas.
- [x] T8–T10 com `fork/core` e validação de marcos.
- [x] T11 com resultados e três `.arm` validados por `clang`.
- [x] Runner único para os 11 testes.
- [x] Teste pytest do T1 multi-terminal.
- [x] Correções de `parse_ints` e array de atributo com testes unitários.
- [ ] Screenshot do CPUlator.
- [ ] Execução em duas máquinas reais (opcional nesta entrega).
