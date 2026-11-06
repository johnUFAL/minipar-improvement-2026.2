# Teste 1 - Calculadora cliente-servidor (cliente)
#
# Executar no terminal cliente (computador_1):
#   t01_cliente.exe --hosts minipar.hosts --como computador_1
#
# Entradas esperadas: operacao (+,-,*,/) e dois operandos.
# O payload tem sempre quatro campos (string, float, float, float).

c_channel dados computador_1 computador_2

seq {
    print("==== T1 Calculadora - cliente (computador_1) ====");

    var op = input("Operacao (+,-,*,/): ");
    var v1 = to_number(input("Operando 1: "));
    var v2 = to_number(input("Operando 2: "));

    print("Cliente enviou:", op, format_float(v1, 1), format_float(v2, 1));
    dados.send(op, v1, v2, 0.0);

    var resposta_op = "";
    var r1 = 0.0;
    var r2 = 0.0;
    var resultado = 0.0;
    dados.receive(resposta_op, r1, r2, resultado);

    print("Resultado:", format_float(resultado, 1));
}
