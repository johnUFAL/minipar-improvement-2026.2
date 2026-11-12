func ler_nome() {
    var nome = input("Nome: ");
    return nome;
}

seq {
    var soma = 0;
    for i in range(5) {
        if (i == 3) {
            continue;
        }
        soma = soma + i;
    }

    var tentativas = 0;
    do {
        tentativas = tentativas + 1;
        if (tentativas == 2) {
            break;
        }
    } while (tentativas < 10);

    print("Controle OK:", soma, tentativas);
}
