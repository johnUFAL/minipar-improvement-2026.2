# Teste de arte ASCII: fractal de Sierpinski como automato celular (regra 90)
seq {
    print("========================================");
    print("  FRACTAL DE SIERPINSKI (Automato)      ");
    print("========================================");

    var linhas = 32;
    var colunas = 64;
    var meio = 31;

    var anterior = range(colunas);
    var atual = range(colunas);
    var j = 0;
    while (j < colunas) {
        anterior[j] = 0;
        atual[j] = 0;
        j = j + 1;
    }
    anterior[meio] = 1;

    print("Calculo finalizado. Renderizando...");

    var i = 0;
    while (i < linhas) {
        var linha = "";
        j = 0;
        while (j < colunas) {
            if (anterior[j] == 1) {
                linha = linha + "A";
            } else {
                linha = linha + " ";
            }
            j = j + 1;
        }
        print(linha);

        j = 0;
        while (j < colunas) {
            atual[j] = 0;
            j = j + 1;
        }
        j = 1;
        while (j < (colunas - 1)) {
            var esq = anterior[j - 1];
            var dir = anterior[j + 1];
            if ((esq + dir) == 1) {
                atual[j] = 1;
            }
            j = j + 1;
        }
        j = 0;
        while (j < colunas) {
            anterior[j] = atual[j];
            j = j + 1;
        }
        i = i + 1;
    }

    print("========================================");
}
