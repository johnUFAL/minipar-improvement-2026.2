# Teste 11 - Minicompilador de expressoes infixadas com geracao de Assembly ARMv7
# Porte de MiniCompiladorCompleto_ARMv7.java para MiniPar 2026.2.
#
# Para cada expressao o programa imprime tokens, AST, TAC, Assembly ARMv7,
# tabela de simbolos e resultado final, e grava o Assembly em um arquivo .arm
# pronto para colar no CPUlator.

class MiniCompiladorARM {
    var entrada = "";
    var pos = 0;
    var temp_count = 1;
    var reg_count = 0;
    var ast = "";
    var asm = "";
    var ultima_expr = "";
    var simbolos_num = "";
    var simbolos_var = "";

    # ------------------------------------------------------------------
    # Utilidades de string
    # ------------------------------------------------------------------
    func contem(texto: string, alvo: string) -> bool {
        var n = len(alvo);
        if (n == 0) {
            return true;
        }
        var i = 0;
        while (i + n <= len(texto)) {
            if (substring(texto, i, i + n) == alvo) {
                return true;
            }
            i = i + 1;
        }
        return false;
    }

    func indentacao(nivel: int) -> string {
        var texto = "";
        var i = 0;
        while (i < nivel) {
            texto = texto + "  ";
            i = i + 1;
        }
        return texto;
    }

    func eh_operador(token: string) -> bool {
        return token == "+" || token == "-" || token == "*" || token == "/";
    }

    func eh_no_composto(texto: string) -> bool {
        return len(texto) > 0 && char_at(texto, 0) == "(";
    }

    func fim_expressao(texto: string, inicio: int) -> int {
        if (char_at(texto, inicio) == "(") {
            var nivel = 0;
            var i = inicio;
            while (i < len(texto)) {
                var c = char_at(texto, i);
                if (c == "(") {
                    nivel = nivel + 1;
                }
                if (c == ")") {
                    nivel = nivel - 1;
                    if (nivel == 0) {
                        return i + 1;
                    }
                }
                i = i + 1;
            }
            return len(texto);
        }
        var j = inicio;
        while (j < len(texto) && not is_space(char_at(texto, j)) && char_at(texto, j) != ")") {
            j = j + 1;
        }
        return j;
    }

    func operador_de(texto: string) -> string {
        var i = 1;
        while (i < len(texto) && is_space(char_at(texto, i))) {
            i = i + 1;
        }
        var inicio = i;
        while (i < len(texto) && not is_space(char_at(texto, i)) && char_at(texto, i) != ")") {
            i = i + 1;
        }
        return substring(texto, inicio, i);
    }

    func esquerda_de(texto: string) -> string {
        var i = 1;
        while (i < len(texto) && not is_space(char_at(texto, i))) {
            i = i + 1;
        }
        while (i < len(texto) && is_space(char_at(texto, i))) {
            i = i + 1;
        }
        var fim = this.fim_expressao(texto, i);
        return substring(texto, i, fim);
    }

    func direita_de(texto: string) -> string {
        var i = 1;
        while (i < len(texto) && not is_space(char_at(texto, i))) {
            i = i + 1;
        }
        while (i < len(texto) && is_space(char_at(texto, i))) {
            i = i + 1;
        }
        var fim_esq = this.fim_expressao(texto, i);
        var j = fim_esq;
        while (j < len(texto) && is_space(char_at(texto, j))) {
            j = j + 1;
        }
        return substring(texto, j, len(texto) - 1);
    }

    # ------------------------------------------------------------------
    # Analise lexica
    # ------------------------------------------------------------------
    func char_atual() -> string {
        if (this.pos < len(this.entrada)) {
            return char_at(this.entrada, this.pos);
        }
        return "";
    }

