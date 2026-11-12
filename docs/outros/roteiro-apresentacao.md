# Roteiro de apresentação — Compilador MiniPar 2026.2

> Documento de apoio para a apresentação do projeto **minipar-improvement 2026.2**
> (compilador da linguagem MiniPar: análise léxica/sintática/semântica → TAC → C++17 → binário).
>
> **Duração-alvo:** 22 min de exposição + 5 min de perguntas.
> **Apex:** 3 demos ao vivo (fases, erro semântico, paralelismo) + 2 diagramas.

| Material | Caminho |
|---|---|
| Relatório final (MD/DOCX/PDF) | `docs/relatorio/RELATORIO-2026.2-revisado2.{md,docx,pdf}` |
| Diagrama de atividades (fluxo de compilação) | `docs/uml/atividades_compilacao.png` (fonte: `.puml`) |
| Diagrama de classes conceitual | `docs/uml/classes_conceitual.png` (fonte: `.puml`) |
| Gramática (EBNF LL(1)) | `docs/gramatica.md` |
| Backlog / sprints | `docs/backlog.md` |
| Rede / `fork em host` | `docs/rede.md`, `minipar.hosts` |
| Código | `https://github.com/johnUFAL/minipar-improvement-2026.2` |

---

## 0. Antes de apresentar (15 min de preparo)

1. **Terminal limpo**, com o repo aberto na raiz (`minipar-improvement-2026.2`) e `python3`/`minipar` no PATH.
   Teste rápido: `minipar compilar programas_teste/t03_neuronio.mp --tokens | head -3`.
2. **Navegador aberto** em `http://127.0.0.1:5000/editor` (rode `python3 main.py` → opção 2 *web*).
   Deixe a aba do editor pronta com o T3 carregado.
3. **Slides em PDF e PNG** (caso o projetor não abra `.pptx`): diagrams exportados em PNG.
4. **Não dependa da rede**: o 2º computador é opcional (ver Bloco E). Se a rede do Yosemite/sala falhar, siga o plano de contingência do Apêndice 3.
5. Tenha à mão os números do Bloco G (11/11 testes, 15,62×, ~3,1×) — o professor anota número.

---

## 1. Pitch de 60 segundos (use se o tempo cair para 5 min)

> "MiniPar é uma linguagem de programação parallels que a turma 2026.2 implementou como
> **compilador completo**, não interpretador. O programa escrito em `.mp` passa por léxico,
> parser LL(1), análise semântica em duas passagens, vira código de três endereços (TAC),
> é transpilado para C++17 e compilado com `g++`, gerando um binário nativo.
> A partir daí, o programa roda de verdade em vários núcleos (`fork em core(N)`) e conversa
> por canais TCP com outra máquina (`fork em host`). Entregue também uma IDE web didática
> que mostra cada fase da compilação, e 11 testes de aceitação do enunciado — 11/11 passando."

Guarde esta frase para a abertura e para o encerramento.

---

## 2. Roteiro detalhado

### Bloco A — Abertura e enquadramento (1,5 min)

**Fala (sugestão):**

> "Bom dia. Somos a turma 2026.2 e o projeto é o *minipar-improvement 2026.2*, continuação da
> versão 2026.1. O objetivo do enunciado era implementar um compilador para a linguagem MiniPar
> — uma linguagem de scripting com sintaxe parecida com Python e **paralelismo explícito**.
> A 2026.1 já tinha o esqueleto do compilador; a nossa versão 2026.2 concentrou-se em fechar
> o enunciado: tipagem real, `do…while`, classes com construtor, canais tipados, execução em
> dois computadores e a IDE web.
>
> Vou mostrar três coisas: **o que a linguagem é**, **como o compilador é organizado** (com os
> diagramas que produzimos) e, principalmente, **a compilação funcionando ao vivo**."

**Não esqueça:** dizer o nome da equipe (5 integrantes da turma 2026.2) e o repositório.

---

### Bloco B — A linguagem MiniPar (2 min)

Mostre **um** exemplo curto na tela (não mais que 12 linhas). Sugestão: `programas_teste/t03_neuronio.mp`.

