import socket
import time
from collections.abc import Callable
from typing import Any

import pytest

from interfaces.conexao.cliente import ClienteHub
from interfaces.conexao.hub import ServidorHub, ips_locais
from interfaces.conexao.protocolo import (
    SALA_PUBLICA,
    codificar,
    decodificar,
)


def _aguardar(
    predicado: Callable[[], Any],
    *,
    timeout: float = 3.0,
    intervalo: float = 0.02,
) -> Any:
    limite = time.monotonic() + timeout
    ultimo: Any = None
    while time.monotonic() < limite:
        ultimo = predicado()
        if ultimo:
            return ultimo
        time.sleep(intervalo)
    raise AssertionError(f"Condição não atingida; último valor: {ultimo!r}")


@pytest.fixture()
def hub() -> Any:
    servidor = ServidorHub(host="127.0.0.1", porta=0)
    porta = servidor.iniciar()
    try:
        yield servidor, porta
    finally:
        servidor.parar()


@pytest.fixture()
def criar_cliente(hub: Any) -> Any:
    _, porta = hub
    clientes: list[ClienteHub] = []

    def criar(nome: str) -> ClienteHub:
        cliente = ClienteHub()
        cliente.conectar("127.0.0.1", porta, nome)
        clientes.append(cliente)
        return cliente

    try:
        yield criar
    finally:
        for cliente in clientes:
            cliente.fechar()


def test_pareamento_e_chat_entre_duas_sessoes(hub: Any, criar_cliente: Any) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")
    bob_id = bob.snapshot()["peer_id"]

    _aguardar(
        lambda: any(
            peer["id"] == bob_id for peer in alice.snapshot()["peers"]
        )
    )

    alice.solicitar(bob_id)
    pedido = _aguardar(lambda: bob.snapshot()["solicitacao"])
    assert pedido["de"] == alice.snapshot()["peer_id"]
    assert pedido["nome"] == "Alice"

    bob.responder(pedido["request_id"], True)
    _aguardar(
        lambda: (
            alice.snapshot()["estado"] == "conectado"
            and bob.snapshot()["estado"] == "conectado"
        )
    )
    assert alice.snapshot()["conectado_com"]["nome"] == "Bob"
    assert bob.snapshot()["conectado_com"]["nome"] == "Alice"

    alice.chat("olá, Bob")
    _aguardar(
        lambda: any(
            mensagem["texto"] == "olá, Bob"
            for mensagem in bob.snapshot()["chat"]
        )
    )
    assert any(
        mensagem["proprio"] and mensagem["texto"] == "olá, Bob"
        for mensagem in alice.snapshot()["chat"]
    )

    bob.desconectar()
    _aguardar(lambda: alice.snapshot()["estado"] == "registrado")
    assert alice.snapshot()["conectado_com"] is None

    carol = criar_cliente("Carol")
    carol_id = carol.snapshot()["peer_id"]
    _aguardar(
        lambda: any(
            peer["id"] == carol_id for peer in alice.snapshot()["peers"]
        )
    )
    alice.solicitar(carol_id)
    novo_pedido = _aguardar(lambda: carol.snapshot()["solicitacao"])
    carol.responder(novo_pedido["request_id"], True)
    _aguardar(
        lambda: (
            alice.snapshot()["estado"] == "conectado"
            and carol.snapshot()["estado"] == "conectado"
        )
    )
    assert alice.snapshot()["chat"] == []


def _parear(alice: ClienteHub, bob: ClienteHub) -> None:
    bob_id = bob.snapshot()["peer_id"]
    _aguardar(
        lambda: any(
            peer["id"] == bob_id for peer in alice.snapshot()["peers"]
        )
    )
    alice.solicitar(bob_id)
    pedido = _aguardar(lambda: bob.snapshot()["solicitacao"])
    bob.responder(pedido["request_id"], True)
    _aguardar(
        lambda: (
            alice.snapshot()["estado"] == "conectado"
            and bob.snapshot()["estado"] == "conectado"
        )
    )


