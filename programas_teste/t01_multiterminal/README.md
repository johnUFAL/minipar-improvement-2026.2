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
aridade e tipos iguais nas duas direções:

```text
requisição: (op, v1, v2, 0.0)
resposta:   (status, resultado, 0.0, 0.0)
```

- `status = "OK"` em sucesso;
- `status = "ERRO: divisao por zero"` em `/0`;
- `status = "ERRO: operacao invalida"` para operador desconhecido.

O servidor fica em loop até receber `"sair"`, então continua atendendo após um
erro de divisão por zero.

> **Desvio em relação à issue #32:** a issue pede cliente e servidor no mesmo
> arquivo. Nesta entrega eles estão em dois arquivos que compartilham o mesmo
> canal lógico. O comportamento e os papéis por `--como` são os mesmos.

## Execução automatizada

```powershell
.\.venv\Scripts\python.exe scripts\run_multiterminal.py --scenario all
.\.venv\Scripts\python.exe scripts\run_multiterminal.py --requests "/,5,0;+,12,30;sair"
```

O script compila os dois programas, aloca portas livres, escreve um
`minipar.hosts` temporário, inicia o servidor, espera a porta e executa o
cliente com todas as requisições.

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

Entradas do cliente para testar soma e erro:

```text
+
12
30
/
5
0
sair
```

Saída esperada: `Resultado: 42.0` e depois `ERRO: divisao por zero`.

## Por que não usar o menu interativo?

O menu multi-terminal apenas monitora a sessão; ele não inicia o segundo
processo nem passa `--como`/`--hosts`. Use o script acima para a troca real de
mensagens.
