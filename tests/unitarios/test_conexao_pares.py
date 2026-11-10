import subprocess
import sys
import time

from interfaces.conexao.execucao import ExecucaoProcesso
from interfaces.web import conexao_api


def test_par_do_arquivo_troca_cliente_e_servidor() -> None:
    cliente = "t01_multiterminal/t01_calculadora_cliente.mp"
    servidor = "t01_multiterminal/t01_calculadora_servidor.mp"

    assert conexao_api._par_do_arquivo(cliente) == servidor
    assert conexao_api._par_do_arquivo(servidor) == cliente
    assert conexao_api._par_do_arquivo("t01_calculadora.mp") is None
    assert conexao_api._par_do_arquivo("../fora_cliente.mp") is None


def test_papeis_do_arquivo_seguem_o_nome() -> None:
    papeis = ["computador_1", "computador_2"]

    assert conexao_api._papeis_do_arquivo("x/a_cliente.mp", papeis) == (
        "computador_1",
        "computador_2",
    )
    assert conexao_api._papeis_do_arquivo("x/a_servidor.mp", papeis) == (
        "computador_2",
        "computador_1",
    )


def test_stdin_interativo_responde_a_linhas_digitadas() -> None:
    codigo = (
        "import sys\n"
        "nome = input('Nome: ')\n"
        "print('Ola,', nome)\n"
        "sys.stdout.flush()\n"
    )
    processo = subprocess.Popen(
        [sys.executable, "-u", "-c", codigo],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    execucao = ExecucaoProcesso(processo)
    try:
        limite = time.monotonic() + 5
        while "Nome:" not in execucao.estado()["stdout"]:
            assert time.monotonic() < limite
            time.sleep(0.02)
        # Sem entradas prévias o stdin continua aberto para digitação.
        execucao.escrever_entradas("")
        assert execucao.enviar_linha("Ana") is True
        assert execucao.aguardar(timeout=5) == 0
        execucao.juntar_threads()
        saida = execucao.estado()["stdout"]
        assert "Ana\n" in saida
        assert "Ola, Ana" in saida
        assert execucao.enviar_linha("tarde demais") is False
    finally:
        execucao.parar()
