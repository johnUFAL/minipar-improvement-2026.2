# T5 - Cofre com senha (cliente)
#
# Execute este lado como computador_1. Voce tem 3 tentativas para descobrir a
# senha que quem esta no servidor cadastrou.

c_channel cofre computador_1 computador_2

seq {
    print("==== T5 Cofre - cliente (computador_1) ====");
    print("Descubra a senha do cofre. Voce tem 3 tentativas.");

    var tentativa = "";
    var status = "";
    var dica = "";
    var restantes = 3.0;
    var ignorado = 0.0;
    var continuar = true;

    while (continuar) {
        tentativa = input("Senha: ");
        cofre.send("tentar", tentativa, 0.0, 0.0);
        cofre.receive(status, dica, restantes, ignorado);

        if (status == "ABERTO") {
            print("Cofre aberto!");
            continuar = false;
        } elif (status == "BLOQUEADO") {
            print("Cofre bloqueado. Sem tentativas.");
            continuar = false;
        } else {
            print("Senha incorreta.", dica, "Restam", format_float(restantes, 0), "tentativas.");
        }
    }

    print("Cliente encerrando.");
}
