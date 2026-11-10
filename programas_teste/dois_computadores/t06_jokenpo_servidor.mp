# T6 - Pedra, papel e tesoura (servidor)
#
# Execute este lado como computador_2. Em cada rodada, o servidor recebe a
# jogada do cliente, digita a propria jogada, decide o vencedor e devolve
# (resultado, jogada do servidor, placar do cliente, placar do servidor).

c_channel jokenpo computador_1 computador_2

seq {
    print("==== T6 Jokenpo - servidor (computador_2) ====");

    var jogada = "";
    var vazio = "";
    var rodada = 0.0;
    var ignorado = 0.0;
    var minha = "";
    var resultado = "";
    var placar_cliente = 0.0;
    var placar_servidor = 0.0;
    var continuar = true;

    while (continuar) {
        jokenpo.receive(jogada, vazio, rodada, ignorado);

        if (jogada == "sair") {
            continuar = false;
            print("Servidor encerrando.");
        } elif (jogada != "pedra" && jogada != "papel" && jogada != "tesoura") {
            print("Cliente enviou jogada invalida:", jogada);
            jokenpo.send("invalida", "", placar_cliente, placar_servidor);
        } else {
            print("Rodada", format_float(rodada, 0), "- o cliente ja jogou.");
            minha = input("Sua jogada (pedra/papel/tesoura): ");
            while (minha != "pedra" && minha != "papel" && minha != "tesoura") {
                minha = input("Invalida. Sua jogada (pedra/papel/tesoura): ");
            }

            if (jogada == minha) {
                resultado = "empate";
            } elif ((jogada == "pedra" && minha == "tesoura") || (jogada == "papel" && minha == "pedra") || (jogada == "tesoura" && minha == "papel")) {
                resultado = "voce ganhou";
                placar_cliente = placar_cliente + 1.0;
            } else {
                resultado = "servidor ganhou";
                placar_servidor = placar_servidor + 1.0;
            }

            print("Cliente:", jogada, "| Servidor:", minha, "->", resultado);
            jokenpo.send(resultado, minha, placar_cliente, placar_servidor);
        }
    }
}