**Pontos para falar (1 frase cada):**

- **Sintaxe:** `if/elif/else`, `while`, `do…while`, `for x in …`, `break/continue`, funções com
  tipo de retorno (`-> float`), classes com `extends`, `new`, `self`, construtor `init`.
- **Tipagem:** `bool, int, float, string, char, list` + classes do usuário; `int → float` implícito,
  `/` sempre devolve `float`.
- **Concorrência em 3 palavras:** `seq { }` (sequencial), `par { }` (bloco paralelo),
  `fork t em core(N)` / `fork t em host("pc2")` + `join t`.
- **Comunicação:** `c_channel dados computador_1 computador_2` no topo + `canal.send(...)` /
  `canal.receive(...)` — o endereço real fica em `minipar.hosts`, sem recompilar.

**Frase de efeito:**

> "Repare que o paralelismo não é biblioteca: ele é **sintaxe**. `fork` é uma palavra-chave do
> analisador sintático, e o runtime decide se a thread vai para um núcleo (`core`) ou para outra
> máquina (`host`)."

**Se perguntarem sobre a gramática:** EBNF LL(1) completa em `docs/gramatica.md`; a BNF antiga
2026.1 está preservada em `docs/uml/BNF-grammaMiniPAR2026-1.md` para comparação.

---

### Bloco C — Arquitetura do compilador (4,5 min) — use os 2 diagramas

Abra `docs/uml/atividades_compilacao.png`.

**Fala:**

> "Este é o fluxo completo de compilação. Ele começa nas três entradas que temos — CLI, menu
> `main.py` e IDE web — e passa por seis fases. Cada fase tem um **código de saída próprio**:
> 2 para erro léxico, 3 sintático, 4 semântico, 5 na geração de TAC/C++, 6 no build, 7 na
> execução. Isso permite ao professor (e ao CI) saber *onde* a compilação parou sem ler log."

**Detalhe de cada fase (uma linha cada, sem medo de profundidade):**

1. **Léxico** — lexer com pilha de indentação: emite `NEWLINE/INDENT/DEDENT` (4 espaços; tab é erro).
2. **Sintático** — parser descendente recursivo LL(1) → AST (dataclasses frozen) + Visitor.
3. **Semântico** — 2 passagens: coleta (funções/classes/escopos) e depois verificação (tipos,
   herança, canais, `fork`/`join`); erros num `DiagnosticBag` com linha e coluna.
4. **TAC** — código de 3 endereços (`t0 = ...`), com executor e otimizador para a IDE.
5. **C++** — transpilação para C++17 (`-O2` padrão, aceita `O0`–`O3`) + runtime.
6. **Execução** — local, ou em dois computadores via Hub de Conexão.

**Atalhos de inspeção** (rodapé do diagrama): `--tokens`, `--ast`, `--tac`, `--emit-cpp` param
o pipeline na fase pedida — é exatamente o que vamos usar na demo.

Abra `docs/uml/classes_conceitual.png`.

**Fala:**

> "Aqui está o modelo conceitual, em quatro camadas: orquestração, front-end, back-end e runtime.
> Destaques: os **7 contratos ABC** em `components/interfaces.py` existem para permitir injeção de
> dependência e fakes nos testes; a **tabela de símbolos** guarda escopos aninhados com herança;
> e o runtime C++ — canais TCP tipados, afinidade por núcleo e worker remoto — é linkado junto
> com cada programa gerado."

**Honestidade intelectual (diga isso, é um ponto a favor):**

> "Um detalhe que vale registrar: no código atual, das implementações dos contratos, apenas a
> `TabelaSimbolos` herda de fato do seu ABC (`ITabelaSimbolos`). As demais classes satisfazem o
> contrato por tipagem estrutural. Por isso o diagrama marca essas relações como *segue o contrato*
> e não como herança — o modelo reflete o código, não a intenção."

---

### Bloco D — Demo ao vivo (6 min) — o coração da apresentação

> Regra: **não corra a demo**. Abra o terminal, digite devagar e comente cada linha de saída.

