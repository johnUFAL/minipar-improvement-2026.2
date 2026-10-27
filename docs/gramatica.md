# Gramática Formal (EBNF) — Linguagem MiniPar 2026.2

**Issue:** Task 2 — Sprint 0 (Fundação e Arquitetura) · Labels: gramatica, decisao, documentacao, P0 · Depende de: #1
**Base:** BNF do relatório 2026.1 + enunciado 2026.2 (seção 2 e Observações 1–5).
**Status:** proposta para revisão. Itens abertos estão na seção 6.

---

## 1. Decisões de projeto

Cada decisão foi tomada uma vez, por escrito, porque léxico, parser, semântico e os dois geradores dependem delas.

| # | Decisão | Veredito | Justificativa |
|---|---------|----------|---------------|
| 1 | Blocos por indentação (`INDENT`/`DEDENT`) | **Aceita** | O enunciado diz "todas as instruções indentadas depois do SEQ/PAR" e permite sintaxe estilo Python. Os 10 testes originais são Python, então a tradução fica quase literal. Custo: o léxico precisa de uma pilha de indentação (a implementação 2026.1 usa `{ }` e `;`). |
| 2 | Tipos de valor: `bool`, `int`, `float`, `string`, `list` (mais classes do usuário) | **Aceita, com ajuste** | Testes 3–5 usam decimais (0.5, 0.01) e os Testes 4–7 usam listas. `float` e `list` entram como tipos nativos; matrizes são listas de listas. O enunciado lista `c_channel` como tipo, mas aqui o canal é uma **entidade nomeada** criada por `decl_canal`, não um valor: nenhuma expressão produz um canal, então um tipo `c_channel` ficaria sem uso (ver decisão 15). |
| 3 | Sem list comprehension, tuplas, `zip`, `enumerate`, f-strings, `try/except`, ternário | **Aceita** | Cada um exigiria produções ou regras semânticas próprias. Sem eles o parser continua descendente recursivo, sem ambiguidade. Tudo é reescrito com `while`/`for`, concatenação e builtins (seção 5). |
| 4 | Precedência: `or` < `and` < `not` < comparações < `+ -` < `* / %` < `-` unário < postfixo (`()`, `.`, `[]`) | **Aceita** | Segue a Observação 2 do enunciado. Um não-terminal por nível, associatividade à esquerda, e a árvore já sai com a precedência certa (útil para o TAC). |
| 5 | E/S: `print(...)` e `input()`; `sys.stdin.readline()` **não** vira alias | **Alterada** | `print` e `input` são palavras reservadas léxicas e builtins semânticos. Alias exigiria o conceito de módulo (`sys.stdin`) só para um sinônimo. Os programas de teste do enunciado usam `sys.stdin.readline()` apenas em comentário. `input()` cobre o caso. |
| 6 | Concorrência: `SEQ`, `PAR`, `fork`/`join`, `c_channel` com `.send()`/`.receive()` | **Aceita, com ajuste** | `fork t em core(n):` e `fork t em host("pc2"):` tornam a alocação parte da sintaxe, como o enunciado pede. A cláusula `em` é opcional (sem ela, o runtime escolhe). O `join` aceita lista de tarefas. |

**Decisões adicionais** (necessárias para fechar a gramática):