    func tokenizar() {
        this.pos = 0;
        while (this.pos < len(this.entrada)) {
            var c = this.char_atual();
            if (is_space(c)) {
                this.pos = this.pos + 1;
            } elif (is_digit(c) || c == ".") {
                var lexema = "";
                while (this.pos < len(this.entrada) && (is_digit(this.char_atual()) || this.char_atual() == ".")) {
                    lexema = lexema + this.char_atual();
                    this.pos = this.pos + 1;
                }
                print("[NUMERO: '" + lexema + "']");
            } elif (is_alpha(c) || c == "_") {
                var lexema = "";
                while (this.pos < len(this.entrada) && (is_alpha(this.char_atual()) || is_digit(this.char_atual()) || this.char_atual() == "_")) {
                    lexema = lexema + this.char_atual();
                    this.pos = this.pos + 1;
                }
                print("[IDENTIFICADOR: '" + lexema + "']");
            } elif (c == "+" || c == "-" || c == "*" || c == "/") {
                print("[OPERADOR: '" + c + "']");
                this.pos = this.pos + 1;
            } elif (c == "=") {
                print("[ATRIBUICAO: '=']");
                this.pos = this.pos + 1;
            } elif (c == "(" || c == ")") {
                print("[PARENTESE: '" + c + "']");
                this.pos = this.pos + 1;
            } elif (c == "#") {
                this.pos = len(this.entrada);
            } else {
                this.pos = this.pos + 1;
            }
        }
    }

    # ------------------------------------------------------------------
    # Analise sintatica: AST em forma parentetizada, ex.: ((2 + 4) * 7)
    # ------------------------------------------------------------------
    func pular_espacos() {
        while (this.pos < len(this.entrada) && is_space(this.char_atual())) {
            this.pos = this.pos + 1;
        }
    }

    func registrar_simbolo(token: string) {
        if (len(token) == 0 || this.eh_operador(token)) {
            return;
        }
        if (is_number(token)) {
            if (not this.contem(" " + this.simbolos_num + " ", " " + token + " ")) {
                this.simbolos_num = this.simbolos_num + " " + token;
            }
        } else {
            if (not this.contem(" " + this.simbolos_var + " ", " " + token + " ")) {
                this.simbolos_var = this.simbolos_var + " " + token;
            }
        }
    }

    func parse_expr() -> string {
        var node = this.parse_termo();
        this.pular_espacos();
        while (this.pos < len(this.entrada) && (this.char_atual() == "+" || this.char_atual() == "-")) {
            var op = this.char_atual();
            this.pos = this.pos + 1;
            var direita = this.parse_termo();
            node = "(" + op + " " + node + " " + direita + ")";
            this.pular_espacos();
        }
        return node;
    }

    func parse_termo() -> string {
        var node = this.parse_fator();
        this.pular_espacos();
        while (this.pos < len(this.entrada) && (this.char_atual() == "*" || this.char_atual() == "/")) {
            var op = this.char_atual();
            this.pos = this.pos + 1;
            var direita = this.parse_fator();
            node = "(" + op + " " + node + " " + direita + ")";
            this.pular_espacos();
        }
        return node;
    }

    func parse_fator() -> string {
        this.pular_espacos();
        var c = this.char_atual();
        if (c == "(") {
            this.pos = this.pos + 1;
            var node = this.parse_expr();
            this.pular_espacos();
            if (this.pos < len(this.entrada) && this.char_atual() == ")") {
                this.pos = this.pos + 1;
            }
            return node;
        }
        var lexema = "";
        if (is_digit(c) || c == ".") {
            while (this.pos < len(this.entrada) && (is_digit(this.char_atual()) || this.char_atual() == ".")) {
                lexema = lexema + this.char_atual();
                this.pos = this.pos + 1;
            }
        } else {
            while (this.pos < len(this.entrada) && (is_alpha(this.char_atual()) || is_digit(this.char_atual()) || this.char_atual() == "_")) {
                lexema = lexema + this.char_atual();
                this.pos = this.pos + 1;
            }
        }
        this.registrar_simbolo(lexema);
        return lexema;
    }

