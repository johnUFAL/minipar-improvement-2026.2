"""Utilitários compartilhados para executar programas MiniPar pareados.

O hub apenas troca contexto e mensagens de coordenação. Este módulo cuida da
parte local: escolher porta, gerar ``minipar.hosts``, compilar o fonte e manter
o processo com stdout/stderr drenados em segundo plano.
"""
from __future__ import annotations

import codecs
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from components.codegen.c_gerador_cpp import CppCodeGenerator
from components.codegen.driver_gcc import DriverGCC
from components.lexico import Lexer
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser
from components.tac.c_gerador_tac import TACGenerator
from erros.diagnosticos import DiagnosticBag

OUTPUT_LIMIT_BYTES = 64 * 1024
TIMEOUT_CANAL_MS = 10 * 60 * 1000


class ExecucaoErro(Exception):
    """Falha local ao preparar ou executar o programa pareado."""

    def __init__(
        self,
        mensagem: str,
        *,
        diagnosticos: list[str] | None = None,
    ) -> None:
        super().__init__(mensagem)
        self.diagnosticos = list(diagnosticos or [])


def free_port() -> int:
    """Reserva uma porta TCP livre no sistema."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("0.0.0.0", 0))
        return int(sock.getsockname()[1])


def port_is_listening(port: int) -> bool:
    """Verifica LISTENING sem abrir uma conexão que consumiria o accept."""
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
        if os.name != "nt" and (
            "LISTEN" in line.upper() or "UNCONN" not in line.upper()
        ):
            return True
    return False


def wait_for_listening(port: int, timeout: float = 15.0) -> None:
    """Aguarda o processo abrir a porta do canal."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_listening(port):
            return
        time.sleep(0.1)
    raise ExecucaoErro(
        f"O programa não abriu a porta {port} em {timeout:.0f} segundos."
    )


def gerar_hosts(
    canal: dict[str, str],
    papel: str,
    host_listener: str,
    porta_listener: int,
) -> str:
    """Gera o arquivo ``minipar.hosts`` para um dos lados do canal."""
    conecta = str(canal.get("conecta") or "").strip()
    escuta = str(canal.get("escuta") or "").strip()
    if not conecta or not escuta:
        raise ExecucaoErro("Canal declarativo sem os dois papéis.")
    if papel not in (conecta, escuta):
        raise ExecucaoErro(
            f"O papel '{papel}' não pertence ao canal declarado."
        )
    if not host_listener.strip():
        raise ExecucaoErro("Informe o host do lado que escuta.")
    if porta_listener < 1 or porta_listener > 65535:
        raise ExecucaoErro("A porta do lado que escuta é inválida.")

    porta_dummy = free_port()
    if papel == escuta:
        linha_conecta = f"{conecta} = 127.0.0.1:{porta_dummy}\n"
        linha_escuta = f"{escuta} = 127.0.0.1:{porta_listener}\n"
    else:
        linha_conecta = f"{conecta} = 127.0.0.1:{porta_dummy}\n"
        linha_escuta = f"{escuta} = {host_listener.strip()}:{porta_listener}\n"
    return linha_conecta + linha_escuta


def compilar_programa(
    source: str,
    workdir: Path,
    *,
    optimization_level: str = "O2",
) -> Path:
    """Compila um programa MiniPar e devolve o caminho do executável."""
    workdir.mkdir(parents=True, exist_ok=True)
    diagnostics = DiagnosticBag(source)
    parser = Parser(Lexer(source, diagnostics), diagnostics)
    try:
        program = parser.parse()
    except Exception as erro:  # noqa: BLE001 - diagnóstico abaixo cobre o caso
        if not diagnostics.has_errors:
            raise ExecucaoErro(f"Falha ao analisar o programa: {erro}") from erro
        program = None
    if not diagnostics.has_errors and program is not None:
        SemanticAnalyzer(diagnostics).analyze(program)
    if diagnostics.has_errors or program is None:
        raise ExecucaoErro(
            diagnostics.format_text() or "Falha ao analisar o programa.",
            diagnosticos=[d.header for d in diagnostics.diagnostics],
        )

    try:
        tac = TACGenerator().generate_text(program)
        cpp = CppCodeGenerator().generate_source(tac)
    except (NotImplementedError, ValueError) as erro:
        raise ExecucaoErro(f"Falha na geração de código: {erro}") from erro

    cpp_path = workdir / "program.cpp"
    cpp_path.write_text(str(cpp), encoding="utf-8")
    executable = workdir / "program"
    if not DriverGCC().compile(cpp_path, executable, optimization_level):
        raise ExecucaoErro(
            "Falha ao compilar o programa C++. Consulte o log do servidor."
        )
    if sys.platform == "win32":
        executable = executable.with_suffix(".exe")
    if not executable.is_file():
        raise ExecucaoErro("O compilador não gerou o executável esperado.")
    return executable


