# Exemplos para dois computadores

Todos os pares usam um unico canal declarativo e podem ser executados pela tela
**Conexao** com execucao automatica. Em cada par:

- `computador_1` e o lado que conecta;
- `computador_2` e o lado que escuta e deve iniciar primeiro.

## T2 - Jogo de adivinhacao

Arquivos:

- `t02_adivinha_servidor.mp` (`computador_2`);
- `t02_adivinha_cliente.mp` (`computador_1`).

O servidor guarda o numero secreto `37`. O cliente envia palpites e recebe
`maior`, `menor` ou `acertou`.

Entradas de teste no cliente:

```text
50
25
37
```

Saida esperada no cliente:

```text
Tente um numero menor.
Tente um numero maior.
Voce acertou em 3 tentativas!
```

Tambem e possivel digitar `sair` no lugar de um palpite para encerrar.

## T3 - Consulta de estoque

Arquivos:

- `t03_estoque_servidor.mp` (`computador_2`);
- `t03_estoque_cliente.mp` (`computador_1`).

Produtos cadastrados:

| Codigo | Produto | Preco |
| --- | --- | --- |
| `A100` | Caneta | 2.50 |
| `B200` | Caderno | 18.00 |
| `C300` | Mochila | 120.00 |

Entradas de teste no cliente:

```text
A100
3
B200
2
ZZZ
1
sair
```

Saida esperada:

```text
Produto: Caneta
Preco unitario: 2.50
Total: 7.50
Produto: Caderno
Preco unitario: 18.00
Total: 36.00
Erro: codigo nao encontrado.
```

## Execucao manual

No editor, abra o arquivo do servidor, execute e escolha o papel
`computador_2`. Informe o IP da maquina que escuta e uma porta livre. No outro
computador, abra o arquivo do cliente, escolha `computador_1` e conecte pelo
hub. Depois do aceite, a execucao automatica inicia os dois lados.

A porta de execucao do servidor tambem precisa estar liberada no firewall.
