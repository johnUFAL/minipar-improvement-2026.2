import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "interfaces" / "web" / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
CODEMIRROR_DIR = (
    FRONTEND_DIR / "static" / "vendor" / "codemirror" / "5.65.13"
)

EXTERNAL_RESOURCE = re.compile(
    r"""(?:src|href)\s*=\s*["'](https?://[^"']+)["']""",
    re.IGNORECASE,
)
EXTERNAL_CSS_URL = re.compile(r"""url\(\s*["']?https?://""", re.IGNORECASE)

CODEMIRROR_ASSETS = (
    "codemirror.min.css",
    "codemirror.min.js",
    "mode/clike/clike.min.js",
    "theme/dracula.min.css",
    "LICENSE",
)


class OfflineAssetsTests(unittest.TestCase):
    def test_templates_do_not_reference_external_resources(self):
        offenders = []
        for template in TEMPLATES_DIR.rglob("*.html"):
            text = template.read_text(encoding="utf-8")
            for match in EXTERNAL_RESOURCE.finditer(text):
                relative = template.relative_to(TEMPLATES_DIR)
                offenders.append(f"{relative}: {match.group(0)}")
        self.assertEqual(offenders, [])

    def test_templates_use_vendored_codemirror(self):
        for template in ("index.html", "legacy/index.html"):
            text = (TEMPLATES_DIR / template).read_text(encoding="utf-8")
            self.assertIn(
                "vendor/codemirror/5.65.13/codemirror.min.js",
                text,
                f"{template} deve carregar o CodeMirror local",
            )

    def test_vendored_codemirror_assets_exist(self):
        missing = [
            asset for asset in CODEMIRROR_ASSETS
            if not (CODEMIRROR_DIR / asset).is_file()
        ]
        self.assertEqual(missing, [])

    def test_vendored_codemirror_css_has_no_external_urls(self):
        offenders = []
        for css_file in CODEMIRROR_DIR.rglob("*.css"):
            text = css_file.read_text(encoding="utf-8")
            if EXTERNAL_CSS_URL.search(text):
                offenders.append(str(css_file.relative_to(CODEMIRROR_DIR)))
        self.assertEqual(offenders, [])

    def test_vendored_codemirror_license_is_present(self):
        license_text = (CODEMIRROR_DIR / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT", license_text)


if __name__ == "__main__":
    unittest.main()