| # | Decisão | Por quê |
|---|---------|---------|
| 7 | Instanciação sempre com `new` (`n = new Neuronio(1, 0)`) | Diferencia chamada de função de criação de objeto já no primeiro token. Sem `new`, o parser precisaria consultar a tabela de símbolos. |
| 8 | Atributos declarados **no corpo da classe**, com valor inicial; o construtor é o método `init`; `self` referencia a instância | O gerador C++ precisa dos membros da classe antes de emitir qualquer método. Se os atributos nascessem por `self.x = ...` dentro do `init`, seria preciso varrer o corpo dos métodos para descobri-los. |
| 9 | Atribuição composta `+=`, `-=`, `*=`, `/=` | Quase todo teste usa `+=`. Custa uma linha na gramática e é açúcar sintático: o parser gera `x = x + ...`. |
| 10 | Parâmetros com tipo opcional e valor padrão literal; retorno com `-> tipo` opcional | Testes 3, 4 e 5 usam valores padrão (`peso_inicial=0.5`, `taxa_aprendizado=0.2`). Os tipos opcionais preenchem o `tipos_var` que estava como "…" no enunciado. |
| 11 | Quebra de linha dentro de `(` `)` e `[` `]` é ignorada pelo léxico; linhas em branco e só com comentário não geram `NEWLINE` | Necessário para listas e expressões em várias linhas (Teste 5) e evita que comentários quebrem a indentação. |
| 12 | `SEQ` e `PAR` em maiúsculas, sem `:`; demais palavras reservadas em minúsculas | O enunciado escreve `SEQ`/`PAR` sem dois-pontos. Os blocos `if/while/for/def/class` usam `:` como em Python. |
| 13 | Cada filho direto de `PAR` é uma thread; para agrupar várias instruções numa thread, usar `SEQ` aninhado | É o modelo que o enunciado descreve (Teste 2) e mantém a produção de `PAR` igual à de `SEQ`. |
| 14 | Um único bloco raiz (`SEQ` ou `PAR`) depois das declarações | O enunciado define `programa_minipar → bloco_stmt → bloco_SEQ \| bloco_PAR`. |
| 15 | Canais só existem via `decl_canal`, no topo do programa; `c_channel` **não** é tipo | Todos os testes (T1 e adicionais) declaram o canal no topo. Isso também remove o `c_channel(ip, porta)` como expressão do 2026.1. Limitação consciente: não é possível criar canal dentro de função/bloco. Se um teste futuro precisar, a gramática volta a ter `c_channel(...)` como expressão e `c_channel` entra em `tipo`. |
| 16 | Comparação **não** encadeia: `expr_comp = expr_arit [ op_rel expr_arit ]` | Em Python `a < b < c` significa `a < b and b < c`; se o parser aceitasse e montasse `(a < b) < c`, o programa mudaria de significado em silêncio. Como os testes vêm de Python, é melhor dar erro sintático. |
| 17 | `void` só aparece em retorno (`tipo_retorno`), nunca em parâmetro ou variável | Custa uma produção a mais e elimina uma checagem semântica. |
| 18 | Blocos e classes não podem ser vazios; não existe `pass` | `suite` e `decl_classe` exigem ao menos um membro/comando. Nenhum teste precisa de bloco vazio, e evita criar uma palavra reservada só para isso. |
| 19 | Construções do 2026.1 removidas: `do-while`, `for` estilo C, `var`, `dict`, `number`, `matrix`, `c_channel(ip, porta)` | `do-while` e `for` C são cobertos por `while` + `break` e `for … in range(...)`. `var` some porque a declaração é a primeira atribuição. `number` vira `int`/`float`. `matrix` vira lista de listas. `dict` não é usado por nenhum teste. Registrado para quem comparar com o BNF antigo. |

---

## 2. Léxico

**Tokens de estrutura:** `NEWLINE`, `INDENT`, `DEDENT`, `EOF`.
Indentação com 4 espaços por nível; tabulação é erro léxico (evita indentação ambígua).

**Palavras reservadas**

```
SEQ  PAR  fork  join  em  core  host  c_channel
class  extends  new  self  def  return
print  input
if  elif  else  while  for  in  break  continue
and  or  not  true  false
bool  int  float  string  list  void
```

**Literais e identificadores**

```ebnf
INT     = digito { digito } ;
FLOAT   = digito { digito } "." digito { digito } ;
STRING  = '"' { caractere | "\n" | "\t" | '\"' | "\\" } '"' ;
IDENT   = ( letra | "_" ) { letra | digito | "_" } ;
```

**Operadores:** `+ - * / %`  `== != < > <= >=`  `= += -= *= /=`  `->`
**Delimitadores:** `( ) [ ] . , :`
**Comentário:** `#` até o fim da linha (descartado pelo léxico).

---

## 3. Gramática EBNF completa

Notação: `{ x }` zero ou mais, `[ x ]` opcional, `( a | b )` agrupamento, `"t"` terminal, MAIÚSCULAS = token.

