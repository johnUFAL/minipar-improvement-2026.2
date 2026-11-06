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

Com o comando `minipar` instalado pelo projeto (`uv sync` ou `pip install -e .`),
compile e execute em um único comando:

```bash
minipar compilar programas_teste/t07_quicksort_iterativo_tac.mp -O2 -o output/t07 --executar
```

Também é possível usar `python main.py compilar` no ambiente de desenvolvimento.
As fases podem ser inspecionadas sem compilar o executável:

```bash
minipar compilar programa.mp --tokens
minipar compilar programa.mp --ast
minipar compilar programa.mp --tac
minipar compilar programa.mp --emit-cpp
```

Os comandos `tokens`, `ast`, `tac`, `cpp`, `build` e `run` são atalhos para as
mesmas operações. `--tac` grava e imprime o TAC sem gerar C++ ou executável;
`-o` escolhe o caminho do binário, e `-O0` a `-O3` configuram a otimização.
Falhas léxicas, sintáticas, semânticas, de geração, de build e de execução usam
códigos de saída `2`, `3`, `4`, `5`, `6` e `7`, respectivamente. Erros de uso
ou de leitura do arquivo retornam `1`.
Na IDE web, marque **Otimizar TAC** para comparar o TAC original e o otimizado
lado a lado. Essa opção afeta apenas a visualização didática do TAC; a geração
e execução do binário C++ permanecem inalteradas.

A API web também oferece `POST /api/compilar`, que recebe
`{"code": "<fonte MiniPar>"}` e retorna `tokens`, `ast`,
`tabela_simbolos`, `tac`, `cpp`, `tac_origin`, `cpp_origin` e `diagnosticos`.
Os mapas de origem relacionam cada `generated_line` do TAC/C++ à
`source_line` correspondente no código MiniPar; a IDE usa essa relação para
destacar a origem ao passar o mouse ou navegar por teclado.
`POST /api/executar`
recebe o mesmo código e uma lista opcional `inputs`, compila e executa em
subprocesso e retorna `stdout`, `stderr`, `exit_code` e `tempo` (em segundos).
A execução é interrompida após 30 segundos ou ao ultrapassar 1 MiB de saída
combinada. A rota legada `POST /api/compile`, usada pela IDE atual, continua
disponível e mantém o contrato de compilar e executar em uma única chamada.

As rotas que carregam programas de `programas_teste` (`POST /api/get_test`,
`POST /api/test_spec` e `POST /api/session/create`) aceitam somente caminhos
relativos dentro desse diretório. Caminhos absolutos, componentes `..`, nomes
vazios, valores que não sejam texto e arquivos inexistentes são rejeitados;
entradas inválidas retornam `400` e arquivos ausentes retornam `404`.

Para executar os testes unitários:

```bash
uv run pytest -v
```
*(O pytest executa os TestCase existentes, então nada precisa ser reescrito.)*

Para verificar os tipos:

```bash
uv run mypy
```

## Afinidade de CPU em `fork`

`fork tarefa em core(N):` solicita afinidade da thread a uma CPU disponível
para o processo. `N` começa em 1 e seleciona a N-ésima CPU permitida; portanto,
o mapeamento também respeita restrições como `taskset` no Linux. Sem `core(N)`,
o escalonador do sistema operacional escolhe a CPU. Se o índice solicitado não
estiver disponível ou não puder ser aplicado, o runtime avisa e executa a
tarefa sem afinidade.

Para registrar a CPU em que cada tarefa executou, defina
`MINIPAR_TRACE_CORES=1`. O benchmark de quatro tarefas CPU-bound geradas pelo
MiniPar pode ser executado com:

```bash
uv run python benchmarks/benchmark_fork_core.py
```

O benchmark reporta a mediana das amostras e o speedup; use uma máquina com
pelo menos quatro CPUs disponíveis para avaliar o critério de `> 2,5x`.

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

### Canais TCP no runtime C++

O runtime oferece comunicação TCP tipada entre processos. Configure um canal
em cada processo: o servidor chama `ouvir(porta)` e o cliente
`conectar(host, porta)`. O timeout de conexão e de E/S é de 5 segundos por
padrão e pode ser alterado com `setTimeout`.

```cpp
MiniParChannel canal;
canal.setTimeout(std::chrono::seconds(10));

// Servidor:
canal.ouvir(5101);
auto [operacao, valor, ativo] =
    canal.receber<std::string, double, bool>();

// Cliente (em outro processo):
canal.conectar("127.0.0.1", 5101);
canal.enviar(std::string("somar"), 2.5, true);
```

Uma chamada `enviar` cria um frame contendo a quantidade de campos, o tipo,
o tamanho e os bytes de cada valor. Inteiros usam 64 bits, `float`/`double`
via IEEE-754 de 64 bits, bool um byte e strings os bytes UTF-8; números e
tamanhos são transmitidos em big-endian. `receber<T...>()` valida tipos e
quantidade de campos e retorna o valor (um tipo) ou uma tupla (vários tipos).
Falhas de rede e timeout geram `std::runtime_error`, capturado pelo `main`
gerado pelo compilador.

`sendData`/`receiveData` permanecem disponíveis como adaptadores para uma
mensagem de string. A declaração MiniPar `c_channel nome computador1
computador2` continua aceita por compatibilidade, mas não escolhe papel nem
porta; a configuração TCP ainda deve ser feita pela API C++ acima. A execução
simulada de TAC continua usando filas em memória.

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
