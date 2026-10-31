# Compilador MiniPar

Compilador MiniPar em Python, com geração de TAC e transpilação para C++17. A IDE web permite editar, compilar e executar os programas. O runtime C++ é compilado e linkado junto com cada programa gerado.

**Pipeline:** fonte `.mp` → Lexer → Parser (AST) → Semântico/Tabela de Símbolos → TAC → C++17 → `g++` → binário

Desenvolvido por:

- 2026.1
    - Emanuele Vitória de Jesus Lima - [Manu-Vii](https://github.com/Manu-Vii)
    - José Lucas de Oliveira Quintela - [lucasqtl](https://github.com/lucasqtl)
    - Luiz Miguel de Melo Bomfim - [luizwhirl](https://github.com/luizwhirl)

- 2026.2
    - João Victor Duarte do Nascimento - [johnUFAL](https://github.com/johnUFAL)
    - Rian Antonio da Silva Gaião - [ryanthecomic](https://github.com/ryanthecomic)
    - José Guilherme de Almeida Novais - [GuilhermeANovais](github.com/GuilhermeANovais)
    - Daniel de Araujo Albuquerque - [Daniel-de-Araujo91](https://github.com/Daniel-de-Araujo91)
    - Guilherme Alessander da Silva Fernandes - [Alessander-Magno](https://github.com/Alessander-Magno)

## Estrutura

```text
components/
  interfaces.py
  lexico/          c_lexico.py, token.py
  sintatico/       c_sintatico.py, ast.py, visitor.py
  semantico/       c_semantico.py
  tabela_simbolos/ c_tabela_simbolos.py
  tac/             c_gerador_tac.py, executor_tac.py, otimizador_tac.py
  codegen/         c_gerador_cpp.py, driver_gcc.py
  controle/        c_controle.py
erros/             diagnosticos.py
runtime/           minipar_rt.hpp, canal.cpp, paralelo.cpp
interfaces/        cli.py, web/api.py, web/frontend/
programas_teste/   programas MiniPar (.mp)
benchmarks/        t08_..., t09_..., t10_...
docs/              gramatica.md, uml/, relatorio/, backlog.md
tests/             unitarios/, integracao/, programas/
```

## Requisitos

- Python 3.11+
- `g++` com suporte a C++17
- Flask para a IDE Web

No Windows, instale uma distribuição GCC/MinGW-w64 e adicione a pasta `bin`
ao `PATH`. Se o compilador tiver outro nome ou caminho, configure `CXX` antes
de iniciar o compilador MiniPar.

A compilação C++ usa `-std=c++17` e `-O2` por padrão. O driver também aceita
`O0`, `O1` e `O3` para escolher outro nível de otimização. Em Linux, o link usa
`-pthread`; no Windows, usa `-lws2_32` e gera um executável `.exe`. Os métodos
`DriverGCC.compilar(cpp_path, saida, nivel_otimizacao="O2")` e
`DriverGCC.executar(saida)` permitem compilar e executar diretamente; a
execução retorna o `stdout` e o código de saída do processo.

Instale as dependências com:

```bash
uv sync --extra dev
```

## Uso

Abra o menu interativo (terminal ou IDE web):

```bash
python main.py
```

Compile diretamente um programa:

```bash
python main.py programas_teste/t03_neuronio.mp
```

O compilador grava os arquivos `.tac`, `.cpp` e o executável em `output/`. No menu, a opção web inicia a IDE em `http://127.0.0.1:5000`.
Na IDE web, marque **Otimizar TAC** para comparar o TAC original e o otimizado
lado a lado. Essa opção afeta apenas a visualização didática do TAC; a geração
e execução do binário C++ permanecem inalteradas.

Para executar os testes unitários:

```bash
uv run pytest -v
```
*(O pytest executa os TestCase existentes, então nada precisa ser reescrito.)*

Para verificar os tipos:

```bash
uv run mypy
```

## Fases

1. Análise léxica e sintática: `components/lexico/` e `components/sintatico/`.
2. Análise semântica e tabela de símbolos: `components/semantico/` e `components/tabela_simbolos/`.
3. Geração e otimização opcional de TAC: `components/tac/`.
4. Geração C++ e compilação/linkedição via `g++`: `components/codegen/` e `runtime/`.

O fluxo principal executa o binário C++ gerado. O TAC também pode ser executado
diretamente para funções, classes (incluindo herança), atribuições indexadas,
`PAR`/`FORK`/`JOIN` e canais. Na execução simulada de TAC, os ramos são
intercalados sequencialmente e os canais usam filas FIFO em memória; essa
simulação não representa paralelismo real nem comunicação entre máquinas.

O lowering de objetos usa `alloc`, `getfield` e `setfield`; chamadas de método
viram funções com o objeto como primeiro argumento. Blocos paralelos delimitam
ramos com `par_begin`/`par_end`, enquanto `send`/`recv` representam operações
de canal no TAC.

## Sintaxe MiniPar

```minipar
seq {
    var x = 42;
    print("Valor:", x);

    par {
        print("Thread A");
        print("Thread B");
    }
}
```

| Sintaxe | Descrição |
|---|---|
| `seq { ... }` | Bloco sequencial |
| `par { ... }` | Bloco paralelo |
| `var nome = expr;` | Declaração de variável |
| `nome = expr;` | Atribuição |
| `print(expr, ...);` | Impressão na saída padrão |
| `# comentário` | Comentário de linha |



## Wireframe para a nova interface no link abaixo 

[wireframe no figma](https://www.figma.com/design/NXKjTBkAbP0foCPBm0ge0M/MiniPar-2026.2?node-id=0-1&t=UdRarWve6l7ARpmw-1)


## Workflow de Desenvolvimento

Todo o trabalho segue o fluxo **branch → commit → PR → review → merge**.
A `main` contém sempre a versão estável e funcional; nada é commitado direto nela.

### 1. Criar uma branch a partir da `main` atualizada

    git checkout main
    git pull origin main
    git checkout -b feat/nome-curto-da-mudanca

**Convenção de nomes:**

| Prefixo   | Uso                                        | Exemplo                        |
|-----------|--------------------------------------------|--------------------------------|
| `feat/`   | Nova funcionalidade                        | `feat/fractal-sierpinski`      |
| `fix/`    | Correção de bug                            | `fix/fila-resultados-bloqueada`|
| `docs/`   | Apenas documentação                        | `docs/readme-workflow`         |
| `refactor/` | Reestruturação sem mudar comportamento   | `refactor/separar-trabalhadores`|

### 2. Commits pequenos e descritivos

    git add .
    git commit -m "feat: adiciona núcleo 6 com desenho do tapete de Sierpinski"

Formato: `tipo: descrição curta no imperativo`.

### 3. Enviar a branch e abrir o Pull Request

    git push -u origin feat/nome-curto-da-mudanca

No GitHub, abra um PR para a `main` descrevendo **o que** mudou, **por que**
mudou e **como testar** (ex.: `python benchmarks/t10_6_nucleos_avaliacao_2_fractais.py`).

### 4. Review e merge

- Ao menos 1 pessoa revisa o PR antes do merge.
- Resolva os comentários com novos commits na mesma branch.
- Use **Squash and merge** para manter o histórico da `main` linear.
- Após o merge, apague a branch (local e remota):

      git branch -d feat/nome-curto-da-mudanca
      git push origin --delete feat/nome-curto-da-mudanca

### 5. Sincronizar

    git checkout main
    git pull origin main
