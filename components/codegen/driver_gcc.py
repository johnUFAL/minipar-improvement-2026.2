from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


_SOURCE_MARKER = re.compile(r"^\s*// MiniPar line (\d+)\s*$")
_GCC_DIAGNOSTIC = re.compile(r"^(.*?):(\d+):(\d+):\s*(.*)$")
_OPTIMIZATION_LEVELS = {"O0", "O1", "O2", "O3"}


def _executable_path(output_path: str | Path) -> Path:
    executable = Path(output_path)
    if sys.platform == "win32" and executable.suffix.lower() != ".exe":
        executable = executable.with_suffix(".exe")
    return executable


def _platform_link_flags(platform: str, operating_system: str) -> list[str]:
    if platform.startswith("linux"):
        return ["-pthread"]
    if operating_system == "nt":
        return ["-lws2_32"]
    return []


def _source_line_map(cpp_path: Path) -> dict[int, int]:
    line_map: dict[int, int] = {}
    source_line: int | None = None
    for cpp_line, content in enumerate(
        cpp_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        marker = _SOURCE_MARKER.match(content)
        if marker:
            source_line = int(marker.group(1))
        elif source_line is not None:
            line_map[cpp_line] = source_line
    return line_map


def _map_diagnostics(stderr: str, cpp_path: Path, source_path: Path) -> str:
    line_map = _source_line_map(cpp_path)
    mapped: list[str] = []
    for diagnostic in stderr.splitlines():
        match = _GCC_DIAGNOSTIC.match(diagnostic)
        if match and Path(match.group(1)).name == cpp_path.name:
            cpp_line = int(match.group(2))
            source_line = line_map.get(cpp_line)
            if source_line is not None:
                diagnostic = (
                    f"{source_path}:{source_line}: {match.group(4)} "
                    f"(C++ gerado: linha {cpp_line})"
                )
        mapped.append(diagnostic)
    return "\n".join(mapped)


def compilar(
    cpp_path: str | Path,
    saida: str | Path,
    nivel_otimizacao: str = "O2",
) -> bool:
    source = Path(cpp_path)
    executable = _executable_path(saida)
    if nivel_otimizacao not in _OPTIMIZATION_LEVELS:
        raise ValueError(
            "nivel_otimizacao deve ser um dos valores O0, O1, O2 ou O3"
        )

    root = Path(__file__).resolve().parents[2]
    runtime_dir = root / "runtime"
    compiler = os.environ.get("CXX", "g++").strip('"')
    compiler_path = shutil.which(compiler)
    if compiler_path is None:
        print(
            f"[ERRO] Compilador C++ '{compiler}' nao encontrado. "
            "Instale um compilador C++17 e adicione-o ao PATH, "
            "ou defina a variavel de ambiente CXX.",
            file=sys.stderr,
        )
        return False

    command = [
        compiler_path,
        "-std=c++17",
        "-Wall",
        f"-{nivel_otimizacao}",
        str(source),
        str(runtime_dir / "canal.cpp"),
        str(runtime_dir / "paralelo.cpp"),
        "-I",
        str(runtime_dir),
        "-o",
        str(executable),
    ]
    command.extend(_platform_link_flags(sys.platform, os.name))

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
        )
    except OSError as error:
        print(
            f"[ERRO] O compilador C++ '{compiler_path}' nao pode ser iniciado. "
            f"Verifique a instalacao e o PATH: {error}",
            file=sys.stderr,
        )
        return False

    if result.stdout:
        print(result.stdout, end="")
    source_path = source.with_suffix(".mp")
    if result.stderr:
        print(
            _map_diagnostics(result.stderr, source, source_path),
            file=sys.stderr,
        )
    if result.returncode == 0:
        if executable.is_file():
            print(f"[SUCESSO] Executavel: {executable}")
            return True
        print(
            f"[ERRO] O compilador terminou sem erro, mas nao gerou "
            f"o executavel esperado: {executable}",
            file=sys.stderr,
        )
        return False

    print("[ERRO] Falha na compilacao.", file=sys.stderr)
    return False


def executar(
    saida: str | Path,
    argumentos: Sequence[str] = (),
) -> subprocess.CompletedProcess[str]:
    executable = _executable_path(saida)
    return subprocess.run(
        [str(executable), *argumentos],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )


class DriverGCC:
    def compile(
        self,
        source_path: str | Path,
        output_path: str | Path | None = None,
        optimization_level: str = "O2",
    ) -> bool:
        source = Path(source_path)
        executable = output_path or source.with_suffix(
            ".exe" if sys.platform == "win32" else ""
        )
        return compilar(source, executable, optimization_level)

    def compilar(
        self,
        cpp_path: str | Path,
        saida: str | Path,
        nivel_otimizacao: str = "O2",
    ) -> bool:
        return compilar(cpp_path, saida, nivel_otimizacao)

    def executar(
        self,
        saida: str | Path,
        argumentos: Sequence[str] = (),
    ) -> subprocess.CompletedProcess[str]:
        return executar(saida, argumentos)
