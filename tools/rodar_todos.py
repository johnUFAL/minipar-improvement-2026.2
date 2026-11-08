"""Executa os programas de exemplo e gera evidencias numeradas.

Uso:
    python tools/rodar_todos.py
    python tools/rodar_todos.py --only t1,t2
    python tools/rodar_todos.py --include-t11
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_testes_2026_2 import (  # noqa: E402
    TESTS,
    check_local,
    run_local,
)

EVIDENCE = ROOT / "docs" / "relatorio" / "evidencias"
TERMINAL = EVIDENCE / "terminal"
WEB = EVIDENCE / "web"
DEFAULT_IDS = [f"t{index}" for index in range(1, 11)]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def environment() -> dict[str, str]:
    return {
        "sistema": platform.platform(),
        "python": platform.python_version(),
        "maquina": platform.machine(),
        "processador": platform.processor() or "desconhecido",
    }


def run_test(
    test: dict[str, object], timeout: float, work: Path
) -> dict[str, object]:
    started = time.perf_counter()
    if test.get("mode") == "multiterminal":
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_multiterminal.py"),
            "--scenario",
            "all",
            "--timeout",
            str(timeout),
        ]
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout + 60,
        )
        output = completed.stdout + completed.stderr
        returncode = completed.returncode
        checks = [
            ("script multi-terminal retornou 0", returncode == 0),
            ("Resultado: 42.0", "Resultado: 42.0" in output),
            ("Resultado: 18.0", "Resultado: 18.0" in output),
            ("Resultado: 3.5", "Resultado: 3.5" in output),
            ("Erro: divisao por zero.", "Erro: divisao por zero." in output),
            ("Erro: operacao invalida.", "Erro: operacao invalida." in output),
        ]
        elapsed = f"{time.perf_counter() - started:.2f}s"
        command_text = "python scripts/run_multiterminal.py --scenario all"
    else:
        result, elapsed = run_local(test, work, timeout)
        output = (result.stdout + result.stderr).decode(
            "utf-8", errors="replace"
        )
        checks = check_local(test, result)
        returncode = result.returncode
        command_text = f"run_local({test.get('file')})"
    return {
        "id": test["id"],
        "name": test["name"],
        "command": command_text,
        "elapsed": elapsed,
        "output": output,
        "checks": checks,
        "ok": returncode == 0 and all(passed for _, passed in checks),
        "returncode": returncode,
    }


def write_terminal(
    path: Path,
    title: str,
    command: str,
    elapsed: str,
    output: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"=== {title} ===\n"
        f"Comando: {command}\n"
        f"Tempo: {elapsed}\n\n"
        f"{output}\n",
        encoding="utf-8",
    )


def _web_screenshots(evidence_dir: Path = EVIDENCE) -> list[Path]:
    web = evidence_dir / "web"
    if not web.is_dir():
        return []
    return sorted(web.glob("*.png"))


def write_index(
    results: list[dict[str, object]],
    evidence_dir: Path = EVIDENCE,
) -> None:
    info = environment()
    screenshots = _web_screenshots(evidence_dir)
    lines = [
        "# Evidencias de execucao — MiniPar 2026.2",
        "",
        f"Gerado em: {time.strftime('%d/%m/%Y %H:%M')}",
        "",
        "## Ambiente",
        "",
        f"- Sistema: {info['sistema']}",
        f"- Python: {info['python']}",
        f"- Maquina: {info['maquina']}",
        f"- Processador: {info['processador']}",
        "",
        "## Programas",
        "",
        "| # | Teste | Tempo | Status | Evidencia |",
        "|---|---|---|---|---|",
    ]
    for index, result in enumerate(results, 1):
        status = "OK" if result["ok"] else "FALHOU"
        lines.append(
            f"| {index:02d} | {str(result['id']).upper()} — "
            f"{result['name']} | {result['elapsed']} | {status} | "
            f"[{result['evidence']}]({result['evidence']}) |"
        )

    passed = sum(1 for result in results if result["ok"])
    lines.extend(
        [
            "",
            f"**Resultado:** {passed}/{len(results)} testes passaram.",
            "",
            "## Capturas Web 2",
            "",
        ]
    )
    if screenshots:
        for screenshot in screenshots:
            lines.append(
                f"- [{screenshot.name}](web/{screenshot.name})"
            )
    else:
        lines.append(
            "Nenhuma captura gerada. Rode `python tools/capturar_telas_web.py` "
            "com Playwright/Chrome instalados."
        )
    lines.extend(
        [
            "",
            "## Validacao em duas maquinas",
            "",
            "Pendente de execucao em duas maquinas reais. O procedimento e o "
            "template estao em [`docs/rede.md`](../../rede.md).",
            "",
        ]
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "README.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Executa os programas e gera evidencias numeradas."
    )
    parser.add_argument("--only", help="ids separados por virgula (ex.: t1,t2)")
    parser.add_argument(
        "--include-t11", action="store_true", help="inclui o T11"
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    arguments = parser.parse_args()

    selected = {
        item.strip().lower()
        for item in (arguments.only or "").split(",")
        if item.strip()
    }
    wanted = list(DEFAULT_IDS)
    if arguments.include_t11:
        wanted.append("t11")
    if selected:
        wanted = [item for item in wanted if item in selected]
    tests = [test for test in TESTS if test["id"] in wanted]
    if not tests:
        print("Nenhum teste selecionado.", file=sys.stderr)
        return 2

    TERMINAL.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="minipar-evidencias-") as directory:
        work = Path(directory)
        for index, test in enumerate(tests, 1):
            print(f"[{index}/{len(tests)}] {test['id']} — {test['name']}")
            result = run_test(test, arguments.timeout, work)
            filename = (
                f"{index:02d}_{test['id']}_"
                f"{slugify(str(test['name']))}.txt"
            )
            write_terminal(
                TERMINAL / filename,
                f"{test['id'].upper()} — {test['name']}",
                str(result["command"]),
                str(result["elapsed"]),
                str(result["output"]),
            )
            result["evidence"] = f"terminal/{filename}"
            results.append(result)

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "resumo.json").write_text(
        json.dumps(
            {"ambiente": environment(), "resultados": results},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    write_index(results)

    passed = sum(1 for result in results if result["ok"])
    print(f"\n{passed}/{len(results)} testes passaram.")
    print(f"Evidencias: {EVIDENCE}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
