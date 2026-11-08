func fatorial(n) {
    if (n <= 1) {
        return 1;
    }
    return n * fatorial(n - 1);
}

func fibonacci(n) {
    if (n <= 1) {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}

par {
    seq {
        var inicio_fatorial = clock();
        print("FATORIAL_INICIO", inicio_fatorial);
        var resultado = fatorial(10);
        print("Fatorial de 10:", resultado);
        while (clock() - inicio_fatorial < 0.25) {
            var manter_ocupado = 1;
        }
        print("FATORIAL_FIM", clock());
    }
    seq {
        var inicio_fibonacci = clock();
        print("FIBONACCI_INICIO", inicio_fibonacci);
        var indice = 0;
        while (indice < 10) {
            print("FIBONACCI", fibonacci(indice));
            indice = indice + 1;
        }
        while (clock() - inicio_fibonacci < 0.25) {
            var manter_ocupado = 1;
        }
        print("FIBONACCI_FIM", clock());
    }
}
