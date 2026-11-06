# Teste 2 com ERRO PROPOSITAL — usado para validar a interface de diagnóstico.
#
# O erro está no meio do bloco Fibonacci: uma variável declarada como int
# recebe uma string. O programa deve compilar a AST e o TAC até a fase
# semântica, mas a interface deve exibir o diagnóstico com linha e coluna.
#
# Não faz parte dos 11 testes oficiais; serve para testar a UI.

par {
    seq {
        var n = 5;
        var fat = 1;
        var i = 1;
        while (i <= n) {
            fat = fat * i;
            i = i + 1;
        }
        print("Fatorial de 5:", fat);
    }
    seq {
        var limite = 8;
        var a = 0;
        var b = 1;
        var i = 0;
        print("Fibonacci:");
        while (i < limite) {
            print(a);
            var prox = a + b;
            a = b;
            b = prox;
            i = i + 1;
        }

        # ERRO PROPOSITAL: int recebendo string.
        var resultado_invalido: int = "isto nao e um numero";
        print("Resultado invalido:", resultado_invalido);
    }
}
