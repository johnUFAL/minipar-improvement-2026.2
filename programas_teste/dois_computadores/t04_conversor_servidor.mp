# T4 - Conversor de unidades (servidor)
#
# Execute este lado como computador_2. Recebe (conversao, valor) e responde
# (status, resultado).

c_channel conversor computador_1 computador_2

seq {
    print("==== T4 Conversor - servidor (computador_2) ====");

    var tipo = "";
    var valor = 0.0;
    var ignorado1 = 0.0;
    var ignorado2 = 0.0;
    var status = "";
    var resultado = 0.0;
    var continuar = true;

    while (continuar) {
        conversor.receive(tipo, valor, ignorado1, ignorado2);

        if (tipo == "sair") {
            continuar = false;
            print("Servidor encerrando.");
        } else {
            status = "OK";
            resultado = 0.0;

            if (tipo == "c2f") {
                resultado = valor * 9.0 / 5.0 + 32.0;
            } elif (tipo == "f2c") {
                resultado = (valor - 32.0) * 5.0 / 9.0;
            } elif (tipo == "km2mi") {
                resultado = valor * 0.621371;
            } elif (tipo == "mi2km") {
                resultado = valor / 0.621371;
            } elif (tipo == "kg2lb") {
                resultado = valor * 2.20462;
            } elif (tipo == "lb2kg") {
                resultado = valor / 2.20462;
            } else {
                status = "Erro: conversao desconhecida.";
            }

            print("Pedido:", tipo, format_float(valor, 2), "->", status, format_float(resultado, 2));
            conversor.send(status, resultado, 0.0, 0.0);
        }
    }
}
