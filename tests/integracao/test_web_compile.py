import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from interfaces.web import api
from interfaces.web import benchmark
from components.codegen.c_gerador_cpp import CppCodeGenerator
from components.tac import TACOptimizer


ROOT = Path(__file__).resolve().parents[2]
PROGRAMS_DIR = ROOT / "programas_teste"
CXX = os.environ.get("CXX", "g++").strip('"')
CXX_AVAILABLE = shutil.which(CXX) is not None


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
        self.assertNotIn('id="test-list"', page)

    def test_screens_share_base_layout_and_have_dedicated_routes(self):
        routes = {
            "/": "Painel",
            "/resultados": "Resultados do compilador",
            "/benchmark": "Benchmark",
            "/configuracoes": "Configurações",
            "/editor": "Editor MiniPar",
            "/pipeline": "Pipeline MiniPar",
            "/ajuda": "Ajuda",
        }
        for path, label in routes.items():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                page = response.get_data(as_text=True)
                self.assertIn('class="sidebar"', page)
                self.assertIn('class="topbar"', page)
                self.assertIn(f"<span id=\"topbar-page\">{label}</span>", page)
                self.assertNotIn("OpenMP", page)
                self.assertNotIn("SIMD", page)
                self.assertNotIn("HPC", page)

        panel_page = self.client.get("/").get_data(as_text=True)
        benchmark_page = self.client.get("/benchmark").get_data(as_text=True)
        results_page = self.client.get("/resultados").get_data(as_text=True)
        settings_page = self.client.get("/configuracoes").get_data(as_text=True)
        self.assertIn('id="panel-run-benchmark"', panel_page)
        self.assertIn('id="panel-compiler-total"', panel_page)
        self.assertNotIn('id="benchmark-run"', panel_page)
        self.assertIn('id="benchmark-state"', benchmark_page)
        self.assertIn('role="progressbar"', benchmark_page)
        self.assertIn('id="benchmark-cores-bars"', benchmark_page)
        self.assertIn('id="benchmark-tasks-result"', benchmark_page)
        self.assertIn('id="benchmark-tasks-pagination"', benchmark_page)
        self.assertIn('id="compiler-history-list"', results_page)
        detail_page = self.client.get("/resultados/execucao-teste").get_data(as_text=True)
        self.assertIn('id="result-detail"', detail_page)
        self.assertIn('class="result-detail"', detail_page)
        self.assertIn('data-run-id="execucao-teste"', detail_page)
        self.assertIn('id="back-to-results"', detail_page)
        self.assertIn('SOMENTE LEITURA', detail_page)
        compat_page = self.client.get("/result-detail").get_data(as_text=True)
        self.assertIn('data-run-id="latest"', compat_page)
        self.assertIn('id="settings-cores"', settings_page)
        self.assertIn('id="hardware-max"', settings_page)

    def test_dashboard_exposes_benchmark_controls_without_running_there(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        for element_id in (
            "benchmark-students",
            "benchmark-activities",
            "benchmark-cores",
            "benchmark-fractals",
            "benchmark-repetitions",
            "panel-run-benchmark",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', page)
        for element_id in ("benchmark-run", "benchmark-results", "benchmark-csv"):
            with self.subTest(element_id=element_id):
                self.assertNotIn(f'id="{element_id}"', page)

    def test_benchmark_page_exposes_execution_and_results(self):
        response = self.client.get("/benchmark")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        for element_id in (
            "benchmark-run",
            "benchmark-state",
            "benchmark-results",
            "benchmark-summary",
            "benchmark-cores-result",
            "benchmark-tasks-result",
            "benchmark-csv",
            "benchmark-history",
            "benchmark-history-list",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', page)

    def test_benchmark_hardware_and_validation_endpoints(self):
        hardware = self.client.get("/api/hardware")
        self.assertEqual(hardware.status_code, 200)
        hardware_data = hardware.get_json()
        self.assertGreaterEqual(hardware_data["available_cores"], 1)
        self.assertLessEqual(
            hardware_data["benchmark_max_cores"],
            hardware_data["available_cores"],
        )
        self.assertLessEqual(hardware_data["benchmark_max_cores"], 256)
        with patch.object(api, "available_cpu_count", return_value=512):
            hardware = self.client.get("/api/hardware")
        self.assertEqual(hardware.get_json()["available_cores"], 512)
        self.assertEqual(hardware.get_json()["benchmark_max_cores"], 256)

        for payload in (
            None,
            {"alunos": True},
            {"fractais": 3},
            {"alunos": 2000, "atividades": 2},
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/benchmark", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.get_json()["error"])

    @unittest.skipUnless(CXX_AVAILABLE, "g++ is required for benchmark API integration")
    def test_benchmark_runs_asynchronously_and_exports_metrics_csv(self):
        response = self.client.post(
            "/api/benchmark",
            json={
                "alunos": 1,
                "atividades": 2,
                "nucleos": 1,
                "fractais": 1,
                "repeticoes": 1,
            },
        )
        self.assertEqual(response.status_code, 202)
        job_id = response.get_json()["job_id"]

        hardware = self.client.get("/api/hardware")
        self.assertEqual(hardware.status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/benchmark/{job_id}/csv").status_code,
            409,
        )

        deadline = time.monotonic() + 60
        job = None
        while time.monotonic() < deadline:
            response = self.client.get(f"/api/benchmark/{job_id}")
            self.assertEqual(response.status_code, 200)
            job = response.get_json()
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(0.1)

        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "completed", job)
        self.assertEqual(job["state"], "concluído")
        result = job["result"]
        self.assertEqual(result["parameters"]["total_atividades"], 2)
        self.assertEqual(result["parameters"]["nucleos_utilizados"], 1)
        self.assertGreater(result["sequential_seconds"], 0)
        self.assertGreater(result["parallel_seconds"], 0)
        self.assertGreaterEqual(result["speedup"], 0)
        self.assertIn("@@METRICAS ", result["metrics_line"])
        self.assertEqual(len(result["tasks"]), 3)
        self.assertEqual(
            {task["task"] for task in result["tasks"]},
            {"activity", "mandelbrot"},
        )
        self.assertEqual(
            sum(task["task"] == "activity" for task in result["tasks"]),
            2,
        )

        csv_response = self.client.get(f"/api/benchmark/{job_id}/csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("text/csv", csv_response.content_type)
        self.assertIn("resumo_sequencial", csv_response.get_data(as_text=True))
        self.assertIn("mandelbrot", csv_response.get_data(as_text=True))

    def test_benchmark_caps_requested_cores_to_available_hardware(self):
        tasks = [
            {
                "task_id": core - 1,
                "task": "activity",
                "core": core,
                "units": 1,
                "seconds": 0.01,
            }
            for core in (1, 2)
        ]

        with (
            patch.object(benchmark, "_program", return_value="program"),
            patch.object(
                benchmark,
                "_compile_program",
                side_effect=lambda _source, name, _directory: Path(name),
            ),
            patch.object(
                benchmark,
                "_run_program",
                side_effect=lambda executable, _arguments: (
                    (0.04, tasks[:1])
                    if executable.name == "sequential"
                    else (0.02, tasks)
                ),
            ),
        ):
            result = benchmark._run_benchmark(
                benchmark.BenchmarkConfig(
                    students=1,
                    activities_per_student=4,
                    requested_cores=3,
                    fractals=0,
                    repetitions=1,
                ),
                cpu_count=2,
                progress=lambda _progress, _message: None,
            )

        self.assertEqual(result["parameters"]["nucleos_utilizados"], 2)
        self.assertEqual(result["parameters"]["nucleos_solicitados"], 3)
        self.assertIn("3 núcleos", result["warnings"][0])
        self.assertIn("2 disponíveis", result["warnings"][0])

    @unittest.skipUnless(CXX_AVAILABLE, "g++ is required for benchmark core distribution")
    def test_benchmark_distributes_activities_across_cores(self):
        result = benchmark._run_benchmark(
            benchmark.BenchmarkConfig(
                students=1,
                activities_per_student=2,
                requested_cores=2,
                fractals=0,
                repetitions=1,
            ),
            cpu_count=2,
            progress=lambda _progress, _message: None,
        )
        activity_tasks = [
            task
            for task in result["tasks"]
            if task["task"] == "activity"
        ]
        self.assertEqual(len(activity_tasks), 2)
        self.assertEqual(sorted(task["core"] for task in activity_tasks), [1, 2])
        self.assertEqual(
            [core["task_count"] for core in result["cores"]],
            [1, 1],
        )

    def test_editor_assets_are_served_locally_for_both_interfaces(self):
        for route in ("/editor", "/modelo-antigo"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                page = response.get_data(as_text=True)
                self.assertNotIn("https://", page)
                self.assertIn(
                    "/static/vendor/codemirror/5.65.13/codemirror.min.js", page
                )
                self.assertIn(
                    "/static/vendor/codemirror/5.65.13/mode/clike/clike.min.js", page
                )

        for asset in (
            "vendor/codemirror/5.65.13/codemirror.min.js",
            "vendor/codemirror/5.65.13/codemirror.min.css",
            "vendor/codemirror/5.65.13/mode/clike/clike.min.js",
            "vendor/codemirror/5.65.13/theme/dracula.min.css",
        ):
            with self.subTest(asset=asset):
                self.assertEqual(
                    self.client.get(f"/static/{asset}").status_code,
                    200,
                )

    def test_new_interface_contains_origin_highlight_contract(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        script = self.client.get("/static/script.js").get_data(as_text=True)
        self.assertIn("data-source-line", script)
        self.assertIn("origin-highlight", script)
        self.assertIn("cm-origin-line", script)
        self.assertIn('role="button"', script)
        self.assertIn("tac-origin-popover", script)
        self.assertIn("moveTacPopover", script)
        self.assertIn('scope.querySelector(".mapped-code")', script)
        self.assertIn('line.closest(".mapped-code")', script)
        self.assertIn("pointermove", script)
        self.assertIn('querySelectorAll(".tac-origin-popover")', script)
        self.assertIn("cm-origin-line", script)
        self.assertNotIn("editor.scrollIntoView", script)
        self.assertIn("panel.addEventListener(\"pointerleave\", clear)", script)
        self.assertIn("readonly-code-line", script)
        self.assertIn("type: \"readonly\"", script)
        self.assertIn("result-source-code", script)
        self.assertIn("resultPhaseContent, source:", script)
        self.assertIn("bindSourceOriginHighlights", script)
        self.assertIn("highlightSource", script)
        self.assertIn("coordsChar", script)
        self.assertIn("index < editor.lineCount()", script)
        self.assertIn('editor.removeLineClass(index, "background", "cm-origin-line")', script)

    def test_new_interface_marks_diagnostic_columns(self):
        script = self.client.get("/static/script.js").get_data(as_text=True)
        style = self.client.get("/static/style.css").get_data(as_text=True)

        self.assertIn("columnMarkers", script)
        self.assertIn("editor.markText", script)
        self.assertIn("cm-error-token", script)
        self.assertIn(".cm-error-token", style)

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

    def test_get_test_rejects_path_traversal(self):
        for filename in (
            "../README.md",
            "..\\README.md",
            "C:\\README.md",
            "C:README.md",
            "\\\\server\\share\\x.mp",
            "/etc/passwd",
            "foo/../../README.md",
            "foo\\..\\README.md",
        ):
            with self.subTest(filename=filename):
                response = self.client.post(
                    "/api/get_test",
                    json={"filename": filename},
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["error"],
                    "Nome de arquivo inválido.",
                )

    def test_file_endpoints_reject_invalid_filenames(self):
        for endpoint in ("/api/test_spec", "/api/session/create"):
            with self.subTest(endpoint=endpoint):
                response = self.client.post(
                    endpoint,
                    json={"filename": "../programas_teste/t01_calculadora.mp"},
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["error"],
                    "Nome de arquivo inválido.",
                )

    def test_get_test_loads_file_inside_tests_directory(self):
        response = self.client.post(
            "/api/get_test",
            json={"filename": "t01_calculadora.mp"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["code"])

    def test_file_endpoints_distinguish_missing_files(self):
        for endpoint in ("/api/get_test", "/api/test_spec", "/api/session/create"):
            with self.subTest(endpoint=endpoint):
                response = self.client.post(
                    endpoint,
                    json={"filename": "does-not-exist.mp"},
                )

                self.assertEqual(response.status_code, 404)

    def test_get_test_rejects_missing_or_non_text_filename(self):
        for filename in ("", None, 42):
            with self.subTest(filename=filename):
                response = self.client.post(
                    "/api/get_test",
                    json={"filename": filename},
                )

                self.assertEqual(response.status_code, 400)

    @unittest.skipUnless(
        CXX_AVAILABLE, "g++ is required for the end-to-end web acceptance tests"
    )
    def test_acceptance_programs_run_through_web_pipeline(self):
        cases = {
            "t02_fatorial_fibonacci_par.mp": (
                [],
                ["FATORIAL_INICIO", "FIBONACCI_INICIO", "Fatorial de 10: 3628800", "FIBONACCI 34"],
            ),
            "t03_neuronio.mp": (
                [],
                [
                    "Valor desejado: 0",
                    "#### Iteração: 51",
                    "✅ Parabéns! O neurônio aprendeu.",
                ],
            ),
            "t05_recomendacao.mp": (
                ["1", "0", "0", "0", "0", "1", "0", "0", "0", "1", "0", "0", "1", "0", "0", "0"],
                [
                    "Produtos recomendados para voce:",
                    "Máquina de lavar",
                    "Não-ficção",
                ],
            ),
            "t06_quicksort_classes.mp": (
                ["10 -3 -40 80 70 -100"],
                [
                    "Vetor original: [10, -3, -40, 80, 70, -100]",
                    "Vetor ordenado: [-100, -40, -3, 10, 70, 80]",
                ],
            ),
            "t07_quicksort_iterativo_tac.mp": (
                [],
                ["Array ordenado: [5, 12, 33, 61, 98]"],
            ),
        }

        for filename, (inputs, expected_fragments) in cases.items():
            with self.subTest(program=filename):
                source = (PROGRAMS_DIR / filename).read_text(encoding="utf-8")
                response = self.client.post(
                    "/api/executar",
                    json={"code": source, "inputs": inputs},
                )

                self.assertEqual(response.status_code, 200)
                result = response.get_json()
                self.assertTrue(result["success"], result.get("stderr"))
                self.assertEqual(result["exit_code"], 0)
                for fragment in expected_fragments:
                    self.assertIn(fragment, result["stdout"])

    @unittest.skipUnless(
        CXX_AVAILABLE, "g++ is required for the end-to-end web acceptance tests"
    )
    def test_xor_program_learns_through_web_pipeline(self):
        source = (PROGRAMS_DIR / "t04_rede_neural_xor.mp").read_text(
            encoding="utf-8"
        )
        response = self.client.post(
            "/api/executar", json={"code": source, "inputs": []}
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["success"], result.get("stderr"))
        predictions = [
            float(value)
            for value in re.findall(
                r"Predicted Output:\s*([0-9.]+)", result["stdout"]
            )
        ]
        self.assertEqual(len(predictions), 4)
        self.assertLess(predictions[0], 0.1)
        self.assertGreater(predictions[1], 0.9)
        self.assertGreater(predictions[2], 0.9)
        self.assertLess(predictions[3], 0.1)

    def test_calculadora_compiles_through_web_but_channel_execution_needs_peer(self):
        source = (
            PROGRAMS_DIR
            / "t01_multiterminal"
            / "t01_calculadora_cliente.mp"
        ).read_text(encoding="utf-8")
        response = self.client.post(
            "/api/compilar", json={"code": source}
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["success"], result.get("diagnosticos"))
        self.assertIn("MiniParChannel", result["cpp"])

    def test_tests_endpoint_lists_split_pairs_recursively(self):
        response = self.client.get("/api/tests")

        self.assertEqual(response.status_code, 200)
        tests = response.get_json()["tests"]
        self.assertIn("t01_multiterminal/t01_calculadora_cliente.mp", tests)
        self.assertIn("dois_computadores/t02_adivinha_cliente.mp", tests)
        self.assertIn("dois_computadores/t03_estoque_servidor.mp", tests)

    def test_new_two_computer_examples_compile(self):
        for path in sorted(
            (PROGRAMS_DIR / "dois_computadores").glob("*.mp")
        ):
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                response = self.client.post(
                    "/api/compilar", json={"code": source}
                )

                self.assertEqual(response.status_code, 200)
                result = response.get_json()
                self.assertTrue(result["success"], result.get("diagnosticos"))
                self.assertIn("MiniParChannel", result["cpp"])

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

    @patch("interfaces.web.api._run_limited")
    @patch("interfaces.web.api.DriverGCC.compile", return_value=True)
    @patch("interfaces.web.api._compile_phases")
    def test_execute_endpoint_applies_requested_optimization(
        self, compile_phases, gcc_compile, run
    ):
        compile_phases.return_value = {
            "success": True,
            "cpp": "int main() { return 0; }",
            "tac": "t0 = 2 + 3\nprint t0\n",
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

        captured_sources = []

        def _capture_cpp(cpp_path, executable_path):
            captured_sources.append(cpp_path.read_text(encoding="utf-8"))
            return True

        gcc_compile.side_effect = _capture_cpp

        response = self.client.post(
            "/api/executar",
            json={"code": "print(42);", "inputs": [], "optimization_level": "O1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(
            captured_sources[-1],
            CppCodeGenerator().generate_source(TACOptimizer().optimize("t0 = 2 + 3\nprint t0\n", "O1")),
        )

        response = self.client.post(
            "/api/executar",
            json={"code": "print(42);", "inputs": [], "optimization_level": "O0"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_sources[-1], "int main() { return 0; }")

    def test_session_endpoints_manage_multi_terminal_lifecycle(self):
        filename = "t01_calculadora.mp"

        try:
            response = self.client.post("/api/session/create", json={"filename": filename})
            self.assertEqual(response.status_code, 200)
            created = response.get_json()
            self.assertTrue(created["success"])
            self.assertEqual(created["session"]["test_file"], filename)

            response = self.client.get("/api/session")
            self.assertEqual(response.status_code, 200)
            current = response.get_json()
            self.assertTrue(current["active"])
            self.assertEqual(current["session"]["test_file"], filename)

            response = self.client.post("/api/session/join", json={})
            self.assertEqual(response.status_code, 200)
            joined = response.get_json()
            self.assertTrue(joined["success"])
            self.assertEqual(len(joined["session"]["participants"]), 1)

            response = self.client.post("/api/session/ready", json={})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_json()["success"])

            response = self.client.get("/api/session")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["session"]["status"], "running")
        finally:
            self.client.post("/api/session/clear", json={})


    def test_editor_no_longer_renders_removed_terminal_panel(self):
        response = self.client.get("/editor")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertNotIn('id="terminal-panel"', page)
        self.assertNotIn('id="terminal-output"', page)
        self.assertNotIn('id="session-progress"', page)
        self.assertIn('id="phase-content"', page)
        self.assertIn('id="compile-button"', page)


if __name__ == "__main__":
    unittest.main()
