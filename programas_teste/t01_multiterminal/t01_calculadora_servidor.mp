# Teste 1 - Calculadora cliente-servidor (servidor)
#
# Executar no terminal servidor (computador_2):
#   t01_servidor.exe --hosts minipar.hosts --como computador_2
#
# Protocolo (quatro campos em ambas as direcoes):
#   requisicao: (op, v1, v2, 0.0)
#   resposta:   (status, resultado, 0.0, 0.0)
#
# O servidor continua em loop ate receber "sair". Assim, um erro de divisao
# por zero nao derruba o servico: ele responde o erro e atende a proxima
# requisicao.

func calcular(op: string, v1: float, v2: float) -> float {
    if (op == "+") {
        return v1 + v2;
    }
    if (op == "-") {
        return v1 - v2;
    }
    if (op == "*") {
        return v1 * v2;
    }
    if (op == "/") {
        return v1 / v2;
    }
    return 0.0;
}

c_channel dados computador_1 computador_2

seq {
    print("==== T1 Calculadora - servidor (computador_2) ====");

    var op = "";
    var v1 = 0.0;
    var v2 = 0.0;
    var ignorado = 0.0;
    var continuar = true;

    while (continuar) {
        dados.receive(op, v1, v2, ignorado);

        if (op == "sair") {
            continuar = false;
            print("Servidor encerrando.");
        } else {
            print("Servidor recebeu:", op, format_float(v1, 1), format_float(v2, 1));

            var status = "OK";
            var resultado = 0.0;

            if (op != "+" && op != "-" && op != "*" && op != "/") {
                status = "ERRO: operacao invalida";
            } elif (op == "/" && v2 == 0.0) {
                status = "ERRO: divisao por zero";
            } else {
                resultado = calcular(op, v1, v2);
            }

            print("Servidor respondeu:", status, format_float(resultado, 1));
            dados.send(status, resultado, 0.0, 0.0);
        }
    }
}
