"""Executa de verdade cada par cliente/servidor de ``dois_computadores``."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from run_multiterminal import (  # noqa: E402
    build_program,
    free_port,
    wait_for_listening,
)

PASTA = ROOT / "programas_teste" / "dois_computadores"

pytestmark = pytest.mark.skipif(
    shutil.which(os.environ.get("CXX", "g++").strip('"')) is None,
    reason="g++ é necessário para executar os pares",
)

# (prefixo, entradas do servidor, entradas do cliente, trechos esperados no
# cliente, trechos esperados no servidor)
CASOS = [
    (
        "t02_adivinha",
        "37\n",
        "50\n25\n37\n",
        ["menor", "maior", "acertou em 3"],
        ["Numero secreto: 37", "acertou em 3"],
    ),
    (
        "t03_estoque",
        "",
        "A100\n3\nB200\n2\nZZZ\n1\nsair\n",
        ["Total: 7.50", "Total: 36.00", "codigo nao encontrado"],
        ["Consulta: A100"],
    ),
    (
        "t04_conversor",
        "",
        "c2f\n100\nkm2mi\n10\nxx\n1\nsair\n",
        ["212.00", "6.21", "conversao desconhecida"],
        ["Pedido: c2f"],
    ),
    (
        "t05_senha",
        "abelha\n",
        "errada\nabelha\n",
        ["Senha incorreta", "comeca com 'a'", "Cofre aberto"],
        ["Tentativa errada: errada", "cofre aberto"],
    ),
    (
        "t05_senha",
        "abelha\n",
        "a\nb\nc\n",
        ["Cofre bloqueado"],
        ["erro 3 de 3"],
    ),
    (
        "t06_jokenpo",
        "tesoura\npapel\n",
        "pedra\nxx\nsair\n",
        ["Servidor jogou: tesoura -> voce ganhou", "Jogada invalida"],
        ["Rodada 1", "invalida"],
    ),
    (
        "t07_estatisticas",
        "",
        "10\nabc\n20\nfim\n",
        ["Soma: 30.00", "Media: 15.00", "maior 20.00, menor 10.00"],
        ["encerrando com 2"],
    ),
]


@pytest.mark.parametrize("prefixo,entrada_srv,entrada_cli,esp_cli,esp_srv", CASOS)
def test_par_executa(prefixo, entrada_srv, entrada_cli, esp_cli, esp_srv):
    with tempfile.TemporaryDirectory(prefix="minipar-par-") as tmp:
        work = Path(tmp)
        servidor = build_program(PASTA / f"{prefixo}_servidor.mp", work)
        cliente = build_program(PASTA / f"{prefixo}_cliente.mp", work)
        porta_cli, porta_srv = free_port(), free_port()
        hosts = work / "minipar.hosts"
        hosts.write_text(
            f"computador_1 = 127.0.0.1:{porta_cli}\n"
            f"computador_2 = 127.0.0.1:{porta_srv}\n",
            encoding="utf-8",
        )
        srv = subprocess.Popen(
            [str(servidor), "--hosts", str(hosts), "--como", "computador_2"],
            cwd=str(work),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            srv.stdin.write(entrada_srv)
            srv.stdin.close()
            wait_for_listening(porta_srv)
            cli = subprocess.run(
                [str(cliente), "--hosts", str(hosts), "--como", "computador_1"],
                cwd=str(work),
                input=entrada_cli,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            saida_srv, erro_srv = srv.communicate(timeout=60)
        finally:
            if srv.poll() is None:
                srv.kill()
                srv.communicate()

        assert cli.returncode == 0, cli.stdout + cli.stderr
        assert srv.returncode == 0, saida_srv + erro_srv
        for trecho in esp_cli:
            assert trecho in cli.stdout, f"{trecho!r} não está em:\n{cli.stdout}"
        for trecho in esp_srv:
            assert trecho in saida_srv, f"{trecho!r} não está em:\n{saida_srv}"
