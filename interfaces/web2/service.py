"""Servicos da segunda interface Web (didatica) do MiniPar 2026.2.

A interface didatica reutiliza o mesmo pipeline do compilador, mas expoe cada
fase de forma independente para o aluno: lexico, sintatico, semantico, TAC e
codigo C++. Tambem compila, executa e disponibiliza o executavel para download.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from components.codegen.c_gerador_cpp import CppCodeGenerator
from components.codegen.driver_gcc import DriverGCC
from components.lexico.c_lexico import Lexer
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.ast import Program
from components.sintatico.c_sintatico import Parser, _ParseError
from components.tac.c_gerador_tac import TACGenerator
from erros.diagnosticos import DiagnosticBag

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = PROJECT_ROOT / "programas_teste"
TESTE11_DIR = TESTS_DIR / "teste11"
T11_SOURCE = TESTS_DIR / "t11_minicompilador_arm.mp"

EXECUTION_TIMEOUT_SECONDS = 30
EXECUTION_OUTPUT_LIMIT_BYTES = 1024 * 1024
MAX_INPUT_BYTES = 1024 * 1024

_ARTIFACTS: dict[str, dict[str, Any]] = {}
_ARTIFACTS_LOCK = threading.Lock()
_ARTIFACT_TTL_SECONDS = 60 * 60


def _serialize_diagnostic(diagnostic: Any) -> dict[str, object]:
    phase = getattr(diagnostic.phase, "value", diagnostic.phase)
    severity = getattr(diagnostic.severity, "value", diagnostic.severity)
    return {
        "phase": phase,
        "message": diagnostic.message,
        "line": diagnostic.line,
        "column": diagnostic.column,
        "length": diagnostic.length,
        "severity": severity,
        "header": diagnostic.header,
    }


def _dedupe_diagnostics(*bags: DiagnosticBag) -> list[dict[str, object]]:
    serialized: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for bag in bags:
        for diagnostic in bag.diagnostics:
            item = _serialize_diagnostic(diagnostic)
            key = tuple(item.values())
            if key not in seen:
                seen.add(key)
                serialized.append(item)
    return serialized


def analyze(source: str) -> dict[str, Any]:
    """Executa lexico, sintatico, semantico, TAC e codegen sem compilar."""
    token_diagnostics = DiagnosticBag(source)
    tokens = Lexer(source, token_diagnostics).tokenize()

    diagnostics = DiagnosticBag(source)
    lexer = Lexer(source, diagnostics)
    try:
        program = Parser(lexer, diagnostics).parse()
    except _ParseError:
        program = Program()

    analyzer = SemanticAnalyzer(diagnostics)
    if not diagnostics.has_errors:
        analyzer.analyze(program)

    tac = ""
    cpp = ""
    if not diagnostics.has_errors:
        try:
            tac = TACGenerator().generate_text(program)
            cpp = CppCodeGenerator().generate_source(tac)
        except (NotImplementedError, ValueError) as error:
            diagnostics.error("generation", str(error))

    serialized = _dedupe_diagnostics(token_diagnostics, diagnostics)
    return {
        "success": not diagnostics.has_errors,
        "tokens": [
            {
                "type": token.type.name,
                "lexeme": token.lexeme,
                "line": token.line,
                "column": token.column,
                "value": token.value,
            }
            for token in tokens
        ],
        "ast": program.para_dict(),
        "tabela_simbolos": analyzer.symbol_table.export(),
        "tac": tac,
        "cpp": cpp,
        "diagnosticos": serialized,
    }


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _build_executable(source: str, work: Path, optimization: str) -> tuple[bool, str, Path | None]:
    analysis = analyze(source)
    if not analysis["success"]:
        return False, "O programa possui erros. Corrija-os antes de compilar.", None

    cpp_path = work / "program.cpp"
    executable = work / "program"
    cpp_path.write_text(str(analysis["cpp"]), encoding="utf-8")
    if not DriverGCC().compile(cpp_path, executable, optimization):
        return False, "Falha ao compilar o codigo C++ gerado.", None

    actual = executable
    if sys.platform == "win32":
        actual = executable.with_suffix(".exe")
    return True, "", actual


def compile_for_download(source: str, optimization: str = "O2") -> dict[str, Any]:
    work = Path(tempfile.mkdtemp(prefix="minipar-web2-build-"))
    ok, error, executable = _build_executable(source, work, optimization)
    if not ok or executable is None:
        return {"success": False, "stderr": error}

    token = uuid.uuid4().hex
    with _ARTIFACTS_LOCK:
        _cleanup_artifacts_locked()
        _ARTIFACTS[token] = {
            "path": executable,
            "created": time.time(),
            "name": "programa.exe" if sys.platform == "win32" else "programa",
        }
    return {
        "success": True,
        "download_url": f"/api/artefato/{token}",
        "filename": _ARTIFACTS[token]["name"],
        "size": executable.stat().st_size,
    }


def _cleanup_artifacts_locked() -> None:
    cutoff = time.time() - _ARTIFACT_TTL_SECONDS
    for token in [key for key, value in _ARTIFACTS.items() if value["created"] < cutoff]:
        entry = _ARTIFACTS.pop(token, None)
        if entry is None:
            continue
        path = Path(entry["path"])
        try:
            path.unlink(missing_ok=True)
            path.parent.rmdir()
        except OSError:
            pass


def artifact_path(token: str) -> Path | None:
    with _ARTIFACTS_LOCK:
        _cleanup_artifacts_locked()
        entry = _ARTIFACTS.get(token)
        if entry is None:
            return None
        path = Path(entry["path"])
    return path if path.is_file() else None


def execute(source: str, input_text: str = "", optimization: str = "O2") -> dict[str, Any]:
    if len(input_text.encode("utf-8")) > MAX_INPUT_BYTES:
        return {
            "success": False,
            "stdout": "",
            "stderr": "A entrada padrao excede o limite de 1 MB.",
            "exit_code": None,
            "tempo": 0.0,
            "timed_out": False,
        }

    work = Path(tempfile.mkdtemp(prefix="minipar-web2-run-"))
    (work / "programas_teste" / "teste11").mkdir(parents=True, exist_ok=True)
    (work / "output").mkdir(exist_ok=True)
    ok, error, executable = _build_executable(source, work, optimization)
    if not ok or executable is None:
        return {
            "success": False,
            "stdout": "",
            "stderr": error,
            "exit_code": None,
            "tempo": 0.0,
            "timed_out": False,
        }

    started = time.perf_counter()
    try:
        result = subprocess.run(
            [str(executable)],
            input=input_text.encode("utf-8"),
            capture_output=True,
            check=False,
            timeout=EXECUTION_TIMEOUT_SECONDS,
            cwd=str(work),
        )
    except subprocess.TimeoutExpired as expired:
        elapsed = time.perf_counter() - started
        return {
            "success": False,
            "stdout": _decode(expired.stdout or b"")[:EXECUTION_OUTPUT_LIMIT_BYTES].replace("\r\n", "\n"),
            "stderr": (
                f"Tempo limite de {EXECUTION_TIMEOUT_SECONDS}s excedido. "
                "Verifique lacos infinitos ou reduza a carga."
            ),
            "exit_code": None,
            "tempo": round(elapsed, 3),
            "timed_out": True,
        }
    except OSError as error:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Falha ao iniciar o executavel: {error}",
            "exit_code": None,
            "tempo": 0.0,
            "timed_out": False,
        }

    elapsed = time.perf_counter() - started
    stdout = _decode(result.stdout)[:EXECUTION_OUTPUT_LIMIT_BYTES].replace("\r\n", "\n")
    stderr = _decode(result.stderr)[:EXECUTION_OUTPUT_LIMIT_BYTES].replace("\r\n", "\n")
    return {
        "success": result.returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": result.returncode,
        "tempo": round(elapsed, 3),
        "timed_out": False,
    }


def list_examples() -> list[dict[str, str]]:
    if not TESTS_DIR.is_dir():
        return []
    examples = []
    for path in sorted(TESTS_DIR.glob("*.mp")):
        examples.append({"name": path.name, "title": _example_title(path)})
    return examples


def _example_title(path: Path) -> str:
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0]
    except OSError:
        return path.stem
    first = first.lstrip("# ").strip()
    return first or path.stem


def read_example(name: str) -> str | None:
    candidate = (TESTS_DIR / name).resolve()
    if candidate.parent != TESTS_DIR.resolve() or candidate.suffix != ".mp":
        return None
    if not candidate.is_file():
        return None
    return candidate.read_text(encoding="utf-8")


def generate_arm() -> dict[str, Any]:
    """Compila e executa o Teste 11, devolvendo os tres arquivos .arm."""
    if not T11_SOURCE.is_file():
        return {"success": False, "stderr": "Programa do Teste 11 nao encontrado."}

    source = T11_SOURCE.read_text(encoding="utf-8")
    work = Path(tempfile.mkdtemp(prefix="minipar-web2-arm-"))
    ok, error, executable = _build_executable(source, work, "O0")
    if not ok or executable is None:
        return {"success": False, "stderr": error}

    try:
        result = subprocess.run(
            [str(executable)],
            capture_output=True,
            check=False,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "stderr": "Tempo limite ao gerar o Assembly."}
    except OSError as error:
        return {"success": False, "stderr": f"Falha ao executar o Teste 11: {error}"}

    files = []
    for name in ("expr1.arm", "expr2.arm", "expr3.arm"):
        path = TESTE11_DIR / name
        if path.is_file():
            files.append(
                {
                    "name": name,
                    "content": path.read_text(encoding="utf-8"),
                    "download_url": f"/api/arm/{name}",
                }
            )

    return {
        "success": result.returncode == 0 and len(files) == 3,
        "stdout": _decode(result.stdout)[:EXECUTION_OUTPUT_LIMIT_BYTES].replace("\r\n", "\n"),
        "stderr": _decode(result.stderr)[:EXECUTION_OUTPUT_LIMIT_BYTES].replace("\r\n", "\n"),
        "files": files,
    }


def arm_file(name: str) -> Path | None:
    if name not in {"expr1.arm", "expr2.arm", "expr3.arm"}:
        return None
    path = TESTE11_DIR / name
    return path if path.is_file() else None


def project_root() -> Path:
    return PROJECT_ROOT


def environment_info() -> dict[str, str]:
    compiler = os.environ.get("CXX", "g++").strip('"')
    return {
        "compiler": compiler,
        "platform": sys.platform,
        "python": sys.version.split()[0],
    }