#### D1 — As fases (2 min)

```bash
# 1) léxico: tipo, lexema, linha e coluna
minipar compilar programas_teste/t03_neuronio.mp --tokens | head -12

# 2) sintático: a AST em JSON
minipar compilar programas_teste/t03_neuronio.mp --ast | head -30

# 3) TAC: código de três endereços
minipar compilar programas_teste/t03_neuronio.mp --tac | head -25

# 4) C++ gerado
minipar compilar programas_teste/t03_neuronio.mp --emit-cpp
head -20 programas_teste/t03_neuronio.cpp
```

**O que falar em cada uma:**

- **Tokens:** "note que `INDENT`/`DEDENT` são tokens de verdade, gerados pelo léxico — é isso que
  permite `if`/`else` com blocos por indentação."
- **AST:** "a AST é uma árvore de dataclasses imutáveis; o Visitor é o que percorre a árvore para
  gerar TAC — assim o parser não conhece o back-end."
- **TAC:** "três endereços: `t0`, `t1`…; cada temporário tem um tipo. Na IDE web, esse TAC é
  executado/otimizado **em memória** só para visualização — o binário C++ não muda por causa disso."
- **C++:** "isto vai virar um executável nativo. Repare que geramos C++17 com `-O2` e linkamos o
  runtime (`canal.cpp`, `paralelo.cpp`, `worker.cpp`)."

#### D2 — Build + execução real (1,5 min)

```bash
# fluxo completo: gera .tac, .cpp e o executável em output/
python3 main.py programas_teste/t03_neuronio.mp

# executa o binário nativo
./output/t03_neuronio
```

**Fala:**

> "Este é o T3 do enunciado: uma rede neural de um neurônio com peso e viés, 100 iterações
> com descida de gradiente. O programa foi **compilado para C++ e executado nativamente** —
> o `print` que vocês veem saiu do binário, não de um interpretador Python."

<details>
<summary>Alternativa pela CLI (se o professor preferir a CLI)</summary>

```bash
minipar compilar "$PWD/programas_teste/t03_neuronio.mp" -o "$PWD/output/t03_demo" --executar
```

Use **caminho absoluto**: no Linux, `driver_gcc.py` roda o `g++` com `cwd` = pasta do executável e
o caminho relativo do `.cpp` não é encontrado (bug conhecido — ver Apêndice 3).
</details>

#### D3 — Erro semântico com diagnóstico e código de saída (1 min)

```bash
cat > /tmp/erro.mp <<'EOF'
seq {
    var x : int = 10
    var y : int = "texto"
    print(x + y)
}
EOF

minipar compilar /tmp/erro.mp
echo "exit=$?"
```

**Saída esperada (verificada):**

```text
erro semântico [3:9]: Tipo incompativel em 'y': esperado int, recebido string.
  3 |     var y : int = "texto"
    |         ^

1 erro(s), 0 aviso(s)
exit=4
```

**Fala:**

> "O compilador não para com uma exceção: ele **acumula** diagnósticos — `DiagnosticBag` — com
> arquivo, linha, coluna e um trecho da origem, e devolve o **código de saída 4** (semântico).
> O mesmo `DiagnosticBag` atravessa léxico, sintático e semântico, então o aluno recebe todos os
> erros de uma vez em vez de um por execução."

#### D4 — Paralelismo de verdade (1,5 min) — *se houver tempo*

```bash
head -30 programas_teste/t08_avaliacao_4_nucleos.mp     # mostra fork ... em core(N) e join
python3 main.py programas_teste/t08_avaliacao_4_nucleos.mp
./output/t08_avaliacao_4_nucleos
```

**Fala:**

> "O T8 avalia quatro modelos em paralelo. No C++ gerado isso vira `std::thread` com afinidade
> de CPU; o `join` garante a barreira. Os benchmarks mediram speedup real: **3,1×** contra a
> versão sequencial, com meta de 2,5×."

---

### Bloco E — Execução em dois computadores (2 min) — *opcional, com plano B*

Explique (não precisa ter a segunda máquina ligada):

