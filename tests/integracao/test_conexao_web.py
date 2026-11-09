import time
import unittest
from collections.abc import Callable
from typing import Any

from interfaces.web import api, conexao_api


class TestConexaoWeb(unittest.TestCase):
    def setUp(self) -> None:
        conexao_api.encerrar_tudo()
        self.cliente = api.app.test_client()

    def tearDown(self) -> None:
        conexao_api.encerrar_tudo()

    def _post(self, caminho: str, dados: dict[str, Any]) -> Any:
        return self.cliente.post(caminho, json=dados)

    def _estado(self, client_id: str) -> dict[str, Any]:
        resposta = self.cliente.get(
            "/api/conexao/estado",
            query_string={"client_id": client_id},
        )
        self.assertEqual(resposta.status_code, 200)
        return resposta.get_json()

    def _esperar(
        self,
        client_id: str,
        predicado: Callable[[dict[str, Any]], Any],
        *,
        timeout: float = 3.0,
    ) -> dict[str, Any]:
        limite = time.monotonic() + timeout
        ultimo: dict[str, Any] = {}
        while time.monotonic() < limite:
            ultimo = self._estado(client_id)
            if predicado(ultimo):
                return ultimo
            time.sleep(0.02)
        self.fail(f"Condição não atingida; último estado: {ultimo!r}")

    def _iniciar_hub(self) -> int:
        resposta = self._post("/api/conexao/hub/iniciar", {"porta": 0})
        self.assertEqual(resposta.status_code, 200, resposta.get_data(as_text=True))
        dados = resposta.get_json()
        self.assertTrue(dados["ativo"])
        return int(dados["porta"])

    def _conectar(self, client_id: str, porta: int, nome: str) -> dict[str, Any]:
        resposta = self._post(
            "/api/conexao/conectar",
            {
                "client_id": client_id,
                "host": "127.0.0.1",
                "porta": porta,
                "nome": nome,
            },
        )
        self.assertEqual(resposta.status_code, 200, resposta.get_data(as_text=True))
        return resposta.get_json()

    def test_pagina_de_conexao_e_assets(self) -> None:
        resposta = self.cliente.get("/conexao?program=t01_calculadora.mp")

        self.assertEqual(resposta.status_code, 200)
        pagina = resposta.get_data(as_text=True)
        self.assertIn('id="connection-log"', pagina)
        self.assertIn('id="connection-peers"', pagina)
        self.assertIn('id="connection-chat"', pagina)
        self.assertIn("Conexão", pagina)
        self.assertIn("t01_calculadora.mp", pagina)
        self.assertIn("/static/conexao.js", pagina)
        self.assertEqual(self.cliente.get("/static/conexao.js").status_code, 200)

    def test_editor_redireciona_programas_com_canal(self) -> None:
        script = self.cliente.get("/static/script.js").get_data(as_text=True)

        self.assertIn("requiresMultiComputerConnection", script)
        self.assertIn("minipar-conexao-handoff", script)
        self.assertIn("/conexao?program=", script)

    def test_fluxo_completo_de_conexao_e_chat_pela_api(self) -> None:
        porta = self._iniciar_hub()
        self._conectar("cliente-a", porta, "Alice")
        bob = self._conectar("cliente-b", porta, "Bob")
        bob_id = bob["peer_id"]

        self._esperar(
            "cliente-a",
            lambda estado: any(
                peer["id"] == bob_id for peer in estado["peers"]
            ),
        )

        resposta = self._post(
            "/api/conexao/solicitar",
            {"client_id": "cliente-a", "peer_id": bob_id},
        )
        self.assertEqual(resposta.status_code, 200, resposta.get_data(as_text=True))

        pedido = self._esperar(
            "cliente-b",
            lambda estado: estado.get("solicitacao"),
        )["solicitacao"]

        resposta = self._post(
            "/api/conexao/responder",
            {
                "client_id": "cliente-b",
                "request_id": pedido["request_id"],
                "aceitar": True,
            },
        )
        self.assertEqual(resposta.status_code, 200, resposta.get_data(as_text=True))

        self._esperar(
            "cliente-a",
            lambda estado: estado["estado"] == "conectado",
        )
        self._esperar(
            "cliente-b",
            lambda estado: estado["estado"] == "conectado",
        )

        resposta = self._post(
            "/api/conexao/chat",
            {"client_id": "cliente-a", "texto": "olá, Bob"},
        )
        self.assertEqual(resposta.status_code, 200, resposta.get_data(as_text=True))

        self._esperar(
            "cliente-b",
            lambda estado: any(
                mensagem["texto"] == "olá, Bob"
                for mensagem in estado["chat"]
            ),
        )

        resposta = self._post(
            "/api/conexao/desconectar",
            {"client_id": "cliente-b"},
        )
        self.assertEqual(resposta.status_code, 200, resposta.get_data(as_text=True))
        self._esperar(
            "cliente-a",
            lambda estado: estado["estado"] == "registrado",
        )

    def test_sala_privada_pela_api_aceita_dois_participantes(self) -> None:
        porta = self._iniciar_hub()
        self._conectar("sala-a", porta, "Alice")
        self._conectar("sala-b", porta, "Bob")

        resposta = self._post(
            "/api/conexao/sala/criar",
            {
                "client_id": "sala-a",
                "nome": "Sala de teste",
                "senha": "segredo",
            },
        )
        self.assertEqual(resposta.status_code, 200, resposta.get_data(as_text=True))

        sala = self._esperar(
            "sala-a",
            lambda estado: (
                (estado.get("sala") or {}).get("codigo") != "publica"
                and estado.get("sala")
            ),
        )["sala"]

        resposta = self._post(
            "/api/conexao/sala/entrar",
            {
                "client_id": "sala-b",
                "codigo": sala["codigo"],
                "senha": "segredo",
            },
        )
        self.assertEqual(resposta.status_code, 200, resposta.get_data(as_text=True))

        estado = self._esperar(
            "sala-b",
            lambda atual: (
                (atual.get("sala") or {}).get("codigo") == sala["codigo"]
            ),
        )
        self.assertEqual(estado["sala"]["lotacao"], 2)

    def test_acoes_invalidas_retornam_erro(self) -> None:
        resposta = self._post(
            "/api/conexao/chat",
            {"client_id": "inexistente", "texto": "oi"},
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(resposta.get_json()["success"])

        resposta = self._post(
            "/api/conexao/conectar",
            {
                "client_id": "cliente-x",
                "host": "127.0.0.1",
                "porta": 70000,
                "nome": "X",
            },
        )
        self.assertEqual(resposta.status_code, 400)

        self.assertEqual(
            self.cliente.get("/api/conexao/hub").get_json()["ativo"],
            False,
        )


if __name__ == "__main__":
    unittest.main()
