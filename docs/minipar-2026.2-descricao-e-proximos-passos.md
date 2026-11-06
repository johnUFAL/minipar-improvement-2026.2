# MiniPar 2026.2 — Descrição do Projeto e Próximos Passos

> **Status em 06/11/2026:** Fases 1–5 concluídas (linguagem/runtime, Testes 8–10,
> Teste 11 com os três `.arm`, segunda interface Web e documentação/testes). A
> suíte completa está verde (226 passed, 1 skipped, 40 subtests). Restam a
> validação manual no CPUlator, os screenshots dessa execução e a publicação
> final no GitHub.
> Relatório em [`relatorio/RELATORIO-2026.2.md`](relatorio/RELATORIO-2026.2.md)
> e roteiro em [`relatorio/APRESENTACAO-2026.2.md`](relatorio/APRESENTACAO-2026.2.md).

**Disciplina:** Compiladores — COMP379  
**Professor:** Arturo Hernández Domínguez  
**Entrega do relatório, apresentação e sistema:** **11/11/2026 (quarta-feira)**  
**Reavaliação presencial:** 25/11/2026  
**Final presencial:** 02/12/2026  

**Repositório de trabalho:** `minipar-improvement-2026.2`  
**Referência 2026.1:** <https://github.com/luizwhirl/minipar-improvement>  
**Interface de referência:** <http://pesquisa06.lages.ifsc.edu.br/>  

---

## 1. Resumo executivo

O projeto consiste em evoluir o compilador da linguagem **MiniPar 2026.2**, orientada a objetos, mantendo a arquitetura baseada em **componentes de software** e acrescentando:

1. os **Testes 8, 9 e 10** de algoritmos paralelos com `fork`/`join`, alocação em **núcleos de CPU** ou em **computadores diferentes**;
2. o **Teste 11**, um minicompilador de expressões infixadas escrito em MiniPar, que gera **Assembly ARMv7** para o **CPULATOR** e salva a saída em arquivo `.arm`;
3. a **Segunda Interface Web**, didática, mantendo também a interface de terminal e a primeira interface Web (voltada ao desenvolvedor);
4. a atualização da gramática BNF, dos módulos do compilador, da documentação, dos diagramas UML e do relatório/apresentação.

O prazo é curto: **5 dias** entre 06/11 e 11/11/2026. O escopo precisa ser congelado e executado em fases curtas, com validação ao final de cada fase.

---

## 2. Material disponibilizado

Pasta de anexos:

`C:\Users\RianGaião\Downloads\2026.2-Compiladores-COMP379 – Sala de Aula_files`

| Arquivo | Conteúdo | Uso no projeto |
|---|---|---|
| `Projeto-Compilador-MiniPar2026-2-Atualizado.pdf` | Especificação completa (54 páginas): linguagem, BNF, Testes 1–10, requisitos da segunda interface, backlog, UML, relatório | **Documento principal de requisitos** |
| `Teste8-Avaliacao-Atividades-Versao-Uso-de-4Nucleos.py` | Algoritmo paralelo com 4 núcleos (160 atividades) | Base para `t08_*.mp` |
| `Teste9-5Nucleos-4Avaliadores-UmFractal.py` | 4 avaliadores + Mandelbrot ASCII em 5 núcleos | Base para `t09_*.mp` |
| `Teste10-Nucleos-AvaliacaoAtiv-e-2Fractais.py` | 4 avaliadores + Mandelbrot + Sierpinski em 6 núcleos | Base para `t10_*.mp` |
| `teste 11 minipar\MiniCompiladorCompleto_ARMv7.java.txt` | Minicompilador Java de expressões infixadas | **Referência do Teste 11** |
| `teste 11 minipar\Codigo-Assembly-ARMV7.arm.txt` | Assembly ARMv7 esperado para `((2+4)*7)-(5*4)` | Gabarito do `.arm` |
| `teste 11 minipar\Execucao-Saida-okRodounoCPULATOR.txt` | Saída completa: tokens, AST, TAC, Assembly, tabela e resultado | Gabarito da execução |
| `BNF-grammaMiniPAR2026-1.md` | Gramática BNF da versão 2026.1 | Base a ser revisada/complementada |
| `Relatório-MiniPar2025.1-Compiladores-Helio-10,0-InterfaceWeb.pdf` | Relatório com a interface Web 2025.1 | Referência histórica de interface |
| `RelatorioMinipar2026-1-Compilador-GeracaoCodigoExe-10,0-okokok.pdf` | Relatório da implementação 2026.1 | Referência da arquitetura atual |
| `Elementos de Implementacao Utilizando Componentes-ok-next -ok.pdf` | Modelagem com componentes e interfaces | Base para a UML de componentes |
| `Modelagem-do-Interpretador2025.1-usandoComponentes de Software.pdf` | Modelagem do interpretador 2025.1 | Referência de modelagem |
| `Minipar - 2024-1-Thiago Ribeiro-10.pdf` | Trabalho anterior | Referência histórica |
| `link na Web-Compilador-Full-Educacional.txt` | Link do compilador educacional | Referência visual da segunda interface |
| `2026.2-Compiladores-COMP379 – Sala de Aula.html` | Stream do Classroom | Contém o post do Teste 11 e o lembrete de entrega |

