"""Rotas web do hub de conexão MiniPar.

Cada aba do navegador usa um ``client_id`` próprio (guardado em
``sessionStorage`` no frontend), então duas abas podem participar como duas
sessões independentes. O estado de cada cliente fica em memória no processo
Flask.
"""
from __future__ import annotations

import atexit
import threading
import uuid
from typing import Any

from flask import Blueprint, jsonify, render_template, request

from ..conexao.cliente import ClienteHub
from ..conexao.hub import ServidorHub

conexao_bp = Blueprint("conexao", __name__)

_clientes: dict[str, ClienteHub] = {}
_clientes_lock = threading.Lock()
_hub: ServidorHub | None = None
_hub_lock = threading.Lock()


def _dados() -> dict[str, Any]:
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else {}


def _client_id(dados: dict[str, Any], *, obrigatorio: bool = True) -> str | None:
    valor = dados.get("client_id")
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    if obrigatorio:
        raise ValueError("Informe client_id.")
    return None


def _obter_cliente(client_id: str) -> ClienteHub:
    with _clientes_lock:
        cliente = _clientes.get(client_id)
    if cliente is None:
        raise ValueError("Sessão de conexão não encontrada.")
    return cliente


def _snapshot(cliente: ClienteHub, client_id: str) -> Any:
    dados = cliente.snapshot()
    dados.update({
        "success": True,
        "client_id": client_id,
        "eventos": cliente.drenar_eventos(),
    })
    return jsonify(dados)


def _erro(mensagem: str, status: int = 400) -> Any:
    return jsonify({"success": False, "error": mensagem}), status


def _executar(client_id: str | None, acao: Any) -> Any:
    try:
        if client_id is None:
            raise ValueError("Informe client_id.")
        cliente = _obter_cliente(client_id)
        acao(cliente)
    except ValueError as erro:
        return _erro(str(erro), 400)
    except (OSError, ConnectionError, TimeoutError) as erro:
        return _erro(str(erro), 502)
    return _snapshot(cliente, client_id)


@conexao_bp.route("/conexao")
def conexao_page() -> Any:
    programa = request.args.get("program", "")
    return render_template(
        "conexao.html",
        active_page="conexao",
        program=programa,
    )


# ------------------------------------------------------------------ hub local
@conexao_bp.route("/api/conexao/hub", methods=["GET"])
def hub_status() -> Any:
    with _hub_lock:
        if _hub is None:
            return jsonify({"success": True, "ativo": False})
        return jsonify({
            "success": True,
            "ativo": True,
            "porta": _hub.porta,
            "host": _hub.host,
        })


@conexao_bp.route("/api/conexao/hub/iniciar", methods=["POST"])
def hub_iniciar() -> Any:
    global _hub
    dados = _dados()
    porta_bruta = dados.get("porta", 5010)
    try:
        porta = int(porta_bruta)
    except (TypeError, ValueError):
        return _erro("Porta inválida.")
    if not 0 <= porta <= 65535:
        return _erro("Porta fora do intervalo.")
    with _hub_lock:
        if _hub is not None:
            return jsonify({
                "success": True,
                "ativo": True,
                "porta": _hub.porta,
                "host": _hub.host,
            })
        hub = ServidorHub(host="0.0.0.0", porta=porta)
        try:
            porta_efetiva = hub.iniciar()
        except OSError as erro:
            return _erro(f"Não foi possível iniciar o hub: {erro}", 409)
        _hub = hub
        return jsonify({
            "success": True,
            "ativo": True,
            "porta": porta_efetiva,
            "host": hub.host,
        })


@conexao_bp.route("/api/conexao/hub/parar", methods=["POST"])
def hub_parar() -> Any:
    global _hub
    with _hub_lock:
        hub = _hub
        _hub = None
    if hub is not None:
        hub.parar()
    return jsonify({"success": True, "ativo": False})


# ------------------------------------------------------------------- cliente
@conexao_bp.route("/api/conexao/conectar", methods=["POST"])
def conectar() -> Any:
    dados = _dados()
    client_id = _client_id(dados, obrigatorio=False) or uuid.uuid4().hex
    host = dados.get("host") or "127.0.0.1"
    porta_bruta = dados.get("porta", 5010)
    nome = dados.get("nome")
    if not isinstance(host, str):
        return _erro("Endereço do hub inválido.")
    try:
        porta = int(porta_bruta)
    except (TypeError, ValueError):
        return _erro("Porta do hub inválida.")
    if not 1 <= porta <= 65535:
        return _erro("Porta do hub fora do intervalo.")
    if not isinstance(nome, str):
        return _erro("Informe o nome do participante.")

    with _clientes_lock:
        antigo = _clientes.pop(client_id, None)
    if antigo is not None:
        antigo.fechar()

    cliente = ClienteHub()
    try:
        cliente.conectar(host, porta, nome)
    except (OSError, ValueError, ConnectionError, TimeoutError) as erro:
        cliente.fechar()
        return _erro(f"Não foi possível conectar: {erro}", 502)
    with _clientes_lock:
        _clientes[client_id] = cliente
    return _snapshot(cliente, client_id)