```ebnf
(* ── Programa ── *)
programa       = { decl_canal | decl_funcao | decl_classe } bloco_raiz EOF ;
bloco_raiz     = bloco_seq | bloco_par ;

(* ── Canais ── *)
decl_canal     = "c_channel" IDENT IDENT IDENT NEWLINE ;
                 (* c_channel <nome> <comp1> <comp2> *)

(* ── Funções ── *)
decl_funcao    = ("def" | "func") IDENT "(" [ params ] ")"
                 [ "->" tipo_retorno ] suite ;
params         = param { "," param } ;
param          = IDENT [ ":" tipo ] [ "=" literal ] ;
tipo           = "bool" | "int" | "float" | "string" | "list" | IDENT ;
tipo_retorno   = tipo | "void" ;

(* ── Classes ── *)
decl_classe    = "class" IDENT [ "extends" IDENT ] suite_classe ;
suite_classe   = ":" NEWLINE INDENT membro { membro } DEDENT
               | "{" { membro } "}" ;
membro         = decl_atributo | decl_metodo ;
decl_atributo  = [ "var" ] IDENT [ ":" tipo ] "=" expr fim_stmt ;
decl_metodo    = decl_funcao ;       (* o método "init" é o construtor *)

(* ── Blocos e concorrência ── *)
suite          = ":" NEWLINE INDENT stmt { stmt } DEDENT | "{" { stmt } "}" ;
fim_stmt       = NEWLINE | ";" ;
bloco_seq      = ("SEQ" | "seq") suite ;
bloco_par      = ("PAR" | "par") suite ;
fork_stmt      = "fork" IDENT [ "em" alocacao ] suite ;
alocacao       = "core" "(" expr ")"
               | "host" "(" ( STRING | IDENT ) ")" ;
join_stmt      = "join" IDENT { "," IDENT } fim_stmt ;

(* Para blocos indentados, suite começa com ":" NEWLINE INDENT.
   O destino core/host é preservado em ForkStmt.target_kind e target. *)

(* ── Comandos ── *)
stmt           = bloco_seq | bloco_par | fork_stmt | join_stmt
               | if_stmt | while_stmt | for_stmt
               | return_stmt | break_stmt | continue_stmt
               | simples_stmt ;

if_stmt        = "if" expr suite
                 { "elif" expr suite }
                 [ "else" suite ] ;
while_stmt     = "while" expr suite ;
for_stmt       = "for" IDENT "in" expr suite ;
return_stmt    = "return" [ expr ] fim_stmt ;
break_stmt     = "break" fim_stmt ;
continue_stmt  = "continue" fim_stmt ;

simples_stmt   = [ "var" ] IDENT [ ":" tipo ] "=" expr fim_stmt
               | expr [ ":" tipo "=" expr | op_atrib expr ] fim_stmt ;
op_atrib       = "=" | "+=" | "-=" | "*=" | "/=" ;
                 (* ver §4: o parser fatora o prefixo comum *)

(* ── Expressões (menor → maior precedência) ── *)
expr           = expr_or ;
expr_or        = expr_and  { ("or" | "||") expr_and } ;
expr_and       = expr_not  { ("and" | "&&") expr_not } ;
expr_not       = "not" expr_not | expr_comp ;
expr_comp      = expr_arit [ op_rel expr_arit ] ;   (* sem encadeamento, decisão 16 *)
op_rel         = "==" | "!=" | "<" | ">" | "<=" | ">=" ;
expr_arit      = expr_termo { ( "+" | "-" ) expr_termo } ;
expr_termo     = expr_unario { ( "*" | "/" | "%" ) expr_unario } ;
expr_unario    = "-" expr_unario | expr_posfixo ;
expr_posfixo   = primario { "." IDENT [ "(" [ args ] ")" ] | "[" expr "]" } ;

primario       = INT | FLOAT | STRING | "true" | "false" | ("self" | "this")
               | IDENT [ "(" [ args ] ")" ]
               | "new" IDENT "(" [ args ] ")"
               | lista
               | "(" expr ")" ;
lista          = "[" [ args ] "]" ;
args           = expr { "," expr } ;
literal        = [ "-" ] ( INT | FLOAT ) | STRING | "true" | "false" ;
```

**Chamada de método, envio e recebimento** são todos `expr_posfixo` seguido de `NEWLINE`:

```
neuronio.treinar()                       # chamada de método
calculadora.send(op, v1, v2)             # envio pelo canal
calculadora.receive(op, v1, v2)          # recepção: os argumentos são variáveis preenchidas
x = calculadora.receive()                # forma alternativa, como expressão
```

---

**Restrições conscientes** (aceitas pela gramática ou rejeitadas de propósito):

- `suite` e `decl_classe` exigem pelo menos um elemento (decisão 18).
- `decl_canal` só no topo (decisão 15).
- `join` é reconhecido sintaticamente independentemente de existir um `fork`
  correspondente; essa validação pertence à análise semântica.
- `a < b < c` é erro sintático (decisão 16).
- Parâmetros e variáveis não aceitam `void` (decisão 17).
- A semântica de "argumentos preenchidos" em `receive(a, b, c)` é regra do semântico, não da gramática (§6).
- `func`, `var`, `this`, `seq`/`par` minúsculos, chaves, `;`, `&&` e `||` são aliases de compatibilidade com os programas OO anteriores; `this` produz o mesmo nó AST que `self`, os operadores lógicos são normalizados para `and`/`or`, e `init` é o nome convencional do construtor.

