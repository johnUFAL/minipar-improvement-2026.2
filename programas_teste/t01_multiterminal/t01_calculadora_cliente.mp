# Teste 1 - Calculadora cliente-servidor (cliente)
#
# Executar no terminal cliente (computador_1):
#   t01_cliente.exe --hosts minipar.hosts --como computador_1
#
# Protocolo (quatro campos em ambas as direcoes):
#   requisicao: (op, v1, v2, 0.0)
#   resposta:   (status, resultado, 0.0, 0.0)
#
# O cliente le operacoes ate "sair". Para cada uma, envia a requisicao e
# imprime "Resultado: X" ou a mensagem de erro devolvida pelo servidor.

c_channel dados computador_1 computador_2

seq {
    print("==== T1 Calculadora - cliente (computador_1) ====");

    var op = input("Operacao (+,-,*,/): ");
    var v1 = 0.0;
    var v2 = 0.0;
    var status = "";
    var resultado = 0.0;
    var r1 = 0.0;
    var r2 = 0.0;

    while (op != "sair") {
        v1 = to_number(input("Operando 1: "));
        v2 = to_number(input("Operando 2: "));

        print("Cliente enviou:", op, format_float(v1, 1), format_float(v2, 1));
        dados.send(op, v1, v2, 0.0);
        dados.receive(status, resultado, r1, r2);

        if (status == "OK") {
            print("Resultado:", format_float(resultado, 1));
        } else {
            print(status);
        }

        op = input("Operacao (+,-,*,/): ");
    }

    # Mantem a aridade de quatro campos para o servidor encerrar o laco.
    dados.send("sair", 0.0, 0.0, 0.0);
    print("Cliente encerrando.");
}
