# Resultados das execuções — 06/11/2026

Arquivos gerados pela execução dos programas MiniPar 2026.2 nesta máquina
(Windows 10, GCC 16.2.0, 8 CPUs lógicas disponíveis).

| Arquivo | Programa | Resultado |
|---|---|---|
| `t08_saida.txt` | `t08_avaliacao_4_nucleos.mp` | 3,33× de speedup (0,59 s → 0,18 s) |
| `t09_saida.txt` | `t09_5_nucleos_4_avaliadores_1_fractal.mp` | 3,39× de speedup (0,54 s → 0,16 s) |
| `t10_saida.txt` | `t10_6_nucleos_avaliacao_2_fractais.mp` | 3,25× de speedup (0,54 s → 0,17 s) |
| `t11_saida.txt` | `t11_minicompilador_arm.mp` | 22.0, -84.0 e 22.0 |

Os arquivos `.arm` do Teste 11 estão versionados em
`programas_teste/teste11/` e foram validados com:

```bash
clang --target=armv7-none-eabi -x assembler -c programas_teste/teste11/expr1.arm -o expr1.o
clang --target=armv7-none-eabi -x assembler -c programas_teste/teste11/expr2.arm -o expr2.o
clang --target=armv7-none-eabi -x assembler -c programas_teste/teste11/expr3.arm -o expr3.o
```

A execução no CPUlator é manual: colar o conteúdo de cada `.arm`, compilar,
executar e conferir `r8` (22 na primeira e terceira expressões; -84 na segunda).
