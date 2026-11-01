from __future__ import annotations

import argparse
import ctypes
import os
import re
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from components.codegen.c_gerador_cpp import CppCodeGenerator
from components.codegen.driver_gcc import DriverGCC


def _workload(index: int, iterations: int) -> list[str]:
    total = f"total_{index}"
    return [
        f"{total} = benchmark_work({iterations}, {index + 1})",
    ]


def _program(iterations: int, parallel: bool) -> str:
    lines = [
        f"total_{index}:int = 0"
        for index in range(4)
    ]
    tac = "\n".join(lines) + "\n"
    if parallel:
        tac += "par_begin 4\n"
        for index in range(4):
            tac += (
                f"fork worker_{index}, core, {index + 1}, BRANCH_{index}\n"
            )
        tac += "join " + ", ".join(f"worker_{index}" for index in range(4))
        tac += "\ngoto END\n"
        for index in range(4):
            tac += f"BRANCH_{index}:\n"
            tac += "\n".join(_workload(index, iterations))
            tac += f"\njoin worker_{index}\n"
        tac += "END:\npar_end\n"
    else:
        for index in range(4):
            tac += "\n".join(_workload(index, iterations)) + "\n"
    tac += "print " + ", ".join(f"total_{index}" for index in range(4))
    generated = CppCodeGenerator._generate_cpp(tac)
    helper = """static std::int64_t benchmark_work(
    std::int64_t iterations, std::int64_t seed
) {
    volatile std::uint64_t state = static_cast<std::uint64_t>(seed);
    for (std::int64_t index = 0; index < iterations; ++index) {
        state = state * 2862933555777941757ULL
            + 3037000493ULL + static_cast<std::uint64_t>(index);
    }
    return static_cast<std::int64_t>(state);
}

"""
    marker = "int main(int argc, char** argv) {"
    if marker not in generated:
        raise RuntimeError("Gerador C++ nao produziu a funcao main esperada.")
    return generated.replace(marker, helper + marker, 1)


def _compile(cpp: str, name: str, directory: Path) -> Path:
    source = directory / f"{name}.cpp"
    executable = directory / (f"{name}.exe" if os.name == "nt" else name)
    source.write_text(cpp, encoding="utf-8")
    if not DriverGCC().compilar(source, executable, "O2"):
        raise RuntimeError(f"Falha ao compilar o benchmark {name}.")
    return executable


def _runtime(executable: Path) -> float:
    started = time.perf_counter()
    result = subprocess.run(
        [str(executable)], capture_output=True, check=False, text=True
    )
    elapsed = time.perf_counter() - started
    if result.returncode:
        raise RuntimeError(
            f"Benchmark falhou ({result.returncode}): {result.stderr}"
        )
    return elapsed


def _reported_cpus(executable: Path) -> list[str]:
    environment = os.environ.copy()
    environment["MINIPAR_TRACE_CORES"] = "1"
    result = subprocess.run(
        [str(executable)], capture_output=True, check=False, text=True,
        env=environment,
    )
    if result.returncode:
        raise RuntimeError(
            f"Diagnostico do benchmark falhou ({result.returncode}): "
            f"{result.stderr}"
        )
    return re.findall(r"executou no CPU (\d+)", result.stderr)


def _available_cpu_count() -> int:
    if hasattr(os, "sched_getaffinity"):
        return len(os.sched_getaffinity(0))
    if os.name == "nt":
        process_mask = ctypes.c_size_t()
        system_mask = ctypes.c_size_t()
        get_affinity = ctypes.windll.kernel32.GetProcessAffinityMask
        if get_affinity(
            ctypes.windll.kernel32.GetCurrentProcess(),
            ctypes.byref(process_mask),
            ctypes.byref(system_mask),
        ):
            return process_mask.value.bit_count()
    return os.cpu_count() or 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara quatro tarefas MiniPar sequenciais e com afinidade."
    )
    parser.add_argument("--iterations", type=int, default=100_000_000)
    parser.add_argument("--samples", type=int, default=5)
    arguments = parser.parse_args()
    if arguments.iterations < 1 or arguments.samples < 1:
        parser.error("--iterations e --samples devem ser positivos")

    with tempfile.TemporaryDirectory(prefix="minipar-fork-core-") as temp:
        directory = Path(temp)
        sequential = _compile(
            _program(arguments.iterations, False), "sequential", directory
        )
        parallel = _compile(
            _program(arguments.iterations, True), "parallel", directory
        )
        cpu_ids = _reported_cpus(parallel)
        sequential_runs = []
        parallel_runs = []
        for sample in range(arguments.samples):
            if sample % 2:
                parallel_runs.append(_runtime(parallel))
                sequential_runs.append(_runtime(sequential))
            else:
                sequential_runs.append(_runtime(sequential))
                parallel_runs.append(_runtime(parallel))
        sequential_time = statistics.median(sequential_runs)
        parallel_time = statistics.median(parallel_runs)

    speedup = sequential_time / parallel_time
    print(f"Iteracoes por tarefa: {arguments.iterations:,}")
    print(f"Amostras (mediana):   {arguments.samples}")
    print(f"Tempo sequencial:     {sequential_time:.3f} s")
    print(f"Tempo paralelo:       {parallel_time:.3f} s")
    print(f"Speedup:              {speedup:.2f}x")
    if cpu_ids:
        print(f"CPUs observadas:      {', '.join(cpu_ids)}")
    available = _available_cpu_count()
    print(f"CPUs logicas disponiveis ao processo: {available}")
    if available < 4:
        print("Speedup de referencia nao avaliado: menos de 4 CPUs disponiveis.")
    if speedup <= 2.5:
        print("Criterio > 2,5x nao atingido neste ambiente.")
        if available >= 4:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
