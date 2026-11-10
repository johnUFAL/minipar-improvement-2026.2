# T3 - Consulta de estoque (cliente)
#
# Execute este lado como computador_1. Informe o codigo e a quantidade.
# Use "sair" no codigo para encerrar o servidor.

c_channel estoque computador_1 computador_2

seq {
    print("==== T3 Estoque - cliente (computador_1) ====");
    print("Produtos disponiveis: A100, B200, C300");

    var codigo = input("Codigo do produto: ");
    var quantidade = 0.0;
    var status = "";
    var nome = "";
    var preco = 0.0;
    var total = 0.0;
    var ignorado = 0.0;

    while (codigo != "sair") {
        quantidade = to_number(input("Quantidade: "));

        estoque.send(codigo, "", quantidade, 0.0);
        estoque.receive(status, nome, preco, total);

        if (status == "OK") {
            print("Produto:", nome);
            print("Preco unitario:", format_float(preco, 2));
            print("Total:", format_float(total, 2));
        } else {
            print(status);
        }

        codigo = input("Codigo do produto: ");
    }

    estoque.send("sair", "", 0.0, 0.0);
    print("Cliente encerrando.");
}
