# Teste 8 - Avaliacao de atividades em 4 nucleos (MiniPar 2026.2)
# Porte de benchmarks/t08_avaliacao_4_nucleos.py
#
# 160 atividades (40 alunos x 4 atividades) sao corrigidas por 4 avaliadores,
# cada um fixado em um nucleo de CPU diferente via fork ... em core(n).

func avaliar_atividade(tarefa: string, avaliador: string, semente: int) {
    random_seed(semente);
    var tempo_correcao = random_uniforme(0.05, 0.15);
    var iteracoes = int(tempo_correcao * 20000000.0);
    var soma = 0.0;
    var i = 0;
    while (i < iteracoes) {
        soma = soma * 1.0000001 + 1.0;
        i = i + 1;
    }
    return soma;
}

func trabalhador(avaliador: string, inicio: int, quantidade: int) {
    var total = 0.0;
    var k = 0;
    while (k < quantidade) {
        var t = inicio + k;
        var aluno = t / 4 + 1;
        var atividade = t % 4 + 1;
        var tarefa = "Aluno " + str(aluno) + " - Atividade " + str(atividade);
        total = total + avaliar_atividade(tarefa, avaliador, t);
        k = k + 1;
    }
    print("[" + avaliador + "] Concluiu " + str(quantidade) + " atividades (checksum " + format_float(total, 2) + ")");
    return total;
}

seq {
    print("Total de Atividades a Avaliar: 160 (40 alunos x 4 atividades)");
    print("");

    print("--- 1. Executando Modo Sequencial (Apenas 1 Nucleo / Professor) ---");
    var inicio = clock();
    var total_seq = trabalhador("Professor", 0, 160);
    var fim = clock();
    var tempo_seq = fim - inicio;
    print("Tempo Sequencial Concluido em:", format_float(tempo_seq, 2), "segundos");
    print("");

    print("--- 2. Executando Modo Paralelo (4 Nucleos Dedicados) ---");
    inicio = clock();
    fork prof em core(1) {
        var r_prof = trabalhador("Professor", 0, 40);
    }
    fork mon1 em core(2) {
        var r_mon1 = trabalhador("Monitor 1", 40, 40);
    }
    fork mon2 em core(3) {
        var r_mon2 = trabalhador("Monitor 2", 80, 40);
    }
    fork mon3 em core(4) {
        var r_mon3 = trabalhador("Monitor 3", 120, 40);
    }
    join prof, mon1, mon2, mon3
    fim = clock();
    var tempo_par = fim - inicio;
    print("Tempo Paralelo Concluido em:  ", format_float(tempo_par, 2), "segundos");
    print("");

    var speedup = tempo_seq / tempo_par;
    var reducao = ((tempo_seq - tempo_par) / tempo_seq) * 100.0;
    print("==========================================");
    print("         BENCHMARK DE DESEMPENHO          ");
    print("==========================================");
    print("Nucleos Utilizados (Paralelo) : 4");
    print("Tempo Sequencial :", format_float(tempo_seq, 2), "s");
    print("Tempo Paralelo   :", format_float(tempo_par, 2), "s");
    print("Aceleracao       :", format_float(speedup, 2), "x mais rapido!");
    print("Reducao no tempo :", format_float(reducao, 1), "% de economia");
    print("==========================================");
}
