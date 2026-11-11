# T5 - Cofre com senha (servidor)
#
# Execute este lado como computador_2. Quem esta no servidor cadastra a senha;
# o servidor confere cada tentativa, da uma dica sobre o tamanho e bloqueia o
# cofre apos 3 erros.

c_channel cofre computador_1 computador_2

seq {
    print("==== T5 Cofre - servidor (computador_2) ====");

    var senha = input("Cadastre a senha do cofre: ");
    print("Senha cadastrada. Aguardando tentativas...");

    var comando = "";
    var tentativa = "";
    var ignorado1 = 0.0;
    var ignorado2 = 0.0;
    var erros = 0.0;
    var dica = "";
    var continuar = true;

    while (continuar) {
        cofre.receive(comando, tentativa, ignorado1, ignorado2);

        if (tentativa == senha) {
            print("Tentativa correta: cofre aberto.");
            cofre.send("ABERTO", "", 3.0 - erros, 0.0);
            continuar = false;
        } else {
            erros = erros + 1.0;
            print("Tentativa errada:", tentativa, "(erro", format_float(erros, 0), "de 3)");
            if (erros >= 3.0) {
                cofre.send("BLOQUEADO", "", 0.0, 0.0);
                continuar = false;
            } else {
                dica = "Dica: a senha comeca com '" + substring(senha, 0, 1) + "'.";
                cofre.send("ERRO", dica, 3.0 - erros, 0.0);
            }
        }
    }
    print("Servidor encerrando.");
}
