# Compilador MiniPar

Compilador MiniPar em Python, com geração de TAC e transpilação para C++20. A IDE web permite editar, compilar e executar os programas. O runtime C++ é compilado e linkado junto com cada programa gerado.

Desenvolvido por:

- Emanuele Vitória de Jesus Lima — [Manu-Vii](https://github.com/Manu-Vii)
- José Lucas de Oliveira Quintela — [lucasqtl](https://github.com/lucasqtl)
- Luiz Miguel de Melo Bomfim — [luizwhirl](https://github.com/luizwhirl)

## Estrutura

```text
components/
  interfaces.py
  lexico/          c_lexico.py, token.py
  sintatico/       c_sintatico.py, ast.py, visitor.py
  semantico/       c_semantico.py
  tabela_simbolos/ c_tabela_simbolos.py
  tac/             c_gerador_tac.py
  codegen/         c_gerador_cpp.py, driver_gcc.py
  controle/        c_controle.py
erros/             diagnosticos.py
runtime/           minipar_rt.hpp, canal.cpp, paralelo.cpp
interfaces/        cli.py, web/api.py, web/frontend/
programas_teste/   programas MiniPar (.mp)
benchmarks/        scripts Python de baseline, quando disponíveis
docs/              gramatica.md, uml/, relatorio/, backlog.md
tests/             unitarios/, integracao/, programas/
```

## Requisitos

- Python 3.8 ou superior
- `g++` com suporte a C++20
- Flask para a IDE Web

No Windows, instale uma distribuição GCC/MinGW-w64 e adicione a pasta `bin`
ao `PATH`. Se o compilador tiver outro nome ou caminho, configure `CXX` antes
de iniciar o compilador MiniPar.

Instale as dependências com:

```bash
pip install -r requirements.txt
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

Para executar os testes unitários:

```bash
python -m unittest discover -s tests/unitarios
```

## Fases

1. Análise léxica e sintática: `components/lexico/` e `components/sintatico/`.
2. Análise semântica e tabela de símbolos: `components/semantico/` e `components/tabela_simbolos/`.
3. Geração de TAC: `components/tac/`.
4. Geração C++ e compilação/linkedição via `g++`: `components/codegen/` e `runtime/`.

O fluxo principal executa o binário C++ gerado; o TAC também pode ser executado
diretamente para expressões, desvios, atribuições simples e `print`. O executor TAC
não cobre ainda chamadas de função, canais, atribuições indexadas ou todos os
recursos da linguagem.

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
