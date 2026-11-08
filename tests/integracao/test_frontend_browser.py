import importlib.util
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.serving import make_server

from interfaces.web import api

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
        self.page.goto(f"{self.base_url}/#ide", wait_until="domcontentloaded")
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

        self.page.click('.nav-item[data-page="results"]')
        self.page.wait_for_selector("#results-list .history-row")
        self.assertFalse(self.page.locator("#compile-button").is_visible())
        self.page.locator("#results-list .history-row").first.click()
        self.page.wait_for_selector("#page-result-detail.active-page")
        self.assertFalse(self.page.locator("#compile-button").is_visible())

        self.page.click('[data-result-phase="tac"]')
        self.page.click("#result-compare-tac")
        self.page.wait_for_selector(
            "#result-tac-comparison .mapped-code-line[data-source-line]"
        )
        self._assert_popover_and_highlight(
            "#result-tac-comparison .mapped-code-line[data-source-line]",
            ".readonly-code-line.origin-highlight",
        )

        self.page.click('[data-result-phase="cpp"]')
        self.page.wait_for_selector(
            "#result-phase-content .mapped-code-line[data-source-line]"
        )
        self._assert_popover_and_highlight(
            "#result-phase-content .mapped-code-line[data-source-line]",
            ".readonly-code-line.origin-highlight",
        )

    def test_responsiveness_and_accessibility_contract(self):
        self.page.goto(f"{self.base_url}/#dashboard", wait_until="domcontentloaded")
        self.page.wait_for_function("typeof CodeMirror === 'function'")
        self.assertFalse(self.page.locator("#compile-button").is_visible())

        for width, height in ((820, 1000), (390, 844)):
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

        self.page.click('.nav-item[data-page="results"]')
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


if __name__ == "__main__":
    unittest.main()
