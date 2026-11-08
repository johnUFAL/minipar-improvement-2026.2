"""Benchmark dos Testes 8, 9 e 10: MiniPar -O2 x linhas de base Python."""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_testes_2026_2 import build_program  # noqa: E402

RESULTS = ROOT / "docs" / "relatorio" / "resultados" / "t08_t10_tempo.json"
PROGRAMS = {
    "t08": {"file": "t08_avaliacao_4_nucleos.mp", "cores": 4},
    "t09": {"file": "t09_5_nucleos_4_avaliadores_1_fractal.mp", "cores": 5},
    "t10": {"file": "t10_6_nucleos_avaliacao_2_fractais.mp", "cores": 6},
}
MINIPAR_SEQ = re.compile(r"Tempo Sequencial Concluido em:\s*([\d.]+)")
MINIPAR_PAR = re.compile(r"Tempo Paralelo Concluido em:\s*([\d.]+)")
MINIPAR_SPEEDUP = re.compile(r"Aceleracao\s*:\s*([\d.]+)")
PYTHON_SEQ = re.compile(r"Tempo Sequencial Conclu[ií]do em:\s*([\d.]+)")
PYTHON_PAR = re.compile(r"Tempo Paralelo Conclu[ií]do em:\s*([\d.]+)")
INLINE_SEQ = re.compile(r"SEQ\s+([\d.]+)")
INLINE_PAR = re.compile(r"PAR\s+([\d.]+)")


def _first(pattern: re.Pattern[str], text: str) -> float:
    match = pattern.search(text)
    if match is None:
        raise ValueError(
            f"Padrao nao encontrado: {pattern.pattern}\n{text}"
        )
    return float(match.group(1))


def _run(command: list[str], timeout: int = 900) -> str:
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Falha ao executar {' '.join(command)}:\n{result.stderr}"
        )
    return result.stdout


def _logical_cpus() -> int:
    if hasattr(os, "sched_getaffinity"):
        return len(os.sched_getaffinity(0))
    return os.cpu_count() or 0


def _physical_cpus() -> int | None:
    try:
        import psutil
    except ImportError:
        return None
    return psutil.cpu_count(logical=False)


def _summarize(
    sequential: list[float], parallel: list[float]
) -> dict[str, object]:
    median_sequential = statistics.median(sequential)
    median_parallel = statistics.median(parallel)
    return {
        "sequential_samples": sequential,
        "parallel_samples": parallel,
        "median_sequential": median_sequential,
        "median_parallel": median_parallel,
        "median_speedup": (
            median_sequential / median_parallel if median_parallel else 0.0
        ),
    }


def _measure_minipar(executable: Path, samples: int) -> dict[str, object]:
    sequential: list[float] = []
    parallel: list[float] = []
    speedups: list[float] = []
    for _ in range(samples):
        output = _run([str(executable)])
        sequential.append(_first(MINIPAR_SEQ, output))
        parallel.append(_first(MINIPAR_PAR, output))
        speedups.append(_first(MINIPAR_SPEEDUP, output))
    data = _summarize(sequential, parallel)
    data["speedup_samples"] = speedups
    data["median_reported_speedup"] = statistics.median(speedups)
    return data


def _python_baseline(script: Path, samples: int) -> dict[str, object]:
    sequential: list[float] = []
    parallel: list[float] = []
    for _ in range(samples):
        output = _run([sys.executable, str(script)])
        sequential.append(_first(PYTHON_SEQ, output))
        parallel.append(_first(PYTHON_PAR, output))
    return _summarize(sequential, parallel)


def _python_t10_baseline(samples: int) -> dict[str, object]:
    benchmarks = ROOT / "benchmarks"
    code = (
        "import sys; "
        f"sys.path.insert(0, r'{benchmarks}'); "
        "import t10_6_nucleos_avaliacao_2_fractais as m; "
        "m.executar_trabalhador_sierpinski = lambda: None; "
        "seq, _ = m.execucao_sequencial(); "
        "par, _ = m.execucao_paralela(); "
        "print('SEQ', seq); print('PAR', par)"
    )
    sequential: list[float] = []
    parallel: list[float] = []
    for _ in range(samples):
        output = _run([sys.executable, "-c", code])
        sequential.append(_first(INLINE_SEQ, output))
        parallel.append(_first(INLINE_PAR, output))
    return _summarize(sequential, parallel)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark T8-T10")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--python-samples", type=int, default=1)
    parser.add_argument("--skip-python", action="store_true")
    arguments = parser.parse_args()
    if arguments.samples < 1 or arguments.python_samples < 1:
        parser.error("--samples e --python-samples devem ser positivos")

    programs_data: dict[str, dict[str, object]] = {}
    python_data: dict[str, dict[str, object]] = {}

    with tempfile.TemporaryDirectory(prefix="minipar-t08-t10-") as directory:
        work = Path(directory)
        executables: dict[str, Path] = {}
        for key, spec in PROGRAMS.items():
            executable = build_program(
                ROOT / "programas_teste" / spec["file"], work, "O2"
            )
            if not executable.is_file():
                alternative = executable.with_suffix(".exe")
                if alternative.is_file():
                    executable = alternative
            executables[key] = executable

        for key in PROGRAMS:
            print(f"[benchmark] MiniPar {key}...")
            programs_data[key] = _measure_minipar(
                executables[key], arguments.samples
            )

    if not arguments.skip_python:
        print("[benchmark] Python T8...")
        python_data["t08"] = _python_baseline(
            ROOT / "benchmarks" / "t08_avaliacao_4_nucleos.py",
            arguments.python_samples,
        )
        print("[benchmark] Python T9...")
        python_data["t09"] = _python_baseline(
            ROOT / "benchmarks" / "t09_5_nucleos_4_avaliadores_1_fractal.py",
            arguments.python_samples,
        )
        print("[benchmark] Python T10 (Sierpinski Turtle desativado)...")
        python_data["t10"] = _python_t10_baseline(
            arguments.python_samples
        )

    environment: dict[str, object] = {
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "logical_cpus": _logical_cpus(),
        "physical_cpus": _physical_cpus(),
    }
    data: dict[str, object] = {
        "environment": environment,
        "samples": arguments.samples,
        "python_samples": arguments.python_samples,
        "programs": programs_data,
        "python_baseline": python_data,
    }

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("=== Benchmark T8-T10 ===")
    print(
        "CPUs logicas:",
        environment["logical_cpus"],
        "| fisicas:",
        environment["physical_cpus"],
    )
    print("Teste  Seq(s)  Par(s)  Speedup  Nucleos")
    for key, spec in PROGRAMS.items():
        result = programs_data[key]
        print(
            f"{key.upper():<5}  "
            f"{result['median_sequential']:.3f}   "
            f"{result['median_parallel']:.3f}   "
            f"{result['median_speedup']:.2f}x    "
            f"{spec['cores']}"
        )
    if python_data:
        print("=== Linha de base Python ===")
        for key, result in python_data.items():
            print(
                f"{key.upper():<5}  seq {result['median_sequential']:.3f}s  "
                f"par {result['median_parallel']:.3f}s  "
                f"speedup {result['median_speedup']:.2f}x"
            )
        print("T10 Python: Sierpinski Turtle desativado (headless).")
    print(f"Resultado salvo em: {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
