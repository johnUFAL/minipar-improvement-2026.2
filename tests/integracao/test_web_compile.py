import sys
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

    def test_new_interface_links_to_legacy_reference_gallery(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("/modelo-antigo", page)
        self.assertIn('id="dashboard-example"', page)
        self.assertIn('id="dashboard-analyze"', page)
        self.assertIn('id="example-select"', page)
        self.assertIn('id="page-pipeline"', page)
        self.assertIn('data-page-target="pipeline"', page)
        self.assertNotIn('dashboard-pipeline-card', page)
        self.assertNotIn('id="test-list"', page)

    def test_legacy_interface_is_independent_and_links_to_new(self):
        response = self.client.get("/modelo-antigo")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Explorer", response.get_data(as_text=True))
        self.assertIn("C++ Output", response.get_data(as_text=True))
        self.assertIn('href="/"', response.get_data(as_text=True))
        image = self.client.get(
            "/modelo-antigo/static/style.css"
        )
        self.assertEqual(image.status_code, 200)
        self.assertIn(".app-container", image.get_data(as_text=True))
        gallery = self.client.get("/modelo-antigo/referencias")
        self.assertEqual(gallery.status_code, 200)
        self.assertIn("Modelo anterior do MiniPar", gallery.get_data(as_text=True))

    def test_symbols_endpoint_returns_serializable_symbol_table(self):
        response = self.client.post(
            "/api/symbols",
            json={
                "code": (
                    "SEQ\n"
                    "    result: int = 42\n"
                    "    print(result)\n"
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["success"])
        exported_symbols = [
            symbol
            for scope in result["symbols"]["scopes"]
            for symbol in scope["symbols"]
        ]
        self.assertTrue(any(symbol["name"] == "result" for symbol in exported_symbols))

    def test_compile_phases_returns_tac_and_cpp_origin_maps(self):
        response = self.client.post(
            "/api/compilar",
            json={"code": "SEQ\n    print(42)\n"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["success"])
        self.assertTrue(result["tac_origin"])
        self.assertTrue(result["cpp_origin"])
        self.assertTrue(
            any(item["source_line"] == 2 for item in result["tac_origin"])
        )
        self.assertTrue(
            any(item["source_line"] == 2 for item in result["cpp_origin"])
        )

    def test_optimization_levels_have_distinct_contracts(self):
        source = "SEQ\n    result: int = 2 + 3\n    print(result)\n"
        outputs = {}
        for level in ("O0", "O1", "O2", "O3"):
            response = self.client.post(
                "/api/otimizar",
                json={"code": source, "optimization_level": level},
            )
            self.assertEqual(response.status_code, 200)
            outputs[level] = response.get_json()

        self.assertEqual(outputs["O0"]["tac"], outputs["O0"]["tac_optimized"])
        self.assertNotEqual(outputs["O1"]["tac"], outputs["O1"]["tac_optimized"])
        self.assertLessEqual(
            outputs["O2"]["tac_instruction_counts"]["optimized"],
            outputs["O1"]["tac_instruction_counts"]["optimized"],
        )
        self.assertLessEqual(
            outputs["O3"]["tac_instruction_counts"]["optimized"],
            outputs["O2"]["tac_instruction_counts"]["optimized"],
        )

    def test_symbols_endpoint_rejects_missing_source(self):
        response = self.client.post("/api/symbols", json={})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])

    @patch("interfaces.web.api._run_limited")
    @patch("interfaces.web.api.subprocess.run")
    def test_web_forwards_inputs_and_returns_program_output(self, run, execute):
        run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="compiled", stderr=""
        )
        execute.return_value = {
            "stdout": "Resultado: 42\n",
            "stderr": "",
            "exit_code": 0,
            "tempo": 0.01,
            "timed_out": False,
            "output_limited": False,
        }
        exe_ext = ".exe" if sys.platform == "win32" else ""
        executable = Path(api.OUTPUT_DIR) / f"input_output{exe_ext}"
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
        self.assertEqual(execute.call_args.kwargs["input_text"], "42\n")

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

    @patch("interfaces.web.api.subprocess.run")
    def test_web_returns_original_and_optimized_tac_when_requested(self, run):
        run.return_value = CompletedProcess(
            args=[], returncode=1, stdout="", stderr="compilation failed"
        )
        tac_path = Path(api.OUTPUT_DIR) / "comparison.tac"
        tac_path.write_text(
            "t0 = 2 + 3\nt1 = t0\nprint t1\n", encoding="utf-8"
        )

        response = self.client.post(
            "/api/compile",
            json={
                "code": "print(5);",
                "filename": "comparison.mp",
                "optimize_tac": True,
            },
        )

        result = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(result["tac"], "t0 = 2 + 3\nt1 = t0\nprint t1\n")
        self.assertEqual(result["tac_optimized"], "print 5\n")
        self.assertEqual(
            result["tac_instruction_counts"], {"original": 3, "optimized": 1}
        )

    def test_web_rejects_non_boolean_tac_optimization_flag(self):
        response = self.client.post(
            "/api/compile",
            json={
                "code": "print(5);",
                "filename": "comparison.mp",
                "optimize_tac": "yes",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("optimize_tac", response.get_json()["error"])

    def test_compile_phases_returns_the_documented_json_shape(self):
        response = self.client.post(
            "/api/compilar",
            json={"code": "SEQ\n    result: int = 42\n    print(result)\n"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(
            set(result),
            {
                "tokens", "ast", "tabela_simbolos", "tac", "cpp",
                "tac_origin", "cpp_origin", "diagnosticos", "success",
            },
        )
        self.assertIsInstance(result["tokens"], list)
        self.assertIsInstance(result["ast"], dict)
        self.assertIsInstance(result["tabela_simbolos"], dict)
        self.assertIsInstance(result["tac"], str)
        self.assertIsInstance(result["cpp"], str)
        self.assertIsInstance(result["diagnosticos"], list)
        self.assertTrue(result["success"])

    def test_compile_phases_returns_diagnostics_for_invalid_source(self):
        response = self.client.post("/api/compilar", json={"code": ""})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertFalse(result["success"])
        self.assertTrue(result["diagnosticos"])
        self.assertEqual(result["cpp"], "")
        self.assertEqual(result["tac"], "")

    def test_compile_phases_returns_schema_for_ten_test_programs(self):
        filenames = [
            *(f"t0{number}_{name}.mp" for number, name in [
                (1, "calculadora"),
                (2, "fatorial_fibonacci_par"),
                (3, "neuronio"),
                (4, "rede_neural_xor"),
                (5, "recomendacao"),
                (6, "quicksort_classes"),
                (7, "quicksort_iterativo_tac"),
            ]),
            "teste_adicional1_paralelismo_3_computadores.mp",
            "teste_adicional2_tapete_sierpinski.mp",
            "teste_bnf_controles_input.mp",
        ]
        required_fields = {
            "tokens", "ast", "tabela_simbolos", "tac", "cpp",
            "tac_origin", "cpp_origin", "diagnosticos", "success",
        }

        for filename in filenames:
            with self.subTest(filename=filename):
                source = (Path(api.TESTS_DIR) / filename).read_text(encoding="utf-8")
                response = self.client.post("/api/compilar", json={"code": source})
                self.assertEqual(response.status_code, 200)
                result = response.get_json()
                self.assertEqual(set(result), required_fields)
                self.assertIsInstance(result["tokens"], list)
                self.assertIsInstance(result["ast"], dict)
                self.assertIsInstance(result["tabela_simbolos"], dict)
                self.assertIsInstance(result["tac"], str)
                self.assertIsInstance(result["cpp"], str)
                self.assertIsInstance(result["diagnosticos"], list)

    @patch("interfaces.web.api._run_limited")
    @patch("interfaces.web.api.DriverGCC.compile", return_value=True)
    @patch("interfaces.web.api._compile_phases")
    def test_execute_endpoint_returns_process_result(self, compile_phases, _, run):
        compile_phases.return_value = {
            "success": True,
            "cpp": "int main() {}",
            "diagnosticos": [],
        }
        run.return_value = {
            "stdout": "42\n",
            "stderr": "",
            "exit_code": 0,
            "tempo": 0.02,
            "timed_out": False,
            "output_limited": False,
        }

        response = self.client.post(
            "/api/executar",
            json={"code": "print(42);", "inputs": ["value"]},
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["stdout"], "42\n")
        self.assertEqual(result["stderr"], "")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["tempo"], 0.02)
        self.assertTrue(result["success"])
        self.assertEqual(run.call_args.kwargs["input_text"], "value\n")

    def test_execute_endpoint_rejects_non_scalar_input(self):
        response = self.client.post(
            "/api/executar",
            json={"code": "print(42);", "inputs": [{"unexpected": "object"}]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("inputs", response.get_json()["error"])

    def test_execution_timeout_and_output_are_bounded(self):
        timeout_result = api._run_limited(
            [sys.executable, "-c", "import time; time.sleep(2)"],
            timeout=0.1,
        )
        output_result = api._run_limited(
            [
                sys.executable,
                "-c",
                "while True: print('output', flush=True)",
            ],
            timeout=2,
            output_limit=64,
        )

        self.assertTrue(timeout_result["timed_out"])
        self.assertLessEqual(
            len(str(output_result["stdout"]).encode("utf-8"))
            + len(str(output_result["stderr"]).encode("utf-8")),
            64,
        )
        self.assertTrue(output_result["output_limited"])

    @patch("interfaces.web.api._run_limited")
    @patch("interfaces.web.api.DriverGCC.compile", return_value=True)
    @patch("interfaces.web.api._compile_phases")
    def test_server_responds_after_execution_timeout(self, compile_phases, _, run):
        compile_phases.return_value = {
            "success": True,
            "cpp": "int main() {}",
            "diagnosticos": [],
        }
        run.return_value = {
            "stdout": "",
            "stderr": "",
            "exit_code": -9,
            "tempo": api.EXECUTION_TIMEOUT_SECONDS,
            "timed_out": True,
            "output_limited": False,
        }

        execution = self.client.post("/api/executar", json={"code": "print(42);"})
        follow_up = self.client.get("/api/tests")

        self.assertFalse(execution.get_json()["success"])
        self.assertTrue(execution.get_json()["timed_out"])
        self.assertEqual(follow_up.status_code, 200)


if __name__ == "__main__":
    unittest.main()
