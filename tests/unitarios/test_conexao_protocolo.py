import json

import pytest

from interfaces.conexao.protocolo import (
    MAX_FRAME_BYTES,
    MAX_MEMBROS_SALA,
    MAX_NOME,
    MAX_TEXTO_CHAT,
    SALA_PUBLICA,
    ProtocoloErro,
    Sala,
    codificar,
    decodificar,
    normalizar_nome,
    normalizar_texto_chat,
)


def test_codificar_e_decodificar_mensagem_com_acentos():
    mensagem = {"type": "chat", "texto": "olá, conexão"}

    linha = codificar(mensagem)

    assert linha.endswith(b"\n")
    assert decodificar(linha) == mensagem


def test_codificar_recusa_mensagem_sem_type():
    with pytest.raises(ProtocoloErro):
        codificar({"texto": "sem tipo"})


def test_codificar_recusa_mensagem_grande_demais():
    with pytest.raises(ProtocoloErro):
        codificar({"type": "chat", "texto": "x" * MAX_FRAME_BYTES})


def test_decodificar_recusa_linha_vazia_ou_invalida():
    with pytest.raises(ProtocoloErro):
        decodificar(b"")
    with pytest.raises(ProtocoloErro):
        decodificar(b"{nao-e-json}\n")


def test_decodificar_recusa_json_sem_type():
    with pytest.raises(ProtocoloErro):
        decodificar(json.dumps({"texto": "oi"}).encode("utf-8"))


def test_normalizar_nome_remove_espacos_e_valida_limites():
    assert normalizar_nome("  Daniel  ") == "Daniel"
    assert normalizar_nome("x" * MAX_NOME) == "x" * MAX_NOME

    with pytest.raises(ProtocoloErro):
        normalizar_nome("   ")
    with pytest.raises(ProtocoloErro):
        normalizar_nome("x" * (MAX_NOME + 1))
    with pytest.raises(ProtocoloErro):
        normalizar_nome(123)  # type: ignore[arg-type]


def test_normalizar_texto_chat_remove_espacos_e_valida_limites():
    assert normalizar_texto_chat("  ola  ") == "ola"
    assert normalizar_texto_chat("x" * MAX_TEXTO_CHAT) == "x" * MAX_TEXTO_CHAT

    with pytest.raises(ProtocoloErro):
        normalizar_texto_chat("   ")
    with pytest.raises(ProtocoloErro):
        normalizar_texto_chat("x" * (MAX_TEXTO_CHAT + 1))
    with pytest.raises(ProtocoloErro):
        normalizar_texto_chat(None)  # type: ignore[arg-type]


def test_sala_publica_nao_tem_limite_e_privada_aceita_dois():
    publica = Sala(SALA_PUBLICA, "Sala pública")
    assert publica.maximo is None
    publica.membros.update({"a", "b", "c"})
    assert not publica.lotada()

    privada = Sala("A1B2C", "Privada", privada=True)
    assert privada.maximo == MAX_MEMBROS_SALA
    privada.membros.add("a")
    assert not privada.lotada()
    privada.membros.add("b")
    assert privada.lotada()


def test_sala_para_dict_expoe_lotacao_e_limite():
    sala = Sala("A1B2C", "Privada", privada=True)
    sala.membros.update({"a", "b"})

    dados = sala.para_dict()

    assert dados == {
        "codigo": "A1B2C",
        "nome": "Privada",
        "privada": True,
        "com_senha": False,
        "automatica": False,
        "dono": "",
        "dono_id": "",
        "lotacao": 2,
        "maximo": 2,
    }
