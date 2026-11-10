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

    # A conexão aceita move os dois para uma sala privada automática.
    sala_auto = alice.snapshot()["sala"]
    assert sala_auto["automatica"] and sala_auto["codigo"] != SALA_PUBLICA
    assert bob.snapshot()["sala"]["codigo"] == sala_auto["codigo"]

    bob.desconectar()
    _aguardar(lambda: alice.snapshot()["estado"] == "registrado")
    assert alice.snapshot()["conectado_com"] is None
    # A dona continua na sala, esperando uma nova conexão.
    assert alice.snapshot()["sala"]["codigo"] == sala_auto["codigo"]
    assert bob.snapshot()["sala"]["codigo"] == SALA_PUBLICA

    carol = criar_cliente("Carol")
    carol_id = carol.snapshot()["peer_id"]
    carol.entrar_sala(sala_auto["codigo"])
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


def test_chat_livre_na_sala_publica(hub: Any, criar_cliente: Any) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")
    carol = criar_cliente("Carol")

    alice.chat("olá, pessoal")

    for destino in (bob, carol):
        _aguardar(
            lambda destino=destino: any(
                m["texto"] == "olá, pessoal"
                for m in destino.snapshot()["chat"]
            )
        )


def test_chat_exige_estar_no_hub() -> None:
    with pytest.raises(ValueError):
        ClienteHub().chat("olá")


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


def _sala_de(cliente: ClienteHub) -> dict[str, Any]:
    return cliente.snapshot()["sala"] or {}


def test_lista_de_salas_mostra_cadeado_e_oculta_automaticas(
    hub: Any,
    criar_cliente: Any,
) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")
    carol = criar_cliente("Carol")
    dave = criar_cliente("Dave")

    alice.criar_sala("Aberta", True, "")
    bob.criar_sala("Trancada", True, "segredo")
    _aguardar(lambda: len(carol.snapshot()["salas"]) == 2)
    por_nome = {sala["nome"]: sala for sala in carol.snapshot()["salas"]}
    assert por_nome["Aberta"]["com_senha"] is False
    assert por_nome["Trancada"]["com_senha"] is True
    assert por_nome["Aberta"]["maximo"] == 2

    # Sala automática (criada pelo aceite) não aparece na lista.
    carol_id = carol.snapshot()["peer_id"]
    dave.solicitar(carol_id)
    pedido = _aguardar(lambda: carol.snapshot()["solicitacao"])
    carol.responder(pedido["request_id"], True)
    _aguardar(lambda: carol.snapshot()["estado"] == "conectado")
    assert {s["nome"] for s in carol.snapshot()["salas"]} == {
        "Aberta",
        "Trancada",
    }


def test_dono_sai_e_a_sala_some(hub: Any, criar_cliente: Any) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")
    alice.criar_sala("Dupla", True, "")
    codigo = _aguardar(lambda: _sala_de(alice).get("codigo") not in (None, SALA_PUBLICA) and _sala_de(alice)["codigo"])
    bob.entrar_sala(codigo)
    _aguardar(lambda: _sala_de(bob).get("codigo") == codigo)

    alice.sair_sala()
    _aguardar(lambda: _sala_de(bob).get("codigo") == SALA_PUBLICA)
    _aguardar(lambda: _sala_de(alice).get("codigo") == SALA_PUBLICA)
    _aguardar(lambda: bob.snapshot()["salas"] == [])


def test_outro_lado_sai_e_a_sala_continua_aguardando(
    hub: Any,
    criar_cliente: Any,
) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")
    carol = criar_cliente("Carol")
    alice.criar_sala("Dupla", True, "")
    codigo = _aguardar(lambda: _sala_de(alice).get("codigo") not in (None, SALA_PUBLICA) and _sala_de(alice)["codigo"])
    bob.entrar_sala(codigo)
    _aguardar(lambda: _sala_de(alice).get("lotacao") == 2)

    bob.sair_sala()
    _aguardar(lambda: _sala_de(alice).get("lotacao") == 1)
    assert _sala_de(alice)["codigo"] == codigo

    carol.entrar_sala(codigo)
    _aguardar(lambda: _sala_de(carol).get("codigo") == codigo)
    assert _sala_de(alice)["lotacao"] == 2


def test_sala_fecha_apos_inatividade_com_aviso() -> None:
    servidor = ServidorHub(
        host="127.0.0.1", porta=0, inatividade=1.0, aviso=0.6
    )
    porta = servidor.iniciar()
    alice = ClienteHub()
    try:
        alice.conectar("127.0.0.1", porta, "Alice")
        alice.criar_sala("Quieta", True, "")
        _aguardar(lambda: _sala_de(alice).get("codigo") != SALA_PUBLICA)
        _aguardar(lambda: _sala_de(alice).get("fecha_em") is not None)
        _aguardar(lambda: _sala_de(alice).get("codigo") == SALA_PUBLICA)
        assert alice.snapshot()["salas"] == []
    finally:
        alice.fechar()
        servidor.parar()


