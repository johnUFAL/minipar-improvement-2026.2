# Teste adicional 1: paralelismo com 3 nucleos (execucao local)
func quicksort_resumo() {
    return "PC1 QuickSort: [33,12,98,5,61] -> [5,12,33,61,98]";
}

func matrizes_resumo() {
    return "PC2 Matrizes: [[1,2],[3,4]] x [[5,6],[7,8]] -> [[19,22],[43,50]]";
}

func fatorial_resumo() {
    var n = 5;
    var fat = 1;
    var i = 1;
    while (i <= n) {
        fat = fat * i;
        i = i + 1;
    }
    return "PC3 Fatorial: 5! = 120";
}

seq {
    print("==== Teste adicional 1: paralelismo com 3 nucleos ====");
    print("Nucleo 1: QuickSort | Nucleo 2: Matrizes | Nucleo 3: Fatorial");

    fork pc1 em core(1) {
        print(quicksort_resumo());
    }
    fork pc2 em core(2) {
        print(matrizes_resumo());
    }
    fork pc3 em core(3) {
        print(fatorial_resumo());
    }
    join pc1, pc2, pc3

    print("==== Fim do teste adicional 1 ====");
}