@conexao_bp.route("/api/conexao/estado", methods=["GET"])
def estado() -> Any:
    client_id = request.args.get("client_id", "")
    if not isinstance(client_id, str) or not client_id.strip():
        return jsonify({
            "success": True,
            "estado": "desconectado",
            "peers": [],
            "chat": [],
            "eventos": [],
        })
    with _clientes_lock:
        cliente = _clientes.get(client_id.strip())
    if cliente is None:
        return jsonify({
            "success": True,
            "client_id": client_id,
            "estado": "desconectado",
            "peers": [],
            "chat": [],
            "eventos": [],
        })
    return _snapshot(cliente, client_id.strip())


@conexao_bp.route("/api/conexao/sala/criar", methods=["POST"])
def sala_criar() -> Any:
    dados = _dados()
    try:
        client_id = _client_id(dados)
    except ValueError as erro:
        return _erro(str(erro))
    nome = dados.get("nome") or "Sala privada"
    senha = dados.get("senha") or ""
    if not isinstance(nome, str) or not isinstance(senha, str):
        return _erro("Dados da sala inválidos.")
    return _executar(client_id, lambda cliente: cliente.criar_sala(nome, True, senha))


@conexao_bp.route("/api/conexao/sala/entrar", methods=["POST"])
def sala_entrar() -> Any:
    dados = _dados()
    try:
        client_id = _client_id(dados)
    except ValueError as erro:
        return _erro(str(erro))
    codigo = dados.get("codigo") or dados.get("sala") or ""
    senha = dados.get("senha") or ""
    if not isinstance(codigo, str) or not codigo.strip():
        return _erro("Informe o código da sala.")
    if not isinstance(senha, str):
        return _erro("Senha inválida.")
    return _executar(client_id, lambda cliente: cliente.entrar_sala(codigo, senha))


@conexao_bp.route("/api/conexao/sala/sair", methods=["POST"])
def sala_sair() -> Any:
    dados = _dados()
    try:
        client_id = _client_id(dados)
    except ValueError as erro:
        return _erro(str(erro))
    return _executar(client_id, lambda cliente: cliente.sair_sala())


@conexao_bp.route("/api/conexao/solicitar", methods=["POST"])
def solicitar() -> Any:
    dados = _dados()
    try:
        client_id = _client_id(dados)
    except ValueError as erro:
        return _erro(str(erro))
    peer_id = dados.get("peer_id")
    if not isinstance(peer_id, str) or not peer_id:
        return _erro("Informe o participante de destino.")
    return _executar(client_id, lambda cliente: cliente.solicitar(peer_id))


@conexao_bp.route("/api/conexao/responder", methods=["POST"])
def responder() -> Any:
    dados = _dados()
    try:
        client_id = _client_id(dados)
    except ValueError as erro:
        return _erro(str(erro))
    request_id = dados.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        return _erro("Solicitação inválida.")
    aceitar = bool(dados.get("aceitar"))
    return _executar(
        client_id,
        lambda cliente: cliente.responder(request_id, aceitar),
    )


@conexao_bp.route("/api/conexao/chat", methods=["POST"])
def chat() -> Any:
    dados = _dados()
    try:
        client_id = _client_id(dados)
    except ValueError as erro:
        return _erro(str(erro))
    texto = dados.get("texto")
    if not isinstance(texto, str):
        return _erro("Mensagem inválida.")
    return _executar(client_id, lambda cliente: cliente.chat(texto))


@conexao_bp.route("/api/conexao/desconectar", methods=["POST"])
def desconectar() -> Any:
    dados = _dados()
    try:
        client_id = _client_id(dados)
    except ValueError as erro:
        return _erro(str(erro))
    return _executar(client_id, lambda cliente: cliente.desconectar())


@conexao_bp.route("/api/conexao/desligar", methods=["POST"])
def desligar() -> Any:
    dados = _dados()
    client_id = _client_id(dados, obrigatorio=False)
    if client_id:
        with _clientes_lock:
            cliente = _clientes.pop(client_id, None)
        if cliente is not None:
            cliente.fechar()
    return jsonify({"success": True})


def encerrar_tudo() -> None:
    """Fecha clientes e hub embutido (usado no encerramento do processo)."""
    global _hub
    with _clientes_lock:
        clientes = list(_clientes.values())
        _clientes.clear()
    for cliente in clientes:
        cliente.fechar()
    with _hub_lock:
        hub = _hub
        _hub = None
    if hub is not None:
        hub.parar()


atexit.register(encerrar_tudo)
