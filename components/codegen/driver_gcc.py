from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


class DriverGCC:
    def compile(self, source_path: str | Path) -> bool:
        source = Path(source_path)
        root = Path(__file__).resolve().parents[2]
        runtime_dir = root / "runtime"
        executable = source.with_suffix(".exe" if sys.platform == "win32" else "")
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
            "-O3",
            str(source),
            str(runtime_dir / "canal.cpp"),
            str(runtime_dir / "paralelo.cpp"),
            "-I",
            str(runtime_dir),
            "-o",
            str(executable),
            "-pthread",
        ]
        if os.name == "nt":
            command.append("-lws2_32")

        try:
            result = subprocess.run(command, check=False)
        except FileNotFoundError:
            print(
                f"[ERRO] O compilador C++ '{compiler_path}' nao pode ser iniciado. "
                "Verifique a instalacao e o PATH.",
                file=sys.stderr,
            )
            return False
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
