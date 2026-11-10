# Execucao de programas MiniPar em rede

> **Teste 1 (2026.2):** o par `programas_teste/t01_multiterminal/` usa um canal
> lógico bidirecional e deve ser executado com dois processos. Use
> `python scripts/run_multiterminal.py --scenario all` para validar as quatro
> operações, divisão por zero e operação inválida. O procedimento manual está em
> `programas_teste/t01_multiterminal/README.md`.
> O menu interativo oferece o hub de conexão (opção **3**), que pareia os dois
> participantes. Na GUI, o chat e a execução automática (quando o programa usa
> um canal declarativo) ficam disponíveis depois do aceite. Também é possível
> executar manualmente pelo runner scriptado ou por `--hosts`/`--como`.

## Hub de conexao

O hub é um ponto único de encontro em TCP. Ele registra participantes, isola
salas privadas, pareia dois lados por pedido/aceite e relay as mensagens de
chat. A conexão é sempre 1:1: um participante não pode estar conectado a dois
outros ao mesmo tempo, e cada sala privada aceita no máximo dois membros.

No terminal, abra o menu principal e escolha **3 - Conexao (Hub)**. Na GUI,
abra o item **Conexao** na barra lateral, inicie o hub local ou informe o
endereço de um hub existente, crie/entre em uma sala, selecione o participante
e aguarde o aceite. O chat da GUI só é habilitado depois do aceite dos dois
lados.

### Endereço de escuta e servidores disponíveis

Na GUI, o campo **Ouvir em** define em qual interface o hub local aceita
conexões:

- `0.0.0.0` escuta em todas as interfaces (recomendado quando a máquina tem
  Wi-Fi, Ethernet ou VPN e você não sabe qual será usada);
- um IP específico limita o hub àquela interface.

Depois de iniciar, a lista **Servidores disponíveis** mostra o hub local e os
endereços já usados/salvos neste navegador, com indicação de disponibilidade.
Clique em um servidor para preencher **Endereço do hub** e **Porta**, ou use
**Atualizar** para testar novamente os servidores salvos. O botão **Procurar na
rede** envia uma descoberta UDP e adiciona hubs MiniPar encontrados na mesma
rede. O campo **Endereço do hub** é o endereço remoto usado para conectar; ele
não altera o endereço de escuta do hub local.

Para a descoberta automática funcionar, libere também a porta UDP `5011` no
firewall da máquina que hospeda o hub. Se a rede bloquear broadcast, informe o
endereço manualmente e use **Atualizar** para testar.

Se outro computador não conseguir conectar, confira se o hub está escutando em
`0.0.0.0` (ou no IP correto), se a porta TCP está liberada no firewall e se o
endereço informado pertence à mesma rede. Evite usar endereços de VPN ou
adaptadores virtuais quando os dois computadores estiverem na LAN.

Inicie o hub em uma das máquinas:

```powershell
python -m interfaces.conexao.hub --porta 5010
```

Na outra máquina, use o endereço mostrado pelo comando (`IP:5010`). A porta TCP
precisa estar liberada no firewall da máquina que hospeda o hub. As mensagens
trafegam em JSON por linha e não há autenticação de rede: use o hub em uma rede
confiável.

Programas MiniPar que usam `c_channel` com `send`/`receive` redirecionam para a
tela de conexão quando executados no editor da GUI. Depois do aceite, a GUI
coordena a execução automática dos dois lados: o papel que escuta abre a porta,
avisa quando está pronto e o papel que conecta inicia em seguida. A conexão e
o chat permanecem ativos ao trocar de tela; o hub é encerrado pelo botão
**Desligar**, pelo fechamento da aba (após o timeout de inatividade) ou quando
o processo local termina.

A execução manual pelo runtime de canais continua disponível:

```powershell
python scripts/run_multiterminal.py --scenario all
```

Pares adicionais para dois computadores estão em
`programas_teste/dois_computadores/`:

- T2: `t02_adivinha_servidor.mp` e `t02_adivinha_cliente.mp`;
- T3: `t03_estoque_servidor.mp` e `t03_estoque_cliente.mp`;
- T4: conversor de unidades, T5: cofre com senha, T6: pedra/papel/tesoura e T7: estatísticas remotas (`t04_*` a `t07_*`, sufixos `_servidor` e `_cliente`).

O [README dos exemplos](../programas_teste/dois_computadores/README.md) traz
papéis, entradas de teste e saídas esperadas.

## Teste 1 — protocolo da calculadora

O canal `dados` troca quatro campos em ambas as direções:

