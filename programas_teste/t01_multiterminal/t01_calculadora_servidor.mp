# Teste 1 - Calculadora cliente-servidor (servidor)
#
# Executar no terminal servidor (computador_2):
#   t01_servidor.exe --hosts minipar.hosts --como computador_2
#
# O cliente (t01_cliente.mp) envia (operacao, operando1, operando2) pelo
# mesmo canal bidirecional e recebe o resultado. O payload tem sempre quatro
# campos (string, float, float, float) para manter aridade e tipos iguais nas
# duas direcoes.

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
        if (v2 == 0.0) {
            return 0.0;
        }
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
    dados.receive(op, v1, v2, ignorado);

    print("Servidor recebeu:", op, format_float(v1, 1), format_float(v2, 1));
    var resultado = calcular(op, v1, v2);
    print("Servidor calculou:", format_float(resultado, 1));

    dados.send("", 0.0, 0.0, resultado);
    print("Servidor enviou a resposta.");
}
