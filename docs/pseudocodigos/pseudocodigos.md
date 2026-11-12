# Pseudocódigos dos componentes

Este documento descreve os algoritmos implementados, não uma especificação
alternativa da linguagem. As referências apontam para as funções que devem ser
consultadas se a implementação mudar.

## 1. Analisador léxico

**Referência:** [`components/lexico/c_lexico.py`](../../components/lexico/c_lexico.py),
`Lexer.next_token`, `Lexer._scan_step`, `Lexer._scan_indentation`,
`Lexer._apply_indentation`, `Lexer._scan_token`, `Lexer._scan_newline` e
`Lexer._finish`.

```text
inicializar(fonte):
    remover BOM inicial
    cursor = início; linha = 1; coluna = 1
    pilha_indentação = [0]
    delimitadores_abertos = []
    marcar início de linha e criar buffer de tokens

próximo_token():
    enquanto buffer não contém token:
        se início de linha e nenhum delimitador aberto:
            consumir espaços, CR e tabulações
            registrar erro para tabulação na indentação
            se linha vazia ou comentário '#':
                consumir até newline; continuar
            comparar largura com topo(pilha_indentação):
                se maior: empilhar largura e emitir INDENT
                se menor: desempilhar e emitir DEDENT até alcançar a largura
                se largura não corresponder a nível anterior:
                    registrar erro e ajustar nível para recuperação
        reconhecer o próximo token:
            ignorar espaços em branco e comentários '#'
            reconhecer palavra/palavra-chave, número, string ou caractere
            reconhecer operador de um ou dois caracteres
            validar e atualizar a pilha de delimitadores
            emitir token com lexema, valor e localização
        ao newline fora de parênteses/colchetes:
            emitir NEWLINE se a linha lógica continha tokens
    ao fim da fonte:
        emitir NEWLINE final se necessário
        emitir um DEDENT por nível de indentação ainda aberto
        registrar delimitadores não fechados
        emitir END_OF_FILE
    devolver o primeiro token do buffer
```

Uma linha iniciada por `#` é ignorada, assim como o restante de uma linha após
um `#` encontrado durante a varredura. O newline dentro de `(...)` ou `[...]`
não encerra a linha lógica. A indentação usa largura de quatro espaços por
nível; inconsistências são diagnosticadas sem interromper a tokenização, para
que o parser também receba os tokens seguintes.

## 2. Analisador sintático

**Referência:** [`components/sintatico/c_sintatico.py`](../../components/sintatico/c_sintatico.py),
`Parser.parse`, `Parser._suite`, `Parser._statement_recovering`,
`Parser._synchronize`, `Parser._statement`, `Parser._simple_statement`,
`Parser._expression` e `Parser._parse_or` até `Parser._primary`.

```text
parse():
    ignorar NEWLINEs iniciais
    enquanto não chegou ao bloco raiz:
        analisar declaração de canal, função ou classe
        se ocorrer erro:
            avançar até NEWLINE, DEDENT ou EOF e retomar
    analisar bloco raiz SEQ ou PAR
    exigir EOF e construir Program com as declarações e o bloco

analisar_bloco():
    aceitar bloco entre chaves ou ':' NEWLINE INDENT ... DEDENT
    enquanto não chegou ao terminador do bloco:
        analisar uma instrução
        se ocorrer erro:
            sincronizar até o fim da instrução/limite do bloco
    rejeitar bloco vazio

analisar_expressão():
    analisar OR
    OR chama AND; AND chama NOT; NOT chama comparação
    comparação chama soma e aceita no máximo um operador comparativo
    soma analisa produto repetido por '+' ou '-'
    produto analisa unário repetido por '*', '/' ou 'mod'
    unário consome '+'/'-' recursivamente ou chama pós-fixo
    pós-fixo estende primário com acesso a membro, método ou índice
    primário reconhece literais, identificadores, chamadas,
        listas, input, new e expressão entre parênteses
    construir nós AST à medida que cada produção é reconhecida
```

O encadeamento das chamadas implementa a precedência, da menor para a maior:
`or`, `and`, `not`, comparação, soma, produto, unário e pós-fixo/primário.
Comparações encadeadas são rejeitadas. A recuperação é por instrução e respeita
`}`, `DEDENT` e EOF para não consumir o restante de um bloco válido.

## 3. Analisador semântico

