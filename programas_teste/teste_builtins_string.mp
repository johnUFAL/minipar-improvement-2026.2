# Teste da Fase 1 do MiniPar 2026.2: builtins de string/arquivo e tipo char.
seq {
    var texto = "MiniPar 2026.2";
    var primeira = char_at(texto, 0);
    var segunda = texto[1];
    var pedaco = substring(texto, 0, 7);
    var digito = '7';
    var espaco = ' ';
    var letra = 'M';
    var numero = is_number("123.5");
    var nao_numero = is_number("12a");

    print("primeira:", primeira);
    print("segunda:", segunda);
    print("pedaco:", pedaco);
    print("digito:", is_digit(digito));
    print("letra:", is_alpha(letra));
    print("espaco:", is_space(espaco));
    print("numero:", numero, nao_numero);

    var status = write_file("output/builtins_teste.txt", texto + "|" + pedaco);
    print("write_file:", status);
}
