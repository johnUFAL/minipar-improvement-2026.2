# Teste 10 - 6 nucleos: avaliacao + Mandelbrot + Sierpinski (MiniPar 2026.2)
# Porte de benchmarks/t10_6_nucleos_avaliacao_2_fractais.py
#
# Nucleos 1..4: correcao das 160 atividades.
# Nucleo 5: Mandelbrot ASCII.
# Nucleo 6: Tapete de Sierpinski ASCII (substitui o Turtle do original).

func avaliar_atividade(tarefa: string, avaliador: string) {
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

func trabalhador_avaliacao(avaliador: string, inicio: int, quantidade: int) {
    var total = 0.0;
    var k = 0;
    while (k < quantidade) {
        var t = inicio + k;
        var aluno = t / 4 + 1;
        var atividade = t % 4 + 1;
        var tarefa = "Aluno " + str(aluno) + " - Atividade " + str(atividade);
        total = total + avaliar_atividade(tarefa, avaliador);
        k = k + 1;
    }
    print("[" + avaliador + "] Concluiu " + str(quantidade) + " atividades (checksum " + format_float(total, 2) + ")");
    return total;
}

func mandelbrot() {
    var largura = 50;
    var altura = 20;
    var max_iter = 100;
    var caracteres = " .:-=+#%@";
    var texto = "\n=== FRACTAL DE MANDELBROT (Gerado pelo Nucleo 5) ===\n";
    var y = 0;
    while (y < altura) {
        var linha = "";
        var cy = (float(y) / float(altura)) * 2.4 - 1.2;
        var x = 0;
        while (x < largura) {
            var cx = (float(x) / float(largura)) * 3.0 - 2.0;
            var zx = 0.0;
            var zy = 0.0;
            var iteracao = 0;
            while (zx * zx + zy * zy <= 4.0 && iteracao < max_iter) {
                var tmp = zx * zx - zy * zy + cx;
                zy = 2.0 * zx * zy + cy;
                zx = tmp;
                iteracao = iteracao + 1;
            }
            var idx = int((float(iteracao) / float(max_iter)) * float(len(caracteres) - 1));
            linha = linha + char_at(caracteres, idx);
            x = x + 1;
        }
        texto = texto + linha + "\n";
        y = y + 1;
    }
    texto = texto + "====================================================\n";
    return texto;
}

func sierpinski() {
    var tamanho = 27;
    var texto = "\n=== TAPETE DE SIERPINSKI (Gerado pelo Nucleo 6) ===\n";
    var y = 0;
    while (y < tamanho) {
        var linha = "";
        var x = 0;
        while (x < tamanho) {
            # Regra do tapete: a celula e vazia quando os digitos
            # correspondentes de x e y, na base 3, valem 1 ao mesmo tempo.
            var a = x;
            var b = y;
            var vazio = false;
            while (a > 0 || b > 0) {
                if ((a % 3 == 1) && (b % 3 == 1)) {
                    vazio = true;
                }
                a = int(a / 3);
                b = int(b / 3);
            }
            if (vazio) {
                linha = linha + " ";
            } else {
                linha = linha + "#";
            }
            x = x + 1;
        }
        texto = texto + linha + "\n";
        y = y + 1;
    }
    texto = texto + "====================================================\n";
    return texto;
}

seq {
    print("Carga de Trabalho: 160 atividades + Mandelbrot (ASCII) + Sierpinski (ASCII)");
    print("");

    print("--- 1. Executando Modo Sequencial (Apenas 1 Nucleo) ---");
    var inicio = clock();
    var total_seq = trabalhador_avaliacao("Professor", 0, 160);
    var fractal_seq = mandelbrot();
    var tapete_seq = sierpinski();
    var fim = clock();
    var tempo_seq = fim - inicio;
    print("Tempo Sequencial Concluido em:", format_float(tempo_seq, 2), "segundos");
    print("");

    print("--- 2. Executando Modo Paralelo (6 Nucleos Dedicados) ---");
    inicio = clock();
    fork prof em core(1) {
        var r_prof = trabalhador_avaliacao("Professor", 0, 40);
    }
    fork mon1 em core(2) {
        var r_mon1 = trabalhador_avaliacao("Monitor 1", 40, 40);
    }
    fork mon2 em core(3) {
        var r_mon2 = trabalhador_avaliacao("Monitor 2", 80, 40);
    }
    fork mon3 em core(4) {
        var r_mon3 = trabalhador_avaliacao("Monitor 3", 120, 40);
    }
    fork fractal em core(5) {
        var texto = mandelbrot();
        print(texto);
    }
    fork tapete em core(6) {
        var texto_tapete = sierpinski();
        print(texto_tapete);
    }
    join prof, mon1, mon2, mon3, fractal, tapete
    fim = clock();
    var tempo_par = fim - inicio;
    print("Tempo Paralelo Concluido em:  ", format_float(tempo_par, 2), "segundos");
    print("");

    var speedup = tempo_seq / tempo_par;
    var reducao = ((tempo_seq - tempo_par) / tempo_seq) * 100.0;
    print("==========================================");
    print("         BENCHMARK DE DESEMPENHO          ");
    print("==========================================");
    print("Nucleos Utilizados (Paralelo) : 6");
    print("Tempo Sequencial :", format_float(tempo_seq, 2), "s");
    print("Tempo Paralelo   :", format_float(tempo_par, 2), "s");
    print("Aceleracao       :", format_float(speedup, 2), "x mais rapido!");
    print("Reducao no tempo :", format_float(reducao, 1), "% de economia");
    print("==========================================");
}
