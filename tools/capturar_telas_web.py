"""Captura telas da Web 2 para os programas de exemplo.

Requer Playwright + Chrome:

    pip install playwright
    python -m playwright install chrome
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from interfaces.web import api  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from run_testes_2026_2 import TESTS  # noqa: E402

EVIDENCE = ROOT / "docs" / "relatorio" / "evidencias" / "web"
DEFAULT_IDS = [f"t{index}" for index in range(1, 11)]
T1_SOURCE = (
    ROOT
    / "programas_teste"
    / "t01_multiterminal"
    / "t01_calculadora_cliente.mp"
)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def source_for(test: dict[str, object]) -> str | None:
    filename = test.get("file")
    if filename:
        path = ROOT / "programas_teste" / str(filename)
        if path.is_file():
            return path.read_text(encoding="utf-8")
    if test["id"] == "t1" and T1_SOURCE.is_file():
        return T1_SOURCE.read_text(encoding="utf-8")
    return None


def inputs_for(test: dict[str, object]) -> str:
    return "\n".join(str(item) for item in test.get("inputs", []))


def playwright_status() -> tuple[bool, str]:
    if importlib.util.find_spec("playwright") is None:
        return False, "playwright nao instalado"
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            browser.close()
    except Exception as exc:  # noqa: BLE001 - diagnostico amigavel
        return False, str(exc)
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Captura telas da Web 2 para os programas de exemplo."
    )
    parser.add_argument("--only", help="ids separados por virgula (ex.: t2,t4)")
    parser.add_argument("--timeout", type=float, default=120.0)
    arguments = parser.parse_args()

    available, reason = playwright_status()
    if not available:
        print(f"Playwright/Chrome indisponivel: {reason}")
        print("Instale com:")
        print("  pip install playwright")
        print("  python -m playwright install chrome")
        return 0

    selected = {
        item.strip().lower()
        for item in (arguments.only or "").split(",")
        if item.strip()
    }
    tests = [
        test
        for test in TESTS
        if test["id"] in DEFAULT_IDS
        and (not selected or test["id"] in selected)
    ]
    if not tests:
        print("Nenhum teste selecionado.", file=sys.stderr)
        return 2

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    workspace = tempfile.TemporaryDirectory(prefix="minipar-web-evidencias-")
    work = Path(workspace.name)
    temp_patch = patch.object(api, "TEMP_DIR", str(work / "temp"))
    output_patch = patch.object(api, "OUTPUT_DIR", str(work / "output"))
    temp_patch.start()
    output_patch.start()
    Path(api.TEMP_DIR).mkdir()
    Path(api.OUTPUT_DIR).mkdir()
    server = make_server("127.0.0.1", 0, api.app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel="chrome", headless=True
            )
            page = browser.new_page(
                viewport={"width": 1440, "height": 950}
            )
            page.set_default_timeout(arguments.timeout * 1000)
            for index, test in enumerate(tests, 1):
                source = source_for(test)
                if source is None:
                    print(f"[{index}] {test['id']}: fonte nao encontrada")
                    continue
                print(f"[{index}/{len(tests)}] {test['id']} — {test['name']}")
                page.goto(f"{base_url}/editor", wait_until="domcontentloaded")
                page.wait_for_function("typeof CodeMirror === 'function'")
                page.wait_for_selector("#page-ide .CodeMirror")
                page.evaluate(
                    "(source) => {"
                    " const editor = document.querySelector("
                    "'#page-ide .CodeMirror').CodeMirror;"
                    " editor.setValue(source);"
                    "}",
                    source,
                )
                page.fill("#program-input", inputs_for(test))
                if test["id"] != "t1":
                    page.click("#editor-compile")
                    page.wait_for_function(
                        "document.getElementById('phase-count')"
                        "?.textContent === '7 de 7'"
                    )
                filename = (
                    f"{index:02d}_{test['id']}_"
                    f"{slugify(str(test['name']))}.png"
                )
                page.screenshot(
                    path=str(EVIDENCE / filename), full_page=True
                )
                print(f"  -> {filename}")
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=10)
        temp_patch.stop()
        output_patch.stop()
        workspace.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
