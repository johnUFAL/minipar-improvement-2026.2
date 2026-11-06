# Execucao de programas MiniPar em rede

> **Teste 1 (2026.2):** o par `programas_teste/t01_multiterminal/` usa um canal
> lógico bidirecional e deve ser executado com dois processos. Use
> `python scripts/run_multiterminal.py --operacao + --v1 7 --v2 5` ou siga o
> procedimento manual em `programas_teste/t01_multiterminal/README.md`.
> O menu interativo apenas monitora sessões; ele não inicia os dois processos
> nem passa `--como`/`--hosts`. Por isso, testes multi-terminal são executados
> pelo runner scriptado.

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
