# Análise das issues e plano de implementação

**Data da análise:** 08/11/2026  
**Branch de acompanhamento:** `fix/quest_docs_minipar_2026`
**Escopo:** inventário das issues T32–T50; as alterações desta branch limitam-se
às tasks 42, 43, 44, 45 e 47.

> As issues T32–T50 estavam abertas no GitHub durante a análise. O estado abaixo
> descreve o código observado no checkout, não o status administrativo das
> issues. A atualização em 08/11/2026 executou a suíte completa com cobertura:
> **247 passaram, 8 falharam, 8 foram ignorados e 89 subtestes passaram**;
> cobertura de **81,03%** (mínimo 80%). As falhas atuais são dos testes de T1
> (issue #32) e dos assets offline (fora do escopo desta branch). `mypy` passou;
> Ruff continua apontando nomes não definidos no runner T1. Uma suíte verde
> não comprova critérios que ainda não têm testes automatizados.

## Resumo por issue

| Issue | Estado observado | Já implementado | Falta / divergência |
|---|---|---|---|
| [#32 — Calculadora cliente/servidor](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/32) | Parcial | Cliente e servidor separados e execução em localhost pelo [runner](scripts/run_multiterminal.py). | Implementar protocolo/erros conforme a issue; testar `+`, `-`, `*`, `/`, divisão por zero e servidor sobrevivente; validar em duas máquinas. |
| [#33 — Fatorial e Fibonacci em PAR](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/33) | Parcial | Dois ramos em `PAR` em [T2](programas_teste/t02_fatorial_fibonacci_par.mp). | Fatorial é iterativo e de 5; Fibonacci tem 8 termos. Faltam recursão, valores requeridos, medição de sobreposição e teste repetido 20 vezes. |
| [#34 — Neurônio](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/34) | Parcial | Classe, método de treino e convergência em [T3](programas_teste/t03_neuronio.mp). | Adequar saída e precisão à referência, incluindo linhas/iterações exigidas; comparar os trechos de referência automaticamente. |
| [#35 — XOR](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/35) | Parcial | Rede com três neurônios ocultos e 20.000 épocas em [T4](programas_teste/t04_rede_neural_xor.mp). | Testar as quatro saídas contra as faixas XOR e registrar comparação de desempenho com a versão Python no relatório. |
| [#36 — Recomendador](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/36) | Parcial | Rede e recomendador determinísticos em [T5](programas_teste/t05_recomendacao.mp), com saída congelada em [expected_results](tests/integracao/expected_results). | Implementar as classes de domínio solicitadas, preservar acentos UTF-8 e validar exatamente as 12 recomendações. |
| [#37 — Quicksort com entrada](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/37) | Parcial | Quicksort recursivo com classe e entrada numérica em [T6](programas_teste/t06_quicksort_classes.mp). | Validar entrada inválida com reentrada, tratar entrada vazia e vetor unitário, e cobrir esses casos por testes. |
| [#38 — Quicksort iterativo/TAC](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/38) | Parcial | Programa e saída correta do T7; há referências em [expected_results](tests/integracao/expected_results). | Comparar TAC gerado com referência por equivalência; testar saída do executor TAC contra a do binário e documentar diferenças. |
| [#39 — Benchmarks T8–T10](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/39) | Parcial | Programas MiniPar e baselines Python existem; T10 inclui Sierpinski no sequencial e no fork de sexto núcleo. | Medir N repetições e mediana, semear avaliadores separadamente, comparar trabalho equivalente e apresentar tabela de resultados. |
| [#40 — Testes de integração](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/40) | Parcial | Há testes unitários, de integração e CI em [tests](tests) e [.github/workflows/ci.yml](.github/workflows/ci.yml). | Criar pelo menos 10 programas inválidos, testar cada fronteira com casos positivos e negativos e publicar/exigir cobertura mínima de 80%. |
| [#41 — Execuções e evidências](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/41) | Parcial | Runner dos testes e instruções de rede em [run_testes_2026_2.py](scripts/run_testes_2026_2.py) e [docs/rede.md](docs/rede.md). | Gerar evidências numeradas, registrar resultados dos 10 programas e executar T1/fork remoto em duas máquinas reais com ambiente e problemas documentados. |
| [#42 — Pseudocódigos](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/42) | Implementada localmente, revisão pendente | Léxico, parser, semântico, diagnósticos e tabela de símbolos estão descritos com referências a funções reais em [docs/relatorio/pseudocodigos.md](docs/relatorio/pseudocodigos.md). | Solicitar e registrar a revisão cruzada por outro integrante; não marcar a issue remota como concluída antes disso. |
| [#43 — Product/Sprint Backlogs](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/43) | Backlog local implementado; Project não verificado | [docs/backlog.md](docs/backlog.md) lista as 50 issues e os nove sprints; o snapshot confirmou uma associação por issue a milestone. | A listagem/configuração do board GitHub requer o escopo `read:project`, ausente na autenticação atual. |
| [#44 — Relatório e entrega](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/44) | Parcial | O [relatório de execução](docs/relatorio/RELATORIO-TESTES-2026.2.md) registra resultados de todos os testes e pendências. | O checkout não contém o enunciado integral para mapear os 17 itens sem inferência; faltam revisão final, clone limpo, PDF final, tag e release `v2026.2`. |
| [#45 — Limites de array/T7](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/45) | Implementada localmente; CI Linux pendente | Pilha do T7 dimensionada; runtime valida leitura e escrita fora dos limites com mensagem e código não zero; testes nativos adicionados. | O workflow agora exige ASan/UBSan; anexar e conferir o resultado do job Linux. A tentativa local Windows falhou ao linkar `-lasan`/`-lubsan`, ausentes no toolchain instalado. |
| [#46 — Regressão T1–T10](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/46) | Parcial | O [runner](scripts/run_testes_2026_2.py) compara saídas para parte dos casos e verifica marcos dos benchmarks. | Implementar comparador adequado por teste (exato, faixa, linhas-chave, ordem não determinística), normalização definida e integração à CI. |
| [#47 — Backend de benchmark](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/47) | Implementada localmente; validação funcional pendente | [interfaces/web/benchmark.py](interfaces/web/benchmark.py) executa código C++ gerado do TAC MiniPar; API em [interfaces/web/api.py](interfaces/web/api.py) oferece hardware, jobs assíncronos, progresso, métricas, medianas e CSV; runtime fornece `argumento(n)` e `clock()`. | Confirmar em ambiente de entrega o job completo e a correspondência do workload gerado com os critérios específicos dos programas T8–T10 antes de fechar a issue. |
| [#48 — Telas Flask](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/48) | Implementada localmente; validação visual pendente | `base.html` único, rotas `/`, `/benchmark`, `/resultados`, `/configuracoes` e `/editor`; Painel só configura e navega para `/benchmark?autorun=1`, página dedicada executa/progride/exporta e `/resultados` mantém o histórico do compilador, com persistência em `localStorage` em [frontend](interfaces/web/frontend). | Revisar o layout em 1280 px/tablet no ambiente de entrega e fechar a issue remota; terminal/sessões permanecem no escopo de #50 (T49). |
| [#49 — Migração da IDE e sessões](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/49) | Parcial | Editor, fases do compilador, execução e API de sessões estão disponíveis na interface atual. | Fechar paridade funcional no novo layout: explorer, editor, abas de fases, terminal, entrada, seletor `-O` e sessões; validar fluxo entre dois navegadores e documentar a paridade. |
| [#50 — Assets offline](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/50) | Pendente | CSS e JavaScript próprios já estão em [static](interfaces/web/frontend/static). | Hospedar CodeMirror, fontes, ícones e logo localmente; remover referências externas dos templates e validar a interface sem internet. |

## Plano de implementação por issue

### T32 — Calculadora cliente/servidor
1. Ajustar cliente e servidor MiniPar para o protocolo definido na issue, mantendo a configuração de host/porta e os papéis por processo.
2. No servidor, retornar erro explícito para operação inválida e divisão por zero sem encerrar o serviço indevidamente.
3. Ampliar o runner para cobrir as quatro operações, resultado decimal, erro de divisão por zero e disponibilidade posterior do servidor.
4. Executar em localhost e em duas máquinas; registrar procedimento e resultados em [docs/rede.md](docs/rede.md).

### T33 — Fatorial e Fibonacci
1. Implementar funções recursivas de fatorial e Fibonacci nos dois ramos.
2. Ajustar os casos para `fatorial(10)` e os dez primeiros termos de Fibonacci.
3. Emitir marcadores de início/fim com relógio monotônico para demonstrar a sobreposição.
4. Criar teste que valida conteúdo sem depender da ordem entre ramos e executá-lo 20 vezes.

### T34 — Neurônio
1. Conferir os valores e a saída de referência do enunciado.
2. Ajustar a impressão e a precisão numérica sem mudar a lógica de aprendizado exigida.
3. Acrescentar testes para número de iterações, mensagem final e primeiras/últimas iterações de referência.

### T35 — XOR
1. Confirmar a arquitetura e o algoritmo de backpropagation do programa atual com a especificação.
2. Fazer o teste extrair as quatro saídas e verificar `< 0,1` para XOR zero e `> 0,9` para XOR um.
3. Medir a execução compilada com `-O2`, executar o baseline Python equivalente e publicar ambiente e tempos no relatório.

### T36 — Recomendador
1. Completar o modelo com `Produto`, `Categoria`, `Usuario`, `RedeNeural` e `Recomendador`, mantendo a lista de recomendações prevista.
2. Definir o histórico de entrada padrão do teste e corrigir textos para UTF-8 com acentos.
3. Atualizar o golden file e comparar exatamente as 12 recomendações, inclusive acentos.

### T37 — Quicksort com validação
1. Adicionar validação explícita da entrada sem introduzir exceções que não existem na linguagem.
2. Reapresentar o pedido ao usuário quando houver token inválido; definir o comportamento para entrada vazia.
3. Testar a entrada do enunciado, `1 a 3`, entrada vazia e vetor de um elemento.

### T38 — TAC de referência
1. Incorporar o TAC esperado do enunciado como referência de teste.
2. Comparar a saída do executor TAC e do executável C++ para a mesma fonte.
3. Documentar diferenças textuais permitidas e garantir equivalência observável do resultado.

### T39 — Benchmarks
1. Revisar T8–T10 para garantir o mesmo trabalho nas execuções sequencial e paralela.
2. Garantir seeds independentes por avaliador e manter os fractais medidos em ambos os modos.
3. Criar runner configurável com várias repetições, mediana, número de núcleos e comparação com os baselines Python.
4. Registrar resultados, speedup e limitações de hardware no relatório; investigar diferenças sem transformar metas de desempenho em resultados presumidos.

### T40 — Integração e erros
1. Mapear as fronteiras léxico→parser→semântico→TAC→C++→GCC e criar testes positivos e negativos para cada uma.
2. Criar pelo menos dez fontes inválidas cobrindo erros léxicos, sintáticos, semânticos e de concorrência, verificando diagnósticos.
3. Adicionar cobertura à configuração de desenvolvimento e à CI, com meta de 80%, e corrigir lacunas relevantes.

### T41 — Execuções e evidências
1. Revisar o runner único para compilar/executar os dez programas, preservar saídas e tempos e compará-los às expectativas.
2. Organizar capturas numeradas do terminal e da interface, referenciadas no relatório.
3. Executar T1 e fork remoto em duas máquinas reais; registrar sistemas operacionais, topologia, portas, firewall, comandos e resultados.
4. Atualizar [docs/rede.md](docs/rede.md) com o procedimento efetivamente validado.

### T42 — Pseudocódigos
1. Escrever pseudocódigos de léxico, parser, semântico/erros e tabela de símbolos a partir da implementação atual.
2. Incluir comentários, INDENT/DEDENT, precedência, recuperação, passes semânticos, tipos, concorrência e escopos quando aplicável.
3. Referenciar os módulos/funções correspondentes e obter revisão de outro integrante.

### T43 — Backlogs
1. Inventariar todas as issues, milestones, prioridades e status reais.
2. Verificar o GitHub Project; criar/configurar board e associar issues, ajustando permissões se necessário.
3. Reescrever [docs/backlog.md](docs/backlog.md) com Product Backlog, nove Sprint Backlogs e incrementos efetivamente entregues.
4. Conferir que cada issue pertence a exatamente um milestone e registrar pendências de associação.

### T44 — Relatório e release
1. Criar checklist dos 17 itens do enunciado e ligar cada item à seção/evidência correspondente.
2. Completar relatório final com gramática, UML, resultados, benchmarks, tecnologias, versões e ambiente.
3. Preparar capa com integrantes e link do repositório, revisar comentários explicativos e gerar PDF final.
4. Validar clone limpo seguindo somente o README, depois publicar a tag e release `v2026.2` com o PDF.

### T45 — Limites de array
1. Corrigir a declaração da pilha do T7 para uma capacidade adequada ao algoritmo, sem depender de expansão implícita do runtime.
2. Adicionar/ajustar teste específico de acesso fora dos limites, verificando mensagem legível e código diferente de zero.
3. Compilar e executar T7 e o caso inválido com `-fsanitize=address,undefined`; registrar comandos e resultados.

### T46 — Regressão T1–T10
1. Consolidar um runner de testes que compila e executa cada programa com entradas documentadas.
2. Definir comparação por caso: exata para saídas determinísticas, por faixa para resultados aleatórios, por linhas-chave para saídas longas e sem ordem global para ramos paralelos.
3. Normalizar apenas diferenças portáveis justificadas, como CRLF/LF, sem remover diferenças semânticas ou acentos.
4. Executar no CI e verificar que uma alteração deliberada de saída faz o teste falhar.

### T47 — Backend de benchmark
1. Definir contrato de hardware e validação dos parâmetros de benchmark.
2. Implementar endpoints para iniciar job e consultar estado/progresso/resultado sem bloquear requisições do Flask.
3. Implementar workloads parametrizados com TAC/C++ MiniPar para avaliação e zero, um ou dois fractais; medir tarefas e núcleos e produzir a linha `@@METRICAS`. Confirmar a equivalência com os programas de aceitação T8–T10 antes de fechar a issue.
4. Calcular mediana, speedup e eficiência, limitar núcleos ao hardware disponível e permitir exportação CSV.
5. Testar a responsividade do servidor e validar que os parâmetros são repassados ao binário e alteram o trabalho medido.
6. Corrigir a partição de tarefas entre núcleos: o TAC gerado usa `__minipar_divide` com inteiros; o gerador estava agrupando `total * núcleo` com a divisão por engano, o que fazia o último núcleo receber todas as tarefas. A geração agora calcula limites com divisão inteira equivalente por variáveis intermediárias.

### T48 — Telas
1. Criar template base compartilhado com uma única paleta, tipografia e componentes de navegação.
2. Separar as rotas/páginas de Painel, Resultados e Configurações conforme a issue.
3. Ligar telas aos endpoints do benchmark #47, incluindo estados, progresso, resultados e hardware detectado.
4. Persistir configurações e testar layout em 1280 px e tablet; remover rótulos que não correspondam à implementação real.

### T49 — Migração da IDE e sessões
1. Definir a nova tela do compilador e a correspondência entre cada função legada e seu destino.
2. Migrar explorer, editor, abas de tokens/AST/tabela/TAC/C++/execução, terminal, botões, entradas e seletor `-O`.
3. Integrar painel de progresso e sessões multi-terminal, preservando os contratos da API existente.
4. Testar fluxo completo em duas sessões/navegadores e documentar a tabela de paridade no PR.

### T50 — Assets offline
1. Adicionar versões locais de CodeMirror, fontes e ícones; confirmar permissão/licença do logo antes de incluí-lo.
2. Remover URLs externas dos templates e servir todos os recursos pela aplicação.
3. Atualizar [README.md](README.md) com instruções para gerar/atualizar CSS se houver etapa de build.
4. Validar as telas com a rede desativada e verificar que nenhuma dependência externa é carregada.

## Atualização — T49 (#49), 08/11/2026

O T49 avançou na migração da nova IDE:

- O terminal, o painel de progresso e a integração de sessões multi-terminal
  na interface nova foram removidos conforme a decisão do mantenedor; a tela
  `/editor` voltou a cobrir as fases do compilador sem o terminal novo.
- O seletor `-O` foi integrado ao fluxo de execução: `POST /api/executar`
  aceita `optimization_level` (O0–O3), otimiza o TAC com `TACOptimizer` e
  regenera o C++ com `CppCodeGenerator`.
- Testes de integração novos cobrem a otimização no endpoint de execução e o
  ciclo de vida da sessão (`/api/session`, `/join`, `/ready`, `/clear`); teste
  de regressão garante que a tela `/editor` não renderiza o terminal removido.

### Tabela de paridade — legado → novo layout

| Função legada | Destino no novo layout | Estado |
|---|---|---|
| Explorer com specs | Explorador de programas com specs (metadados multi-computador, ex.: t01_calculadora.mp); a IDE nova não carrega specs | Pendente |
| Editor de código | Fase `code` (7 fases do compilador) | Disponível |
| Tokens / AST / Símbolos / TAC / C++ / Execução | Fases 1–7 | Disponível |
| Terminal | Painel da IDE nova que exibia o STDOUT/STDERR em execução; removido por decisão do mantenedor | Removido |
| Entradas | Campo de inputs na fase de execução | Disponível |
| Seletor `-O` | `optimization_level` em `/api/executar` | Integrado |
| Botões run/compile/save | Ações das fases e histórico | Disponível |

Pendências: validar fluxo completo em duas sessões/navegadores (Playwright sem
Chromium no ambiente local) e fechar a issue remota #49.

## Sequência recomendada

1. Fechar os defeitos e testes dos programas T1–T7 (#32–38) e a validação de arrays (#45).
2. Completar benchmarks e testes de regressão/integração (#39, #40, #46).
3. Implementar a API de benchmark antes das telas que dependem dela (#47 → #48), preservando a IDE e as sessões (#49); empacotar assets (#50).
4. Concluir evidências e documentação de entrega (#41–44), atualizando o relatório com resultados medidos e não estimados.

## Atualização da branch de documentação/runtime — 08/11/2026

As tasks #42, #43, #44, #45 e #47 são o escopo da branch atual. O código e os
documentos foram atualizados para refletir o estado local; issues abertas não
foram fechadas. A revisão humana dos pseudocódigos, o acesso ao GitHub Project,
o enunciado integral para a matriz de 17 itens, a execução ASan/UBSan no CI e a
validação final da correspondência do benchmark com T8–T10 permanecem como
evidências externas ou pendências.

## Atualização — T48 (#49), 08/11/2026

O T48 foi implementado localmente nesta branch:

- `base.html` concentra sidebar, topbar, sprite de ícones e tokens únicos; as
  telas `painel.html`, `benchmark.html`, `resultados.html`,
  `configuracoes.html` e `editor.html` estendem o mesmo layout. `/pipeline`
  preserva o guia didático.
- Rotas Flask dedicadas: `/` (Painel), `/benchmark`, `/resultados`,
  `/configuracoes`, `/editor` e `/pipeline`; a IDE continua funcional em
  `/editor` até a migração completa de terminal/sessões do T49.
- O Painel apenas prepara o benchmark: ajusta carga/núcleos, salva as
  preferências e o botão navega para `/benchmark?autorun=1`. A execução,
  progresso e resultados ficam na página dedicada `/benchmark`, que consome
  `/api/hardware`, `POST /api/benchmark`, o polling de estado e o CSV.
- As telas se separam por domínio: `/resultados` mostra o histórico do
  compilador (`minipar-compiler-history`) e cada execução abre em
  `/resultados/<run_id>` com a mesma visão de 7 fases do editor original
  (Código, Tokens, AST, Símbolos, TAC, C++ e Execução), apenas leitura. O
  histórico persiste `compileResult` para restaurar tokens, AST, tabela de
  símbolos, TAC, C++ e mapeamentos de origem sem recompilar, com fallback para
  entradas antigas que só guardavam o C++. O endereço antigo `/#result-detail`
  é redirecionado para a execução mais recente e a rota `/result-detail` também
  existe por compatibilidade. O `/benchmark` guarda a
  última medição paralela (`minipar-benchmark-last`) e um histórico restaurável
  de até 10 execuções (`minipar-benchmark-history`); a tabela de tarefas medidas
  pagina de 15 em 15 linhas. Parâmetros, otimização, tema e hardware também são
  persistidos em `localStorage`.
- O estado do benchmark passa por Aguardando → Executando → Concluído/Falhou,
  com barra de progresso acessível, cards de resumo, barras por núcleo, tabela e
  exportação CSV. Os parâmetros de carga usam sliders sincronizados com campos
  numéricos, e Configurações separa as seções de benchmark e de compilador.
- Os testes de integração cobrem as rotas, o fluxo Painel → `/benchmark` com
  `autorun`, a máquina de estados com resposta simulada, a persistência após
  recarregar e a ausência de overflow em 1280 px, 820 px e 390 px. `ruff` e
  `mypy` passaram; a suíte completa mantém apenas as 4 falhas preexistentes de
  T1 (#32), sem relação com a interface.

Pendências externas: revisão visual no ambiente de entrega e fechamento da
issue remota. A migração completa da IDE/terminal/sessões continua no T49 (#50)
e o empacotamento integral de assets no T50 (#48).
