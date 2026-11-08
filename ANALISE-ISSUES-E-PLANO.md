# Análise das issues e plano de implementação

**Data da análise:** 08/11/2026  
**Branch analisada:** `hotfix/fix_issues32-50`  
**Escopo:** issues T32–T50 da lista fornecida e estado do checkout nesta data.

> As issues T32–T50 estavam abertas no GitHub durante a análise. O estado abaixo
> descreve o código observado no checkout, não o status administrativo das
> issues. A suíte executada foi `uv run pytest -q`: **229 passaram, 6 foram
> ignorados e 61 subtestes passaram**. Uma suíte verde não comprova critérios
> que ainda não têm testes automatizados.

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
| [#42 — Pseudocódigos](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/42) | Parcial | Pseudocódigo da tabela de símbolos em [docs/pseudocodigo_tabela_simbolos.md](docs/pseudocodigo_tabela_simbolos.md). | Escrever léxico, parser, semântico, concorrência e tratamento de erros, referenciando funções reais e obtendo revisão cruzada. |
| [#43 — Product/Sprint Backlogs](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/43) | Pendente | Existe um backlog preliminar em [docs/backlog.md](docs/backlog.md). | Expandir para Product Backlog e nove sprints, com issues, status e incrementos; verificar/configurar o GitHub Project e a associação das issues aos milestones. |
| [#44 — Relatório e entrega](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/44) | Parcial | Há relatório de execução e PDF anterior em [docs/relatorio](docs/relatorio). | Produzir relatório final com checklist dos itens 1–17, capa com link do repositório, tecnologias/ambiente, referências às evidências, tag e release `v2026.2`. |
| [#45 — Limites de array/T7](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/45) | Quase implementada | Leituras verificam limites; atribuições expandem o vetor; existe teste de erro e código de saída não zero em [runtime](runtime/minipar_rt.hpp) e [test_runtime.py](tests/runtime/test_runtime.py). | Corrigir explicitamente a capacidade inicial da pilha no T7; compilar e executar com AddressSanitizer e UBSan; testar mensagem e saída do programa inválido conforme os critérios. |
| [#46 — Regressão T1–T10](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/46) | Parcial | O [runner](scripts/run_testes_2026_2.py) compara saídas para parte dos casos e verifica marcos dos benchmarks. | Implementar comparador adequado por teste (exato, faixa, linhas-chave, ordem não determinística), normalização definida e integração à CI. |
| [#47 — Backend de benchmark](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/47) | Pendente | API de compilação/execução e sessões existe em [interfaces/web/api.py](interfaces/web/api.py). | Criar hardware, criação/polling de jobs, execução real sequencial/paralela, métricas por tarefa/núcleo, mediana, limite de núcleos e exportação CSV. |
| [#48 — Telas Flask](https://github.com/johnUFAL/minipar-improvement-2026.2/issues/48) | Parcial | Painel, editor, resultados e configurações existem em um template e compartilham estilos em [frontend](interfaces/web/frontend). | Criar `base.html` e rotas/páginas requeridas; substituir métricas estáticas por dados do backend #47; concluir estado de execução, hardware e responsividade. |
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
3. Executar os programas reais T8–T10 nos modos sequencial/paralelo; medir tarefas e núcleos e produzir a linha `@@METRICAS`.
4. Calcular mediana, speedup e eficiência, limitar núcleos ao hardware disponível e permitir exportação CSV.
5. Testar concorrência do servidor e validar que mudar parâmetros altera o trabalho executado e as métricas.

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

## Sequência recomendada

1. Fechar os defeitos e testes dos programas T1–T7 (#32–38) e a validação de arrays (#45).
2. Completar benchmarks e testes de regressão/integração (#39, #40, #46).
3. Implementar a API de benchmark antes das telas que dependem dela (#47 → #48), preservando a IDE e as sessões (#49); empacotar assets (#50).
4. Concluir evidências e documentação de entrega (#41–44), atualizando o relatório com resultados medidos e não estimados.