> "A parte mais ambiciosa do enunciado é executar o mesmo programa distribuído. O programa declara
> `c_channel dados computador_1 computador_2`; o runtime resolve esses nomes lógicos para IP e
> porta via `minipar.hosts`. O `fork ... em host("pc2")` faz o binário subir o `minipar_worker`
> na outra máquina e falar por **TCP com tipagem**: o protocolo é campo a campo, big-endian, e o
> runtime valida quantidade e tipos de cada mensagem — se o outro lado mandar algo errado, o erro
> é explícito, não memória corrompida."

**Se a rede estiver disponível:** mostre o vídeo/print do T1 (`python3 scripts/run_multiterminal.py --scenario all`)
e a página do Hub de Conexão na IDE web (sala + convite + par cliente/servidor).

**Se não estiver:** siga o Apêndice 3 (contingência).

---

### Bloco F — IDE web e gestão do projeto (1,5 min)

Abra `http://127.0.0.1:5000/editor`.

**Fala (apontando a tela):**

> "A IDE é Flask + JavaScript puro, **offline** (o CodeMirror está versionado localmente, sem CDN).
> Ela tem as sete fases do pipeline como abas: Código, Tokens, AST, Símbolos, TAC, C++ e Execução.
> O aluno colou o programa, vê o que cada fase produziu e baixa o `.exe`. Tem ainda página de Ajuda,
> página de benchmark com histórico, e o Hub de Conexão para o par cliente/servidor."

**Sobre gestão (1 frase):** "O projeto foi conduzido por sprints e backlog versionado
(`docs/backlog.md`), com issues e PRs — inclusive um *backlog de produto* com as histórias do
enunciado e o que ficou pendente."

---

### Bloco G — Testes, evidências e métricas (2 min)

Slide com números (todos versionados no repo):

| Métrica | Valor | Onde está a evidência |
|---|---|---|
| Testes de aceitação T1–T11 | **11/11 passaram** | `docs/relatorio/resultados/testes_2026_2/*.json` + logs |
| Suíte `pytest` | 339 passed, 3 skipped, 141 subtests (18 min 52 s) | `docs/relatorio/RELATORIO-TESTES-2026.2.md` |
| Cobertura mínima no CI | 80% (`pytest-cov`) | workflow do GitHub Actions |
| `ruff` + `mypy` | passam | idem |
| Speedup T4 (rede neural XOR) | **15,62×** (`0,0147 s` C++ vs `0,2292 s` Python) | `docs/relatorio/resultados/t04_tempo.json` |
| Speedup T8–T10 (paralelo) | **~3,1×** (meta > 2,5×) | `docs/relatorio/resultados/t08_t10_tempo.json` |
| Testes escritos | 369 funções de teste (195 unit, 138 integração, 25 programas, 11 runtime) | `tests/` |

**Fala:**

> "O ponto que eu gostaria de destacar: **nenhum resultado está só no relatório**. Cada speedup e
> cada saída de teste está em JSON versionado, com log por teste. O runner
> `scripts/run_testes_2026_2.py` recompila e reexecuta os 11 programas e compara com as saídas
> congeladas em `tests/integracao/expected_results/`."

---

### Bloco H — Limitações e trabalho futuro (2 min) — *não pule este bloco*

> "Não vou esconder as pendências, porque elas estão mapeadas no backlog:
>
> 1. `list.append`, `string.split` e `string.strip` passam na análise semântica, mas ainda **não
>    têm lowering completo** para TAC/C++ — os programas novos evitam esses builtins.
> 2. **Canais só podem ser declarados no topo** do programa (decisão documentada 15).
> 3. A execução de TAC na IDE é **simulada** (intercalação + FIFO em memória): serve para
>    visualizar, não representa paralelismo real nem rede.
> 4. O `fork em host` foi validado em **localhost**; a validação em duas máquinas reais ficou
>    pendente (T41), e o procedimento não está ainda registrado em `docs/rede.md`.
> 5. O botão *Baixar .exe* entrega só o executável do programa — o `minipar_worker` não vai junto.
>
> O que vem a seguir: lowering dos builtins de lista/string, recuperação de erro sintático mais
> rica, e a validação em duas máquinas com o procedimento documentado."

