# Teste 1 — calculadora cliente-servidor multi-terminal

Este diretório contém o par usado para validar a comunicação real entre dois
processos:

- `t01_calculadora_servidor.mp` — executado com `--como computador_2`;
- `t01_calculadora_cliente.mp` — executado com `--como computador_1`.

O canal é único e bidirecional:

```minipar
c_channel dados computador_1 computador_2
```

O payload tem sempre quatro campos `(string, float, float, float)` para manter
aridade e tipos iguais nas duas direções.

## Execução automatizada

```powershell
.\.venv\Scripts\python.exe scripts\run_multiterminal.py --operacao + --v1 7 --v2 5
```

O script compila os dois programas, aloca uma porta livre, escreve um
`minipar.hosts` temporário, inicia o servidor, espera a porta e executa o
cliente.

## Execução manual

Crie um `minipar.hosts`:

```text
computador_1 = 127.0.0.1:5101
computador_2 = 127.0.0.1:5102
```

Em duas janelas:

```powershell
# janela 1 — servidor (deve iniciar primeiro)
.\t01_calculadora_servidor.exe --hosts .\minipar.hosts --como computador_2

# janela 2 — cliente
.\t01_calculadora_cliente.exe --hosts .\minipar.hosts --como computador_1
```

Entradas do cliente: `+`, `7`, `5`. Saída esperada: `Resultado: 12.0`.

## Por que não usar o menu interativo?

O menu multi-terminal apenas monitora a sessão; ele não inicia o segundo
processo nem passa `--como`/`--hosts`. Use o script acima para a troca real de
mensagens.
