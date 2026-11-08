"""Runner multi-terminal do Teste 1 (calculadora cliente-servidor).

O menu interativo do MiniPar apenas monitora sessoes; ele nao inicia os dois
processos. Este script faz a orquestracao real:

1. compila servidor e cliente em um diretorio temporario;
2. aloca portas livres e escreve um minipar.hosts temporario;
3. inicia o servidor com --como computador_2;
4. espera a porta entrar em LISTENING;
5. executa o cliente com --como computador_1 e as requisicoes informadas;
6. valida as respostas e encerra os processos.

Uso:
    python scripts/run_multiterminal.py
    python scripts/run_multiterminal.py --scenario all
    python scripts/run_multiterminal.py --requests "/,5,0;+,12,30;sair"
    python scripts/run_multiterminal.py --operacao + --v1 12 --v2 30
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

Request = tuple[str, str, str]

SCENARIOS: dict[str, list[Request]] = {
    "basic": [("+", "12", "30")],
    "error": [("/", "5", "0"), ("+", "12", "30")],
    "invalid": [("%", "2", "3")],
    "all": [
        ("+", "12", "30"),
        ("-", "30", "12"),
        ("*", "6", "7"),
        ("/", "7", "2"),
        ("/", "5", "0"),
        ("+", "12", "30"),
        ("%", "2", "3"),
    ],
}


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


def parse_requests(text: str) -> list[Request]:
    requests: list[Request] = []
    for item in text.split(";"):
        item = item.strip()
        if not item:
            continue
        parts = [part.strip() for part in item.split(",")]
        if len(parts) != 3:
            raise SystemExit(
                f"Requisicao invalida: '{item}'. Use op,v1,v2 separados por ';'."
            )
        requests.append((parts[0], parts[1], parts[2]))
    if not requests:
        raise SystemExit("Nenhuma requisicao informada.")
    return requests


def requests_to_input(requests: list[Request]) -> str:
    lines: list[str] = []
    for operacao, v1, v2 in requests:
        lines.extend([operacao, v1, v2])
    lines.append("sair")
    return "\n".join(lines) + "\n"


def expected_outcome(operacao: str, v1: str, v2: str) -> tuple[str, str | None]:
    if operacao not in {"+", "-", "*", "/"}:
        return "ERRO: operacao invalida", None
    if operacao == "/" and float(v2) == 0.0:
        return "ERRO: divisao por zero", None
    a = float(v1)
    b = float(v2)
    result = {"+": a + b, "-": a - b, "*": a * b, "/": a / b}[operacao]
    return "OK", f"{result:.1f}"


def run_t1(requests: list[Request], keep_temp: bool, timeout: float) -> int:
    work = Path(tempfile.mkdtemp(prefix="minipar-t1-"))
    print(f"[T1] Diretorio de trabalho: {work}")
    print(f"[T1] Requisicoes: {requests}")

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
            input=requests_to_input(requests),
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

    checks: dict[str, bool] = {
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
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        default="basic",
        help="cenario pronto (basic, error, invalid, all)",
    )
    parser.add_argument(
        "--requests",
        help="requisicoes no formato op,v1,v2;op,v1,v2 (ex.: '/,5,0;+,12,30')",
    )
    parser.add_argument("--operacao", choices=["+", "-", "*", "/"])
    parser.add_argument("--v1", default="7")
    parser.add_argument("--v2", default="5")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    if args.requests:
        requests = parse_requests(args.requests)
    elif args.operacao:
        requests = [(args.operacao, args.v1, args.v2)]
    else:
        requests = SCENARIOS[args.scenario]

    return run_t1(requests, args.keep_temp, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