**Frase de fechamento do bloco:** "Prefiro listar cinco pendências reais a declarar dez
funcionalidades que não funcionam."

---

### Bloco I — Conclusão (1 min)

> "Para resumir: o MiniPar 2026.2 é um compilador **de verdade** — léxico, sintático LL(1),
> semântico em duas passagens, tabela de símbolos com escopos e herança, TAC de três endereços,
> transpilação para C++17, build com `g++` e execução nativa, com paralelismo por núcleo e por
> máquina. Ele tem IDE web, 11 testes de aceitação passando, suíte automatizada e benchmarks
> medidos.
>
> As duas etapas que eu gostaria de defender em particular são: o **código de saída por fase**,
> que é o que torna o compilador integrável a ferramentas, e o **runtime de canais tipados**,
> que é o que torna o paralelismo distribuído seguro para um aluno usar.
>
> Obrigado. Estou à disposição para perguntas."

---

## Apêndice 1 — Roteiro de slides (10 slides, 1 por bloco)

| # | Título | Conteúdo visual |
|---|---|---|
| 1 | Capa | título, equipe, repositório |
| 2 | O problema | MiniPar é paralela por sintaxe; 2026.1 → 2026.2 |
| 3 | A linguagem | tabela de recursos + 12 linhas de `.mp` |
| 4 | Arquitetura | `docs/uml/atividades_compilacao.png` (6 fases + códigos de saída) |
| 5 | Modelo conceitual | `docs/uml/classes_conceitual.png` (4 camadas + contratos) |
| 6 | Demo: as fases | prints de `--tokens`, `--ast`, `--tac`, `--emit-cpp` |
| 7 | Demo: build + erro | print do binário + print do diagnóstico (exit 4) |
| 8 | Paralelismo e rede | `fork core(N)` / `fork host("pc2")` / canal tipado |
| 9 | Qualidade | tabela de métricas (Bloco G) + backlog |
| 10 | Limitações e conclusão | 5 pendências + 2.defesas |

**Regra de ouro:** o slide 4 e 5 são os seus diagramas — deixe-os em PNG (não redesenhe no
PowerPoint), para manter a mesma linguagem visual do conjunto `docs/uml/`.

---

## Apêndice 2 — Perguntas prováveis do professor (e como responder)

1. **"Por que Python, se vocês geram C++?"**
   → "Python é só a *implementação do compilador* (didático, rápido de escrever). O *programa do
   aluno* é C++ nativo — T4 roda 15,62× mais rápido que a versão Python equivalente."

2. **"Como vocês garantem que o parser é LL(1)?"**
   → "A gramática está em `docs/gramatica.md` com FIRST/Follow de cada não-terminal. Existe **uma**
   exceção documentada: `simples_stmt` lê a expressão antes de decidir se era chamada ou
   atribuição, e a validação fica no semântico. Está escrito no relatório, não escondido."

3. **"Onde está a tabela de símbolos? Como funciona o escopo?"**
   → "`components/tabela_simbolos/c_tabela_simbolos.py` — pilha de escopos, `enter_scope/exit_scope`,
   busca no escopo atual e nos pais, e classes associate um escopo persistente aos membros, com
   busca em superclasses para método/atributo. O pseudocódigo está em
   `docs/pseudocodigo_tabela_simbolos.md`."

4. **"O TAC é de três endereços de verdade? E tem otimizador?"**
   → "Sim: temporários `t0..tn` tipados. O otimizador (`components/tac/otimizador_tac.py`) é
   didático e roda **na IDE, em memória**, só para visualização — o binário final é o C++ gerado
   direto do TAC, sem passar pelo otimizador."

5. **"Como vocês tratam erros? Dão mensagem boa?"**
   → "`DiagnosticBag` acumula tudo, com arquivo, linha, coluna e trecho da origem (mostrei o
   exemplo do `int` recebendo `string`). E cada fase tem código de saída próprio (2–7)."