    # ------------------------------------------------------------------
    # Impressao da AST (direita, raiz, esquerda)
    # ------------------------------------------------------------------
    func imprimir_ast(texto: string, nivel: int) {
        if (not this.eh_no_composto(texto)) {
            print(this.indentacao(nivel) + texto);
            return;
        }
        var op = this.operador_de(texto);
        var esq = this.esquerda_de(texto);
        var dir = this.direita_de(texto);
        this.imprimir_ast(dir, nivel + 1);
        print(this.indentacao(nivel) + op);
        this.imprimir_ast(esq, nivel + 1);
    }

    # ------------------------------------------------------------------
    # TAC
    # ------------------------------------------------------------------
    func gerar_tac(texto: string) -> string {
        if (not this.eh_no_composto(texto)) {
            return texto;
        }
        var op = this.operador_de(texto);
        var esq = this.esquerda_de(texto);
        var dir = this.direita_de(texto);
        var a1 = this.gerar_tac(esq);
        var a2 = this.gerar_tac(dir);
        var temp = "t" + str(this.temp_count);
        this.temp_count = this.temp_count + 1;
        print(temp + " = " + a1 + " " + op + " " + a2);
        return temp;
    }

    # ------------------------------------------------------------------
    # Assembly ARMv7
    # ------------------------------------------------------------------
    func formatar_expr(texto: string) -> string {
        if (not this.eh_no_composto(texto)) {
            return texto;
        }
        var op = this.operador_de(texto);
        var esq = this.esquerda_de(texto);
        var dir = this.direita_de(texto);
        return "(" + this.formatar_expr(esq) + " " + op + " " + this.formatar_expr(dir) + ")";
    }

    func gerar_arm(texto: string) -> string {
        if (not this.eh_no_composto(texto)) {
            var reg = "r" + str(this.reg_count);
            this.reg_count = this.reg_count + 1;
            var linha = "    MOV    " + reg + ", #" + texto;
            this.asm = this.asm + linha + "\n";
            print(linha);
            return reg;
        }

        var op = this.operador_de(texto);
        var esq = this.esquerda_de(texto);
        var dir = this.direita_de(texto);
        var a1 = this.gerar_arm(esq);
        var a2 = this.gerar_arm(dir);
        var reg = "r" + str(this.reg_count);
        this.reg_count = this.reg_count + 1;
        var expr = this.formatar_expr(texto);
        var linha = "";

        if (op == "+") {
            linha = "    ADD    " + reg + ", " + a1 + ", " + a2 + "    @ resultado de '" + expr + "'";
        } elif (op == "-") {
            linha = "    SUB    " + reg + ", " + a1 + ", " + a2 + "    @ resultado de '" + expr + "'";
        } elif (op == "*") {
            linha = "    MUL    " + reg + ", " + a1 + ", " + a2 + "    @ resultado de '" + expr + "'";
        } else {
            linha = "    @ divisão não suportada: " + a1 + " / " + a2 + "    @ resultado de '" + expr + "'";
        }

        this.asm = this.asm + linha + "\n";
        print(linha);
        return reg;
    }

    # ------------------------------------------------------------------
    # Tabela de simbolos (constantes em ordem numerica, depois variaveis)
    # ------------------------------------------------------------------
    func contar_tokens(texto: string) -> int {
        if (len(texto) == 0) {
            return 0;
        }
        var total = 1;
        var i = 0;
        while (i < len(texto)) {
            if (is_space(char_at(texto, i))) {
                total = total + 1;
            }
            i = i + 1;
        }
        return total;
    }

