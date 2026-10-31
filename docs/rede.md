# Execucao de programas MiniPar em rede

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
