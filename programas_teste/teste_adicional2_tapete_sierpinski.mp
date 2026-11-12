# Teste adicional 2: tapete de Sierpinski (regra dos digitos na base 3)
func celula_vazia(x: int, y: int) {
    var a = x;
    var b = y;
    var vazio = false;
    while (a > 0 || b > 0) {
        if ((a % 3 == 1) && (b % 3 == 1)) {
            vazio = true;
        }
        a = int(a / 3);
        b = int(b / 3);
    }
    return vazio;
}

seq {
    print("==== Teste adicional 2: tapete de Sierpinski ====");
    var tamanho = 9;
    var y = 0;
    while (y < tamanho) {
        var linha = "";
        var x = 0;
        while (x < tamanho) {
            if (celula_vazia(x, y)) {
                linha = linha + " ";
            } else {
                linha = linha + "#";
            }
            x = x + 1;
        }
        print(linha);
        y = y + 1;
    }
}
