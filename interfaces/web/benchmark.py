from __future__ import annotations

import csv
import ctypes
import json
import logging
import math
import os
import shutil
import statistics
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Callable, TypedDict

from components.codegen.c_gerador_cpp import CppCodeGenerator

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
MAX_ACTIVITY_COUNT = 2_000
MAX_REPETITIONS = 9
MAX_REQUESTED_CORES = 256
JOB_QUEUE_LIMIT = 4


@dataclass(frozen=True)
class BenchmarkConfig:
    students: int
    activities_per_student: int
    requested_cores: int
    fractals: int
    repetitions: int

    @property
    def activity_count(self) -> int:
        return self.students * self.activities_per_student


class BenchmarkTask(TypedDict):
    task_id: int
    task: str
    core: int
    units: int
    seconds: float


class MedianBenchmarkTask(TypedDict):
    task_id: int
    task: str
    core: int
    units: int
    median_seconds: float


def available_cpu_count() -> int:
    if hasattr(os, "sched_getaffinity"):
        return max(1, len(os.sched_getaffinity(0)))
    if os.name == "nt":
        process_mask = ctypes.c_size_t()
        system_mask = ctypes.c_size_t()
        get_affinity = ctypes.windll.kernel32.GetProcessAffinityMask
        if get_affinity(
            ctypes.windll.kernel32.GetCurrentProcess(),
            ctypes.byref(process_mask),
            ctypes.byref(system_mask),
        ):
            return max(1, process_mask.value.bit_count())
    return max(1, os.cpu_count() or 1)


def parse_config(data: object, cpu_count: int) -> tuple[BenchmarkConfig | None, str | None]:
    if not isinstance(data, dict):
        return None, "O corpo deve ser um objeto JSON."

    defaults = {
        "alunos": 40,
        "atividades": 4,
        "nucleos": min(cpu_count, MAX_REQUESTED_CORES),
        "fractais": 0,
        "repeticoes": 3,
    }
    values = {**defaults, **data}

    for field in ("alunos", "atividades", "nucleos", "fractais", "repeticoes"):
        if type(values[field]) is not int:
            return None, f"O campo '{field}' deve ser um inteiro."

    if not 1 <= values["alunos"] <= MAX_ACTIVITY_COUNT:
        return None, f"'alunos' deve estar entre 1 e {MAX_ACTIVITY_COUNT}."
    if not 1 <= values["atividades"] <= MAX_ACTIVITY_COUNT:
        return None, f"'atividades' deve estar entre 1 e {MAX_ACTIVITY_COUNT}."
    if values["alunos"] * values["atividades"] > MAX_ACTIVITY_COUNT:
        return None, (
            f"O total de atividades deve ser no máximo {MAX_ACTIVITY_COUNT}."
        )
    if not 1 <= values["nucleos"] <= MAX_REQUESTED_CORES:
        return None, f"'nucleos' deve estar entre 1 e {MAX_REQUESTED_CORES}."
    if not 0 <= values["fractais"] <= 2:
        return None, "'fractais' deve ser 0, 1 ou 2."
    if not 1 <= values["repeticoes"] <= MAX_REPETITIONS:
        return None, f"'repeticoes' deve estar entre 1 e {MAX_REPETITIONS}."

    return BenchmarkConfig(
        students=values["alunos"],
        activities_per_student=values["atividades"],
        requested_cores=values["nucleos"],
        fractals=values["fractais"],
        repetitions=values["repeticoes"],
    ), None


