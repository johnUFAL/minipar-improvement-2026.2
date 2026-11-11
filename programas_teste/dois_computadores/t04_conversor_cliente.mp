# T4 - Conversor de unidades (cliente)
#
# Execute este lado como computador_1. Escolha a conversao e o valor; o
# servidor calcula e devolve o resultado. Use "sair" para encerrar.

c_channel conversor computador_1 computador_2

seq {
    print("==== T4 Conversor - cliente (computador_1) ====");
    print("Conversoes: c2f f2c km2mi mi2km kg2lb lb2kg");

    var tipo = input("Conversao: ");
    var valor = 0.0;
    var status = "";
    var resultado = 0.0;
    var ignorado1 = 0.0;
    var ignorado2 = 0.0;

    while (tipo != "sair") {
        valor = to_number(input("Valor: "));
        conversor.send(tipo, valor, 0.0, 0.0);
        conversor.receive(status, resultado, ignorado1, ignorado2);

        if (status == "OK") {
            print(format_float(valor, 2), tipo, "=", format_float(resultado, 2));
        } else {
            print(status);
        }
        tipo = input("Conversao: ");
    }

    conversor.send("sair", 0.0, 0.0, 0.0);
    print("Cliente encerrando.");
}
