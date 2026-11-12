# Pseudocódigo da Tabela de Símbolos

A implementação está em `components/tabela_simbolos/c_tabela_simbolos.py`.
Escopos encerrados permanecem registrados para exportação e para permitir a
consulta dos membros de classes, mas só os escopos ativos participam da busca
lexical normal.

```text
inicializar:
    criar escopo global
    pilha_atual = [global]
    registrar global na árvore de escopos

entrar_escopo(nome):
    pai = topo(pilha_atual)
    escopo = criar filho nomeado de pai
    registrar escopo na árvore
    empilhar escopo

sair_escopo:
    se pilha_atual tiver mais de um escopo:
        desempilhar

declarar(simbolo):
    escopo = topo(pilha_atual)
    se simbolo.nome já existe em escopo:
        retornar falso
    registrar simbolo com o caminho de escopo atual
    retornar verdadeiro

buscar(nome):
    para escopo em pilha_atual, do mais interno ao global:
        se nome existe em escopo:
            retornar símbolo
    retornar nenhum

buscar_local(nome):
    retornar símbolo de nome no topo(pilha_atual), ou nenhum

buscar_membro(classe, nome):
    visitadas = conjunto vazio
    enquanto classe existe e ainda não foi visitada:
        marcar classe como visitada
        procurar nome no escopo de membros da classe
        se encontrado:
            retornar símbolo
        classe = superclasse registrada
    retornar nenhum

exportar:
    serializar cada escopo registrado, seu pai e seus símbolos
```

A API web disponibiliza a exportação em `POST /api/symbols`, recebendo
`{"code": "<fonte MiniPar>"}` e retornando `symbols` e os diagnósticos
produzidos durante a análise.