**Referência:** [`components/semantico/c_semantico.py`](../../components/semantico/c_semantico.py),
`SemanticAnalyzer.analyze`, `SemanticAnalyzer._collect_declarations`,
`SemanticAnalyzer._check_inheritance_cycles`,
`SemanticAnalyzer._check_method_overrides`, `SemanticAnalyzer.validate_node`,
`SemanticAnalyzer._infer_type`, `SemanticAnalyzer._check_concurrent_write` e
`SemanticAnalyzer._validate_channel_signatures`.

```text
analyze(program):
    limpar estado temporário de concorrência, fork/join e canais
    PASSO 1 — coletar declarações:
        registrar canais, funções e classes no escopo global
        registrar atributos e métodos em escopos de classe
        verificar ciclos de herança e compatibilidade de sobrescritas
    PASSO 2 — validar cada declaração/instrução em ordem:
        ao entrar em bloco, função, classe, laço ou ramo concorrente:
            entrar no escopo correspondente e salvar contexto
        inferir tipos das expressões e validar declarações/atribuições
        validar chamadas, argumentos, condições e retornos
        validar membros herdados e acessos a índices
        em PAR/fork, marcar escopos concorrentes e verificar escritas externas
        registrar forks e chamadas de canal para validar joins e assinaturas
        ao sair do contexto, restaurar escopo e estado anterior
    validar compatibilidade de aridade e tipos entre envios/recebimentos
    devolver sucesso se o coletor não contém erros
```

A inferência de tipos é recursiva e armazena o tipo inferido no nó de expressão.
Tipos desconhecidos são tratados como compatíveis em verificações que não
podem ser concluídas estaticamente; os erros conhecidos são acumulados, não
lançados como exceções.

## 4. Diagnósticos e recuperação de erros

**Referência:** [`erros/diagnosticos.py`](../../erros/diagnosticos.py),
`Diagnostic`, `DiagnosticBag.report`, `DiagnosticBag.error`,
`DiagnosticBag.format`, `DiagnosticBag.format_text` e `DiagnosticBag.to_dict`;
recuperação sintática em `Parser._synchronize`.

```text
reportar(fase, mensagem, linha, coluna, comprimento):
    criar Diagnostic imutável
    anexá-lo ao DiagnosticBag sem interromper a análise

formatar(diagnóstico):
    mapear fase e severidade para apresentação
    se houver linha de fonte:
        mostrar cabeçalho, linha e marcador na coluna indicada
    senão:
        mostrar somente o cabeçalho

formatar_todos():
    formatar cada diagnóstico na ordem de registro
    acrescentar contagem de erros e avisos

ao erro sintático:
    avançar até NEWLINE, DEDENT ou EOF
    consumir NEWLINE quando aplicável e retomar no próximo comando
```

## 5. Tabela de símbolos e escopos

**Referência:** [`components/tabela_simbolos/c_tabela_simbolos.py`](../../components/tabela_simbolos/c_tabela_simbolos.py),
`TabelaSimbolos.enter_scope`, `TabelaSimbolos.exit_scope`,
`TabelaSimbolos.define`, `TabelaSimbolos.lookup`,
`TabelaSimbolos.lookup_local`, `TabelaSimbolos.lookup_member` e
`TabelaSimbolos.export`.

```text
inicializar():
    criar escopo global como raiz
    pilha_de_escopos_ativos = [global]
    manter índice de todos os escopos criados para exportação

enter_scope(nome):
    pai = topo(pilha_de_escopos_ativos)
    criar escopo filho com caminho único sob pai
    registrar escopo na árvore e no índice global
    empilhar escopo

exit_scope():
    se houver escopo ativo além do global:
        desempilhar; manter o escopo registrado

define(símbolo):
    escopo = topo(pilha_de_escopos_ativos)
    se nome já existe localmente: retornar falso
    registrar símbolo com caminho do escopo atual; retornar verdadeiro

lookup(nome):
    procurar do escopo ativo mais interno até o global
    devolver primeira ocorrência ou nenhum

lookup_member(classe, nome):
    percorrer classe e ancestrais, evitando revisitar classe
    procurar no escopo de membros de cada classe
    devolver primeira ocorrência ou nenhum

export():
    serializar todos os escopos registrados, pais e símbolos
```

Os escopos encerrados permanecem na árvore para exportação e consulta de
membros. A busca lexical normal considera somente a pilha ativa. A revisão
independente solicitada na issue #42 ainda precisa ser feita por outro membro
da equipe.
