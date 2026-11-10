# T2 - Jogo de adivinhacao (servidor)
#
# Execute este lado como computador_2. Quem esta no servidor escolhe o numero
# secreto (entre 1 e 100); o cliente tenta adivinhar e o servidor responde
# "maior", "menor" ou "acertou" para cada palpite, mostrando o jogo aqui.

c_channel jogo computador_1 computador_2

seq {
    print("==== T2 Adivinhacao - servidor (computador_2) ====");

    var segredo = to_number(input("Escolha o numero secreto (1 a 100): "));
    while (segredo < 1.0 || segredo > 100.0) {
        print("Numero fora do intervalo.");
        segredo = to_number(input("Escolha o numero secreto (1 a 100): "));
    }
    print("Numero secreto:", format_float(segredo, 0), "- aguardando palpites...");

    var comando = "";
    var palpite = 0.0;
    var tentativas = 0.0;
    var ignorado = 0.0;
    var continuar = true;

    while (continuar) {
        jogo.receive(comando, palpite, tentativas, ignorado);

        if (comando == "sair") {
            continuar = false;
            print("O jogador desistiu. Servidor encerrando.");
        } else {
            tentativas = tentativas + 1.0;
            print("Tentativa", format_float(tentativas, 0), ": palpite", format_float(palpite, 0));

            if (palpite < segredo) {
                print("  -> o segredo e maior");
                jogo.send("maior", palpite, tentativas, 0.0);
            } elif (palpite > segredo) {
                print("  -> o segredo e menor");
                jogo.send("menor", palpite, tentativas, 0.0);
            } else {
                print("  -> acertou em", format_float(tentativas, 0), "tentativas!");
                jogo.send("acertou", palpite, tentativas, 0.0);
                continuar = false;
            }
        }
    }
}
