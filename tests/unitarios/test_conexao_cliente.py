from interfaces.conexao.cliente import ClienteHub


def test_manter_vivo_envia_um_ping_por_intervalo(monkeypatch) -> None:
    cliente = ClienteHub()
    cliente._sock = object()
    cliente.estado = "registrado"
    enviados: list[dict[str, object]] = []

    monkeypatch.setattr(cliente, "_enviar", enviados.append)

    cliente.manter_vivo()
    cliente.manter_vivo()

    assert enviados == [{"type": "ping"}]


def test_pong_nao_polui_a_fila_de_eventos() -> None:
    cliente = ClienteHub()

    cliente._processar({"type": "pong"})

    assert cliente.drenar_eventos() == []