def _helper_source() -> str:
    return r"""
struct MiniParBenchmarkMetric {
    std::int64_t task_id;
    const char* task;
    std::int64_t core;
    std::int64_t units;
    double seconds;
};

static std::mutex minipar_benchmark_mutex;
static std::vector<MiniParBenchmarkMetric> minipar_benchmark_metrics;

static void minipar_benchmark_record(
    std::int64_t task_id,
    const char* task,
    std::int64_t core,
    std::int64_t units,
    double seconds
) {
    std::lock_guard<std::mutex> lock(minipar_benchmark_mutex);
    minipar_benchmark_metrics.push_back(
        {task_id, task, core, units, seconds}
    );
}

static std::int64_t benchmark_activities(
    std::int64_t first_task,
    std::int64_t count,
    std::int64_t core
) {
    volatile std::uint64_t state =
        static_cast<std::uint64_t>(first_task + 1);
    for (std::int64_t task = first_task; task < first_task + count; ++task) {
        const double started = agora();
        for (std::int64_t iteration = 0;
             iteration < 100000;
             ++iteration) {
            state = state * 2862933555777941757ULL
                + 3037000493ULL + static_cast<std::uint64_t>(iteration + task);
        }
        const double elapsed = agora() - started;
        minipar_benchmark_record(task, "activity", core, 1, elapsed);
    }
    return static_cast<std::int64_t>(state);
}

static std::uint64_t minipar_benchmark_sierpinski(int depth, std::uint64_t seed) {
    if (depth <= 0) {
        return seed + 1;
    }
    std::uint64_t result = seed;
    for (std::uint64_t branch = 0; branch < 8; ++branch) {
        result ^= minipar_benchmark_sierpinski(
            depth - 1, seed * 17 + branch + 1
        );
    }
    return result;
}

static std::int64_t benchmark_fractal(
    std::int64_t kind,
    std::int64_t core,
    std::int64_t enabled_fractals
) {
    if (kind >= enabled_fractals) {
        return 0;
    }
    const double started = agora();
    volatile std::uint64_t result = 0;
    const char* task_name = kind == 0 ? "mandelbrot" : "sierpinski";
    if (kind == 0) {
        constexpr int width = 140;
        constexpr int height = 80;
        constexpr int max_iterations = 160;
        for (int y = 0; y < height; ++y) {
            const double cy = (static_cast<double>(y) / height) * 2.4 - 1.2;
            for (int x = 0; x < width; ++x) {
                const double cx = (static_cast<double>(x) / width) * 3.0 - 2.0;
                double zx = 0.0;
                double zy = 0.0;
                int iteration = 0;
                while (zx * zx + zy * zy <= 4.0 &&
                       iteration < max_iterations) {
                    const double next_x = zx * zx - zy * zy + cx;
                    zy = 2.0 * zx * zy + cy;
                    zx = next_x;
                    ++iteration;
                }
                result += static_cast<std::uint64_t>(iteration);
            }
        }
    } else {
        result = minipar_benchmark_sierpinski(7, 1);
    }
    const double elapsed = agora() - started;
    minipar_benchmark_record(-kind - 1, task_name, core, 1, elapsed);
    return static_cast<std::int64_t>(result);
}

static void benchmark_report() {
    std::lock_guard<std::mutex> lock(minipar_benchmark_mutex);
    std::cout << "@@METRICAS {\"tasks\":[";
    for (std::size_t index = 0; index < minipar_benchmark_metrics.size(); ++index) {
        const auto& metric = minipar_benchmark_metrics[index];
        if (index != 0) {
            std::cout << ',';
        }
        std::cout << "{\"task_id\":" << metric.task_id
                  << ",\"task\":\"" << metric.task
                  << "\",\"core\":" << metric.core
                  << ",\"units\":" << metric.units
                  << ",\"seconds\":" << std::setprecision(12)
                  << metric.seconds << '}';
    }
    std::cout << "]}" << std::endl;
}
"""


def _call_lines(
    first_task: str,
    activity_count: str,
    core: int,
    fractals: tuple[int, ...],
    temporary_index: int,
) -> tuple[list[str], int]:
    lines: list[str] = []
    if activity_count:
        lines.extend(
            (
                f"result_{temporary_index}:int = 0",
                f"result_{temporary_index} = benchmark_activities("
                f"{first_task}, {activity_count}, {core})",
            )
        )
        temporary_index += 1
    for fractal in fractals:
        lines.extend(
            (
                f"result_{temporary_index}:int = 0",
                f"result_{temporary_index} = benchmark_fractal("
                f"{fractal}, {core}, fractal_count)",
            )
        )
        temporary_index += 1
    return lines, temporary_index