def iniciar_processo(
    executavel: Path,
    workdir: Path,
    hosts_path: Path,
    papel: str,
) -> subprocess.Popen[str]:
    """Inicia o executável com ``--hosts`` e ``--como``."""
    ambiente = dict(os.environ)
    # O usuário digita as entradas com calma: o outro lado não pode estourar o
    # timeout de 5 s do canal enquanto espera.
    ambiente.setdefault("MINIPAR_CHANNEL_TIMEOUT_MS", str(TIMEOUT_CANAL_MS))
    return subprocess.Popen(
        [
            str(executavel),
            "--hosts",
            str(hosts_path),
            "--como",
            papel,
        ],
        env=ambiente,
        cwd=str(workdir),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )


class ExecucaoProcesso:
    """Processo em execução com stdout/stderr limitados e drenados."""

    def __init__(
        self,
        processo: subprocess.Popen[str],
        *,
        output_limit: int = OUTPUT_LIMIT_BYTES,
    ) -> None:
        self.processo = processo
        self._lock = threading.Lock()
        self._output_limit = output_limit
        self._stdout = ""
        self._stderr = ""
        self._truncado = False
        self._threads = [
            threading.Thread(
                target=self._drenar,
                args=("stdout", processo.stdout),
                name="minipar-exec-stdout",
                daemon=True,
            ),
            threading.Thread(
                target=self._drenar,
                args=("stderr", processo.stderr),
                name="minipar-exec-stderr",
                daemon=True,
            ),
        ]
        for thread in self._threads:
            thread.start()

    def _drenar(self, nome: str, stream: Any) -> None:
        if stream is None:
            return
        # Lê o que estiver disponível (sem esperar encher o bloco), para que
        # prompts sem quebra de linha apareçam na hora, como em um terminal.
        bruto = getattr(stream, "buffer", None)
        decodificador = codecs.getincrementaldecoder("utf-8")(errors="replace")
        while True:
            if bruto is not None and hasattr(bruto, "read1"):
                dados = bruto.read1(4096)
                if not dados:
                    resto = decodificador.decode(b"", final=True)
                    if resto:
                        self._anexar(nome, resto)
                    return
                chunk = decodificador.decode(dados)
                if not chunk:
                    continue
            else:
                chunk = stream.read(1)
                if not chunk:
                    return
            self._anexar(nome, chunk)

    def _anexar(self, nome: str, chunk: str) -> None:
        with self._lock:
            atual = self._stdout if nome == "stdout" else self._stderr
            restante = max(0, self._output_limit - len(atual))
            if restante:
                if nome == "stdout":
                    self._stdout += chunk[:restante]
                else:
                    self._stderr += chunk[:restante]
            if len(chunk) > restante:
                self._truncado = True

    def escrever_entradas(self, texto: str) -> None:
        """Envia entradas prévias. Sem texto, a entrada fica aberta (interativa)."""
        if self.processo.stdin is None:
            return
        if not texto:
            return
        try:
            self.processo.stdin.write(texto)
            self.processo.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    def enviar_linha(self, texto: str) -> bool:
        """Escreve uma linha no stdin do programa em execução."""
        if self.processo.stdin is None or self.processo.poll() is not None:
            return False
        linha = texto.rstrip("\r\n") + "\n"
        try:
            self.processo.stdin.write(linha)
            self.processo.stdin.flush()
        except (BrokenPipeError, ValueError, OSError):
            return False
        with self._lock:
            # Eco da entrada digitada, na ordem em que o programa a recebeu.
            restante = max(0, self._output_limit - len(self._stdout))
            self._stdout += linha[:restante]
        return True

    def poll(self) -> int | None:
        return self.processo.poll()

    def aguardar(self, timeout: float | None = None) -> int:
        return self.processo.wait(timeout=timeout)

    def parar(self, timeout: float = 2.0) -> None:
        if self.processo.poll() is not None:
            return
        try:
            self.processo.terminate()
            self.processo.wait(timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            try:
                self.processo.kill()
                self.processo.wait(timeout=timeout)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def juntar_threads(self, timeout: float = 1.0) -> None:
        for thread in self._threads:
            thread.join(timeout=timeout)

    def estado(self) -> dict[str, Any]:
        with self._lock:
            stdout = self._stdout
            stderr = self._stderr
            truncado = self._truncado
        return {
            "rodando": self.processo.poll() is None,
            "exit_code": self.processo.poll(),
            "stdout": stdout,
            "stderr": stderr,
            "output_limited": truncado,
        }


def remover_diretorio(caminho: Path | None) -> None:
    if caminho is not None:
        shutil.rmtree(caminho, ignore_errors=True)