def test_atividade_no_chat_reinicia_o_contador() -> None:
    servidor = ServidorHub(
        host="127.0.0.1", porta=0, inatividade=1.0, aviso=0.5
    )
    porta = servidor.iniciar()
    alice = ClienteHub()
    try:
        alice.conectar("127.0.0.1", porta, "Alice")
        alice.criar_sala("Ativa", True, "")
        codigo = _aguardar(
            lambda: _sala_de(alice).get("codigo") not in (None, SALA_PUBLICA)
            and _sala_de(alice)["codigo"]
        )
        limite = time.monotonic() + 2.0
        while time.monotonic() < limite:
            alice.chat("ainda aqui")
            time.sleep(0.2)
            assert _sala_de(alice).get("codigo") == codigo
    finally:
        alice.fechar()
        servidor.parar()


CONVITE = {
    "programa": "calculadora",
    "arquivo": "t01_multiterminal/t01_calculadora_cliente.mp",
    "par_arquivo": "t01_multiterminal/t01_calculadora_servidor.mp",
    "papel_iniciador": "computador_1",
    "papel_convidado": "computador_2",
}


def test_convite_para_a_sala_publica_o_primeiro_a_aceitar_fecha_o_par(
    hub: Any,
    criar_cliente: Any,
) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")
    carol = criar_cliente("Carol")

    alice.convidar_execucao(CONVITE)
    convite_bob = _aguardar(lambda: bob.snapshot()["convites"])[0]
    _aguardar(lambda: carol.snapshot()["convites"])
    _aguardar(lambda: alice.snapshot()["convite_enviado"])

    bob.responder_convite(convite_bob["convite_id"], True)
    _aguardar(lambda: alice.snapshot()["execucao_multi"])
    _aguardar(lambda: bob.snapshot()["execucao_multi"])

    assert alice.snapshot()["estado"] == "conectado"
    assert bob.snapshot()["estado"] == "conectado"
    sala = alice.snapshot()["sala"]
    assert sala["automatica"] and sala["dono_id"] == alice.snapshot()["peer_id"]
    multi_alice = alice.snapshot()["execucao_multi"]
    multi_bob = bob.snapshot()["execucao_multi"]
    assert multi_alice["papel"] == "computador_1"
    assert multi_alice["arquivo"].endswith("cliente.mp")
    assert multi_bob["papel"] == "computador_2"
    assert multi_bob["arquivo"].endswith("servidor.mp")
    # Carol perde o convite que já foi aceito por outra pessoa.
    _aguardar(lambda: carol.snapshot()["convites"] == [])
    assert carol.snapshot()["estado"] == "registrado"


def test_convite_recusado_mantem_o_convite_para_os_demais(
    hub: Any,
    criar_cliente: Any,
) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")
    carol = criar_cliente("Carol")

    alice.convidar_execucao(CONVITE)
    convite = _aguardar(lambda: bob.snapshot()["convites"])[0]
    _aguardar(lambda: carol.snapshot()["convites"])

    bob.responder_convite(convite["convite_id"], False)
    _aguardar(
        lambda: (alice.snapshot()["convite_resultado"] or {}).get("resultado")
        == "recusado"
    )
    assert bob.snapshot()["convites"] == []
    assert len(carol.snapshot()["convites"]) == 1
    assert alice.snapshot()["convite_enviado"]

    carol.responder_convite(carol.snapshot()["convites"][0]["convite_id"], False)
    _aguardar(
        lambda: (alice.snapshot()["convite_resultado"] or {}).get("resultado")
        == "todos_recusaram"
    )
    assert alice.snapshot()["convite_enviado"] is None


def test_convite_cancelado_some_para_os_convidados(
    hub: Any,
    criar_cliente: Any,
) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")

    alice.convidar_execucao(CONVITE)
    _aguardar(lambda: bob.snapshot()["convites"])
    alice.cancelar_convite()
    _aguardar(lambda: bob.snapshot()["convites"] == [])
    assert alice.snapshot()["convite_enviado"] is None


def test_convite_vai_so_ao_parceiro_quando_ja_conectados(
    hub: Any,
    criar_cliente: Any,
) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")
    carol = criar_cliente("Carol")
    _parear(alice, bob)

    alice.convidar_execucao(CONVITE)
    convite = _aguardar(lambda: bob.snapshot()["convites"])[0]
    time.sleep(0.2)
    assert carol.snapshot()["convites"] == []

    bob.responder_convite(convite["convite_id"], True)
    _aguardar(lambda: bob.snapshot()["execucao_multi"])
    _aguardar(lambda: alice.snapshot()["execucao_multi"])
    assert alice.snapshot()["estado"] == "conectado"


def test_convite_exige_alguem_disponivel_na_sala(
    hub: Any,
    criar_cliente: Any,
) -> None:
    alice = criar_cliente("Alice")

    alice.convidar_execucao(CONVITE)
    _aguardar(lambda: "ninguém" in str(alice.snapshot()["ultimo_erro"]).lower())
    assert alice.snapshot()["convite_enviado"] is None


def test_convite_some_quando_o_iniciador_sai(
    hub: Any,
    criar_cliente: Any,
) -> None:
    alice = criar_cliente("Alice")
    bob = criar_cliente("Bob")

    alice.convidar_execucao(CONVITE)
    _aguardar(lambda: bob.snapshot()["convites"])
    alice.fechar()
    _aguardar(lambda: bob.snapshot()["convites"] == [])
