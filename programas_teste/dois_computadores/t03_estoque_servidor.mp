# T3 - Consulta de estoque (servidor)
#
# Execute este lado como computador_2. O servidor consulta o codigo recebido
# e devolve status, nome, preco unitario e total do pedido.

c_channel estoque computador_1 computador_2

seq {
    print("==== T3 Estoque - servidor (computador_2) ====");
    print("Produtos: A100, B200, C300");

    var codigo = "";
    var nome_recebido = "";
    var quantidade = 0.0;
    var ignorado = 0.0;
    var status = "";
    var nome = "";
    var preco = 0.0;
    var total = 0.0;
    var continuar = true;

    while (continuar) {
        estoque.receive(codigo, nome_recebido, quantidade, ignorado);

        if (codigo == "sair") {
            continuar = false;
            print("Servidor encerrando.");
        } else {
            status = "OK";
            nome = "";
            preco = 0.0;

            if (codigo == "A100") {
                nome = "Caneta";
                preco = 2.5;
            } elif (codigo == "B200") {
                nome = "Caderno";
                preco = 18.0;
            } elif (codigo == "C300") {
                nome = "Mochila";
                preco = 120.0;
            } else {
                status = "Erro: codigo nao encontrado.";
            }

            total = preco * quantidade;
            print("Consulta:", codigo, "quantidade", format_float(quantidade, 0));
            print("Resposta:", status, nome, format_float(total, 2));
            estoque.send(status, nome, preco, total);
        }
    }
}
