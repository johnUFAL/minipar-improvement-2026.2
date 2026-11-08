class Neuronio {
    var input_val = 1;
    var output_desejado = 0;
    var peso = 0.5;
    var bias = 1;
    var peso_bias = 0.5;
    var taxa_aprendizado = 0.01;
    var erro = 999;
    var iteracao = 0;

    func ativacao(soma) {
        if (soma > 0) {
            return 1;
        }
        return 0;
    }

    func treinar() {
        print("==== Teste 3: neuronio simples com classes e objetos ====");
        print("Entrada:", this.input_val, "| Saída desejada:", this.output_desejado);

        while (this.erro != 0) {
            this.iteracao = this.iteracao + 1;

            var soma = (this.input_val * this.peso) + (this.bias * this.peso_bias);
            var saida = this.ativacao(soma);
            this.erro = this.output_desejado - saida;

            print("#### Iteração:", this.iteracao);
            print("Peso:", format_float(this.peso, 4));
            print("Saída:", saida);
            print("Erro:", this.erro);
            print("Peso do bias:", format_float(this.peso_bias, 4));

            if (this.erro != 0) {
                this.peso = this.peso + ((this.taxa_aprendizado * this.input_val) * this.erro);
                this.peso_bias = this.peso_bias + ((this.taxa_aprendizado * this.bias) * this.erro);
            }
        }

        print("✅ Parabéns! O neurônio aprendeu.");
        print("Valor desejado:", this.output_desejado);
    }
}

seq {
    var neuronio = new Neuronio();
    neuronio.treinar();
}