def _program(
    core_count: int,
    parallel: bool,
) -> str:
    tac = [
        "goto MAIN",
        "MAIN:",
        "student_count:int = int(to_number(argumento(1)))",
        "activities_per_student:int = int(to_number(argumento(2)))",
        "fractal_count:int = int(to_number(argumento(3)))",
        "total_activities:int = student_count * activities_per_student",
    ]
    if parallel:
        tac.append(f"par_begin {core_count}")
        for core in range(1, core_count + 1):
            tac.extend((
                f"start_numerator_{core}:int = total_activities * {core - 1}",
                f"end_numerator_{core}:int = total_activities * {core}",
                f"start_{core}:int = start_numerator_{core} / {core_count}",
                f"end_{core}:int = end_numerator_{core} / {core_count}",
                f"count_{core}:int = end_{core} - start_{core}",
            ))
        for core in range(1, core_count + 1):
            tac.append(f"fork worker_{core}, core, {core}, BRANCH_{core}")
        tac.append("join " + ", ".join(f"worker_{core}" for core in range(1, core_count + 1)))
        tac.extend(("goto AFTER_WORKERS",))
        temporary_index = 0
        for core in range(1, core_count + 1):
            assigned_fractals = tuple(
                fractal
                for fractal in range(2)
                if fractal % core_count + 1 == core
            )
            tac.append(f"BRANCH_{core}:")
            lines, temporary_index = _call_lines(
                f"start_{core}",
                f"count_{core}",
                core,
                assigned_fractals,
                temporary_index,
            )
            tac.extend(lines)
            tac.append(f"join worker_{core}")
        tac.extend(("AFTER_WORKERS:", "par_end"))
    else:
        lines, _ = _call_lines(
            "0",
            "total_activities",
            1,
            (0, 1),
            0,
        )
        tac.extend(lines)
    tac.extend(("call benchmark_report, 0", "goto END", "END:"))
    generated = CppCodeGenerator().generate_source("\n".join(tac))
    marker = "int main(int argc, char** argv) {"
    if marker not in generated:
        raise RuntimeError("O gerador C++ não produziu a função main esperada.")
    return generated.replace(marker, _helper_source() + "\n" + marker, 1)


def _compile_program(source: str, name: str, directory: Path) -> Path:
    cpp_path = directory / f"{name}.cpp"
    executable = directory / (f"{name}.exe" if os.name == "nt" else name)
    cpp_path.write_text(source, encoding="utf-8")
    compiler = shutil.which(os.environ.get("CXX", "g++").strip('"'))
    if compiler is None:
        raise RuntimeError("Compilador C++ não encontrado para executar o benchmark.")

    command = [
        compiler,
        "-std=c++17",
        "-O2",
        "-Wall",
        str(cpp_path),
        str(RUNTIME_DIR / "canal.cpp"),
        str(RUNTIME_DIR / "paralelo.cpp"),
        str(RUNTIME_DIR / "worker.cpp"),
        "-I",
        str(RUNTIME_DIR),
        "-o",
        executable.name,
    ]
    command.extend(["-lws2_32"] if os.name == "nt" else ["-pthread"])
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            cwd=directory,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"Compilação do benchmark excedeu 60 segundos: {name}.") from error
    if result.returncode != 0:
        details = result.stderr.strip()[-4_000:]
        raise RuntimeError(
            f"Falha ao compilar o benchmark {name} "
            f"(código {result.returncode}): {details}"
        )
    return executable


def _decode_tasks(payload: object) -> list[BenchmarkTask]:
    if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
        raise RuntimeError("O contrato @@METRICAS não contém uma lista de tarefas.")

    tasks: list[BenchmarkTask] = []
    for item in payload["tasks"]:
        if not isinstance(item, dict):
            raise RuntimeError("O contrato @@METRICAS contém uma tarefa inválida.")
        task_id = item.get("task_id")
        task = item.get("task")
        core = item.get("core")
        units = item.get("units")
        seconds = item.get("seconds")
        if (
            not isinstance(task_id, int)
            or isinstance(task_id, bool)
            or not isinstance(task, str)
            or not isinstance(core, int)
            or isinstance(core, bool)
            or not isinstance(units, int)
            or isinstance(units, bool)
            or not isinstance(seconds, (int, float))
            or isinstance(seconds, bool)
        ):
            raise RuntimeError("O contrato @@METRICAS contém campos inválidos.")
        seconds_value = float(seconds)
        if not math.isfinite(seconds_value) or seconds_value < 0:
            raise RuntimeError("O contrato @@METRICAS contém campos inválidos.")
        tasks.append({
            "task_id": task_id,
            "task": task,
            "core": core,
            "units": units,
            "seconds": seconds_value,
        })
    return tasks


