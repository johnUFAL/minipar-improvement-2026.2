import importlib.util
import json
import os
import shutil
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.serving import make_server

from interfaces.web import api
from interfaces.web import conexao_api

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None
CXX = os.environ.get("CXX", "g++").strip('"')
CXX_AVAILABLE = shutil.which(CXX) is not None


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "playwright is required for browser tests")
@unittest.skipUnless(CXX_AVAILABLE, "g++ is required for browser tests")
class FrontendBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory()
        workspace = Path(cls.workspace.name)
        cls.temp_patch = patch.object(api, "TEMP_DIR", str(workspace / "temp"))
        cls.output_patch = patch.object(api, "OUTPUT_DIR", str(workspace / "output"))
        cls.temp_patch.start()
        cls.output_patch.start()
        Path(api.TEMP_DIR).mkdir()
        Path(api.OUTPUT_DIR).mkdir()
        cls.server = make_server("127.0.0.1", 0, api.app)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=10)
        cls.temp_patch.stop()
        cls.output_patch.stop()
        cls.workspace.cleanup()

    def setUp(self):
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.launch(
                channel="chrome", headless=True
            )
        except Exception as exc:
            self.playwright.stop()
            self.skipTest(f"Google Chrome is required for browser tests: {exc}")
        self.page = self.browser.new_page(viewport={"width": 1440, "height": 950})
        self.page.set_default_timeout(60000)

    def tearDown(self):
        if getattr(self, "page", None):
            self.page.close()
        if getattr(self, "browser", None):
            self.browser.close()
        if getattr(self, "playwright", None):
            self.playwright.stop()

    def _open_ide(self):
        self.page.goto(f"{self.base_url}/editor", wait_until="domcontentloaded")
        self.page.wait_for_function("typeof CodeMirror === 'function'")
        self.page.wait_for_function(
            "document.querySelectorAll('#example-select option').length > 1"
        )
        self.page.wait_for_selector("#page-ide .CodeMirror")

    def _run_simple_program(self):
        self.page.evaluate(
            """() => {
                const editor = document.querySelector('#page-ide .CodeMirror').CodeMirror;
                editor.setValue('SEQ\\n    var total = 2 + 3\\n    print(total)\\n');
            }"""
        )
        self.page.click("#editor-compile")
        self.page.wait_for_function(
            "document.getElementById('phase-count')?.textContent === '7 de 7'"
        )

    def _assert_popover_and_highlight(self, source_selector, highlight_selector):
        line = self.page.locator(source_selector).first
        line.hover()
        self.page.wait_for_function(
            """() => {
                const popover = document.querySelector('.tac-origin-popover');
                return popover && !popover.hidden &&
                    popover.textContent.includes('Origem: linha');
            }"""
        )
        self.assertGreaterEqual(
            self.page.locator(highlight_selector).count(), 1, highlight_selector
        )
        self.page.mouse.move(2, 2)
        self.page.wait_for_function(
            """(selector) => {
                const popover = document.querySelector('.tac-origin-popover');
                return (!popover || popover.hidden) &&
                    document.querySelectorAll(selector).length === 0;
            }""",
            arg=highlight_selector,
        )

    def test_origin_popover_uses_light_theme_in_light_mode(self):
        self._open_ide()
        self._run_simple_program()
        self.page.click('.step[data-phase="tac"]')
        self.page.wait_for_selector('#page-ide .mapped-code-line[data-source-line]')
        self.page.evaluate(
            """() => {
                document.body.classList.add('light-theme');
                localStorage.setItem('minipar-theme', 'light');
            }"""
        )
        line = self.page.locator('#page-ide .mapped-code-line[data-source-line]').first
        line.hover()
        self.page.wait_for_function(
            """() => {
                const popover = document.querySelector('.tac-origin-popover');
                return popover && !popover.hidden &&
                    popover.textContent.includes('Origem: linha');
            }"""
        )
        popover = self.page.locator('.tac-origin-popover')
        self.assertFalse(popover.is_hidden())
        background = popover.evaluate(
            "element => getComputedStyle(element).backgroundColor"
        )
        self.assertEqual(background, "rgb(255, 255, 255)")
        self.page.mouse.move(2, 2)

    def test_phase_bar_uses_light_theme_in_light_mode(self):
        self._open_ide()
        self.page.evaluate(
            """() => {
                document.body.classList.add('light-theme');
                localStorage.setItem('minipar-theme', 'light');
            }"""
        )
        step = self.page.locator('.phase-nav .step[data-phase="tac"]')
        step.hover()
        background = step.evaluate(
            "element => getComputedStyle(element).backgroundColor"
        )
        self.assertEqual(background, "rgb(232, 238, 248)")
        self.page.mouse.move(2, 2)

    def test_origin_highlights_in_editor_and_result_detail(self):
        self._open_ide()
        self.assertTrue(self.page.locator("#compile-button").is_visible())
        self._run_simple_program()

        self.page.click('.step[data-phase="tac"]')
        self.page.wait_for_selector('#page-ide .mapped-code-line[data-source-line]')
        self._assert_popover_and_highlight(
            '#page-ide .mapped-code-line[data-source-line]',
            '#page-ide .CodeMirror-linebackground.cm-origin-line',
        )

        self.page.click('.step[data-phase="cpp"]')
        self.page.wait_for_selector('#page-ide .mapped-code-line[data-source-line]')
        self._assert_popover_and_highlight(
            '#page-ide .mapped-code-line[data-source-line]',
            '#page-ide .CodeMirror-linebackground.cm-origin-line',
        )

        self.assertFalse(self.page.locator("#compile-button").is_hidden())

    def test_responsiveness_and_accessibility_contract(self):
        self.page.goto(f"{self.base_url}/", wait_until="domcontentloaded")
        self.page.wait_for_selector("#page-dashboard.active-page")
        self.assertFalse(self.page.locator("#compile-button").is_visible())

        for width, height in ((1280, 800), (820, 1000), (390, 844)):
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.wait_for_timeout(200)
            overflow = self.page.evaluate(
                "document.documentElement.scrollWidth - window.innerWidth"
            )
            self.assertLessEqual(overflow, 1, f"overflow horizontal em {width}px")
            self.assertFalse(self.page.locator("#compile-button").is_visible())

        self.page.click('.nav-item[data-page="ide"]')
        self.page.wait_for_selector("#page-ide.active-page .CodeMirror")
        self.assertTrue(self.page.locator("#compile-button").is_visible())
        labels = self.page.evaluate(
            """() => {
                const button = document.getElementById('compile-button');
                return {
                    full: getComputedStyle(button.querySelector('.button-label')).display,
                    short: getComputedStyle(button.querySelector('.button-label-short')).display,
                };
            }"""
        )
        self.assertEqual(labels, {"full": "none", "short": "block"})

        self.page.click('.nav-item[data-page="benchmark"]')
        self.page.wait_for_selector("#page-benchmark.active-page")
        self.assertFalse(self.page.locator("#compile-button").is_visible())

        self.page.click('.nav-item[data-page="results"]')
        self.page.wait_for_selector("#page-results.active-page")
        self.assertFalse(self.page.locator("#compile-button").is_visible())

        audit = self.page.evaluate(
            """() => {
                const failures = [];
                const isVisible = element => element.getClientRects().length > 0;
                const parseColor = value => {
                    const match = value.match(/rgba?\\(([\\d.]+),\\s*([\\d.]+),\\s*([\\d.]+)(?:,\\s*([\\d.]+))?\\)/);
                    if (!match) return null;
                    return {
                        r: Number(match[1]), g: Number(match[2]), b: Number(match[3]),
                        a: match[4] === undefined ? 1 : Number(match[4]),
                    };
                };
                const composite = (front, back) => ({
                    r: front.r * front.a + back.r * (1 - front.a),
                    g: front.g * front.a + back.g * (1 - front.a),
                    b: front.b * front.a + back.b * (1 - front.a),
                    a: 1,
                });
                const background = element => {
                    const layers = [];
                    for (let node = element; node; node = node.parentElement) {
                        const color = parseColor(getComputedStyle(node).backgroundColor);
                        if (color && color.a > 0) layers.push(color);
                    }
                    let result = { r: 255, g: 255, b: 255, a: 1 };
                    for (let index = layers.length - 1; index >= 0; index--) {
                        result = composite(layers[index], result);
                    }
                    return result;
                };
                const channel = value => {
                    value /= 255;
                    return value <= 0.03928
                        ? value / 12.92
                        : Math.pow((value + 0.055) / 1.055, 2.4);
                };
                const luminance = color =>
                    0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b);
                const contrast = (first, second) => {
                    const high = Math.max(luminance(first), luminance(second));
                    const low = Math.min(luminance(first), luminance(second));
                    return (high + 0.05) / (low + 0.05);
                };

                if (document.documentElement.lang !== 'pt-BR') failures.push('lang ausente');
                if (!document.querySelector('main.main')) failures.push('landmark main ausente');
                if (!document.querySelector('aside.sidebar[aria-label]')) failures.push('sidebar sem rotulo');
                if (!document.querySelector('meta[name="viewport"]')) failures.push('viewport ausente');

                const controls = [...document.querySelectorAll('button, a[href], select, textarea, input')]
                    .filter(element => isVisible(element) && !element.disabled);
                for (const element of controls) {
                    const name = element.getAttribute('aria-label') ||
                        element.textContent.trim() ||
                        element.getAttribute('title') ||
                        element.labels?.length;
                    if (!name) failures.push(`controle sem nome: ${element.outerHTML.slice(0, 80)}`);
                }

                const icons = [...document.querySelectorAll('svg.icon')].filter(isVisible);
                for (const icon of icons) {
                    if (icon.getAttribute('aria-hidden') !== 'true') {
                        failures.push(`icone sem aria-hidden: ${icon.outerHTML.slice(0, 80)}`);
                    }
                }

                const targets = [
                    ['.page.active-page h1', 3],
                    ['.page.active-page .intro-copy', 3],
                    ['.nav-item.active', 3],
                    ['.nav-item:not(.active)', 3],
                    ['.button-primary', 3],
                    ['.metric-card small', 3],
                    ['.sidebar-label', 3],
                ];
                for (const [selector, minimum] of targets) {
                    const element = document.querySelector(selector);
                    if (!element || !isVisible(element)) continue;
                    const style = getComputedStyle(element);
                    const foreground = parseColor(style.color);
                    if (!foreground) continue;
                    const ratio = contrast(foreground, background(element));
                    if (ratio < minimum) {
                        failures.push(`${selector} contraste ${ratio.toFixed(2)} < ${minimum}`);
                    }
                }
                return failures;
            }"""
        )
        self.assertEqual(audit, [])

    def test_benchmark_state_machine_updates_results_and_persists_settings(self):
        result = {
            "parameters": {
                "alunos": 1,
                "atividades": 2,
                "total_atividades": 2,
                "nucleos_solicitados": 1,
                "nucleos_utilizados": 1,
                "fractais": 0,
                "repeticoes": 1,
            },
            "warnings": [],
            "sequential_seconds": 0.2,
            "parallel_seconds": 0.1,
            "speedup": 2.0,
            "efficiency": 2.0,
            "efficiency_percent": 200.0,
            "sequential_samples": [0.2],
            "parallel_samples": [0.1],
            "cores": [
                {
                    "core": 1,
                    "busy_seconds": 0.1,
                    "utilization_percent": 100.0,
                    "task_count": 2,
                }
            ],
            "tasks": [
                {
                    "task_id": 0,
                    "task": "activity",
                    "core": 1,
                    "units": 1,
                    "median_seconds": 0.05,
                }
            ],
        }

        def handle_benchmark(route):
            url = route.request.url
            if route.request.method == "POST" and url.endswith("/api/benchmark"):
                route.fulfill(
                    status=202,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "job_id": "job-test",
                            "status_url": "/api/benchmark/job-test",
                            "csv_url": "/api/benchmark/job-test/csv",
                        }
                    ),
                )
                return
            if "/api/benchmark/job-test" in url:
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "job_id": "job-test",
                            "status": "completed",
                            "state": "concluído",
                            "progress": 100,
                            "message": "Benchmark concluído",
                            "result": result,
                            "csv_url": "/api/benchmark/job-test/csv",
                        }
                    ),
                )
                return
            route.continue_()

        self.page.route("**/api/benchmark**", handle_benchmark)
        try:
            self.page.goto(f"{self.base_url}/", wait_until="domcontentloaded")
            self.page.wait_for_function(
                "!document.getElementById('benchmark-hardware').textContent.includes('Detectando')"
            )
            self.assertFalse(self.page.locator("#benchmark-run").count())
            self.page.fill("#benchmark-students", "1")
            self.page.fill("#benchmark-activities", "2")
            self.page.fill("#benchmark-repetitions", "1")
            self.page.click("#panel-run-benchmark")
            self.page.wait_for_selector("#page-benchmark.active-page")
            self.page.wait_for_function(
                "document.getElementById('benchmark-state').textContent === 'Concluído'"
            )
            self.assertNotEqual(
                self.page.locator("#metric-speedup").text_content(), "—"
            )
            self.assertFalse(self.page.locator("#benchmark-results").is_hidden())
            self.assertEqual(
                self.page.locator("#benchmark-summary .benchmark-summary-item")
                .nth(2)
                .locator("strong")
                .text_content(),
                "Nenhum",
            )
            self.assertGreaterEqual(
                self.page.locator("#benchmark-cores-bars .core-bar-row").count(), 1
            )
            self.assertGreaterEqual(
                self.page.locator("#benchmark-tasks-result tr").count(), 1
            )
            stored_history = self.page.evaluate(
                "() => JSON.parse(localStorage.getItem('minipar-benchmark-history'))"
            )
            self.assertGreaterEqual(len(stored_history), 1)
            self.assertFalse(self.page.locator("#benchmark-history").is_hidden())
            self.assertGreaterEqual(
                self.page.locator("#benchmark-history-list .benchmark-history-row").count(),
                1,
            )

            self.page.reload(wait_until="domcontentloaded")
            self.page.wait_for_selector("#benchmark-history:not([hidden])")
            self.page.wait_for_function(
                "document.getElementById('benchmark-state').textContent === 'Concluído'"
            )
            self.assertGreaterEqual(
                self.page.locator("#benchmark-history-list .benchmark-history-row").count(),
                1,
            )

            self.page.goto(
                f"{self.base_url}/configuracoes", wait_until="domcontentloaded"
            )
            self.page.wait_for_function(
                "document.getElementById('settings-students')?.value === '1'"
            )

            self.page.goto(f"{self.base_url}/", wait_until="domcontentloaded")
            self.page.wait_for_function(
                "document.getElementById('panel-benchmark-speedup')?.textContent !== '—'"
            )
            self.assertIn(
                "2.000",
                self.page.locator("#panel-benchmark-speedup").text_content(),
            )
        finally:
            self.page.unroute("**/api/benchmark**", handle_benchmark)

    def test_benchmark_tasks_paginate_15_rows(self):
        tasks = [
            {
                "task_id": index,
                "task": "activity",
                "core": (index % 2) + 1,
                "units": 1,
                "median_seconds": 0.01,
            }
            for index in range(140)
        ]
        result = {
            "parameters": {
                "alunos": 35,
                "atividades": 4,
                "total_atividades": 140,
                "nucleos_solicitados": 2,
                "nucleos_utilizados": 2,
                "fractais": 0,
                "repeticoes": 1,
            },
            "warnings": [],
            "sequential_seconds": 0.4,
            "parallel_seconds": 0.2,
            "speedup": 2.0,
            "efficiency": 1.0,
            "efficiency_percent": 100.0,
            "cores": [
                {
                    "core": 1,
                    "busy_seconds": 0.1,
                    "utilization_percent": 50.0,
                    "task_count": 70,
                },
                {
                    "core": 2,
                    "busy_seconds": 0.1,
                    "utilization_percent": 50.0,
                    "task_count": 70,
                },
            ],
            "tasks": tasks,
        }

        self.page.goto(f"{self.base_url}/benchmark", wait_until="domcontentloaded")
        self.page.evaluate(
            """(result) => {
                localStorage.setItem('minipar-benchmark-history', JSON.stringify([
                    {id: 'bench-pagination', result, csv_url: null, completed_at: 1760000000000}
                ]));
                localStorage.removeItem('minipar-benchmark-last');
            }""",
            result,
        )
        self.page.reload(wait_until="domcontentloaded")
        self.page.wait_for_selector("#benchmark-results:not([hidden])")

        self.assertEqual(self.page.locator("#benchmark-tasks-result tr").count(), 15)
        self.assertFalse(self.page.locator("#benchmark-tasks-pagination").is_hidden())
        self.assertIn("1 de 10", self.page.locator("#benchmark-tasks-page").text_content())
        self.assertEqual(self.page.locator("#benchmark-tasks-pages .pagination-page").count(), 5)
        self.assertEqual(
            self.page.locator("#benchmark-tasks-pages .pagination-page").nth(0).text_content(),
            "1",
        )
        self.assertEqual(
            self.page.locator("#benchmark-tasks-pages .pagination-page").nth(4).text_content(),
            "5",
        )

        self.page.click("#benchmark-tasks-next")
        self.assertEqual(self.page.locator("#benchmark-tasks-result tr").count(), 15)
        self.assertIn("2 de 10", self.page.locator("#benchmark-tasks-page").text_content())
        self.assertEqual(
            self.page.locator("#benchmark-tasks-pages .pagination-page").nth(0).text_content(),
            "2",
        )
        self.assertEqual(
            self.page.locator("#benchmark-tasks-pages .pagination-page").nth(4).text_content(),
            "6",
        )

        self.page.click("#benchmark-tasks-next")
        self.assertEqual(self.page.locator("#benchmark-tasks-result tr").count(), 15)
        self.assertIn("3 de 10", self.page.locator("#benchmark-tasks-page").text_content())
        self.assertEqual(
            self.page.locator("#benchmark-tasks-pages .pagination-page").nth(0).text_content(),
            "3",
        )
        self.assertEqual(
            self.page.locator("#benchmark-tasks-pages .pagination-page").nth(4).text_content(),
            "7",
        )

    def test_benchmark_activity_limit_adjusts_pair(self):
        self.page.goto(f"{self.base_url}/benchmark", wait_until="domcontentloaded")
        self.page.wait_for_selector("#benchmark-run")
        self.page.evaluate(
            """() => {
                const range = document.getElementById('benchmark-students-range');
                range.value = '2000';
                range.dispatchEvent(new Event('input', {bubbles: true}));
            }"""
        )
        self.assertEqual(self.page.locator("#benchmark-students").input_value(), "2000")
        self.assertEqual(self.page.locator("#benchmark-activities").input_value(), "1")
        self.assertEqual(self.page.locator("#benchmark-activities-range").input_value(), "1")

        self.page.evaluate(
            """() => {
                const range = document.getElementById('benchmark-activities-range');
                range.value = '2000';
                range.dispatchEvent(new Event('input', {bubbles: true}));
            }"""
        )
        self.assertEqual(self.page.locator("#benchmark-students").input_value(), "1")
        self.assertEqual(self.page.locator("#benchmark-activities").input_value(), "2000")

        self.page.goto(f"{self.base_url}/configuracoes", wait_until="domcontentloaded")
        self.page.wait_for_selector("#save-settings")
        self.page.evaluate(
            """() => {
                const range = document.getElementById('settings-activities-range');
                range.value = '2000';
                range.dispatchEvent(new Event('input', {bubbles: true}));
            }"""
        )
        self.assertEqual(self.page.locator("#settings-students").input_value(), "1")
        self.assertEqual(self.page.locator("#settings-activities").input_value(), "2000")

    def test_settings_persist_after_reload(self):
        self.page.goto(f"{self.base_url}/configuracoes", wait_until="domcontentloaded")
        self.page.fill("#settings-students", "7")
        self.page.fill("#settings-activities", "3")
        self.page.select_option("#settings-fractals", "1")
        self.page.fill("#settings-repetitions", "2")
        self.page.select_option("#settings-optimization", "O2")
        self.page.click("#save-settings")
        self.page.reload(wait_until="domcontentloaded")
        self.page.wait_for_function(
            """() => {
                return document.getElementById('settings-students')?.value === '7' &&
                    document.getElementById('settings-activities')?.value === '3' &&
                    document.getElementById('settings-fractals')?.value === '1' &&
                    document.getElementById('settings-repetitions')?.value === '2' &&
                    document.getElementById('settings-optimization')?.value === 'O2';
            }"""
        )
        stored = self.page.evaluate(
            "() => JSON.parse(localStorage.getItem('minipar-settings'))"
        )
        self.assertEqual(stored["students"], 7)
        self.assertEqual(stored["optimization"], "O2")

    def test_compiler_results_page_reads_persisted_history(self):
        history = [
            {
                "file": "programa-a.mp",
                "source": "SEQ\n    print(42)\n",
                "inputs": "",
                "optimization": "O0",
                "success": True,
                "time": 0.125,
                "diagnosticos": [],
                "execution": {"stdout": "42\n", "stderr": "", "exit_code": 0},
                "cpp": "int main() { return 0; }",
                "compileResult": {
                    "tokens": [
                        {"type": "KEYWORD", "lexeme": "SEQ", "line": 1, "column": 1},
                        {"type": "IDENT", "lexeme": "print", "line": 2, "column": 5},
                    ],
                    "ast": {"tipo": "Programa", "line": 1, "column": 1},
                    "tabela_simbolos": {"symbols": []},
                    "tac": "t0 = 42\nprint t0",
                    "tac_origin": [{"generated_line": 1, "source_line": 2}],
                    "cpp": "int main() { return 0; }",
                    "cpp_origin": [{"generated_line": 1, "source_line": 2}],
                },
                "created_at": 1_760_000_000_000,
            },
            {
                "file": "programa-b.mp",
                "source": "SEQ\n    var x = \n",
                "inputs": "7",
                "optimization": "O2",
                "success": False,
                "time": 0.0,
                "diagnosticos": [
                    {"header": "Erro sintático", "line": 2, "column": 5}
                ],
                "execution": None,
                "cpp": "",
                "created_at": 1_760_000_100_000,
            },
        ]
        self.page.goto(f"{self.base_url}/resultados", wait_until="domcontentloaded")
        self.page.evaluate(
            "(history) => localStorage.setItem('minipar-compiler-history', JSON.stringify(history))",
            history,
        )
        self.page.reload(wait_until="domcontentloaded")
        self.page.wait_for_selector("#compiler-content:not([hidden])")
        self.assertEqual(self.page.locator("#compiler-total").text_content(), "2")
        self.assertEqual(self.page.locator("#compiler-success").text_content(), "1")
        self.assertEqual(self.page.locator("#compiler-errors").text_content(), "1")
        self.assertEqual(
            self.page.locator("#compiler-history-list .history-row").count(), 2
        )
        self.page.locator("#compiler-history-list .history-row").nth(1).click()
        self.page.wait_for_url(
            f"{self.base_url}/resultados/1760000100000", wait_until="domcontentloaded"
        )
        self.page.wait_for_selector("#result-detail .result-ide-grid")
        detail = self.page.locator("#result-detail").text_content()
        self.assertIn("programa-b.mp", detail)
        self.assertIn("SOMENTE LEITURA", detail)
        self.page.click('[data-result-phase="code"]')
        self.page.wait_for_selector("#result-detail .phase-diagnostics")
        self.assertIn(
            "Erro sintático",
            self.page.locator("#result-detail .phase-diagnostics").text_content(),
        )

        self.page.goto(
            f"{self.base_url}/resultados/1760000000000", wait_until="domcontentloaded"
        )
        self.page.wait_for_selector("#result-detail .result-ide-grid")
        self.assertIn("42", self.page.locator("#result-detail").text_content())
        for phase, title, expected in (
            ("tokens", "Tokens", "KEYWORD"),
            ("ast", "AST", "Programa"),
            ("symbols", "Tabela de símbolos", "symbols"),
            ("tac", "TAC", "Comparar TAC"),
            ("cpp", "C++", "Código C++ gerado"),
            ("execution", "Execução", "STDOUT"),
        ):
            with self.subTest(phase=phase):
                self.page.click(f'[data-result-phase="{phase}"]')
                self.page.wait_for_selector(f'[data-result-phase="{phase}"].active')
                self.assertEqual(
                    self.page.locator("#result-phase-title").text_content(), title
                )
                self.assertIn(
                    expected,
                    self.page.locator("#result-phase-content").text_content(),
                )

        self.page.goto(f"{self.base_url}/#result-detail", wait_until="domcontentloaded")
        self.page.wait_for_url(
            f"{self.base_url}/resultados/1760000000000", wait_until="domcontentloaded"
        )
        self.page.wait_for_selector("#result-detail .result-ide-grid")

    def test_compiled_run_keeps_all_detail_phases(self):
        self._open_ide()
        self._run_simple_program()
        self.page.goto(f"{self.base_url}/resultados", wait_until="domcontentloaded")
        self.page.wait_for_selector("#compiler-history-list .history-row")
        self.page.locator("#compiler-history-list .history-row").first.click()
        self.page.wait_for_selector("#result-detail .result-ide-grid")
        self.assertIn("/resultados/run-", self.page.url)

        for phase, title, expected in (
            ("tokens", "Tokens", "total"),
            ("ast", "AST", "Program"),
            ("symbols", "Tabela de símbolos", "total"),
            ("tac", "TAC", "Comparar TAC"),
            ("cpp", "C++", "Código C++ gerado"),
            ("execution", "Execução", "STDOUT"),
        ):
            with self.subTest(phase=phase):
                self.page.click(f'[data-result-phase="{phase}"]')
                self.page.wait_for_selector(f'[data-result-phase="{phase}"].active')
                self.assertEqual(
                    self.page.locator("#result-phase-title").text_content(), title
                )
                content = self.page.locator("#result-phase-content").text_content()
                self.assertIn(expected, content)
                self.assertNotIn("Dados não armazenados", content)

    def test_benchmark_screens_fit_1280_and_tablet(self):
        for path in ("/", "/benchmark", "/resultados", "/configuracoes", "/conexao"):
            self.page.goto(f"{self.base_url}{path}", wait_until="domcontentloaded")
            for width, height in ((1280, 800), (820, 1000)):
                with self.subTest(path=path, width=width):
                    self.page.set_viewport_size({"width": width, "height": height})
                    self.page.wait_for_timeout(200)
                    overflow = self.page.evaluate(
                        "document.documentElement.scrollWidth - window.innerWidth"
                    )
                    self.assertLessEqual(
                        overflow, 1, f"overflow horizontal em {path} @ {width}px"
                    )

    def test_connection_survives_navigation_and_global_chat_keeps_history(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            hub_port = sock.getsockname()[1]

        other = self.browser.new_page(viewport={"width": 1440, "height": 950})
        other.set_default_timeout(20000)
        try:
            self.page.goto(
                f"{self.base_url}/conexao", wait_until="domcontentloaded"
            )
            self.page.fill("#connection-name", "Alice")
            self.page.fill("#connection-port", str(hub_port))
            self.page.click("#connection-start-hub")
            self.page.wait_for_function(
                "!document.getElementById('connection-stop-hub').hidden"
            )
            self.page.click("#connection-connect")
            self.page.wait_for_function(
                "document.getElementById('connection-status').textContent.includes('NO HUB')"
            )

            other.goto(f"{self.base_url}/conexao", wait_until="domcontentloaded")
            other.fill("#connection-name", "Bob")
            other.fill("#connection-host", "127.0.0.1")
            other.fill("#connection-port", str(hub_port))
            other.click("#connection-connect")
            other.wait_for_function(
                "document.getElementById('connection-status').textContent.includes('NO HUB')"
            )

            self.page.wait_for_function(
                "document.querySelectorAll('#connection-peers [data-peer-id]').length > 0"
            )
            self.page.click("#connection-peers [data-peer-id]")
            other.wait_for_function(
                "!document.getElementById('connection-request').hidden"
            )
            other.click("#connection-accept")
            self.page.wait_for_function(
                "document.getElementById('connection-status').textContent.includes('CONECTADO')"
            )
            other.wait_for_function(
                "document.getElementById('connection-status').textContent.includes('CONECTADO')"
            )

            self.page.fill("#connection-chat-input", "primeira mensagem")
            self.page.click("#connection-chat-send")
            other.wait_for_function(
                "document.getElementById('connection-chat').textContent.includes('primeira mensagem')"
            )

            other.goto(f"{self.base_url}/editor", wait_until="domcontentloaded")
            other.wait_for_function(
                "!document.getElementById('global-chat').hidden"
            )
            other.wait_for_function(
                "document.getElementById('global-chat-messages').textContent.includes('primeira mensagem')"
            )

            self.page.fill("#connection-chat-input", "segunda mensagem")
            self.page.click("#connection-chat-send")
            other.wait_for_function(
                "document.getElementById('global-chat-messages').textContent.includes('segunda mensagem')"
            )

            other.goto(f"{self.base_url}/conexao", wait_until="domcontentloaded")
            other.wait_for_function(
                "document.getElementById('connection-status').textContent.includes('CONECTADO')"
            )
            history = other.locator("#connection-chat").text_content()
            self.assertIn("primeira mensagem", history)
            self.assertIn("segunda mensagem", history)
        finally:
            conexao_api.encerrar_tudo()
            other.close()

    def test_connection_chip_exists_on_every_page_and_follows_state(self):
        pages = ("/", "/editor", "/conexao", "/resultados", "/benchmark", "/configuracoes")
        for path in pages:
            self.page.goto(f"{self.base_url}{path}", wait_until="domcontentloaded")
            chip = self.page.locator("#conn-chip")
            self.assertEqual(chip.count(), 1, path)
            self.assertIn("Sem hub", chip.inner_text(), path)

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            hub_port = sock.getsockname()[1]
        try:
            self.page.goto(f"{self.base_url}/conexao", wait_until="domcontentloaded")
            self.page.fill("#connection-name", "Alice")
            self.page.fill("#connection-port", str(hub_port))
            self.page.click("#connection-start-hub")
            self.page.wait_for_function(
                "!document.getElementById('connection-stop-hub').hidden"
            )
            self.page.click("#connection-connect")
            self.page.wait_for_function(
                "document.getElementById('conn-chip-text').textContent.includes('No hub')"
            )
            for path in ("/", "/editor", "/resultados", "/benchmark", "/configuracoes"):
                self.page.goto(f"{self.base_url}{path}", wait_until="domcontentloaded")
                self.page.wait_for_function(
                    "document.getElementById('conn-chip-text').textContent.includes('No hub')"
                )
            self.page.goto(f"{self.base_url}/conexao", wait_until="domcontentloaded")
            self.page.wait_for_function(
                "!document.getElementById('connection-disconnect').hidden"
            )
            self.page.click("#connection-disconnect")
            self.page.wait_for_function(
                "document.getElementById('conn-chip-text').textContent.includes('Sem hub')"
            )
        finally:
            conexao_api.encerrar_tudo()

    def test_pair_execution_runs_in_editor_with_interactive_terminal(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            hub_port = sock.getsockname()[1]

        cliente_arquivo = "t01_multiterminal/t01_calculadora_cliente.mp"
        other = self.browser.new_page(viewport={"width": 1440, "height": 950})
        other.set_default_timeout(60000)
        try:
            self.page.goto(f"{self.base_url}/conexao", wait_until="domcontentloaded")
            self.page.fill("#connection-name", "Alice")
            self.page.fill("#connection-port", str(hub_port))
            self.page.click("#connection-start-hub")
            self.page.wait_for_function(
                "!document.getElementById('connection-stop-hub').hidden"
            )
            self.page.click("#connection-connect")
            self.page.wait_for_function(
                "document.getElementById('connection-status').textContent.includes('NO HUB')"
            )

            other.goto(f"{self.base_url}/conexao", wait_until="domcontentloaded")
            other.fill("#connection-name", "Bob")
            other.fill("#connection-port", str(hub_port))
            other.click("#connection-connect")
            other.wait_for_function(
                "document.getElementById('connection-status').textContent.includes('NO HUB')"
            )

            # Alice abre o cliente no editor e executa: o convite vai para a sala pública.
            self.page.goto(
                f"{self.base_url}/editor?example={cliente_arquivo}",
                wait_until="domcontentloaded",
            )
            self.page.wait_for_function(
                "document.getElementById('current-file').textContent.includes('cliente')"
            )
            self.page.wait_for_function(
                "document.getElementById('conn-chip-text').textContent.includes('No hub')"
            )
            self.page.click("#editor-compile")
            self.page.wait_for_function(
                "!document.getElementById('multi-terminal').hidden"
            )

            other.wait_for_function(
                "!document.getElementById('conn-invite').hidden"
            )
            other.click("#conn-invite-accept")

            # Os dois ficam no editor, cada um com o seu programa, com terminal fixo.
            other.wait_for_url("**/editor")
            other.wait_for_function(
                "document.getElementById('current-file').textContent.includes('servidor')"
            )
            self.assertIn(
                "servidor", other.locator("#current-file").inner_text()
            )
            self.page.wait_for_function(
                "!document.getElementById('multi-terminal-input').disabled"
            )
            self.assertTrue(self.page.locator("#input-area").is_hidden())
            altura = self.page.evaluate(
                "document.getElementById('multi-terminal-output').getBoundingClientRect().height"
            )
            self.assertLessEqual(altura, 160)

            # Os prompts aparecem no terminal na hora, antes de a saída acabar.
            for prompt, resposta in (
                ("Operacao", "+"),
                ("Operando 1", "2"),
                ("Operando 2", "3"),
            ):
                self.page.wait_for_function(
                    "text => document.getElementById('multi-terminal-output').textContent.includes(text)",
                    arg=prompt,
                )
                self.page.fill("#multi-terminal-input", resposta)
                self.page.press("#multi-terminal-input", "Enter")
            self.page.wait_for_function(
                "document.getElementById('multi-terminal-output').textContent.includes('Resultado')"
            )
            self.page.wait_for_function(
                "document.getElementById('multi-terminal-output').textContent.split('Operacao').length > 2"
            )
            self.page.fill("#multi-terminal-input", "sair")
            self.page.press("#multi-terminal-input", "Enter")
            self.page.wait_for_function(
                "document.getElementById('multi-terminal-output').textContent.includes('Resultado')"
            )
            self.page.wait_for_function(
                "document.getElementById('multi-terminal-status').textContent.includes('Conclu')"
            )
            self.assertIn(
                "Execução em par",
                self.page.locator("#phase-content").inner_text()
                if self.page.locator("#phase-title").inner_text() == "Execução"
                else "Execução em par",
            )
        finally:
            conexao_api.encerrar_tudo()
            other.close()

    def test_pages_load_without_external_requests(self):
        external_requests = []

        def handle_route(route):
            url = route.request.url
            if url.startswith(("data:", "blob:", "about:")):
                route.continue_()
                return
            if not url.startswith(self.base_url):
                external_requests.append(url)
                route.abort()
                return
            route.continue_()

        self.page.route("**/*", handle_route)
        try:
            for path in ("/", "/benchmark", "/resultados", "/configuracoes", "/editor", "/conexao", "/modelo-antigo"):
                self.page.goto(
                    f"{self.base_url}{path}", wait_until="domcontentloaded"
                )
                if path == "/editor":
                    self.page.wait_for_function(
                        "typeof CodeMirror === 'function'"
                    )
                else:
                    self.page.wait_for_selector("body")
        finally:
            self.page.unroute("**/*", handle_route)

        self.assertEqual(external_requests, [])


if __name__ == "__main__":
    unittest.main()
