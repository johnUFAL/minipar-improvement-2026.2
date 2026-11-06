# MiniPar 2026.2 — Roteiro de apresentação

**Duração sugerida:** 12 a 15 minutos  
**Entrega:** 11/11/2026 · **Reavaliação:** 25/11/2026 · **Final:** 02/12/2026

---

## Slide 1 — Capa

**MiniPar 2026.2: compilador, paralelismo e interface didática**

- Disciplina: Compiladores — COMP379
- Professor: Arturo Hernández Domínguez
- Equipe: João Victor, Rian Gaião, José Guilherme, Daniel Albuquerque, Guilherme Alessander
- Repositório: github.com/johnUFAL/minipar-improvement

*Fala:* “Nesta entrega evoluímos o compilador com os Testes 8 a 11, uma segunda
interface Web didática e a documentação completa.”

---

## Slide 2 — O que já existia e o que mudou

| Antes (2026.1) | Agora (2026.2) |
|---|---|
| T1–T7 | T1–T11 |
| Terminal + Web do desenvolvedor | + Web didática (porta 5001) |
| `string`, `int`, `float`, `bool`, `list` | + `char` e builtins de string/arquivo |
| Benchmarks T8–T10 em Python | T8–T10 em MiniPar com `fork`/`core(n)` |
| Sem geração ARM | Teste 11 gera `.arm` ARMv7 |

---

## Slide 3 — Arquitetura em componentes

Inserir `docs/uml/componentes.png` (ou o `.puml`).

- Léxico → Sintático/AST → Semântico/Tabela → TAC → C++17 → g++ → executável.
- Componentes com contratos ABC e um componente de controle.
- Runtime separado: threads, canais TCP, fork/join e worker remoto.

*Fala:* “Cada fase é um componente independente; a segunda interface reutiliza
o mesmo pipeline, sem duplicar o compilador.”

---

## Slide 4 — Linguagem MiniPar 2026.2

```minipar
seq {
    var letra: char = 'M';
    var texto = "MiniPar";
    print(char_at(texto, 0), letra);

    fork avaliador em core(1) {
        print("nucleo 1");
    }
    join avaliador
}
```

- `char` próprio na AST/semântico; `std::string` de 1 caractere no C++.
- Builtins: `char_at`, `substring`, `is_digit`, `is_alpha`, `is_space`,
  `is_number`, `write_file`, `random_uniforme`, `matrix`.
- BNF atualizada em `docs/gramatica.md`.

---

## Slide 5 — Análise léxica e sintática

- Lexer com linha/coluna, strings, `CHAR_LITERAL`, comentários `#`.
- Parser descendente recursivo, precedência:
  `or < and < not < comparação < + - < * / % < unário < postfixo`.
- AST imutável (`dataclass`) com `para_dict()` para as interfaces.

Mostrar a aba **Tokens** e a aba **AST** da interface didática.

*Fala:* “A AST não é texto: é uma estrutura tipada que alimenta o semântico, o
TAC e o desenho SVG.”

---

## Slide 6 — Análise semântica e tabela de símbolos

- Coleta funções/classes antes dos corpos (recursão e referências futuras).
- Tipos: promoção `int`→`float`, `/` sempre `float`, `char`↔`string`.
- `fork`/`par` têm escopo próprio e não escrevem variáveis externas.
- `join` exige `fork` anterior no mesmo escopo.
- Tabela de símbolos exportada por escopo.

Mostrar a aba **Análise Semântica**.

---

## Slide 7 — TAC e código C++

Exemplo `((2+4)*7)-(5*4)`:

```text
t1 = 2 + 4
t2 = t1 * 7
t3 = 5 * 4
t4 = t2 - t3
```

- Codegen traduz TAC → C++17 sem consultar a AST.
- Driver compila com `g++ -std=c++17 -Wall -O2` e linka o runtime.
- Otimizador TAC disponível na Web 1 para comparação didática.

Mostrar as abas **TAC** e **Código C++**.

---

## Slide 8 — Segunda interface Web

**http://127.0.0.1:5001** (`MINIPAR_WEB2_PORT`)

