# Scripts de teste — MiniPar 2026.2

## `run_testes_2026_2.py`

Executa os 11 testes (T1–T11) de forma reproduzível.

```powershell
.\.venv\Scripts\python.exe scripts\run_testes_2026_2.py
.\.venv\Scripts\python.exe scripts\run_testes_2026_2.py --only t1,t11
.\.venv\Scripts\python.exe scripts\run_testes_2026_2.py --update-expected
```

- Compila cada programa em um diretório temporário.
- Fornece entradas fixas para T1, T5 e T6.
- Executa T1 como dois processos reais (servidor/cliente).
- Valida T8–T10 por marcos de saída (os tempos variam).
- Valida T11 pelos resultados e pelos três `.arm`, incluindo `clang` quando disponível.
- Grava logs em `docs/relatorio/resultados/testes_2026_2/`.

## `run_multiterminal.py`

Executa apenas o T1 com dois processos:

```powershell
.\.venv\Scripts\python.exe scripts\run_multiterminal.py --operacao + --v1 7 --v2 5
```

O script:

1. compila `t01_calculadora_servidor.mp` e `t01_calculadora_cliente.mp`;
2. aloca uma porta livre e escreve um `minipar.hosts` temporário;
3. inicia o servidor com `--como computador_2`;
4. espera a porta entrar em `LISTENING` (sem consumir o `accept`);
5. executa o cliente com `--como computador_1`;
6. compara as saídas e encerra os processos.

## Por que não usar o menu “multi-terminal” para T1?

O menu interativo (`python main.py` → opção 1) cria uma sessão e mostra o
progresso dos participantes, mas **apenas o terminal iniciador compila e
executa** o binário. Ele não inicia o segundo processo nem passa `--como` ou
`--hosts`. Para validar a troca real de mensagens, use os scripts acima.

O procedimento manual de duas janelas continua disponível:

```powershell
# janela 1 (servidor)
.\t01_servidor.exe --hosts .\minipar.hosts --como computador_2

# janela 2 (cliente)
.\t01_cliente.exe --hosts .\minipar.hosts --como computador_1
```

Com `minipar.hosts`:

```text
computador_1 = 127.0.0.1:5101
computador_2 = 127.0.0.1:5102
```

O servidor deve ser iniciado primeiro. O canal lógico é único e bidirecional
(`c_channel dados computador_1 computador_2`).