### 2.1 O que o HTML do Classroom acrescenta

- Post de **05/10/2026** com o **Teste 11** e os três anexos.
- Post de **03/11/2026** com o prazo: **11/11/2026**, exigindo “todos os testes solicitados bem sucedidos” e a “Nova Segunda Interface Web solicitada funcionando ok”.
- Post com as datas de **Reavaliação (25/11)** e **Final (02/12)**.

O HTML **não** traz uma especificação separada da segunda interface; essa especificação está no PDF do projeto, páginas 45–47.

---

## 3. Requisitos consolidados

### 3.1 Compilador

- Implementar em **Java, Python ou C++**, com **programação orientada a objetos**.
- Modelagem com **componentes de software** e **UML**.
- Componentes: analisador léxico, analisador sintático, analisador semântico, tabela de símbolos, gerador de TAC e gerador de código C++/C.
- Pipeline: fonte `.mp` → lexer → parser/AST → semântico → TAC → C++ → GCC → executável.
- Tratamento de erros com linha/coluna.
- Comentários com `#`.
- Precedência de operadores aritméticos.
- Instanciação de objetos, chamadas de métodos e recursão.
- Blocos `SEQ`, `PAR`, `fork`/`join`.
- `fork` com alocação em **núcleo** (`core(n)`) ou em **computador diferente** (`host("...")`).
- Canais `c_channel` com `send`/`receive` via sockets.
- Execução local (`localhost`) e, depois, com **dois computadores diferentes**.

### 3.2 Programas de teste

| Teste | Tema | Situação no repositório |
|---|---|---|
| T1 | Calculadora cliente-servidor com `c_channel` | Implementado (`t01_calculadora.mp`) |
| T2 | Fatorial e Fibonacci em `PAR` | Implementado (`t02_fatorial_fibonacci_par.mp`) |
| T3 | Neurônio com classes | Implementado (`t03_neuronio.mp`) |
| T4 | Rede neural XOR | Implementado (`t04_rede_neural_xor.mp`) |
| T5 | Sistema de recomendação | Implementado (`t05_recomendacao.mp`) |
| T6 | Quicksort recursivo com classes | Implementado (`t06_quicksort_classes.mp`) |
| T7 | Quicksort iterativo | Implementado (`t07_quicksort_iterativo_tac.mp`) |
| T8 | Avaliação de atividades em 4 núcleos | **Só existe o Python em `benchmarks/`; falta o `.mp`** |
| T9 | 5 núcleos: 4 avaliadores + Mandelbrot ASCII | **Só existe o Python em `benchmarks/`; falta o `.mp`** |
| T10 | 6 núcleos: avaliação + Mandelbrot + Sierpinski | **Só existe o Python em `benchmarks/`; falta o `.mp`** |
| T11 | Minicompilador de expressões infixadas + Assembly ARMv7 | **Não implementado** |

