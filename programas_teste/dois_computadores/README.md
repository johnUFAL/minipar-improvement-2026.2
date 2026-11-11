# Exemplos para dois computadores

Todos os pares usam um unico canal declarativo e podem ser executados pela tela
**Conexao** com execucao automatica. Em cada par:

- `computador_1` e o lado que conecta;
- `computador_2` e o lado que escuta e deve iniciar primeiro.

## T2 - Jogo de adivinhacao

Arquivos:

- `t02_adivinha_servidor.mp` (`computador_2`);
- `t02_adivinha_cliente.mp` (`computador_1`).

O servidor escolhe o numero secreto (quem esta no servidor digita um valor de 1 a
100) e mostra cada palpite e a dica enviada. O cliente envia palpites e recebe
`maior`, `menor` ou `acertou`. O jogo termina no acerto ou com `sair`.

Entradas de teste: servidor `37`; cliente `50`, `25`, `37`.

Saida esperada no cliente:

```text
Tente um numero menor.
Tente um numero maior.
Voce acertou em 3 tentativas!
```

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

## T4 - Conversor de unidades

`t04_conversor_*.mp`. O cliente escolhe a conversao (`c2f`, `f2c`, `km2mi`,
`mi2km`, `kg2lb`, `lb2kg`) e o valor; o servidor calcula. Ex.: `c2f` com `100`
resulta em `212.00`. `sair` encerra.

## T5 - Cofre com senha

`t05_senha_*.mp`. Quem esta no servidor cadastra a senha; o cliente tem 3
tentativas e recebe uma dica (primeira letra) a cada erro. Apos o terceiro erro
o cofre e bloqueado.

## T6 - Pedra, papel e tesoura

`t06_jokenpo_*.mp`. O cliente digita sua jogada; o servidor digita a dele,
decide o vencedor e devolve o placar. `sair` encerra.

## T7 - Estatisticas remotas

`t07_estatisticas_*.mp`. O cliente envia numeros um a um; o servidor acumula e
devolve soma, media, maior e menor. `fim` encerra.

## Execucao manual

No editor, abra o arquivo do servidor, execute e escolha o papel
`computador_2`. Informe o IP da maquina que escuta e uma porta livre. No outro
computador, abra o arquivo do cliente, escolha `computador_1` e conecte pelo
hub. Depois do aceite, a execucao automatica inicia os dois lados.

A porta de execucao do servidor tambem precisa estar liberada no firewall.
