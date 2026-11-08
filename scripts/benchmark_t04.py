"""Benchmark do Teste 4: binario C++ -O2 x referencia Python."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_testes_2026_2 import build_program  # noqa: E402

T4_SOURCE = ROOT / "programas_teste" / "t04_rede_neural_xor.mp"
PYTHON_SOURCE = ROOT / "benchmarks" / "t04_rede_xor.py"
RESULTS = ROOT / "docs" / "relatorio" / "resultados" / "t04_tempo.json"


def measure(command: list[str], repetitions: int) -> list[float]:
    times: list[float] = []
    for _ in range(repetitions):
        started = time.perf_counter()
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=120,
        )
        elapsed = time.perf_counter() - started
        if result.returncode != 0:
            raise SystemExit(
                f"Falha ao executar {' '.join(command)}:\n{result.stderr}"
            )
        times.append(elapsed)
    return times


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark do T4")
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    repetitions = max(1, args.repetitions)

    with tempfile.TemporaryDirectory(prefix="minipar-t04-bench-") as directory:
        work = Path(directory)
        executable = build_program(T4_SOURCE, work, "O2")
        if not executable.is_file():
            alternative = executable.with_suffix(".exe")
            if alternative.is_file():
                executable = alternative

        compiled_times = measure([str(executable)], repetitions)
        python_times = measure(
            [sys.executable, str(PYTHON_SOURCE)], repetitions
        )

    compiled_median = statistics.median(compiled_times)
    python_median = statistics.median(python_times)
    speedup = python_median / compiled_median if compiled_median else 0.0

    data = {
        "repetitions": repetitions,
        "compiled_o2_seconds": compiled_times,
        "python_seconds": python_times,
        "compiled_o2_median": compiled_median,
        "python_median": python_median,
        "speedup_python_over_compiled": speedup,
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("=== Benchmark T4 ===")
    print(f"Repeticoes: {repetitions}")
    print(f"C++ -O2 : {compiled_median:.4f} s (mediana)")
    print(f"Python  : {python_median:.4f} s (mediana)")
    print(f"Speedup Python/C++: {speedup:.2f}x")
    print(f"Resultado salvo em: {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