    func imprimir_simbolos() {
        var total = this.contar_tokens(this.simbolos_num);
        var ultimo = -1000000000.0;
        var k = 0;
        while (k < total) {
            var menor = -1.0;
            var menor_token = "";
            var i = 0;
            while (i < len(this.simbolos_num)) {
                while (i < len(this.simbolos_num) && is_space(char_at(this.simbolos_num, i))) {
                    i = i + 1;
                }
                var j = i;
                while (j < len(this.simbolos_num) && not is_space(char_at(this.simbolos_num, j))) {
                    j = j + 1;
                }
                var token = substring(this.simbolos_num, i, j);
                if (len(token) > 0) {
                    var valor = to_number(token);
                    if (valor > ultimo && (menor < 0.0 || valor < menor)) {
                        menor = valor;
                        menor_token = token;
                    }
                }
                i = j + 1;
            }
            if (menor < 0.0) {
                k = total;
            } else {
                print("🔹 " + menor_token + " → CONST");
                ultimo = menor;
                k = k + 1;
            }
        }

        var i2 = 0;
        while (i2 < len(this.simbolos_var)) {
            while (i2 < len(this.simbolos_var) && is_space(char_at(this.simbolos_var, i2))) {
                i2 = i2 + 1;
            }
            var j2 = i2;
            while (j2 < len(this.simbolos_var) && not is_space(char_at(this.simbolos_var, j2))) {
                j2 = j2 + 1;
            }
            var nome = substring(this.simbolos_var, i2, j2);
            if (len(nome) > 0) {
                print("🔹 " + nome + " → VAR");
            }
            i2 = j2 + 1;
        }
    }

    # ------------------------------------------------------------------
    # Avaliacao
    # ------------------------------------------------------------------
    func avaliar(texto: string) -> float {
        if (not this.eh_no_composto(texto)) {
            if (is_number(texto)) {
                return to_number(texto);
            }
            print("Aviso: variavel '" + texto + "' sem valor atribuido. Usando 0.");
            return 0.0;
        }
        var op = this.operador_de(texto);
        var esq = this.avaliar(this.esquerda_de(texto));
        var dir = this.avaliar(this.direita_de(texto));
        if (op == "+") {
            return esq + dir;
        }
        if (op == "-") {
            return esq - dir;
        }
        if (op == "*") {
            return esq * dir;
        }
        if (op == "/") {
            if (dir == 0.0) {
                return 0.0;
            }
            return esq / dir;
        }
        return 0.0;
    }

    # ------------------------------------------------------------------
    # Fluxo completo de uma expressao
    # ------------------------------------------------------------------
    func executar(expressao: string, arquivo: string) {
        this.entrada = expressao;
        this.pos = 0;
        this.temp_count = 1;
        this.reg_count = 0;
        this.ast = "";
        this.asm = "";
        this.ultima_expr = "";
        this.simbolos_num = "";
        this.simbolos_var = "";

        print("==================================================");
        print("Expressao: " + expressao);
        print("");

        print("🔍 Tokens gerados pelo analisador léxico:");
        this.tokenizar();

        this.pos = 0;
        this.ast = this.parse_expr();

        print("");
        print("🌳 Árvore Sintática Abstrata (AST):");
        this.imprimir_ast(this.ast, 0);

        print("");
        print("📦 Código de Três Endereços (TAC):");
        this.gerar_tac(this.ast);

        print("");
        print("⚙️ Assembly ARMv7 (CPUlator):");
        this.asm = ".global _start\n.text\n_start:\n";
        print(".global _start");
        print(".text");
        print("_start:");
        this.gerar_arm(this.ast);
        var parada = "    b .    @ loop infinito para parar o programa";
        this.asm = this.asm + parada + "\n";
        print(parada);

        print("");
        print("📚 Tabela de Símbolos:");
        this.imprimir_simbolos();

        print("");
        print("🧮 Resultado final da expressão:");
        var resultado = this.avaliar(this.ast);
        print("➡️  " + format_float(resultado, 1));

        var status = write_file(arquivo, this.asm);
        if (status == 0) {
            print("[OK] Assembly salvo em " + arquivo);
        } else {
            print("[ERRO] Nao foi possivel salvar " + arquivo);
        }
        print("");
    }
}

seq {
    print("==== Teste 11: minicompilador MiniPar -> Assembly ARMv7 ====");
    print("");

    var compilador = new MiniCompiladorARM();
    compilador.executar("((2+4)*7)-(5*4)", "programas_teste/teste11/expr1.arm");
    compilador.executar("((10 -8*7)+4)*2", "programas_teste/teste11/expr2.arm");
    compilador.executar("((2+4)*7)-(5*4)", "programas_teste/teste11/expr3.arm");

    print("==== Fim do Teste 11 ====");
}
