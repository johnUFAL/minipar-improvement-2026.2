# T7 - Estatisticas remotas (servidor)
#
# Execute este lado como computador_2. Mantem soma, contagem, maior e menor
# dos valores recebidos e responde (status, resumo, soma, media).

c_channel stats computador_1 computador_2

seq {
    print("==== T7 Estatisticas - servidor (computador_2) ====");

    var comando = "";
    var vazio = "";
    var valor = 0.0;
    var ignorado = 0.0;
    var soma = 0.0;
    var contagem = 0.0;
    var maior = 0.0;
    var menor = 0.0;
    var resumo = "";
    var continuar = true;

    while (continuar) {
        stats.receive(comando, vazio, valor, ignorado);

        if (comando == "fim") {
            continuar = false;
            print("Servidor encerrando com", format_float(contagem, 0), "valores.");
        } else {
            if (contagem == 0.0) {
                maior = valor;
                menor = valor;
            }
            if (valor > maior) {
                maior = valor;
            }
            if (valor < menor) {
                menor = valor;
            }
            soma = soma + valor;
            contagem = contagem + 1.0;

            resumo = "maior " + format_float(maior, 2) + ", menor " + format_float(menor, 2);
            print("Valor", format_float(valor, 2), "->", resumo);
            stats.send("OK", resumo, soma, soma / contagem);
        }
    }
}
