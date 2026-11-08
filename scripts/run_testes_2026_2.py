"""Runner dos 11 testes do MiniPar 2026.2.

Executa T1 a T11 de forma reproduzivel:
- compila cada programa em um diretorio temporario;
- fornece entradas fixas para T1, T5 e T6;
- executa T1 como dois processos reais (servidor/cliente);
- valida T8-T10 por marcos de saida (tempos variam);
- valida T11 pelos resultados e pelos tres arquivos .arm.

Uso:
    python scripts/run_testes_2026_2.py
    python scripts/run_testes_2026_2.py --only t1,t11
    python scripts/run_testes_2026_2.py --update-expected
    python scripts/run_testes_2026_2.py --keep-temp
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
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

from run_multiterminal import build_program  # noqa: E402

PROGRAMS = ROOT / "programas_teste"
EXPECTED = ROOT / "tests" / "integracao" / "expected_results"
RESULTS = ROOT / "docs" / "relatorio" / "resultados" / "testes_2026_2"
TESTE11 = PROGRAMS / "teste11"


TESTS: list[dict[str, object]] = [
    {
        "id": "t1",
        "name": "Calculadora cliente-servidor (2 terminais)",
        "mode": "multiterminal",
        "inputs": ["+", "7", "5"],
        "checks": ["Resultado: 12.0", "Servidor recebeu: + 7.0 5.0"],
    },
    {
        "id": "t2",
        "name": "Fatorial e Fibonacci em PAR",
        "file": "t02_fatorial_fibonacci_par.mp",
        "inputs": [],
        "checks": ["Fatorial de 10: 3628800", "FIBONACCI 0", "FIBONACCI 34"],
        "expected": "t02_fatorial_fibonacci_par.expected.txt",
        "comparison": "unordered_lines",
    },
    {
        "id": "t3",
        "name": "Neuronio com classes",
        "file": "t03_neuronio.mp",
        "inputs": [],
        "checks": ["Neuronio aprendeu", "Iteracoes totais:"],
        "comparison": "key_lines",
        "key_lines": [
            "Iteracao: 1",
            "Iteracao: 50",
            "Iteracao: 51",
            "Neuronio aprendeu dinamicamente.",
            "Iteracoes totais: 51",
        ],
    },
    {
        "id": "t4",
        "name": "Rede neural XOR",
        "file": "t04_rede_neural_xor.mp",
        "inputs": [],
        "checks": ["Input: [0, 0]", "Input: [1, 1]", "Predicted Output:"],
        "comparison": "float_range",
        "float_count": 4,
    },
    {
        "id": "t5",
        "name": "Sistema de recomendacao",
        "file": "t05_recomendacao.mp",
        "inputs": ["1", "1", "1", "1", "1", "1", "1", "1", "0", "0", "0", "0", "0", "0", "0", "0"],
        "checks": ["Produtos recomendados", "Laptop"],
        "expected": "t05_recomendacao.expected.txt",
    },
    {
        "id": "t6",
        "name": "Quicksort com classes",
        "file": "t06_quicksort_classes.mp",
        "inputs": ["10 -3 -40 80 70 -100"],
        "checks": ["Vetor ordenado: [-100, -40, -3, 10, 70, 80]"],
        "expected": "t06_quicksort_classes.expected.txt",
    },
    {
        "id": "t7",
        "name": "Quicksort iterativo",
        "file": "t07_quicksort_iterativo_tac.mp",
        "inputs": [],
        "checks": ["Array ordenado: [5, 12, 33, 61, 98]"],
        "expected": "t07_quicksort_iterativo_tac.expected.txt",
    },
    {
        "id": "t8",
        "name": "Avaliacao em 4 nucleos",
        "file": "t08_avaliacao_4_nucleos.mp",
        "inputs": [],
        "checks": [
            "Total de Atividades a Avaliar: 160",
            "BENCHMARK DE DESEMPENHO",
            "Nucleos Utilizados (Paralelo) : 4",
            "[Professor] Concluiu 160 atividades",
        ],
    },
    {
        "id": "t9",
        "name": "5 nucleos com Mandelbrot",
        "file": "t09_5_nucleos_4_avaliadores_1_fractal.mp",
        "inputs": [],
        "checks": [
            "FRACTAL DE MANDELBROT",
            "Nucleos Utilizados (Paralelo) : 5",
            "[Monitor 3] Concluiu 40 atividades",
        ],
    },
    {
        "id": "t10",
        "name": "6 nucleos com dois fractais",
        "file": "t10_6_nucleos_avaliacao_2_fractais.mp",
        "inputs": [],
        "checks": [
            "FRACTAL DE MANDELBROT",
            "TAPETE DE SIERPINSKI",
            "Nucleos Utilizados (Paralelo) : 6",
        ],
    },
    {
        "id": "t11",
        "name": "Minicompilador ARMv7",
        "file": "t11_minicompilador_arm.mp",
        "inputs": [],
        "optimization": "O0",
        "checks": ["t1 = 2 + 4", "SUB    r8, r4, r7", "➡️  22.0", "➡️  -84.0"],
        "artifacts": ["expr1.arm", "expr2.arm", "expr3.arm"],
    },
]


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def run_local(test: dict[str, object], work: Path, timeout: float) -> tuple[subprocess.CompletedProcess[bytes], str]:
    source = PROGRAMS / str(test["file"])
    optimization = str(test.get("optimization", "O2"))
    executable = build_program(source, work, optimization)
    inputs = [str(item) for item in test.get("inputs", [])]
    input_text = ("\n".join(inputs) + "\n") if inputs else ""
    started = time.perf_counter()
    result = subprocess.run(
        [str(executable)],
        input=input_text.encode("utf-8"),
        capture_output=True,
        timeout=timeout,
        check=False,
        cwd=str(ROOT),
    )
    elapsed = time.perf_counter() - started
    return result, f"{elapsed:.2f}s"


def check_local(test: dict[str, object], result: subprocess.CompletedProcess[bytes]) -> list[tuple[str, bool]]:
    stdout = result.stdout.decode("utf-8", errors="replace")
    checks: list[tuple[str, bool]] = [("codigo de saida 0", result.returncode == 0)]
    for text in test.get("checks", []):
        checks.append((f"saida contem {text!r}", str(text) in stdout))

    expected_name = test.get("expected")
    comparison = str(test.get("comparison", "exact"))
    if expected_name and comparison in ("exact", "unordered_lines"):
        expected_path = EXPECTED / str(expected_name)
        if expected_path.is_file():
            expected = normalize(expected_path.read_text(encoding="utf-8"))
            actual = normalize(stdout)
            if comparison == "unordered_lines":
                expected_lines = {line for line in expected.splitlines() if line}
                actual_lines = {line for line in actual.splitlines() if line}
                matches = expected_lines <= actual_lines
            else:
                matches = actual == expected
            checks.append((f"saida confere com {expected_path.name}", matches))

    if comparison == "key_lines":
        missing = [line for line in test.get("key_lines", []) if str(line) not in stdout]
        checks.append(("linhas-chave esperadas presentes", not missing))
    elif comparison == "float_range":
        values = [
            float(match.group(1))
            for match in re.finditer(
                r"Predicted Output:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
                stdout,
            )
        ]
        valid = (
            len(values) == int(test.get("float_count", 0))
            and all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values)
        )
        checks.append(("saidas sigmoid finitas na faixa [0, 1]", valid))

    return checks


def update_expected(test: dict[str, object], result: subprocess.CompletedProcess[bytes]) -> None:
    expected_name = test.get("expected")
    if not expected_name:
        return
    EXPECTED.mkdir(parents=True, exist_ok=True)
    stdout = normalize(result.stdout.decode("utf-8", errors="replace")) + "\n"
    (EXPECTED / str(expected_name)).write_text(stdout, encoding="utf-8")


def check_artifacts(test: dict[str, object]) -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []
    for name in test.get("artifacts", []):
        path = TESTE11 / str(name)
        checks.append((f"artefato {name}", path.is_file() and path.stat().st_size > 0))
    clang = shutil.which("clang")
    if clang:
        for name in test.get("artifacts", []):
            arm = TESTE11 / str(name)
            if not arm.is_file():
                continue
            object_file = arm.with_suffix(".o")
            result = subprocess.run(
                [
                    clang,
                    "--target=armv7-none-eabi",
                    "-x",
                    "assembler",
                    "-c",
                    str(arm),
                    "-o",
                    str(object_file),
                ],
                capture_output=True,
                check=False,
            )
            checks.append((f"clang monta {name}", result.returncode == 0))
            try:
                object_file.unlink()
            except OSError:
                pass
    return checks


def run_multiterminal_test(test: dict[str, object], timeout: float) -> tuple[int, str, list[tuple[str, bool]]]:
    inputs = [str(item) for item in test.get("inputs", [])]
    operacao, v1, v2 = (inputs + ["+", "7", "5"])[:3]
    command = [
        sys.executable,
        str(SCRIPTS / "run_multiterminal.py"),
        "--operacao",
        operacao,
        "--v1",
        v1,
        "--v2",
        v2,
        "--timeout",
        str(timeout),
    ]
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout + 60,
    )
    output = result.stdout + result.stderr
    checks: list[tuple[str, bool]] = [("script multi-terminal retornou 0", result.returncode == 0)]
    for text in test.get("checks", []):
        checks.append((f"saida contem {text!r}", str(text) in output))
    return result.returncode, output, checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Runner dos 11 testes do MiniPar 2026.2")
    parser.add_argument("--only", help="lista de ids separados por virgula (ex.: t1,t8)")
    parser.add_argument("--update-expected", action="store_true")
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    selected = {item.strip().lower() for item in (args.only or "").split(",") if item.strip()}
    tests = [test for test in TESTS if not selected or test["id"] in selected]
    if not tests:
        print("Nenhum teste selecionado.", file=sys.stderr)
        return 2

    RESULTS.mkdir(parents=True, exist_ok=True)
    summary: list[dict[str, object]] = []
    failures = 0

    for test in tests:
        test_id = str(test["id"])
        print(f"\n=== {test_id.upper()} — {test['name']} ===")
        started = time.perf_counter()
        checks: list[tuple[str, bool]] = []
        output = ""
        elapsed = 0.0

        if test.get("mode") == "multiterminal":
            returncode, output, checks = run_multiterminal_test(test, args.timeout)
            elapsed = time.perf_counter() - started
        else:
            work = Path(tempfile.mkdtemp(prefix=f"minipar-{test_id}-"))
            try:
                result, elapsed_text = run_local(test, work, args.timeout)
                output = result.stdout.decode("utf-8", errors="replace")
                error = result.stderr.decode("utf-8", errors="replace")
                if error.strip():
                    output += "\n--- stderr ---\n" + error
                if args.update_expected:
                    update_expected(test, result)
                checks = check_local(test, result)
                if test_id == "t11":
                    checks.extend(check_artifacts(test))
                elapsed = time.perf_counter() - started
            except subprocess.TimeoutExpired:
                checks = [("execucao dentro do timeout", False)]
                output = f"Timeout de {args.timeout}s"
                elapsed = time.perf_counter() - started
            except SystemExit as error:
                checks = [("compilacao", False)]
                output = str(error)
                elapsed = time.perf_counter() - started
            finally:
                if not args.keep_temp:
                    shutil.rmtree(work, ignore_errors=True)

        ok = all(passed for _, passed in checks)
        if not ok:
            failures += 1
        for label, passed in checks:
            print(f"  [{'OK' if passed else 'FALHA'}] {label}")
        print(f"  tempo: {elapsed:.2f}s")
        if not ok and output:
            print("  --- saida ---")
            for line in output.splitlines()[:40]:
                print(f"  | {line}")

        (RESULTS / f"{test_id}.log").write_bytes(output.encode("utf-8"))
        summary.append(
            {
                "id": test_id,
                "name": test["name"],
                "ok": ok,
                "elapsed": round(elapsed, 2),
                "checks": [{"label": label, "ok": passed} for label, passed in checks],
            }
        )

    (RESULTS / "testes_2026_2.json").write_text(
        json.dumps({"tests": summary}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n================ RESUMO ================")
    for item in summary:
        status = "OK" if item["ok"] else "FALHA"
        print(f"  [{status}] {item['id'].upper()} — {item['name']} ({item['elapsed']}s)")
    print("========================================")
    print(f"{len(summary) - failures}/{len(summary)} testes passaram.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