```text
requisição: (op, v1, v2, 0.0)
resposta:   (status, resultado, 0.0, 0.0)
```

- `status = "OK"` em sucesso;
- `status = "Erro: divisao por zero."` em `/0`;
- `status = "Erro: operacao invalida."` para operador desconhecido.

O servidor fica em loop até receber `"sair"`. Assim, um erro de divisão por zero
não derruba o serviço: ele responde o erro e atende a próxima requisição.

Exemplo de execução local completa:

```powershell
python scripts/run_multiterminal.py --scenario all
```

Exemplo com requisições explícitas:

```powershell
python scripts/run_multiterminal.py --requests "/,5,0;+,12,30;sair"
```

Os nomes usados na declaracao `c_channel` sao logicos. O endereco e a porta de
cada computador ficam em `minipar.hosts`, portanto a topologia pode mudar sem
recompilar o programa.

## Arquivo de hosts

O formato e uma entrada por linha:

```text
computador_1 = 127.0.0.1:5001
computador_2 = 127.0.0.1:5002
```

Linhas vazias e comentarios iniciados por `#` sao ignorados. A porta deve estar
entre 1 e 65535. Por padrao, o runtime procura `minipar.hosts` no diretorio
atual; use `--hosts caminho` para indicar outro arquivo.

## Teste em localhost

Compile o programa uma vez e abra dois terminais no mesmo computador. Inicie o
terminal servidor primeiro e depois o cliente:

```powershell
.\output\programa.exe --hosts .\minipar.hosts --como computador_2
.\output\programa.exe --hosts .\minipar.hosts --como computador_1
```

O nome informado em `--como` define o papel deste processo. Para um canal
declarado como `c_channel dados computador_1 computador_2`, o processo
`computador_1` conecta ao endereco de `computador_2`; `computador_2` aguarda na
porta configurada para si.

## Teste em dois computadores

Copie o mesmo executavel para as duas maquinas e edite `minipar.hosts` em cada
uma para apontar `computador_1` e `computador_2` aos enderecos alcancaveis entre
elas. A entrada local deve usar a porta em que o processo servidor vai
aguardar; a entrada remota deve apontar para o endereco da maquina servidora.
Execute o mesmo programa com `--como computador_2` na maquina servidora e
`--como computador_1` na cliente. A alteracao do arquivo de hosts nao exige
recompilacao.

Libere no firewall da maquina servidora a porta TCP configurada para o seu
nome logico (por exemplo, 5002), permitindo conexoes de entrada das maquinas
cliente. Verifique tambem regras de rede, NAT e roteamento: os enderecos no
arquivo precisam ser acessiveis pela outra maquina. Se mudar a porta,
atualize a configuracao e a regra de firewall correspondente.

Um papel inexistente ou nao declarado no arquivo produz erro de execucao com
os nomes validos encontrados na configuracao.

## Fork remoto

O codegen cria, junto do executavel MiniPar, uma copia chamada
`minipar_worker` (`minipar_worker.exe` no Windows). Ela contem o mesmo codigo
e os handlers das subtarefas do programa. Argumentos e resultados simples
(`int`, `float`, `bool` e `string`) sao enviados por valor pelo protocolo tipado
do canal; cada subtarefa remota tem um nome de tarefa estavel no programa.

Declare os nomes logicos e os enderecos/portas dos workers no arquivo de hosts:

```text
computador_1 = 192.0.2.10:5001
computador_2 = 192.0.2.11:5002
```

Inicie um worker em cada maquina, usando a porta configurada para ela:

```powershell
.\minipar_worker.exe --porta 5001
.\minipar_worker.exe --porta 5002
```

Execute o programa cliente, que deve usar `fork nome em host("computador_2")`
para encaminhar a subtarefa ao worker correspondente:

```powershell
.\programa.exe --hosts .\minipar.hosts
```

Copie para todas as maquinas o mesmo `minipar_worker` gerado para o programa,
altere `minipar.hosts` para os enderecos alcancaveis e libere as portas dos
workers no firewall. O cliente falha com erro de conexao ou timeout se o worker
nao estiver acessivel. O timeout de conexao/resposta pode ser configurado em
milissegundos pela variavel `MINIPAR_TIMEOUT_MS` (padrao: 5000).

Para validar em dois computadores reais, inicie os workers, execute o programa
cliente e registre neste documento os sistemas operacionais, configuracao de
hosts/portas, comandos e resultados observados (incluindo os resultados
recebidos em `join`). A integracao automatizada valida duas subtarefas remotas
em localhost; essa verificacao nao substitui a execucao em maquinas reais
prevista em T41.
