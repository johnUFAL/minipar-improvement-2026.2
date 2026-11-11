# T2 - Jogo de adivinhacao (cliente)
#
# Execute este lado como computador_1. Digite palpites ate acertar o numero
# secreto. Use "sair" para encerrar antes de acertar.

c_channel jogo computador_1 computador_2

seq {
    print("==== T2 Adivinhacao - cliente (computador_1) ====");
    print("O servidor pensou em um numero entre 1 e 100.");

    var entrada = input("Palpite: ");
    var comando = "palpite";
    if (entrada == "sair") {
        comando = "sair";
    }
    var palpite = 0.0;
    if (comando != "sair") {
        palpite = to_number(entrada);
    }
    var status = "";
    var eco = 0.0;
    var tentativas = 0.0;
    var ignorado = 0.0;
    var continuar = true;

    while (continuar) {
        jogo.send(comando, palpite, tentativas, 0.0);

        if (comando == "sair") {
            continuar = false;
        } else {
            jogo.receive(status, eco, tentativas, ignorado);

            if (status == "maior") {
                print("Tente um numero maior.");
            } elif (status == "menor") {
                print("Tente um numero menor.");
            } elif (status == "acertou") {
                print("Voce acertou em", format_float(tentativas, 0), "tentativas!");
                continuar = false;
            } else {
                print("Resposta inesperada do servidor:", status);
                continuar = false;
            }

            if (continuar) {
                entrada = input("Palpite: ");
                comando = "palpite";
                if (entrada == "sair") {
                    comando = "sair";
                } else {
                    palpite = to_number(entrada);
                }
            }
        }
    }

    if (comando != "sair") {
        jogo.send("sair", 0.0, 0.0, 0.0);
    }
    print("Cliente encerrando.");
}