### 3.3 Teste 11 — requisitos específicos

O programa MiniPar deve reproduzir o comportamento do Java:

1. ler uma expressão infixada;
2. gerar e imprimir os **tokens**;
3. construir e imprimir a **AST** no formato rotacionado (direita → raiz → esquerda);
4. gerar o **TAC** (`t1 = 2 + 4`, …);
5. gerar o **Assembly ARMv7** com `.global _start`, `.text`, `_start:`, `MOV`, `ADD`, `SUB`, `MUL` e `b .`;
6. imprimir a **tabela de símbolos**;
7. calcular e imprimir o **resultado final**;
8. **salvar o Assembly em arquivo `.arm`**.

Expressões e resultados esperados:

| Expressão | Resultado |
|---|---|
| `((2+4)*7)-(5*4)` | `22.0` |
| `((10 -8*7)+4)*2` | `-84.0` |
| `((2+4)*7)-(5*4)` | `22.0` |

O Assembly gerado deve ser colado no **CPULATOR** e executar com sucesso. O código de referência usa registradores `r0…rN` sequenciais e **não implementa divisão no Assembly** (emite `@ divisão não suportada`), embora calcule `/` na avaliação.

### 3.4 Interfaces

O projeto deve manter **três interfaces**:

1. **Terminal** (já existe).
2. **Primeira interface Web** (já existe, voltada ao desenvolvedor).
3. **Segunda interface Web** (nova, didática, para alunos iniciantes).

A segunda interface deve oferecer, no mínimo:

- botão **Tokens — Lexer**;
- botão **AST — Análise Sintática**;
- botão **Análise Semântica**;
- botão **TAC — Geração de Código de 3 Endereços**;
- botão **Código C++ gerado**;
- botão **Compilar e baixar o executável**;
- botão **Executar**.

Requisitos visuais:

- interface clara, limpa e não poluída;
- representação visual muito melhor da **AST** do que nas interfaces 2025.1 e 2026.1;
- árvore navegável, com zoom/pan, nós coloridos por categoria, tooltips e legenda;
- tabela de símbolos legível;
- TAC e C++ com realce de sintaxe;
- painel de execução com entrada/saída;
- mensagens de erro com linha, coluna e destaque no código.

A tela sugerida no PDF (página 46) tem:

- editor de código à esquerda;
- painel de saída à direita;
- opções de compilação em *checkboxes*: `Show Tokens`, `Show AST`, `Show Semantic`, `Show TAC`, `Show C Code`, `Show Assembly`;
- botões `Compile` e `Compile & Download .exe`.