- Barra superior, abas horizontais, editor à esquerda, saída à direita.
- Botões: Tokens, AST, Análise Semântica, TAC, C++, Compilar e baixar, Executar.
- AST em SVG: zoom, pan, nós coloridos, recolhimento, tooltips, legenda,
  exportação SVG/PNG.
- Download do `.exe`, execução com entrada padrão e aba Assembly ARM.

Mostrar screenshots `web2_ast.png`, `web2_executar.png` e `web2_arm.png`.

---

## Slide 9 — Testes 8, 9 e 10: fork/join em núcleos

| Teste | Núcleos | Carga | Speedup medido |
|---|---|---|---|
| T8 | 4 | 160 atividades | 3,33× |
| T9 | 5 | 160 atividades + Mandelbrot | 3,39× |
| T10 | 6 | 160 atividades + Mandelbrot + Sierpinski | 3,25× |

```minipar
fork prof em core(1) { ... }
fork mon1 em core(2) { ... }
join prof, mon1, mon2, mon3
```

- `MINIPAR_TRACE_CORES=1` comprova a CPU usada.
- Fractais em ASCII; Sierpinski pela regra dos dígitos na base 3.

---

## Slide 10 — Teste 11: minicompilador em MiniPar

- Classe `MiniCompiladorARM` dentro de um programa `.mp`.
- Fases: tokens → AST → TAC → Assembly ARMv7 → tabela → resultado.
- Três expressões do enunciado; resultados `22.0`, `-84.0`, `22.0`.
- Grava `expr1.arm`, `expr2.arm`, `expr3.arm`.

```asm
MOV    r0, #2
MOV    r1, #4
ADD    r2, r0, r1    @ resultado de '(2 + 4)'
...
SUB    r8, r4, r7    @ resultado de '(((2 + 4) * 7) - (5 * 4))'
b .
```

---

## Slide 11 — Validação do Assembly

- `clang --target=armv7-none-eabi -x assembler -c` monta os três `.arm`.
- CPUlator: colar o `.arm`, executar e conferir `r8 = 22` / `r8 = -84`.
- Limitações: sem divisão no Assembly e registradores sequenciais (como no
  gabarito Java).

*Fala:* “A validação automática garante a sintaxe; a execução no CPUlator será
demonstrada ao vivo.”

---

## Slide 12 — Testes e qualidade

```text
225 passed, 1 skipped, 40 subtests passed in 291.38s
```

- Unitários: léxico, parser, semântico, TAC, codegen.
- Integração: T1–T11, `write_file`, Web 1 e Web 2.
- O skip é o teste de `taskset`, específico de Linux.
- Testes novos: `test_builtins_string.py`, `test_testes_8_11.py`,
  `test_web2.py`.

---

## Slide 13 — Backlog e próximos passos

- [x] Fase 1 — linguagem e runtime.
- [x] Fase 2 — T8–T10.
- [x] Fase 3 — T11 e `.arm`.
- [x] Fase 4 — Web didática.
- [x] Fase 5 — testes e documentação.
- [ ] CPUlator com screenshots (manual).
- [ ] Publicação final no GitHub.
- Próximos: `list.append` no codegen, divisão no ARM, teste remoto com dois
  computadores.

---

## Slide 14 — Encerramento

- Três interfaces convivem: terminal, Web 1 e Web 2.
- Pipeline completo até executável nativo.
- Paralelismo real com afinidade de CPU.
- Teste 11 cumpre o port do Java para MiniPar.
- Documentação, UML, relatório e apresentação no repositório.

**Perguntas?**

---

## Checklist de ensaio

- [ ] Abrir a Web 2 e mostrar as oito abas.
- [ ] Carregar `t08_avaliacao_4_nucleos.mp` e executar.
- [ ] Mostrar a AST de um programa com `if`/`else`.
- [ ] Gerar e baixar um `.exe`.
- [ ] Abrir a aba Assembly ARM e gerar os três `.arm`.
- [ ] Mostrar o `expr1.arm` no CPUlator (se possível).
- [ ] Rodar `pytest -q` antes da apresentação.
