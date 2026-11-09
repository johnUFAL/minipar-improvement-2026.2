"""Protocolo de mensagens do hub de conexão MiniPar.

As mensagens trafegam como uma linha JSON em UTF-8. O campo ``type`` é
obrigatório e define a ação. O protocolo é pequeno de propósito: controla o
registro de participantes, as salas privadas, o pedido/aceite de conexão e o
chat que existe apenas enquanto dois participantes estão conectados.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

MAX_FRAME_BYTES = 64 * 1024
MAX_NOME = 48
MAX_TEXTO_CHAT = 4000
MAX_MEMBROS_SALA = 2
MAX_PROGRAMA = 160
MAX_PAPEL = 48
MAX_HOST = 255
MAX_CANAIS_EXECUCAO = 8
SALA_PUBLICA = "publica"


class ProtocoloErro(Exception):
    """Mensagem inválida, grande demais ou fora do protocolo."""


def codificar(mensagem: dict[str, Any]) -> bytes:
    """Serializa uma mensagem em uma linha JSON terminada em ``\\n``."""
    if not isinstance(mensagem, dict) or not isinstance(mensagem.get("type"), str):
        raise ProtocoloErro("Mensagem sem campo 'type'.")
    try:
        dados = json.dumps(
            mensagem,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as erro:
        raise ProtocoloErro(f"Mensagem não serializável: {erro}") from erro
    if len(dados) > MAX_FRAME_BYTES:
        raise ProtocoloErro("Mensagem excede o limite permitido.")
    return dados + b"\n"


def decodificar(linha: bytes) -> dict[str, Any]:
    """Converte uma linha JSON em mensagem, validando o formato mínimo."""
    if not linha:
        raise ProtocoloErro("Conexão encerrada.")
    if len(linha) > MAX_FRAME_BYTES + 1:
        raise ProtocoloErro("Mensagem excede o limite permitido.")
    try:
        mensagem = json.loads(linha.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ProtocoloErro("Mensagem não é JSON válido.") from erro
    if not isinstance(mensagem, dict) or not isinstance(mensagem.get("type"), str):
        raise ProtocoloErro("Mensagem sem campo 'type'.")
    return mensagem


def normalizar_nome(valor: object) -> str:
    """Valida e normaliza o nome de exibição de um participante ou sala."""
    if not isinstance(valor, str):
        raise ProtocoloErro("Nome inválido.")
    nome = valor.strip()
    if not nome or len(nome) > MAX_NOME:
        raise ProtocoloErro(
            f"O nome deve ter entre 1 e {MAX_NOME} caracteres."
        )
    return nome


def normalizar_texto_chat(valor: object) -> str:
    """Valida o texto de uma mensagem de chat."""
    if not isinstance(valor, str):
        raise ProtocoloErro("Texto de chat inválido.")
    texto = valor.strip()
    if not texto:
        raise ProtocoloErro("A mensagem de chat está vazia.")
    if len(texto) > MAX_TEXTO_CHAT:
        raise ProtocoloErro(
            f"A mensagem excede {MAX_TEXTO_CHAT} caracteres."
        )
    return texto


def _texto_limitado(valor: object, campo: str, limite: int) -> str:
    if not isinstance(valor, str):
        raise ProtocoloErro(f"{campo} inválido.")
    texto = valor.strip()
    if not texto or len(texto) > limite:
        raise ProtocoloErro(
            f"{campo} deve ter entre 1 e {limite} caracteres."
        )
    return texto


def normalizar_contexto_execucao(valor: object) -> dict[str, Any]:
    """Valida o contexto trocado entre dois lados antes da execução."""
    if not isinstance(valor, dict):
        raise ProtocoloErro("Contexto de execução inválido.")
    programa = _texto_limitado(
        valor.get("programa"), "Programa", MAX_PROGRAMA
    )
    papel = _texto_limitado(valor.get("papel"), "Papel", MAX_PAPEL)
    modo = valor.get("modo")
    if modo not in (None, "", "conecta", "escuta"):
        raise ProtocoloErro("Modo de execução inválido.")
    host = valor.get("host") or ""
    if not isinstance(host, str) or len(host) > MAX_HOST:
        raise ProtocoloErro("Host de execução inválido.")
    porta = valor.get("porta")
    if porta is not None:
        if isinstance(porta, bool) or not isinstance(porta, int):
            raise ProtocoloErro("Porta de execução inválida.")
        if porta < 1 or porta > 65535:
            raise ProtocoloErro("A porta deve estar entre 1 e 65535.")
    canais = valor.get("canais")
    if not isinstance(canais, list) or not canais:
        raise ProtocoloErro("Informe ao menos um canal de execução.")
    if len(canais) > MAX_CANAIS_EXECUCAO:
        raise ProtocoloErro("Quantidade de canais acima do limite.")
    canais_normalizados: list[dict[str, str]] = []
    for canal in canais:
        if not isinstance(canal, dict):
            raise ProtocoloErro("Canal de execução inválido.")
        canais_normalizados.append({
            "nome": _texto_limitado(canal.get("nome"), "Nome do canal", MAX_PAPEL),
            "conecta": _texto_limitado(
                canal.get("conecta"), "Papel que conecta", MAX_PAPEL
            ),
            "escuta": _texto_limitado(
                canal.get("escuta"), "Papel que escuta", MAX_PAPEL
            ),
        })
    return {
        "programa": programa,
        "papel": papel,
        "modo": modo or "",
        "host": host.strip(),
        "porta": porta,
        "canais": canais_normalizados,
    }


@dataclass
class Peer:
    """Participante registrado no hub."""

    peer_id: str
    nome: str
    estado: str = "disponivel"
    sala: str = SALA_PUBLICA

    def para_dict(self) -> dict[str, str]:
        return {"id": self.peer_id, "nome": self.nome, "estado": self.estado}


@dataclass
class Sala:
    """Sala de conexão. A sala pública não tem limite; as privadas têm 2 vagas."""

    codigo: str
    nome: str
    privada: bool = False
    senha: str = ""
    membros: set[str] = field(default_factory=set)

    @property
    def maximo(self) -> int | None:
        return None if self.codigo == SALA_PUBLICA else MAX_MEMBROS_SALA

    def lotada(self) -> bool:
        limite = self.maximo
        return limite is not None and len(self.membros) >= limite

    def para_dict(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "nome": self.nome,
            "privada": self.privada,
            "lotacao": len(self.membros),
            "maximo": self.maximo,
        }
