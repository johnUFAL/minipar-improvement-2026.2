import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from interfaces.web import api


class WebCompileTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.temp_path = patch.object(api, "TEMP_DIR", str(self.root / "temp"))
        self.output_path = patch.object(api, "OUTPUT_DIR", str(self.root / "output"))
        self.temp_path.start()
        self.output_path.start()
        Path(api.TEMP_DIR).mkdir()
        Path(api.OUTPUT_DIR).mkdir()
        self.client = api.app.test_client()

    def tearDown(self):
        self.output_path.stop()
        self.temp_path.stop()
        self.temp_dir.cleanup()

    @patch("interfaces.web.api.subprocess.run")
    def test_web_forwards_inputs_and_returns_program_output(self, run):
        run.side_effect = [
            CompletedProcess(args=[], returncode=0, stdout="compiled", stderr=""),
            CompletedProcess(args=[], returncode=0, stdout="Resultado: 42\n", stderr=""),
        ]
        executable = Path(api.OUTPUT_DIR) / "input_output.exe"
        executable.touch()

        response = self.client.post(
            "/api/compile",
            json={
                "code": 'var valor = to_number(input("Valor: ")); print(valor);',
                "filename": "input_output.mp",
                "inputs": ["42"],
            },
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["success"])
        self.assertIn("Resultado: 42", result["stdout"])
        self.assertEqual(run.call_args_list[1].kwargs["input"], "42\n")

    @patch("interfaces.web.api.subprocess.run")
    def test_web_reports_compiler_failure_without_claiming_success(self, run):
        run.return_value = CompletedProcess(
            args=[], returncode=1, stdout="", stderr="C++ compiler unavailable"
        )

        response = self.client.post(
            "/api/compile",
            json={"code": "print(42);", "filename": "compile_error.mp"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertFalse(result["success"])
        self.assertIn("C++ compiler unavailable", result["stderr"])

    @patch("interfaces.web.api.subprocess.run")
    def test_web_reports_missing_binary_after_successful_compile(self, run):
        run.return_value = CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        response = self.client.post(
            "/api/compile",
            json={"code": "print(42);", "filename": "missing_binary.mp"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertFalse(result["success"])
        self.assertIn("Binário esperado não foi criado", result["stderr"])


if __name__ == "__main__":
    unittest.main()