def _run_program(
    executable: Path,
    arguments: list[str],
) -> tuple[float, list[BenchmarkTask]]:
    started = time.perf_counter()
    try:
        process = subprocess.run(
            [str(executable), *arguments],
            capture_output=True,
            text=True,
            errors="replace",
            cwd=executable.parent,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"Execução do benchmark excedeu 60 segundos: {executable.name}.") from error
    elapsed = time.perf_counter() - started
    if process.returncode != 0:
        raise RuntimeError(
            f"Benchmark {executable.name} terminou com código "
            f"{process.returncode}: {process.stderr.strip()[-2_000:]}"
        )
    metric_lines = [
        line for line in process.stdout.splitlines()
        if line.startswith("@@METRICAS ")
    ]
    if not metric_lines:
        raise RuntimeError(
            f"Benchmark {executable.name} não retornou a linha @@METRICAS."
        )
    try:
        payload = json.loads(metric_lines[-1][len("@@METRICAS "):])
    except json.JSONDecodeError as error:
        raise RuntimeError("O benchmark retornou métricas JSON inválidas.") from error
    return elapsed, _decode_tasks(payload)


def _median_task_metrics(
    runs: list[list[BenchmarkTask]],
) -> list[MedianBenchmarkTask]:
    grouped: dict[tuple[int, str, int, int], list[float]] = {}
    for run in runs:
        for task in run:
            key = (
                int(task["task_id"]),
                str(task["task"]),
                int(task["core"]),
                int(task["units"]),
            )
            grouped.setdefault(key, []).append(float(task["seconds"]))
    result: list[MedianBenchmarkTask] = []
    for (task_id, task_name, core, units), samples in sorted(grouped.items()):
        result.append({
            "task_id": task_id,
            "task": task_name,
            "core": core,
            "units": units,
            "median_seconds": statistics.median(samples),
        })
    return result


