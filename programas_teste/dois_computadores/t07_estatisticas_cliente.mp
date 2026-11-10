# T7 - Estatisticas remotas (cliente)
#
# Execute este lado como computador_1. Envie numeros um a um; o servidor
# acumula e responde soma, media, maior e menor ate agora. "fim" encerra.

c_channel stats computador_1 computador_2

seq {
    print("==== T7 Estatisticas - cliente (computador_1) ====");
    print("Digite numeros e fim para terminar.");

    var entrada = input("Numero: ");
    var status = "";
    var rotulo = "";
    var soma = 0.0;
    var media = 0.0;

    while (entrada != "fim") {
        if (is_number(entrada)) {
            stats.send("valor", "", to_number(entrada), 0.0);
            stats.receive(status, rotulo, soma, media);
            print("Soma:", format_float(soma, 2), "| Media:", format_float(media, 2), "|", rotulo);
        } else {
            print("Entrada invalida.");
        }
        entrada = input("Numero: ");
    }

    stats.send("fim", "", 0.0, 0.0);
    print("Cliente encerrando.");
}