---

## 4. Verificação de conflitos (LL(1))

A gramática é LL(1) com **uma** exceção (fatoração à esquerda em `simples_stmt`). Pontos de decisão verificados:

| Ponto | Lookahead | Como se resolve |
|-------|-----------|-----------------|
| `programa`: declaração ou bloco raiz | `c_channel` / `def` / `func` / `class` vs `SEQ` / `seq` / `PAR` / `par` | FIRST disjuntos |
| `membro` | `IDENT` / `var` (atributo) vs `def` / `func` (método) | FIRST disjuntos |
| `stmt` | palavra reservada vs `IDENT`/`self`/`new`/`(`/literal | FIRST dos comandos são palavras reservadas; o resto cai em `simples_stmt` |
| `if`: `elif` / `else` | `elif`, `else` | Sem *dangling else*: a indentação fecha o bloco (`DEDENT` precede `elif`/`else`) |
| `fork`: alocação opcional | `em` vs `:` | FIRST disjuntos |
| `alocacao` | `core` vs `host` | FIRST disjuntos |
| `decl_funcao`: retorno opcional | `->` vs `:` | FIRST disjuntos |
| `expr_comp`: operador opcional | `op_rel` | FIRST(op_rel) ∩ FOLLOW(expr_comp) = ∅ |
| `param` | `:` (tipo), `=` (padrão), `,`/`)` | FIRST disjuntos |
| `primario` com `IDENT` | `(` ou não | `[ "(" ... ")" ]` decidido por 1 token |
| Laços `{ ... }` em `suite` | `DEDENT` encerra | `DEDENT` ∉ FIRST(stmt) |
| `expr_*` | operador do nível | Recursão à esquerda eliminada com `{ }`; associatividade à esquerda no construtor da AST |

**Exceção 1 — `simples_stmt`.** Uma instrução pode começar com `expr` (chamada) ou com um alvo de atribuição (`x`, `self.peso`, `a[i]`), que também são `expr`. O parser lê a `expr` e só depois olha o próximo token (`=`, `+=`, `:` ou `NEWLINE`). A validação fica no semântico:

- sem sufixo → a `expr` deve ser chamada de função ou de método;
- com `op_atrib` → a `expr` deve ser identificador, acesso `.campo` ou índice `[ ]`;
- com `":" tipo "="` → a `expr` deve ser um identificador simples.

Escolhi isso em vez de duas produções por não precisar de lookahead ilimitado nem de backtracking.

**Exceção 2 — `INDENT`/`DEDENT`.** Não são caracteres da gramática: o léxico os produz comparando a indentação com uma pilha. Vários `DEDENT` seguidos fecham vários blocos de uma vez.

---

## 5. Cobertura dos programas de teste

> O enunciado tem 10 programas (Testes 1–10). Se os rótulos T32–T39 da issue forem a numeração do board, basta renomear a coluna.

### 5.1 Reescritas necessárias (o que não existe em MiniPar)

| Python | MiniPar | Por quê |
|--------|---------|---------|
| `return 1 if soma >= 0 else 0` | `if soma >= 0:` / `return 1` / `return 0` | sem ternário (decisão 3) |
| `f"Peso: {self.peso:.4f}"` | `"Peso: " + format_float(self.peso, 4)` | sem f-string |
| `[x for x in array[1:] if x <= pivot]` | laço `for` + `menores.append(x)` | sem comprehension |
| `a, b = stack.pop()` (tuplas) | duas listas de pilha, ou empilhar `inicio` e `fim` em sequência | sem tuplas |
| `arr[i], arr[j] = arr[j], arr[i]` | `tmp = arr[i]` / `arr[i] = arr[j]` / `arr[j] = tmp` | sem atribuição múltipla |
| `zip(entradas, saidas)` | `for i in range(len(entradas)):` | sem `zip` |
| `float('inf')` | `inf()` | builtin |
| `try/except ValueError` | `if is_number(token):` | sem exceções |
| `x & 0x7FFFFFFF` (LCG, Testes 8–10) | `x % 2147483648` | equivalente para inteiros não negativos; evita operadores bit a bit |
| variável global `_estado_random` | atributo de uma classe `Gerador` | sem `global`; vira atributo (decisão 8) |
| `__import__("time").perf_counter()` | `clock()` | builtin |

