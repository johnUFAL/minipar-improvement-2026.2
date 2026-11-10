# T2 - Jogo de adivinhacao (servidor)
#
# Execute este lado como computador_2. O servidor guarda um numero secreto
# e responde "maior", "menor" ou "acertou" para cada palpite.

c_channel jogo computador_1 computador_2

seq {
    print("==== T2 Adivinhacao - servidor (computador_2) ====");
    print("Numero secreto definido. Aguardando palpites...");

    var comando = "";
    var palpite = 0.0;
    var tentativas = 0.0;
    var ignorado = 0.0;
    var segredo = 37.0;
    var continuar = true;

    while (continuar) {
        jogo.receive(comando, palpite, tentativas, ignorado);

        if (comando == "sair") {
            continuar = false;
            print("Servidor encerrando.");
        } else {
            tentativas = tentativas + 1.0;

            if (palpite < segredo) {
                print("Palpite", format_float(palpite, 0), "-> maior");
                jogo.send("maior", palpite, tentativas, 0.0);
            } elif (palpite > segredo) {
                print("Palpite", format_float(palpite, 0), "-> menor");
                jogo.send("menor", palpite, tentativas, 0.0);
            } else {
                print("Acertou em", format_float(tentativas, 0), "tentativas.");
                jogo.send("acertou", palpite, tentativas, 0.0);
            }
        }
    }
}