def test_execucao_troca_contexto_e_relay(hub: Any, criar_cliente: Any) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")
    _parear(alice, bob)
    canal = {
        "nome": "dados",
        "conecta": "computador_1",
        "escuta": "computador_2",
    }

    alice.anunciar_execucao(
        "cliente.mp",
        "computador_1",
        [canal],
        host="127.0.0.1",
        modo="conecta",
    )
    bob.anunciar_execucao(
        "servidor.mp",
        "computador_2",
        [canal],
        host="127.0.0.1",
        porta=5102,
        modo="escuta",
    )

    _aguardar(
        lambda: (
            (alice.snapshot()["execucao"].get("peer") or {}).get("papel")
            == "computador_2"
            and (bob.snapshot()["execucao"].get("peer") or {}).get("papel")
            == "computador_1"
        )
    )
    assert alice.snapshot()["execucao"]["peer_endereco"] == "127.0.0.1"

    alice.marcar_execucao_preparada()
    _aguardar(lambda: bob.snapshot()["execucao"]["peer_preparado"])

    bob.marcar_execucao_pronta(host="127.0.0.1", porta=5102)
    _aguardar(lambda: alice.snapshot()["execucao"]["peer_pronto"])

    bob.parar_execucao("teste")
    _aguardar(lambda: alice.snapshot()["execucao"]["parar_solicitado"])


def test_execucao_rejeita_papeis_iguais(hub: Any, criar_cliente: Any) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")
    _parear(alice, bob)
    canal = {
        "nome": "dados",
        "conecta": "computador_1",
        "escuta": "computador_2",
    }

    alice.anunciar_execucao("cliente.mp", "computador_1", [canal])
    bob.anunciar_execucao("cliente.mp", "computador_1", [canal])

    erro = _aguardar(
        lambda: next(
            (
                evento
                for evento in bob.drenar_eventos()
                if evento.get("type") == "exec_erro"
                and evento.get("origem") == "hub"
            ),
            None,
        )
    )
    assert "mesmo papel" in erro["mensagem"]


def test_chat_exige_conexao_ativa(hub: Any, criar_cliente: Any) -> None:
    alice = criar_cliente("Alice")

    with pytest.raises(ValueError):
        alice.chat("olá")


def test_ping_responde_pong(hub: Any) -> None:
    _, porta = hub
    with socket.create_connection(("127.0.0.1", porta), timeout=2) as sock:
        sock.settimeout(2)
        arquivo = sock.makefile("rb")
        sock.sendall(codificar({"type": "registrar", "nome": "Ping"}))
        assert decodificar(arquivo.readline())["type"] == "registrado"
        sock.sendall(codificar({"type": "ping"}))
        for _ in range(5):
            mensagem = decodificar(arquivo.readline())
            if mensagem["type"] == "pong":
                break
        else:
            raise AssertionError("O hub não respondeu ao ping.")


def test_ips_locais_inclui_loopback_sem_duplicatas() -> None:
    enderecos = ips_locais()

    assert enderecos
    assert "127.0.0.1" in enderecos
    assert len(enderecos) == len(set(enderecos))


def test_sala_privada_limita_dois_participantes_e_valida_senha(
    hub: Any,
    criar_cliente: Any,
) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")
    carol = criar_cliente("Carol")
    dave = criar_cliente("Dave")

    alice.criar_sala("Dupla", True, "segredo")

    def sala_privada() -> dict[str, Any] | None:
        sala = alice.snapshot()["sala"]
        if isinstance(sala, dict) and sala.get("codigo") != SALA_PUBLICA:
            return sala
        return None

    sala = _aguardar(sala_privada)
    codigo = sala["codigo"]

    bob.entrar_sala(codigo, "segredo")
    _aguardar(
        lambda: (bob.snapshot()["sala"] or {}).get("codigo") == codigo
    )
    _aguardar(
        lambda: any(
            peer["nome"] == "Bob" for peer in alice.snapshot()["peers"]
        )
    )

    carol.entrar_sala(codigo, "segredo")
    _aguardar(
        lambda: "cheia" in str(carol.snapshot()["ultimo_erro"]).lower()
    )
    assert (carol.snapshot()["sala"] or {}).get("codigo") == SALA_PUBLICA

    dave.entrar_sala(codigo, "errada")
    _aguardar(
        lambda: "senha" in str(dave.snapshot()["ultimo_erro"]).lower()
    )
    assert (dave.snapshot()["sala"] or {}).get("codigo") == SALA_PUBLICA


def test_solicitacao_exige_participantes_na_mesma_sala(
    hub: Any,
    criar_cliente: Any,
) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")
    bob_id = bob.snapshot()["peer_id"]

    alice.criar_sala("Isolada", True, "")
    _aguardar(
        lambda: (
            (alice.snapshot()["sala"] or {}).get("codigo") != SALA_PUBLICA
        )
    )

    alice.solicitar(bob_id)
    _aguardar(
        lambda: "outra sala" in str(alice.snapshot()["ultimo_erro"]).lower()
    )
    assert alice.snapshot()["estado"] == "registrado"
