from __future__ import annotations

import unittest

from interfaces.web2.app import app


class Web2DidacticInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = app.test_client()

    def test_index_renders_the_didactic_interface(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("MiniPar", body)
        self.assertIn("Tokens", body)
        self.assertIn("Árvore Sintática Abstrata", body)
        self.assertIn("Compilar e baixar o executável", body)
        self.assertIn("Executar agora", body)

    def test_health_and_environment_endpoints(self) -> None:
        health = self.client.get("/health")
        environment = self.client.get("/api/ambiente")

        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.get_json()["success"])
        self.assertEqual(environment.status_code, 200)
        self.assertTrue(environment.get_json()["success"])

    def test_analyze_returns_every_phase(self) -> None:
        response = self.client.post(
            "/api/analisar",
            json={"code": "seq {\n    var x = 1 + 2;\n    print(x);\n}\n"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["success"])
        self.assertTrue(result["tokens"])
        self.assertEqual(result["ast"]["tipo"], "Program")
        self.assertTrue(result["tac"])
        self.assertTrue(result["cpp"])
        self.assertEqual(result["diagnosticos"], [])
        self.assertIn("scopes", result["tabela_simbolos"])

    def test_analyze_reports_syntax_errors_with_location(self) -> None:
        response = self.client.post("/api/analisar", json={"code": "seq { var = ; }"})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertFalse(result["success"])
        self.assertTrue(result["diagnosticos"])
        self.assertTrue(any(item["line"] for item in result["diagnosticos"]))

    def test_analyze_rejects_missing_source(self) -> None:
        response = self.client.post("/api/analisar", json={})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])

    def test_execute_runs_the_generated_program(self) -> None:
        response = self.client.post(
            "/api/executar",
            json={"code": 'seq { print("resultado:", 6 * 7); }'},
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["success"], result)
        self.assertIn("resultado: 42", result["stdout"])
        self.assertEqual(result["exit_code"], 0)

    def test_execute_honors_standard_input(self) -> None:
        response = self.client.post(
            "/api/executar",
            json={
                "code": 'seq { var nome = input(""); print("Ola,", nome); }',
                "input": "MiniPar\n",
            },
        )

        result = response.get_json()
        self.assertTrue(result["success"], result)
        self.assertIn("Ola, MiniPar", result["stdout"])

    def test_compile_offers_a_downloadable_executable(self) -> None:
        response = self.client.post(
            "/api/compilar",
            json={"code": "seq { print(1 + 2); }"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["success"], result)
        self.assertTrue(result["download_url"].startswith("/api/artefato/"))

        download = self.client.get(result["download_url"])
        self.assertEqual(download.status_code, 200)
        self.assertGreater(len(download.data), 1024)

    def test_compile_rejects_invalid_optimization(self) -> None:
        response = self.client.post(
            "/api/compilar",
            json={"code": "seq { print(1); }", "optimization": "O9"},
        )

        self.assertEqual(response.status_code, 400)

    def test_examples_are_listed_and_loaded(self) -> None:
        listing = self.client.get("/api/exemplos").get_json()
        self.assertTrue(listing["success"])
        names = [item["name"] for item in listing["exemplos"]]
        self.assertIn("t08_avaliacao_4_nucleos.mp", names)
        self.assertIn("t11_minicompilador_arm.mp", names)

        example = self.client.get("/api/exemplo/t11_minicompilador_arm.mp").get_json()
        self.assertTrue(example["success"])
        self.assertIn("MiniCompiladorARM", example["code"])

    def test_example_path_traversal_is_rejected(self) -> None:
        response = self.client.get("/api/exemplo/..%2Fmain.py")
        self.assertEqual(response.status_code, 404)

    def test_arm_files_are_available(self) -> None:
        for name in ("expr1.arm", "expr2.arm", "expr3.arm"):
            response = self.client.get(f"/api/arm/{name}")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b".global _start", response.data)

    def test_arm_endpoint_rejects_unknown_file(self) -> None:
        response = self.client.get("/api/arm/other.arm")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