A referência externa (<http://pesquisa06.lages.ifsc.edu.br/>) organiza o resultado em abas:

`TOKENS` · `ÁRVORE SINTÁTICA` · `TABELA DE SÍMBOLOS` · `LLVM IR` · `ASSEMBLY` · `EXECUÇÃO` · `COMPLEXIDADE DE ALGORITMO`

### 3.5 Relatório e apresentação

O PDF do projeto lista 17 itens que o relatório deve conter, entre eles:

- pseudocódigo do lexer, parser, semântico, tratamento de erros e tabela de símbolos;
- descrição das interfaces;
- product backlog e sprint backlog;
- diagramas UML de casos de uso, componentes e classes;
- testes de integração dos componentes;
- execução dos programas de exemplo com passo a passo das telas;
- tecnologias e ambiente de desenvolvimento;
- código-fonte, programas de teste e relatório no GitHub;
- link do repositório na capa do relatório.

---

## 4. Estado atual do repositório

### 4.1 O que já funciona

- Pipeline completo: fonte `.mp` → lexer → parser/AST → semântico → TAC → C++17 → GCC → executável.
- Backend C++17 com `g++` (GCC 16.2.0 no ambiente atual).
- Runtime com threads, canais, `fork`/`join`, afinidade de CPU e worker remoto.
- Gramática 2026.2 documentada em `docs/gramatica.md`.
- Interface de terminal (`main.py`, `interfaces/cli.py`).
- Primeira interface Web (`interfaces/web`, Flask, CodeMirror, porta 5000).
- Testes: **194 passed, 1 skipped, 28 subtests** (última execução registrada).
- Programas T1–T7 e testes adicionais em `programas_teste/`.
- Benchmarks Python T8–T10 em `benchmarks/`.
- Documentação UML em `docs/uml/`.

### 4.2 Lacunas

| Lacuna | Evidência | Impacto |
|---|---|---|
| T8–T10 não têm versão `.mp` | `programas_teste/` só tem T1–T7; `benchmarks/` tem só `.py` | Testes 8–10 não são executados pelo compilador MiniPar |
| T11 não existe | sem `t11_*.mp`, sem `.arm`, sem gerador ARM | Requisito do professor não atendido |
| Segunda interface Web não existe | só `interfaces/web` | Requisito de 11/11 não atendido |
| Sem `char_at`, `substring`, `is_digit`, `is_alpha`, `is_space` | sem builtins no semântico/runtime | Dificulta o lexer do T11 |
| Sem `write_file` | runtime só imprime em stdout | T11 não consegue salvar `.arm` sozinho |
| Indexação de string inconsistente | semântico diz `string`, codegen devolve `char&` | Comparações e atribuições podem falhar |
| `list.append`, `string.split`, `string.strip` declarados, mas não implementados no TAC/codegen | `components/tac/c_gerador_tac.py` não trata `list.append` | Evitar listas no T11 ou implementar o suporte |
| Relatório/UML ainda são 2026.1 | `docs/relatorio/` e `docs/uml/` | Precisa atualizar para 2026.2 |
| Sem screenshots do CPULATOR e da segunda interface | — | Necessário para o relatório/apresentação |

---

## 5. Arquitetura proposta

### 5.1 Pipeline

```text
fonte .mp
   │
   ▼
[Lexer] ──► tokens
   │
   ▼
[Parser] ──► AST
   │
   ▼
[Semântico + Tabela de Símbolos]
   │
   ▼
[Gerador TAC] ──► .tac
   │
   ▼
[Gerador C++17] ──► .cpp
   │
   ▼
[Driver GCC] ──► executável (.exe)
   │
   ▼
[Runtime] ──► threads, canais, fork/join, worker remoto
```

### 5.2 Componentes

| Componente | Arquivo | Responsabilidade |
|---|---|---|
| Léxico | `components/lexico/c_lexico.py` | tokens, indentação, strings, comentários |
| Sintático | `components/sintatico/c_sintatico.py` | parser descendente recursivo, AST |
| AST | `components/sintatico/ast.py` | nós da árvore |
| Semântico | `components/semantico/c_semantico.py` | tipos, escopos, builtins, erros |
| Tabela de Símbolos | `components/tabela_simbolos/c_tabela_simbolos.py` | símbolos e escopos |
| TAC | `components/tac/c_gerador_tac.py` | código de três endereços |
| Codegen C++ | `components/codegen/c_gerador_cpp.py` | tradução TAC → C++17 |
| Driver GCC | `components/codegen/driver_gcc.py` | compilação/link/execução |
| Runtime | `runtime/minipar_rt.hpp`, `runtime/paralelo.cpp`, `runtime/canal.cpp`, `runtime/worker.cpp` | builtins, threads, canais, remoto |
| Controle | `components/controle/c_controle.py` | orquestração do pipeline |

### 5.3 Teste 11 — arquitetura da aplicação

Criar `programas_teste/t11_minicompilador_arm.mp` com uma classe `MiniCompiladorARM` que contenha:

- `entrada`, `pos`, `temp_count`, `reg_count`, `tac`, `asm`, `simbolos`;
- `tokenizar()` — imprime tokens;
- `parse_expr()`, `parse_termo()`, `parse_fator()` — parser recursivo;
- AST serializada em **string prefixa** (ex.: `-*+2;4;7;*5;4;`);
- `imprimir_ast()`, `gerar_tac()`, `gerar_arm()`, `avaliar()`, `formatar()`;
- `write_file()` para salvar o `.arm`.

**Por que AST em string prefixa?** Porque o suporte atual a listas é limitado (`list` vira `vector<int64_t>` e `append` não está implementado no TAC/codegen). A AST prefixa usa apenas `string`, `int`, `float` e `bool`, que já funcionam.

**Builtins necessários:**

| Builtin | Assinatura | Uso |
|---|---|---|
| `char_at(texto, i)` | `string, int → string` | ler caractere |
| `substring(texto, inicio, fim)` | `string, int, int → string` | extrair lexema |
| `is_digit(c)` | `string → bool` | reconhecer número |
| `is_alpha(c)` | `string → bool` | reconhecer identificador |
| `is_space(c)` | `string → bool` | ignorar espaços |
| `write_file(caminho, conteudo)` | `string, string → int` | salvar `.arm` |

**Mudanças na BNF (opcional, mas recomendada):**

```ebnf
CHAR = "'" ( caractere | "\n" | "\t" | "\\" | "\'" ) "'" ;
primario = ... | CHAR | ... ;
tipo = ... | "char" ;
```

Se o literal de caractere não for adicionado, a BNF não precisa de novas produções: os builtins são chamadas de função já cobertas por `primario`. Nesse caso, a atualização da BNF fica na especificação dos builtins e na regra de indexação de string.

### 5.4 Segunda interface Web — arquitetura

Proposta de estrutura:

```text
interfaces/web2/
  app.py                # Flask da segunda interface (porta 5001)
  service.py            # reutiliza o pipeline e o runtime
  templates/index.html
  static/app.js
  static/style.css
```

Recursos:

- **Editor** MiniPar com realce de sintaxe.
- **Stepper didático**: Léxico → Sintático → Semântico → TAC → C++ → Executável.
- **Abas**: Tokens, AST, Semântica, TAC, C++, Assembly (T11), Execução.
- **Botões**: Tokens, AST, Análise Semântica, TAC, C++ gerado, Compilar e baixar `.exe`, Executar.
- **AST**: SVG com layout de árvore (D3.js), zoom/pan, nós coloridos, tooltips, legenda, expandir/recolher, exportar SVG/PNG.
- **Tokens**: tabela com tipo, lexema, linha, coluna e valor.
- **Semântica**: tabela de símbolos com nome, tipo, escopo, linha e valor; erros destacados.
- **TAC**: linhas numeradas, blocos básicos e tabela de temporários.
- **C++**: código com realce, copiar e baixar.
- **Execução**: campo de entrada padrão, stdout/stderr, código de saída e tempo.
- **Teste 11**: aba extra “Assembly ARM” com botão “Baixar `.arm`” e instruções para o CPULATOR.
- **Link** para a primeira interface (desenvolvedor) e para o terminal.

A primeira interface (`http://127.0.0.1:5000`) permanece como está. A segunda pode ser servida em `http://127.0.0.1:5001` ou em `/didatico` na mesma aplicação. Recomenda-se **porta separada** para deixar claro que são duas interfaces.

---

## 6. Próximos passos

### Fase 0 — Organização (06/11)

- Criar branch de trabalho (`feature/testes-8-11-interface-didatica`).
- Confirmar o escopo e as decisões pendentes da seção 10.
- Fazer backup do estado atual.
- Congelar a lista de entregáveis.

**Critério de conclusão:** branch criada e escopo aprovado.

### Fase 1 — Linguagem e runtime (06–07/11)

- Implementar `char_at`, `substring`, `is_digit`, `is_alpha`, `is_space`, `write_file`.
- Corrigir a indexação de string no codegen (`s[i]` → string de 1 caractere).
- Adicionar assinaturas no semântico e tipos de retorno.
- Opcional: literal de caractere `'x'` e tipo `char`.
- Criar testes unitários de runtime e de compilação.

**Critério de conclusão:** um programa MiniPar de teste usa todos os builtins e compila/executa.

### Fase 2 — Testes 8–10 (07–08/11)

- Converter os três Python de `benchmarks/` para MiniPar:
  - `t08_avaliacao_4_nucleos.mp`;
  - `t09_5_nucleos_1_fractal.mp`;
  - `t10_6_nucleos_2_fractais.mp`.
- Reescrever o que MiniPar não suporta:
  - f-strings → concatenação + `format_float`;
  - list comprehensions → laços;
  - `global` → atributo de classe;
  - `__import__` → `clock()`, `random()`;
  - `multiprocessing.Queue` → `c_channel`/`fork`/`join`;
  - Turtle → matriz ASCII (Sierpinski);
  - `& 0x7FFFFFFF` → `% 2147483648`.
- Usar `fork ... em core(n):` e `join ...`.
- Criar arquivos esperados de saída.
- Medir tempo sequencial e paralelo e registrar speedup.

**Critério de conclusão:** os três programas compilam, executam nos núcleos indicados e produzem a saída esperada.

### Fase 3 — Teste 11 (08–09/11)

- Criar `t11_minicompilador_arm.mp`.
- Implementar lexer, parser, AST, TAC, Assembly e avaliação.
- Gerar os três `.arm` em `programas_teste/teste11/`.
- Validar o Assembly com `clang --target=armv7-none-eabi -c` (quando disponível) e no CPULATOR.
- Criar teste de integração que executa o programa com as três expressões e compara a saída.
- Documentar a limitação de divisão no Assembly e o limite de registradores.

**Critério de conclusão:** as três expressões produzem `22.0`, `-84.0`, `22.0` e os `.arm` executam no CPULATOR.

### Fase 4 — Segunda interface Web (09–10/11)

- Criar `interfaces/web2/`.
- Implementar as abas e os botões exigidos.
- Implementar a AST com D3.js (árvore, zoom, tooltips, legenda).
- Implementar download do `.exe` e do `.arm`.
- Integrar a execução com entrada padrão.
- Adicionar link para a primeira interface.
- Testes com Flask test client.

**Critério de conclusão:** a segunda interface abre, compila um programa, mostra todas as fases, executa e baixa artefatos.

### Fase 5 — Validação e documentação (10/11)

- Rodar a suíte completa (`pytest -q`).
- Rodar os Testes 1–11.
- Rodar o teste remoto com dois computadores (ou localhost + worker).
- Capturar screenshots: terminal, web 1, web 2, CPULATOR, testes 8–10.
- Atualizar `docs/gramatica.md`, `README.md`, `docs/backlog.md`.
- Atualizar UML: componentes, classes, casos de uso, AST, TAC.
- Atualizar o relatório e os slides.

**Critério de conclusão:** suíte verde, documentação atualizada e material de apresentação pronto.

### Fase 6 — Entrega (11/11)

- Revisar o checklist da seção 11.
- Gerar o PDF final do relatório.
- Publicar no GitHub.
- Ensaiar a apresentação.
- Entregar.

---

## 7. Backlog detalhado

| ID | Tarefa | Prioridade | Estimativa | Depende de | Critério de aceite |
|---|---|---|---|---|---|
| L1 | `char_at` no runtime + semântico + testes | P0 | 2 h | — | programa de teste compila e lê caractere |
| L2 | `substring` | P0 | 2 h | L1 | extrai “123” de “a123b” |
| L3 | `is_digit`, `is_alpha`, `is_space` | P0 | 2 h | L1 | classificam caracteres corretamente |
| L4 | `write_file` | P0 | 2 h | — | grava arquivo e conteúdo |
| L5 | Corrigir indexação de string no codegen | P0 | 2 h | — | `s[i]` vira string de 1 caractere |
| L6 | Literal `'x'` e tipo `char` (opcional) | P1 | 3 h | L1 | BNF, lexer, parser, semântico e testes |
| T8 | Portar Teste 8 para MiniPar | P0 | 4 h | L1–L5 | 4 núcleos, saída e benchmark |
| T9 | Portar Teste 9 para MiniPar | P0 | 4 h | T8 | 5 núcleos + Mandelbrot ASCII |
| T10 | Portar Teste 10 para MiniPar | P0 | 4 h | T9 | 6 núcleos + 2 fractais |
| T11a | Lexer/parser/AST do T11 | P0 | 6 h | L1–L5 | tokens e AST iguais ao gabarito |
| T11b | TAC/Assembly/avaliação do T11 | P0 | 6 h | T11a | TAC e `.arm` corretos |
| T11c | `write_file` dos `.arm` | P0 | 1 h | L4, T11b | três `.arm` gerados |
| T11d | Validação no CPULATOR | P0 | 2 h | T11c | três execuções OK + screenshots |
| W2a | Backend da segunda interface | P0 | 6 h | — | endpoints de compilar/executar/baixar |
| W2b | Frontend e abas | P0 | 8 h | W2a | Tokens, AST, Semântica, TAC, C++, Execução |
| W2c | AST com D3.js | P0 | 6 h | W2b | árvore navegável, zoom, tooltips |
| W2d | Download `.exe` e `.arm` | P0 | 2 h | W2a | arquivos baixam corretamente |
| D1 | Atualizar BNF | P0 | 3 h | L1–L6 | builtins e regras novas documentados |
| D2 | Atualizar README/backlog | P1 | 2 h | T11, W2 | instruções completas |
| D3 | Atualizar UML | P0 | 4 h | W2 | componentes/classes/casos de uso |
| D4 | Atualizar relatório | P0 | 6 h | todas | PDF com 17 itens |
| D5 | Slides da apresentação | P0 | 4 h | D4 | roteiro de 10–15 min |
| V1 | Suíte completa | P0 | 2 h | todas | `pytest -q` verde |
| V2 | Teste remoto | P1 | 3 h | T8–T10 | dois processos/computadores |
| V3 | Screenshots | P0 | 2 h | T11, W2 | imagens no relatório |

---

## 8. Estratégia de testes

### 8.1 Testes unitários

- Lexer: tokens, strings, comentários, indentação.
- Parser: precedência, parênteses, classes, funções, `fork`/`join`.
- Semântico: tipos, escopos, builtins, erros.
- TAC: temporários, chamadas, arrays.
- Codegen: compilação C++ dos casos gerados.
- Runtime: builtins novos, canais, threads.

### 8.2 Testes de integração

- Compilar e executar T1–T7.
- Compilar e executar T8–T10, comparando saídas.
- Compilar e executar T11 com as três expressões.
- Validar `.arm` com `clang --target=armv7-none-eabi -c`.
- Mini-emulador Python para conferir o registrador final (`22`, `-84`, `22`).
- CPULATOR manual com screenshots.
- Flask test client para a segunda interface.
- Teste remoto com `worker` e `host("...")`.

### 8.3 Comandos

```powershell
# suíte completa
.\.venv\Scripts\python.exe -m pytest -q

# Teste 11
.\.venv\Scripts\python.exe main.py compilar programas_teste\t11_minicompilador_arm.mp -O2 -o output\t11 --executar

# Interface Web 1
.\.venv\Scripts\python.exe -m interfaces.web.api

# Interface Web 2
.\.venv\Scripts\python.exe -m interfaces.web2.app
```

---

## 9. Riscos e mitigação

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Prazo de 5 dias | Alta | Alto | congelar escopo; priorizar P0; não implementar backend ARM geral |
| `list.append` não implementado | Alta | Médio | evitar listas no T11; usar strings/classes |
| Indexação de string inconsistente | Alta | Médio | corrigir codegen e testar |
| AST grande e ilegível | Média | Alto | D3.js com zoom, colapso e tooltips |
| Teste 10 com Turtle | Alta | Médio | usar Sierpinski ASCII, como já feito no teste adicional |
| Speedup baixo ou negativo | Média | Médio | medir com carga real; documentar limitações |
| Execução remota falhar | Média | Alto | testar localhost primeiro; logs e timeouts |
| CPULATOR rejeitar o Assembly | Baixa | Alto | validar com `clang` e seguir o gabarito |
| Relatório incompleto | Média | Alto | checklist dos 17 itens; começar cedo |

---

## 10. Decisões pendentes

| # | Decisão | Recomendação |
|---|---|---|
| 1 | Teste 11: aplicação MiniPar (Opção A) ou backend ARM no compilador (Opção B)? | **Opção A**: o professor pediu o port do Java; o Assembly é gerado dentro da aplicação |
| 2 | Segunda interface em porta 5001 ou rota `/didatico`? | **Porta 5001**, para evidenciar duas interfaces Web |
| 3 | Adicionar literal de caractere `'x'` e tipo `char`? | **Sim**, é uma atualização visível da BNF e útil ao T11 |
| 4 | Divisão no Assembly do T11 | **Replicar o Java** (`DIV_UNSUPPORTED`) e documentar; os testes não usam `/` |
| 5 | Onde versionar os `.arm`? | `programas_teste/teste11/`, pois `output/` é ignorado pelo Git |
| 6 | Teste 10: Turtle ou ASCII? | **ASCII**, como no `teste_adicional2_tapete_sierpinski.mp` |
| 7 | Testes 8–10: usar `fork` com `core(n)` ou `host`? | `core(n)` para os benchmarks; `host` para o teste remoto |
| 8 | Primeira interface deve mudar? | **Não**: mantê-la como está; a segunda é a didática |

---

## 11. Checklist de entrega (11/11/2026)

- [ ] T1–T7 compilam e executam.
- [ ] T8–T10 em MiniPar compilam, executam e mostram benchmark.
- [ ] T11 em MiniPar compila, executa e gera os três `.arm`.
- [ ] Os três `.arm` rodam no CPULATOR.
- [ ] Segunda interface Web funciona com todos os botões.
- [ ] AST da segunda interface é visualmente superior à das interfaces anteriores.
- [ ] Primeira interface Web e terminal continuam funcionando.
- [ ] BNF atualizada em `docs/gramatica.md`.
- [ ] README atualizado.
- [ ] UML atualizada.
- [ ] Relatório com os 17 itens.
- [ ] Slides da apresentação.
- [ ] Screenshots de todas as telas.
- [ ] Suíte `pytest -q` verde.
- [ ] Código e relatório publicados no GitHub.
- [ ] Link do GitHub na capa do relatório.

---

## 12. Referências

- PDF do projeto: `Projeto-Compilador-MiniPar2026-2-Atualizado.pdf`.
- BNF 2026.1: `BNF-grammaMiniPAR2026-1.md`.
- Relatório 2025.1: `Relatório-MiniPar2025.1-Compiladores-Helio-10,0-InterfaceWeb.pdf`.
- Relatório 2026.1: `RelatorioMinipar2026-1-Compilador-GeracaoCodigoExe-10,0-okokok.pdf`.
- Componentes/UML: `Elementos de Implementacao Utilizando Componentes-ok-next -ok.pdf`.
- Teste 11: `teste 11 minipar/MiniCompiladorCompleto_ARMv7.java.txt`, `Codigo-Assembly-ARMV7.arm.txt`, `Execucao-Saida-okRodounoCPULATOR.txt`.
- Interface de referência: <http://pesquisa06.lages.ifsc.edu.br/>.
- Repositório 2026.1: <https://github.com/luizwhirl/minipar-improvement>.