def _run_benchmark(
    config: BenchmarkConfig,
    cpu_count: int,
    progress: Callable[[int, str], None],
) -> dict[str, object]:
    effective_cores = min(
        config.requested_cores,
        cpu_count,
        config.activity_count + config.fractals,
    )
    warnings: list[str] = []
    if config.requested_cores > cpu_count:
        warnings.append(
            f"Foram solicitados {config.requested_cores} núcleos; "
            f"o benchmark usará os {cpu_count} disponíveis."
        )
    if effective_cores < config.requested_cores and config.requested_cores <= cpu_count:
        warnings.append(
            "O número de núcleos foi limitado à quantidade de tarefas úteis."
        )

    progress(5, "Preparando benchmarks MiniPar")
    with tempfile.TemporaryDirectory(prefix="minipar-benchmark-") as temp_dir:
        directory = Path(temp_dir)
        sequential = _compile_program(
            _program(effective_cores, parallel=False),
            "sequential",
            directory,
        )
        parallel = _compile_program(
            _program(effective_cores, parallel=True),
            "parallel",
            directory,
        )
        progress(15, "Programas sequencial e paralelo compilados")

        sequential_times: list[float] = []
        parallel_times: list[float] = []
        sequential_runs: list[list[BenchmarkTask]] = []
        parallel_runs: list[list[BenchmarkTask]] = []
        total_runs = config.repetitions * 2
        completed_runs = 0
        arguments = [
            str(config.students),
            str(config.activities_per_student),
            str(config.fractals),
        ]
        for sample in range(config.repetitions):
            order = (
                ((parallel, parallel_times, parallel_runs),
                 (sequential, sequential_times, sequential_runs))
                if sample % 2
                else ((sequential, sequential_times, sequential_runs),
                      (parallel, parallel_times, parallel_runs))
            )
            for executable, times, task_runs in order:
                elapsed, tasks = _run_program(executable, arguments)
                times.append(elapsed)
                task_runs.append(tasks)
                completed_runs += 1
                percent = 15 + round(80 * completed_runs / total_runs)
                progress(percent, f"Executando amostra {completed_runs}/{total_runs}")

    sequential_seconds = statistics.median(sequential_times)
    parallel_seconds = statistics.median(parallel_times)
    speedup = sequential_seconds / parallel_seconds if parallel_seconds else 0.0
    efficiency = speedup / effective_cores if effective_cores else 0.0
    task_metrics = _median_task_metrics(parallel_runs)
    core_metrics = []
    for core in range(1, effective_cores + 1):
        core_tasks = [task for task in task_metrics if task["core"] == core]
        busy_seconds = sum(float(task["median_seconds"]) for task in core_tasks)
        core_metrics.append({
            "core": core,
            "busy_seconds": busy_seconds,
            "utilization_percent": min(100.0, busy_seconds / parallel_seconds * 100)
            if parallel_seconds
            else 0.0,
            "task_count": len(core_tasks),
        })

    metric_line = "@@METRICAS " + json.dumps(
        {
            "mode": "parallel",
            "tasks": [
                {
                    "task_id": task["task_id"],
                    "task": task["task"],
                    "core": task["core"],
                    "units": task["units"],
                    "seconds": task["median_seconds"],
                }
                for task in task_metrics
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return {
        "parameters": {
            "alunos": config.students,
            "atividades": config.activities_per_student,
            "total_atividades": config.activity_count,
            "nucleos_solicitados": config.requested_cores,
            "nucleos_utilizados": effective_cores,
            "fractais": config.fractals,
            "repeticoes": config.repetitions,
        },
        "warnings": warnings,
        "sequential_seconds": sequential_seconds,
        "parallel_seconds": parallel_seconds,
        "speedup": speedup,
        "efficiency": efficiency,
        "efficiency_percent": efficiency * 100,
        "sequential_samples": sequential_times,
        "parallel_samples": parallel_times,
        "cores": core_metrics,
        "tasks": task_metrics,
        "metrics_line": metric_line,
    }


class BenchmarkManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, object]] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="minipar-benchmark",
        )

    def submit(
        self,
        config: BenchmarkConfig,
        cpu_count: int,
    ) -> tuple[str | None, str | None]:
        with self._lock:
            active = sum(
                job["status"] in {"queued", "running"}
                for job in self._jobs.values()
            )
            if active >= JOB_QUEUE_LIMIT:
                return None, "A fila de benchmarks está cheia; tente novamente depois."
            job_id = uuid.uuid4().hex
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "progress": 0,
                "message": "Aguardando execução",
                "result": None,
                "error": None,
            }
            self._executor.submit(self._run_job, job_id, config, cpu_count)
            self._prune_jobs()
            return job_id, None

    def get(self, job_id: str) -> dict[str, object] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            result = dict(job)
            result["state"] = {
                "queued": "aguardando",
                "running": "executando",
                "completed": "concluído",
                "failed": "falhou",
            }[str(job["status"])]
            return result

    def csv(self, job_id: str) -> str | None:
        job = self.get(job_id)
        result = job.get("result") if job else None
        if not isinstance(result, dict):
            return None

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(("tipo", "task_id", "tarefa", "nucleo", "unidades", "tempo_segundos", "utilizacao_percent"))
        parameters = result["parameters"]
        writer.writerow((
            "resumo_sequencial", "", "", 1,
            parameters["total_atividades"],
            result["sequential_seconds"], "",
        ))
        writer.writerow((
            "resumo_paralelo", "", "", parameters["nucleos_utilizados"],
            parameters["total_atividades"],
            result["parallel_seconds"], "",
        ))
        for task in result["tasks"]:
            writer.writerow((
                "tarefa",
                task["task_id"],
                task["task"],
                task["core"],
                task["units"],
                task["median_seconds"],
                "",
            ))
        for core in result["cores"]:
            writer.writerow((
                "nucleo",
                "",
                "",
                core["core"],
                core["task_count"],
                core["busy_seconds"],
                core["utilization_percent"],
            ))
        return output.getvalue()

    def _run_job(
        self,
        job_id: str,
        config: BenchmarkConfig,
        cpu_count: int,
    ) -> None:
        self._update(
            job_id,
            status="running",
            message="Preparando execução",
        )
        try:
            result = _run_benchmark(
                config,
                cpu_count,
                lambda progress, message: self._update(
                    job_id,
                    progress=progress,
                    message=message,
                ),
            )
        except Exception as error:
            LOGGER.exception("Benchmark MiniPar %s falhou.", job_id)
            self._update(
                job_id,
                status="failed",
                progress=100,
                message="Benchmark falhou",
                error=str(error),
            )
            return
        self._update(
            job_id,
            status="completed",
            progress=100,
            message="Benchmark concluído",
            result=result,
        )

    def _update(self, job_id: str, **values: object) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.update(values)

    def _prune_jobs(self) -> None:
        if len(self._jobs) < 100:
            return
        completed = [
            job_id
            for job_id, job in self._jobs.items()
            if job["status"] in {"completed", "failed"}
        ]
        for job_id in completed[: len(self._jobs) - 80]:
            self._jobs.pop(job_id, None)


benchmark_manager = BenchmarkManager()
