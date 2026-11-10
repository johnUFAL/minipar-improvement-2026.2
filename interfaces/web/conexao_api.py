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
from ..conexao.hub import ServidorHub, descobrir_hubs, ips_locais
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
    return ips_locais()[0]


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


def _normalizar_host_hub(valor: Any) -> str:
    if valor is None:
        return "0.0.0.0"
    if not isinstance(valor, str):
        raise ValueError("Endereço de escuta inválido.")
    host = valor.strip()
    if not host:
        return "0.0.0.0"
    if "://" in host or "/" in host or ":" in host:
        raise ValueError("Informe o endereço de escuta sem porta nem protocolo.")
    if host.lower() == "localhost":
        return "127.0.0.1"
    return host


def _enderecos_hub(host: str) -> list[str]:
    if host in ("", "0.0.0.0"):
        return ips_locais()
    return [host]


def _hub_dict(hub: ServidorHub) -> dict[str, Any]:
    return {
        "success": True,
        "ativo": True,
        "host": hub.host,
        "porta": hub.porta,
        "enderecos": _enderecos_hub(hub.host),
    }


def _probe_hub(host: str, porta: int) -> bool:
    try:
        with socket.create_connection((host, porta), timeout=0.35):
            return True
    except OSError:
        return False


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
    enderecos = ips_locais()
    with _hub_lock:
        hub = _hub
    resposta: dict[str, Any] = {
        "success": True,
        "ip_local": enderecos[0],
        "ips_locais": enderecos,
        "porta_livre": free_port(),
        "hub_ativo": hub is not None,
    }
    if hub is not None:
        resposta.update({
            "hub_host": hub.host,
            "hub_porta": hub.porta,
            "hub_enderecos": _enderecos_hub(hub.host),
        })
    return jsonify(resposta)


@conexao_bp.route("/api/conexao/hub", methods=["GET"])
def hub_status() -> Any:
    with _hub_lock:
        if _hub is None:
            return jsonify({"success": True, "ativo": False})
        return jsonify(_hub_dict(_hub))


@conexao_bp.route("/api/conexao/hub/iniciar", methods=["POST"])
def hub_iniciar() -> Any:
    global _hub
    dados = _dados()
    try:
        host = _normalizar_host_hub(dados.get("host"))
    except ValueError as erro:
        return _erro(str(erro))
    porta_bruta = dados.get("porta", 5010)
    try:
        porta = int(porta_bruta)
    except (TypeError, ValueError):
        return _erro("Porta inválida.")
    if not 0 <= porta <= 65535:
        return _erro("Porta fora do intervalo.")

    antigo: ServidorHub | None = None
    with _hub_lock:
        if _hub is not None:
            mesma_porta = porta == 0 or _hub.porta == porta
            if _hub.host == host and mesma_porta:
                return jsonify(_hub_dict(_hub))
            antigo = _hub
            _hub = None
    if antigo is not None:
        antigo.parar()

    hub = ServidorHub(host=host, porta=porta)
    try:
        hub.iniciar()
    except OSError as erro:
        return _erro(f"Não foi possível iniciar o hub: {erro}", 409)
    with _hub_lock:
        _hub = hub
    return jsonify(_hub_dict(hub))


@conexao_bp.route("/api/conexao/hub/parar", methods=["POST"])
def hub_parar() -> Any:
    global _hub
    with _hub_lock:
        hub = _hub
        _hub = None
    if hub is not None:
        hub.parar()
    return jsonify({"success": True, "ativo": False})


@conexao_bp.route("/api/conexao/hubs", methods=["POST"])
def hubs_disponiveis() -> Any:
    """Lista o hub local e testa os servidores informados pelo frontend."""
    dados = _dados()
    candidatos = dados.get("hubs")
    if candidatos is None:
        candidatos = []
    if not isinstance(candidatos, list):
        return _erro("Lista de servidores inválida.")

    resultados: list[dict[str, Any]] = []
    vistos: set[tuple[str, int]] = set()
    with _hub_lock:
        hub = _hub
    if hub is not None:
        for endereco in _enderecos_hub(hub.host):
            chave = (endereco, hub.porta)
            if chave in vistos:
                continue
            vistos.add(chave)
            resultados.append({
                "nome": "Hub local",
                "host": endereco,
                "porta": hub.porta,
                "ativo": True,
                "local": True,
            })

    if bool(dados.get("descobrir")):
        for descoberto in descobrir_hubs():
            chave = (str(descoberto.get("host")), int(descoberto.get("porta", 0)))
            if chave in vistos:
                continue
            vistos.add(chave)
            resultados.append(descoberto)

    for item in candidatos[:20]:
        if not isinstance(item, dict):
            continue
        host = item.get("host")
        porta = item.get("porta")
        if not isinstance(host, str) or not host.strip():
            continue
        if not isinstance(porta, (int, str)):
            continue
        try:
            porta_int = int(porta)
        except (TypeError, ValueError):
            continue
        if not 1 <= porta_int <= 65535:
            continue
        host = host.strip()
        if "://" in host or "/" in host or ":" in host:
            continue
        chave = (host, porta_int)
        if chave in vistos:
            continue
        vistos.add(chave)
        nome = item.get("nome")
        resultados.append({
            "nome": nome.strip() if isinstance(nome, str) and nome.strip() else host,
            "host": host,
            "porta": porta_int,
            "ativo": _probe_hub(host, porta_int),
            "local": host in ips_locais(),
        })
    return jsonify({"success": True, "hubs": resultados})


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
    cliente.manter_vivo()
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
