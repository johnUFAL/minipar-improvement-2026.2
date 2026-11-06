# Backlog

## 2026.2 — entregue em 11/11/2026

- [x] Adicionar os programas `t08`–`t10` em MiniPar e manter os baselines Python em `benchmarks/`.
- [x] Portar o Teste 11 (`MiniCompiladorCompleto_ARMv7.java`) para MiniPar e gerar os três `.arm`.
- [x] Criar a segunda interface Web didática em `interfaces/web2/` (porta 5001).
- [x] Desenhar a AST em SVG com zoom, pan, recolhimento, tooltips, legenda e exportação SVG/PNG.
- [x] Implementar download do executável e execução com entrada padrão na Web 2.
- [x] Adicionar literal de caractere, tipo `char` e builtins de string/arquivo.
- [x] Corrigir a indexação de string no codegen (`s[i]` → string de 1 caractere).
- [x] Mapear builtins para o runtime no codegen (`len`, `format_float`, `str`, `write_file` etc.).
- [x] Registrar `matrix` no semântico e mapear para `__make_matrix`.
- [x] Adicionar testes unitários de `char`, builtins e codegen.
- [x] Adicionar testes de integração dos Testes 8–11 e da Web 2.
- [x] Atualizar `docs/gramatica.md`, README, relatório, apresentação e UML da Web 2.
- [x] Suíte completa verde: `226 passed, 1 skipped, 40 subtests`.

## Pendências e próximos passos

- [ ] Executar os três `.arm` no CPUlator e anexar screenshots ao relatório.
- [ ] Publicar o relatório final e o código no GitHub.
- [ ] Implementar `list.append` no TAC/codegen para remover a limitação das listas.
- [ ] Implementar divisão no Assembly ARMv7 do Teste 11.
- [ ] Demonstrar execução remota com dois computadores na reavaliação (25/11).
- [ ] Expandir o executor TAC para chamadas, objetos, paralelismo simulado e canais.
- [ ] Documentar o modelo de execução e comunicação do runtime em `docs/uml/`.
