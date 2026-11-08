"""Renderiza os logs de terminal em PNG usando Playwright."""

from __future__ import annotations

import html
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "relatorio" / "evidencias"
TERMINAL = EVIDENCE / "terminal"
OUTPUT = EVIDENCE / "terminal_png"


def main() -> int:
    if importlib.util.find_spec("playwright") is None:
        print("Playwright/Chrome indisponivel.")
        print("Instale com:")
        print("  pip install playwright")
        print("  python -m playwright install chrome")
        return 0

    from playwright.sync_api import sync_playwright

    files = sorted(TERMINAL.glob("*.txt"))
    if not files:
        print(f"Nenhum log encontrado em {TERMINAL}")
        print("Rode primeiro: python tools/rodar_todos.py")
        return 0

    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        for path in files:
            text = html.escape(path.read_text(encoding="utf-8"))
            page.set_content(
                "<html><body style='margin:0;background:#111;color:#eee;"
                "font-family:Consolas,monospace;font-size:14px;'>"
                f"<pre style='padding:24px;white-space:pre-wrap'>{text}</pre>"
                "</body></html>"
            )
            destination = OUTPUT / f"{path.stem}.png"
            page.screenshot(path=str(destination), full_page=True)
            print(f"{path.name} -> {destination.name}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
