"""Rotas web do hub de conexão MiniPar.

Cada aba do navegador usa um ``client_id`` próprio (guardado em
``sessionStorage`` no frontend), então duas abas podem participar como duas
sessões independentes. O estado de cada cliente fica em memória no processo
Flask.
"""
from __future__ import annotations

import atexit
import socket
import threading
import uuid
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, render_template, request

from ..conexao.cliente import ClienteHub
from ..conexao.execucao import ExecucaoErro, free_port
from ..conexao.hub import ServidorHub
from ..program_analyzer import get_program_spec
from ..test_orchestrator import resolve_test_file
from .conexao_execucao import ExecutorConexao

conexao_bp = Blueprint("conexao", __name__)

_clientes: dict[str, ClienteHub] = {}
_clientes_lock = threading.Lock()
_hub: ServidorHub | None = None
_hub_lock = threading.Lock()
_executor = ExecutorConexao()
MAX_EXECUCAO_SOURCE = 1_000_000


def _ip_local() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


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
        "execucao_local": _executor.estado(client_id),
        "eventos": cliente.drenar_eventos(),
    })
    return jsonify(dados)


def _fonte_programa(dados: dict[str, Any]) -> tuple[str, str]:
    code = dados.get("code")
    if isinstance(code, str) and code.strip():
        if len(code) > MAX_EXECUCAO_SOURCE:
            raise ValueError("O código excede o limite permitido.")
        filename = dados.get("filename")
        if not isinstance(filename, str) or not filename.strip():
            filename = "programa.mp"
        return code, filename
    filename = dados.get("filename")
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("Informe o código ou o nome do programa.")
    path = resolve_test_file(filename)
    source = Path(path).read_text(encoding="utf-8")
    return source, filename


def _canal_execucao(
    dados: dict[str, Any],
    source_path: str,
) -> dict[str, str]:
    canal = dados.get("canal")
    if isinstance(canal, dict):
        nome = canal.get("nome")
        conecta = canal.get("conecta")
        escuta = canal.get("escuta")
        if (
            isinstance(nome, str)
            and isinstance(conecta, str)
            and isinstance(escuta, str)
            and nome.strip()
            and conecta.strip()
            and escuta.strip()
        ):
            return {
                "nome": nome.strip(),
                "conecta": conecta.strip(),
                "escuta": escuta.strip(),
            }
    spec = get_program_spec(source_path)
    multi = spec.get("multi_computer") or {}
    canais = multi.get("channels") or []
    if len(canais) == 1 and isinstance(canais[0], dict):
        candidato = canais[0]
        return {
            "nome": str(candidato.get("nome") or "dados"),
            "conecta": str(candidato.get("conecta") or ""),
            "escuta": str(candidato.get("escuta") or ""),
        }
    raise ValueError("Informe um canal declarativo válido.")


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
@conexao_bp.route("/api/conexao/rede", methods=["GET"])
def rede() -> Any:
    return jsonify({
        "success": True,
        "ip_local": _ip_local(),
        "porta_livre": free_port(),
    })


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
    _executor.encerrar(client_id)
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


@conexao_bp.route("/api/conexao/execucao/preparar", methods=["POST"])
def execucao_preparar() -> Any:
    dados = _dados()
    try:
        client_id = _client_id(dados)
        if client_id is None:
            return _erro("Informe client_id.")
        cliente = _obter_cliente(client_id)
        source, filename = _fonte_programa(dados)
        try:
            source_path = resolve_test_file(filename)
        except ValueError:
            source_path = filename
        canal = _canal_execucao(dados, source_path)
        papel = dados.get("papel")
        if not isinstance(papel, str) or not papel.strip():
            raise ValueError("Escolha o papel deste lado.")
        host = dados.get("host") or "127.0.0.1"
        if not isinstance(host, str):
            raise ValueError("Host de execução inválido.")
        porta = dados.get("porta")
        if porta in (None, ""):
            porta = 0
        else:
            porta = int(porta)
            if not 1 <= porta <= 65535:
                raise ValueError("Porta de execução inválida.")
        entradas = dados.get("entradas") or ""
        if not isinstance(entradas, str):
            raise ValueError("Entradas inválidas.")
        timeout = float(dados.get("timeout") or 60.0)
        estado = _executor.preparar(
            client_id,
            source=source,
            filename=filename,
            canal=canal,
            papel=papel.strip(),
            host=host,
            porta=porta or None,
            entradas=entradas,
            timeout=max(1.0, min(timeout, 3600.0)),
            cliente=cliente,
        )
    except ValueError as erro:
        return _erro(str(erro), 400)
    except ExecucaoErro as erro:
        return _erro(str(erro), 400)
    except (OSError, ConnectionError, TimeoutError) as erro:
        return _erro(str(erro), 502)
    if estado.get("status") == "erro":
        resposta = _snapshot(cliente, client_id)
        return resposta
    return _snapshot(cliente, client_id)