### 5.2 Builtins (não são sintaxe, são nomes pré-definidos no semântico)

`print`, `input`, `len`, `range`, `str`, `int`, `float`, `exp`, `random`, `inf`, `clock`, `format_float(x, casas)`, `is_number(s)`.
Métodos: lista → `append`, `pop`; string → `split`, `strip`; `c_channel` → `send`, `receive`.

### 5.3 Regras semânticas de tipos

- Funções e classes são coletadas antes da validação dos corpos, permitindo recursão e chamadas a funções declaradas posteriormente.
- Literais inteiros e decimais inferem, respectivamente, `int` e `float`; operações numéricas promovem o resultado para `float` quando algum operando é `float` (e `/` sempre produz `float`).
- A conversão implícita `int` → `float` é permitida; `float` → `int` exige conversão explícita.
- A primeira atribuição declara uma variável no escopo atual. Atribuições seguintes devem respeitar seu tipo.
- Condições devem ser booleanas; operadores aritméticos, lógicos e comparações validam os tipos dos operandos.
- Chamadas a funções e métodos verificam aridade e tipos dos argumentos. Funções com retorno declarado diferente de `void` devem retornar um valor compatível em todos os caminhos.

### 5.4 Construção usada em cada teste → produção

| Teste | Construção | Produção |
|-------|-----------|----------|
| **T1** Calculadora cliente-servidor | `c_channel calculadora computador_1 computador_2` | `decl_canal` |
| | `SEQ` + instruções indentadas | `bloco_raiz`, `bloco_seq`, `suite` |
| | `op = input()` | `simples_stmt` (`op_atrib`), `primario` (`IDENT "(" ")"`) |
| | `calculadora.send(op, v1, v2)` / `.receive(...)` | `simples_stmt` → `expr_posfixo` (`"." IDENT "(" args ")"`) |
| | `if op == "+": … elif …` | `if_stmt`, `expr_comp`, `op_rel` |
| **T2** Fatorial ∥ Fibonacci | `PAR` com dois `SEQ` filhos | `bloco_par`, `bloco_seq` |
| | `while i <= n:` | `while_stmt` |
| | `fat *= i` | `op_atrib` (`*=`) |
| **T3** Neurônio | `class Neuronio:` com atributos e métodos | `decl_classe`, `decl_atributo`, `decl_metodo` |
| | `def init(input_val, output_desejado, peso_inicial=0.5)` | `param` com `literal` padrão |
| | `n = new Neuronio(1, 0)` | `primario` (`"new" IDENT "(" args ")"`) |
| | `self.peso += taxa * x * erro` | `expr_posfixo` com `"self"`, `op_atrib` |
| | `while self.erro != 0:` | `while_stmt`, `op_rel` (`!=`) |
| | `n.treinar()` | chamada de método |
| **T4** Rede XOR | funções `sigmoid`, `sigmoid_derivada` | `decl_funcao`, `-> float` |
| | `exp(-x)`, `1 / (1 + exp(-x))` | `expr_unario`, `expr_termo`, `primario` entre `( )` |
| | `self.pesos[i] += …` | `expr_posfixo` (`"[" expr "]"`), `op_atrib` |
| | listas `[[0,0],[0,1],…]` | `lista` aninhada |
| | `for i in range(len(x)):` | `for_stmt` |
| | `random()` | chamada de função builtin |
| **T5** Recomendação | 4 classes com herança de dados e listas de objetos | `decl_classe`, `lista`, `new` |
| | `relu`, `sigmoid` como métodos | `decl_metodo` |
| | listas em várias linhas | quebra de linha ignorada (decisão 11) |
| | `if saida[i] > 0.5 and not comprou:` (o teste `in` vira laço de busca que preenche `comprou`) | `expr_and`, `expr_not` |
| | `print(produto)` dentro de `for` | `for_stmt`, chamada de função |
| **T6** Quicksort recursivo | método recursivo `_quicksort` | `decl_metodo`, `return_stmt`, chamada via `self.` |
| | `entrada = input()`, `entrada.split()`, `is_number` | `expr_posfixo`, builtins |
| | `array[1:]` → laço com índice | `for_stmt`, `[ expr ]` |
| | concatenação de listas `a + [p] + b` → laço com `append` | `expr_arit`, método `append` |
| **T7** Quicksort iterativo | `def quicksort_iterativo(arr):` | `decl_funcao` |
| | `while len(stack) > 0:` | `while_stmt` |
| | `continue` | `continue_stmt` |
| | `arr[i] = arr[j]` | `simples_stmt`, `expr_posfixo` |
| | `print("Array ordenado:", arr)` | chamada com vários `args` |
| **T8** Avaliação (4 núcleos) | `fork prof em core(1):` … `fork mon3 em core(4):` | `fork_stmt`, `alocacao` (`core`) |
| | `join prof, mon1, mon2, mon3` | `join_stmt` |
| | classe `Gerador` (LCG) | `decl_classe`, `%` em `expr_termo` |
| | `simular_atraso(segundos)` com `int(...)` e `while` | `decl_funcao`, builtins |
| **T9** + Mandelbrot (5 núcleos) | 5º `fork … em core(5)` | `fork_stmt` |
| | laços aninhados, `while zx*zx + zy*zy <= 4.0 and it < 100:` | `while_stmt`, `expr_and`, `FLOAT` |
| | `linha = linha + caracteres[idx]` | `expr_arit`, índice em string |
| **T10** + Sierpinski (6 núcleos) | 6º `fork … em core(6)` | `fork_stmt` |
| | recursão `desenhar(x, y, lado, grau)` | `decl_funcao`, chamada recursiva |
| | tapete em matriz ASCII (substitui `turtle`; ver §6) | `lista` aninhada, índice duplo `m[i][j] = "#"` |
| **Testes adicionais** (repo) | `fork t em host("computador_2"):` | `alocacao` (`host`) |
| | `PAR` com `send`/`receive` em 3 canais | `bloco_par`, `decl_canal` ×3 |

