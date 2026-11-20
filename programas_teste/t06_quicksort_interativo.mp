class Quicksort {
    var array = [0];

    func carregar(arr) {
        this.array = arr;
    }

    func trocar(i, j) {
        var temp = this.array[i];
        this.array[i] = this.array[j];
        this.array[j] = temp;
    }

    func particionar(inicio, fim) {
        var pivot = this.array[fim];
        var i = inicio - 1;
        var j = inicio;
        while (j < fim) {
            if (this.array[j] <= pivot) {
                i = i + 1;
                this.trocar(i, j);
            }
            j = j + 1;
        }
        i = i + 1;
        this.trocar(i, fim);
        return i;
    }

    func quicksort(inicio, fim) {
        if (inicio < fim) {
            var p = this.particionar(inicio, fim);
            this.quicksort(inicio, p - 1);
            this.quicksort(p + 1, fim);
        }
    }

    func ordenar() {
        var n = len(this.array) - 1;
        if (n >= 0) {
            this.quicksort(0, n);
        }
        return this.array;
    }
}

seq {
    print("==== Ordenacao com Quicksort ====");
    print("Insira os elementos do vetor separados por espaco:");
    var vetor = [0];
    while (true) {
        var entrada = input("");
        var pedacos = dividir(entrada);
        var valido = len(pedacos) > 0;
        var i = 0;
        while (i < len(pedacos)) {
            if (not eh_inteiro(pedacos[i])) {
                valido = false;
            }
            i = i + 1;
        }
        if (valido) {
            vetor = parse_ints(entrada);
            break;
        }
        print("Entrada invalida. Digite apenas numeros inteiros separados por espaco:");
    }
    print("Vetor original:", vetor);
    var algoritmo = new Quicksort();
    algoritmo.carregar(vetor);
    var vetor_ordenado = algoritmo.ordenar();
    print("Vetor ordenado:", vetor_ordenado);
}