6. **"Qual o gargalo/limitação atual do build?"**
   → Cite honestamente: lowering de builtins de lista/string pendente, canais só no topo,
   execução de TAC simulada, validação `fork host` em duas máquinas pendente.

7. **"Os canais TCP são seguros? E se a outra máquina mandar tipo errado?"**
   → "Não: o protocolo é big-endian campo a campo, e o runtime **valida** quantidade e tipos,
   com `static_assert` no número de campos e `std::runtime_error` em caso de divergência —
   falha explícita, não memória corrompida."

8. **"Como foi gerido o trabalho?"**
   → "Sprints e backlog versionado (`docs/backlog.md`), issues e PRs por fase, com revisão entre
   os 5 integrantes e a branch `main` como integração."

9. **"Isso roda em Windows?"**
   → "Sim — o driver detecta a plataforma: no Windows usa `-lws2_32` e gera `.exe`; no Linux usa
   `-pthread`. O `g++` vem do MSYS2/MinGW-w64."

10. **"Por que a IDE é sua, em Flask, e não em React?"**
    → "Para o projeto rodar **offline**, sem CDN e sem build de front-end: HTML + JS puro com o
    CodeMirror versionado. Menos dependência de instalação = mais chance de o professor rodar."

11. **"Vocês rodaram a suíte inteira antes de entregar?"**
    → "A suíte completa foi reexecutada antes das últimas mudanças (339 passed, 3 skipped,
    141 subtests, 18 min 52 s); depois dela, os 200 unitários e os testes novos passaram. A
    suíte completa não foi reexecutada até o fim após as últimas alterações — isso está escrito
    no relatório."

12. **"Qual foi a parte mais difícil?"**
    → Escolha **uma** e conte uma história curta: (a) manter a paridade entre o TAC e o C++ gerado
    com `self`/herança; ou (b) fazer `fork em host` funcionar com o runtime linkado no binário;
    ou (c) os `INDENT/DEDENT` do léxico obrigando o parser a ser LL(1) "de verdade".

---

## Apêndice 2.1 — Programas recomendados para a demo (tempos medidos nesta máquina)

### No console (CLI) — escolha 2 ou 3, nunca mais que isso

| Programa | O que evidencia | Compila | Executa | Saída-chave |
|---|---|---|---|---|
| `t07_quicksort_iterativo_tac.mp` | TAC **sem recursão** (pilha explícita) — o TAC mais legível | 6,1 s | 0,01 s | `Array ordenado: [5, 12, 33, 61, 98]` |
| `t02_fatorial_fibonacci_par.mp` | `seq`/`par` + recursão + funções | 7,4 s | 0,25 s | `Fatorial de 10: 3628800` |
| `t08_avaliacao_4_nucleos.mp` | `fork ... em core(N)` + **speedup medido ao vivo** | 7,1 s | 0,6 s | `0,46 s` sequencial → `0,12 s` paralelo (**≈3,8×**) |
| `t06_quicksort_classes.mp` | classes + `input()` (interação com o usuário) | 5,7 s | <0,1 s | `Vetor ordenado: [-100, -40, -3, 10, 70, 80]` |
| `t11_minicompilador_arm.mp` | **MiniPar gerando Assembly ARMv7** (o "efeito uau") | 11,5 s | <0,1 s | tokens/AST/TAC/Assembly + 3 arquivos `.arm` |
| `t01` (par cliente/servidor) | canal TCP entre dois processos | — | — | `Servidor recebeu: + 7.0 5.0` / `Resultado: 12.0` |

Comandos (o `main.py` é o caminho que **funciona**; a CLI com `-o` relativo quebra no Linux — Apêndice 3):

```bash
# TAC legível, sem compilar
minipar compilar programas_teste/t07_quicksort_iterativo_tac.mp --tac | head -25

# build + execução nativa
python3 main.py programas_teste/t07_quicksort_iterativo_tac.mp
./output/t07_quicksort_iterativo_tac

# speedup ao vivo
python3 main.py programas_teste/t08_avaliacao_4_nucleos.mp
./output/t08_avaliacao_4_nucleos

# entrada do usuário
echo "10 -3 -40 80 70 -100" | ./output/t06_quicksort_classes

# T1 em localhost (dois processos, canal TCP)
python3 scripts/run_multiterminal.py --scenario all
```

