# Teste 11 — arquivos `.arm`

Estes arquivos são gerados por
`programas_teste/t11_minicompilador_arm.mp` e correspondem às três expressões
do enunciado:

| Arquivo | Expressão | Resultado esperado |
|---|---|---|
| `expr1.arm` | `((2+4)*7)-(5*4)` | `22.0` |
| `expr2.arm` | `((10 -8*7)+4)*2` | `-84.0` |
| `expr3.arm` | `((2+4)*7)-(5*4)` | `22.0` |

Para regenerar:

```bash
python main.py compilar programas_teste/t11_minicompilador_arm.mp -O0 -o t11 --executar
```

Validação automática da sintaxe ARMv7:

```bash
clang --target=armv7-none-eabi -x assembler -c programas_teste/teste11/expr1.arm -o expr1.o
```

Validação manual no CPUlator:

1. abra <https://cpulator.01xz.net/?sys=arm-de1soc>;
2. cole o conteúdo de um `.arm` no editor;
3. compile e execute;
4. confira o registrador final (`r8`): 22, -84 e 22.

O Assembly não implementa divisão, seguindo o gabarito Java
(`@ divisão não suportada`).