@conexao_bp.route("/api/conexao/execucao/iniciar", methods=["POST"])
def execucao_iniciar() -> Any:
    dados = _dados()
    try:
        client_id = _client_id(dados)
        if client_id is None:
            return _erro("Informe client_id.")
        cliente = _obter_cliente(client_id)
        host = dados.get("host")
        porta = dados.get("porta")
        if porta in (None, ""):
            porta_listener = None
        else:
            porta_listener = int(porta)
            if not 1 <= porta_listener <= 65535:
                raise ValueError("Porta de execução inválida.")
        _executor.iniciar(
            client_id,
            cliente=cliente,
            host_listener=str(host).strip() if isinstance(host, str) else None,
            porta_listener=porta_listener,
        )
    except ValueError as erro:
        return _erro(str(erro), 400)
    except ExecucaoErro as erro:
        return _erro(str(erro), 409)
    except (OSError, ConnectionError, TimeoutError) as erro:
        return _erro(str(erro), 502)
    return _snapshot(cliente, client_id)


@conexao_bp.route("/api/conexao/execucao/parar", methods=["POST"])
def execucao_parar() -> Any:
    dados = _dados()
    try:
        client_id = _client_id(dados)
        if client_id is None:
            return _erro("Informe client_id.")
        cliente = _obter_cliente(client_id)
        motivo = dados.get("motivo") or "Execução encerrada pelo usuário."
        if not isinstance(motivo, str):
            raise ValueError("Motivo inválido.")
        notificar = bool(dados.get("notificar", True))
        _executor.parar(
            client_id,
            cliente=cliente,
            motivo=motivo,
            notificar=notificar,
        )
    except ValueError as erro:
        return _erro(str(erro), 400)
    except (OSError, ConnectionError, TimeoutError) as erro:
        return _erro(str(erro), 502)
    return _snapshot(cliente, client_id)


@conexao_bp.route("/api/conexao/desconectar", methods=["POST"])
def desconectar() -> Any:
    dados = _dados()
    try:
        client_id = _client_id(dados)
    except ValueError as erro:
        return _erro(str(erro))
    if client_id is None:
        return _erro("Informe client_id.")

    def acao(cliente: ClienteHub) -> None:
        _executor.parar(
            client_id,
            cliente=cliente,
            motivo="Conexão encerrada.",
            notificar=False,
        )
        cliente.desconectar()
        _executor.encerrar(client_id)

    return _executar(client_id, acao)


@conexao_bp.route("/api/conexao/desligar", methods=["POST"])
def desligar() -> Any:
    dados = _dados()
    client_id = _client_id(dados, obrigatorio=False)
    if client_id:
        with _clientes_lock:
            cliente = _clientes.pop(client_id, None)
        if cliente is not None:
            _executor.parar(
                client_id,
                cliente=cliente,
                motivo="Sessão encerrada.",
                notificar=True,
            )
            _executor.encerrar(client_id)
            cliente.fechar()
    return jsonify({"success": True})


def encerrar_tudo() -> None:
    """Fecha clientes e hub embutido (usado no encerramento do processo)."""
    global _hub
    _executor.encerrar_tudo()
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
