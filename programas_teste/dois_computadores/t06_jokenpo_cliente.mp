# T6 - Pedra, papel e tesoura (cliente)
#
# Execute este lado como computador_1. Digite pedra, papel ou tesoura. O
# servidor tambem joga, calcula o vencedor e mantem o placar. "sair" encerra.

c_channel jokenpo computador_1 computador_2

seq {
    print("==== T6 Jokenpo - cliente (computador_1) ====");

    var jogada = input("Sua jogada (pedra/papel/tesoura/sair): ");
    var rodada = 0.0;
    var resultado = "";
    var jogada_servidor = "";
    var placar_cliente = 0.0;
    var placar_servidor = 0.0;

    while (jogada != "sair") {
        rodada = rodada + 1.0;
        jokenpo.send(jogada, "", rodada, 0.0);
        jokenpo.receive(resultado, jogada_servidor, placar_cliente, placar_servidor);

        if (resultado == "invalida") {
            print("Jogada invalida.");
        } else {
            print("Servidor jogou:", jogada_servidor, "->", resultado);
            print("Placar: voce", format_float(placar_cliente, 0), "x", format_float(placar_servidor, 0), "servidor");
        }
        jogada = input("Sua jogada (pedra/papel/tesoura/sair): ");
    }

    jokenpo.send("sair", "", 0.0, 0.0);
    print("Cliente encerrando.");
}