### 5.5 Cobertura das Observações do enunciado

| Observação | Onde |
|-----------|------|
| 1 `programa_minipar` | `programa` |
| 2 Precedência | §3 `expr_*` e decisão 4 |
| 3 Instanciação, método, recursão | `new`, `expr_posfixo`, chamada de função/método recursiva |
| 4 Gramática cobre todos os testes | tabela 5.3 |
| 5 Tratamento de erros | `NEWLINE`/`INDENT` inconsistentes → erro léxico; produção esperada ausente → erro sintático com linha e coluna; regras de `simples_stmt` → erro semântico |

---

## 6. Decisões em aberto

| Item | Proposta | Responsável |
|------|----------|-------------|
| Sintaxe por indentação em vez das chaves do 2026.1 | O enunciado exige a BNF do relatório 2026.1 "revisada e complementada" e permite sintaxe estilo Python. Confirmar que a troca de `{ }`/`;` por indentação é aceita como "revisão". | Professor (Arturo) |
| Gráficos no Teste 10 (`turtle`) | Trocar pelo tapete em matriz ASCII, como já feito em `teste_adicional2_tapete_sierpinski.mp`. Evita criar uma API gráfica na linguagem. | Equipe → confirmar com professor |
| Mapeamento `computador_1`/`computador_2` → IP:porta | Arquivo de configuração `hosts.cfg` lido pelo runtime; a gramática só usa os nomes. | Equipe (runtime) |
| Semântica de `receive(a, b, c)` | Argumentos são variáveis preenchidas pela mensagem recebida (como no enunciado); a forma `x = canal.receive()` também é aceita. | Equipe (semântico) |
| `sys.stdin.readline()` literal | Só se o professor exigir; vira builtin sem mudar a gramática. | Professor |
| Arquivo antigo `docs/gramatica.md` (2026.1) | Renomear para `docs/gramatica-2026.1.md` antes de adicionar este, preservando o histórico. | Equipe |

---

## 7. Impacto nos componentes (para as próximas issues)

| Componente | Mudança |
|-----------|---------|
| Léxico | Pilha de indentação, tokens `NEWLINE`/`INDENT`/`DEDENT`, `FLOAT`, `->`, `+=` etc., novas palavras reservadas (`fork`, `join`, `em`, `core`, `host`, `elif`, `and`, `or`, `not`, `def`, `self`). Remover `var`, `do`, `seq`/`par` minúsculos. |
| Parser | Um método por produção de §3; `simples_stmt` com o sufixo decidido após `expr`. |
| AST | Novos nós: `ForkStmt`, `JoinStmt`, `Alocacao`, `ChannelDecl`, `AugAssign` (desugar para `Assignment`). |
| Semântico | Regras de `simples_stmt`, tabela de builtins, checagem de `join` para tarefas já declaradas por `fork`. |
| Geradores | `fork … em core(n)` → thread/processo com afinidade; `fork … em host(h)` → processo remoto via `c_channel`. |
