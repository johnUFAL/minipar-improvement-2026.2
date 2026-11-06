"""Runner multi-terminal do Teste 1 (calculadora cliente-servidor).

O menu interativo do MiniPar apenas monitora sessoes; ele nao inicia os dois
processos. Este script faz a orquestracao real:

1. compila servidor e cliente em um diretorio temporario;
2. aloca uma porta livre e escreve um minipar.hosts temporario;
3. inicia o servidor com --como computador_2;
4. espera a porta entrar em LISTENING;
5. executa o cliente com --como computador_1 e as entradas informadas;
6. compara as saidas e encerra os processos.

Uso:
    python scripts/run_multiterminal.py
    python scripts/run_multiterminal.py --operacao + --v1 7 --v2 5
    python scripts/run_multiterminal.py --keep-temp
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from components.codegen.c_gerador_cpp import CppCodeGenerator  # noqa: E402
from components.codegen.driver_gcc import DriverGCC  # noqa: E402
from components.lexico.c_lexico import Lexer  # noqa: E402
from components.semantico.c_semantico import SemanticAnalyzer  # noqa: E402
from components.sintatico.c_sintatico import Parser  # noqa: E402
from components.tac.c_gerador_tac import TACGenerator  # noqa: E402
from erros.diagnosticos import DiagnosticBag  # noqa: E402

PROGRAMS = ROOT / "programas_teste" / "t01_multiterminal"
SERVER_SOURCE = PROGRAMS / "t01_calculadora_servidor.mp"
CLIENT_SOURCE = PROGRAMS / "t01_calculadora_cliente.mp"


def build_program(source_path: Path, work: Path, optimization: str = "O2") -> Path:
    source = source_path.read_text(encoding="utf-8")
    diagnostics = DiagnosticBag(source)
    program = Parser(Lexer(source, diagnostics), diagnostics).parse()
    SemanticAnalyzer(diagnostics).analyze(program)
    if diagnostics.has_errors:
        raise SystemExit(diagnostics.format_text())

    tac = TACGenerator().generate_text(program)
    cpp_path = work / (source_path.stem + ".cpp")
    cpp_path.write_text(CppCodeGenerator().generate_source(tac), encoding="utf-8")
    executable = work / source_path.stem
    if not DriverGCC().compile(cpp_path, executable, optimization):
        raise SystemExit(f"Falha ao compilar {source_path.name}")
    return executable


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def port_is_listening(port: int) -> bool:
    """Verifica LISTENING sem abrir uma conexao (que consumiria o accept)."""
    if os.name == "nt":
        command = ["netstat", "-ano"]
    else:
        command = ["ss", "-ltn"]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    needle = f":{port}"
    for line in result.stdout.splitlines():
        if needle not in line:
            continue
        if os.name == "nt" and "LISTENING" in line.upper():
            return True
        if os.name != "nt" and ("LISTEN" in line.upper() or "UNCONN" not in line.upper()):
            return True
    return False


def wait_for_listening(port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_listening(port):
            return
        time.sleep(0.2)
    raise SystemExit(f"Servidor nao entrou em LISTENING na porta {port}.")


def run_t1(operacao: str, v1: str, v2: str, keep_temp: bool, timeout: float) -> int:
    work = Path(tempfile.mkdtemp(prefix="minipar-t1-"))
    print(f"[T1] Diretorio de trabalho: {work}")

    server_exe = build_program(SERVER_SOURCE, work)
    client_exe = build_program(CLIENT_SOURCE, work)

    port_client = free_port()
    port_server = free_port()
    hosts = work / "minipar.hosts"
    hosts.write_text(
        f"computador_1 = 127.0.0.1:{port_client}\n"
        f"computador_2 = 127.0.0.1:{port_server}\n",
        encoding="utf-8",
    )

    server = subprocess.Popen(
        [
            str(server_exe),
            "--hosts",
            str(hosts),
            "--como",
            "computador_2",
        ],
        cwd=str(work),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    try:
        print(f"[T1] Aguardando o servidor na porta {port_server}...")
        wait_for_listening(port_server)
        print("[T1] Servidor pronto; executando o cliente.")

        client = subprocess.run(
            [
                str(client_exe),
                "--hosts",
                str(hosts),
                "--como",
                "computador_1",
            ],
            cwd=str(work),
            input=f"{operacao}\n{v1}\n{v2}\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        server_stdout, server_stderr = server.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        server.kill()
        server.communicate()
        print("[T1] ERRO: timeout na troca de mensagens.", file=sys.stderr)
        return 1
    finally:
        if server.poll() is None:
            server.kill()
            server.communicate()

    print("\n===== SAIDA DO SERVIDOR =====")
    print(server_stdout.rstrip())
    if server_stderr.strip():
        print("--- stderr do servidor ---")
        print(server_stderr.rstrip())

    print("\n===== SAIDA DO CLIENTE =====")
    print(client.stdout.rstrip())
    if client.stderr.strip():
        print("--- stderr do cliente ---")
        print(client.stderr.rstrip())

    expected_result = {
        "+": float(v1) + float(v2),
        "-": float(v1) - float(v2),
        "*": float(v1) * float(v2),
        "/": (float(v1) / float(v2)) if float(v2) != 0 else 0.0,
    }.get(operacao)
    if expected_result is None:
        print(f"[T1] ERRO: operacao invalida '{operacao}'.", file=sys.stderr)
        return 1

    expected_text = f"Resultado: {expected_result:.1f}"
    checks = {
        "cliente retornou 0": client.returncode == 0,
        "servidor retornou 0": server.returncode == 0,
        "servidor recebeu a requisicao": "Servidor recebeu:" in server_stdout,
        f"cliente exibiu '{expected_text}'": expected_text in client.stdout,
    }

    print("\n===== VERIFICACOES =====")
    for label, ok in checks.items():
        print(f"  [{'OK' if ok else 'FALHA'}] {label}")

    if keep_temp:
        print(f"\n[T1] Diretorio preservado: {work}")
    else:
        import shutil

        shutil.rmtree(work, ignore_errors=True)

    return 0 if all(checks.values()) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Runner multi-terminal do T1")
    parser.add_argument("--operacao", default="+", choices=["+", "-", "*", "/"])
    parser.add_argument("--v1", default="7")
    parser.add_argument("--v2", default="5")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()
    return run_t1(args.operacao, args.v1, args.v2, args.keep_temp, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