### Na interface (IDE web)

| Onde | O que mostrar | Verificado aqui |
|---|---|---|
| `/editor` | as **7 abas** do pipeline: Código, Tokens, AST, Símbolos, TAC, C++, Execução | `/editor` → 200 |
| aba **TAC** | o TAC do T7 e o seletor de otimização: o C++ é **regenerado** a partir do TAC otimizado, sem tocar no binário | idem |
| programa com erro | o IDE mostra o diagnóstico com linha/coluna em vez de stack trace | API: `{"line":3,"column":9,"phase":"semantic","severity":"error"}` |
| botão **Baixar .exe** | entrega um binário ELF real | HTTP 200, `application/octet-stream`, 118 KB |
| `/benchmark` | T4 (15,62×) e T8–T10 (~3,1×), histórico de 10 medições, export CSV | `/benchmark` → 200 |
| `/ajuda` e `/resultados` | documentação da linguagem e resultados medidos | 200 |
| Hub de Conexão | par cliente/servidor em duas máquinas | opcional |

### ⚠️ Não demonstre este programa

`programas_teste/teste_ascii_art_divertidapkrl.mp` **falha hoje** na geração do C++
(erro de tipo em `__minipar_array_set` ao indexar matriz 2D). Se o professor perguntar sobre
casos-limite, use-o como exemplo honesto de pendência — não como demo.

---

## Apêndice 3 — Plano de contingência (demo quebrou)

| Falha | O que fazer |
|---|---|
| `g++` não encontrado | `export CXX=/usr/bin/g++`; conferir `g++ --version` |
| Falha do `g++` com caminho relativo | usar caminho **absoluto** (`"$PWD/..."`) — é o bug do `cwd` do driver (Apêndice 2, item 6) |
| `minipar` não está no PATH | usar `python3 -m interfaces.command_line ...` ou `python3 main.py prog.mp` |
| Flask ausente / porta 5000 ocupada | `python3 main.py` → opção 1 (terminal) e seguir só a demo CLI; ou `flask --app app run --port 5050` |
| A segunda máquina não conecta | pular o Bloco E ao vivo e mostrar o print do T1 + `docs/rede.md` (é o que já está versionado) |
| A rede caiu no meio | mostrar os artefatos locais: `output/*.tac`, `output/*.cpp`, `output/<exe>` |
| A demo está lenta | cortar o Bloco E e o D4, e ir direto para o Bloco G (métricas) |

**Antes de qualquer coisa:** tenho uma captura de tela / print de cada saída no Bloco D. Se a
demo travar, deslize para o slide 7 (que tem os prints) e continue narrando.

---

## Apêndice 4 — Checklist final (5 min antes)

- [ ] `git status` limpo (só commits pushed) e `main` atualizada
- [ ] `minipar compilar ... --tokens` responde
- [ ] `python3 main.py programas_teste/t03_neuronio.mp` compila e `./output/t03_neuronio` roda
- [ ] Terminal com fonte monoespaçada e zoom legível
- [ ] PDF do relatório aberto para ir ao detalhe (Apêndice 2)
- [ ] Slides 4 e 5 são os PNG de `docs/uml/`
- [ ] Números do Bloco G anotados
- [ ] Celular silenciado, notebooks fechados (menos ruído visual)

---

## Apêndice 5 — Frases que fecham bem (escolha uma)

- "O que a gente queria provar era simples: um aluno escreve MiniPar, e o que sai é um binário
  nativo — com canais tipados e paralelismo real."
- "Os diagramas que-produzimos (fluxo de atividades e modelo conceitual) estão no repositório,
  na mesma pasta dos demais, e foram feitos a partir do código, não do enunciado."
- "Toda pendência que eu mencionei está escrita no backlog com responsável e prazo — nenhuma foi
  escondida no relatório."
