"""Cliente do hub de conexão MiniPar.

Mantém uma thread leitora que atualiza o estado local e publica eventos em uma
fila. As interfaces (terminal e web) usam os métodos públicos e consultam
``snapshot``/``drenar_eventos`` para desenhar a tela.
"""
from __future__ import annotations

import queue
import socket
import threading
from datetime import datetime
from typing import Any, BinaryIO

from .protocolo import (
    ProtocoloErro,
    codificar,
    decodificar,
    normalizar_nome,
    normalizar_texto_chat,
)

MAX_HISTORICO_CHAT = 200


def _agora() -> str:
    return datetime.now().strftime("%H:%M:%S")


class ClienteHub:
    """Conexão de um participante com o hub."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._enviar_lock = threading.Lock()
        self._eventos: queue.Queue[dict[str, Any]] = queue.Queue()
        self._registro = threading.Event()
        self._sock: socket.socket | None = None
        self._arquivo: BinaryIO | None = None
        self._thread: threading.Thread | None = None
        self._fechado = False
        self._host = ""
        self._porta = 0
        self.peer_id: str | None = None
        self.nome = ""
        self.estado = "desconectado"
        self.sala: dict[str, Any] | None = None
        self.peers: list[dict[str, str]] = []
        self.conectado_com: dict[str, str] | None = None
        self.solicitacao: dict[str, Any] | None = None
        self.aguardando: dict[str, Any] | None = None
        self.historico_chat: list[dict[str, Any]] = []
        self.ultimo_erro = ""

    # ---------------------------------------------------------------- conexão
    def conectar(
        self,
        host: str,
        porta: int,
        nome: str,
        timeout: float = 5.0,
    ) -> None:
        """Conecta ao hub, registra o nome e espera a confirmação."""
        if self._sock is not None:
            raise ConnectionError("Já existe uma conexão ativa com o hub.")
        nome_normalizado = normalizar_nome(nome)
        sock = socket.create_connection((host, int(porta)), timeout=timeout)
        sock.settimeout(None)
        with self._lock:
            self._sock = sock
            self._arquivo = sock.makefile("rb")
            self._host = host
            self._porta = int(porta)
            self.nome = nome_normalizado
            self._fechado = False
        self._thread = threading.Thread(
            target=self._ler,
            name="minipar-cliente-hub",
            daemon=True,
        )
        self._thread.start()
        self._enviar({"type": "registrar", "nome": nome_normalizado})
        if not self._registro.wait(timeout):
            self.fechar()
            raise TimeoutError("O hub não confirmou o registro.")
        if self.peer_id is None:
            erro = self.ultimo_erro or "O hub recusou o registro."
            self.fechar()
            raise ConnectionError(erro)

    def fechar(self) -> None:
        """Encerra a conexão local sem depender do hub."""
        with self._lock:
            self._fechado = True
            arquivo, sock = self._arquivo, self._sock
            self._arquivo = None
            self._sock = None
            self.estado = "desconectado"
            self.conectado_com = None
            self.solicitacao = None
            self.aguardando = None
        self._registro.set()
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        if arquivo is not None:
            try:
                arquivo.close()
            except OSError:
                pass
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    # ---------------------------------------------------------------- leitura
    def _ler(self) -> None:
        arquivo = self._arquivo
        if arquivo is None:
            return
        try:
            while not self._fechado:
                linha = arquivo.readline()
                if not linha:
                    break
                try:
                    mensagem = decodificar(linha)
                except ProtocoloErro as erro:
                    with self._lock:
                        self.ultimo_erro = str(erro)
                    break
                self._processar(mensagem)
        except OSError:
            pass
        finally:
            with self._lock:
                if not self._fechado and self.estado != "desconectado":
                    self.estado = "desconectado"
                    self.conectado_com = None
            self._registro.set()

    def _processar(self, mensagem: dict[str, Any]) -> None:
        tipo = mensagem.get("type")
        with self._lock:
            if tipo == "registrado":
                self.peer_id = str(mensagem.get("peer_id") or "")
                self.nome = str(mensagem.get("nome") or self.nome)
                self.sala = mensagem.get("sala") if isinstance(
                    mensagem.get("sala"), dict
                ) else self.sala
                self.peers = self._peers(mensagem)
                self.estado = "registrado"
                self._registro.set()
            elif tipo == "peers":
                self.peers = self._peers(mensagem)
                if isinstance(mensagem.get("sala"), dict):
                    self.sala = mensagem["sala"]
            elif tipo in ("sala_atual", "sala_criada"):
                self.sala = mensagem.get("sala") if isinstance(
                    mensagem.get("sala"), dict
                ) else self.sala
                self.peers = self._peers(mensagem)
            elif tipo == "solicitacao":
                self.solicitacao = mensagem
            elif tipo == "aguardando":
                self.aguardando = mensagem
            elif tipo == "resposta":
                if not mensagem.get("aceitar"):
                    self.aguardando = None
                    self.solicitacao = None
            elif tipo == "conectado":
                peer = mensagem.get("peer")
                self.historico_chat = []
                self.conectado_com = peer if isinstance(peer, dict) else None
                self.estado = "conectado"
                self.solicitacao = None
                self.aguardando = None
                if isinstance(mensagem.get("sala"), dict):
                    self.sala = mensagem["sala"]
            elif tipo == "peer_desconectou":
                self.estado = "registrado"
                self.conectado_com = None
            elif tipo == "desconectado":
                self.estado = "registrado"
                self.conectado_com = None
            elif tipo == "chat":
                self._registrar_chat({
                    "de": str(mensagem.get("de") or ""),
                    "nome": str(mensagem.get("nome") or ""),
                    "texto": str(mensagem.get("texto") or ""),
                    "hora": str(mensagem.get("hora") or _agora()),
                    "proprio": False,
                })
            elif tipo == "erro":
                self.ultimo_erro = str(mensagem.get("mensagem") or "Erro no hub.")
        self._eventos.put(mensagem)

    @staticmethod
    def _peers(mensagem: dict[str, Any]) -> list[dict[str, str]]:
        peers = mensagem.get("peers")
        if not isinstance(peers, list):
            return []
        return [peer for peer in peers if isinstance(peer, dict)]

    def _registrar_chat(self, entrada: dict[str, Any]) -> None:
        self.historico_chat.append(entrada)
        if len(self.historico_chat) > MAX_HISTORICO_CHAT:
            self.historico_chat = self.historico_chat[-MAX_HISTORICO_CHAT:]

    # ----------------------------------------------------------------- envio
    def _enviar(self, mensagem: dict[str, Any]) -> None:
        with self._lock:
            sock = self._sock
        if sock is None:
            raise ConnectionError("Não conectado ao hub.")
        dados = codificar(mensagem)
        with self._enviar_lock:
            try:
                sock.sendall(dados)
            except OSError as erro:
                raise ConnectionError(f"Falha ao enviar ao hub: {erro}") from erro

    def listar(self) -> None:
        self._enviar({"type": "listar"})

    def criar_sala(
        self,
        nome: str,
        privada: bool = True,
        senha: str = "",
    ) -> None:
        self._enviar({
            "type": "criar_sala",
            "nome": nome,
            "privada": privada,
            "senha": senha,
        })

    def entrar_sala(self, codigo: str, senha: str = "") -> None:
        self._enviar({
            "type": "entrar_sala",
            "codigo": codigo,
            "senha": senha,
        })

    def sair_sala(self) -> None:
        self._enviar({"type": "sair_sala"})

    def solicitar(self, peer_id: str) -> None:
        self._enviar({"type": "solicitar", "peer_id": peer_id})

    def responder(self, request_id: str, aceitar: bool) -> None:
        self._enviar({
            "type": "responder",
            "request_id": request_id,
            "aceitar": bool(aceitar),
        })

    def chat(self, texto: str) -> None:
        texto_normalizado = normalizar_texto_chat(texto)
        with self._lock:
            if self.estado != "conectado":
                raise ValueError(
                    "Conecte-se a outro participante para conversar."
                )
        self._enviar({"type": "chat", "texto": texto_normalizado})
        with self._lock:
            self._registrar_chat({
                "de": self.peer_id or "",
                "nome": self.nome,
                "texto": texto_normalizado,
                "hora": _agora(),
                "proprio": True,
            })

    def desconectar(self) -> None:
        self._enviar({"type": "desconectar"})

    # ---------------------------------------------------------------- consulta
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "estado": self.estado,
                "peer_id": self.peer_id,
                "nome": self.nome,
                "hub": (
                    {"host": self._host, "porta": self._porta}
                    if self._sock is not None
                    else None
                ),
                "sala": self.sala,
                "peers": list(self.peers),
                "conectado_com": self.conectado_com,
                "solicitacao": self.solicitacao,
                "aguardando": self.aguardando,
                "chat": list(self.historico_chat),
                "ultimo_erro": self.ultimo_erro,
            }

    def drenar_eventos(self) -> list[dict[str, Any]]:
        eventos: list[dict[str, Any]] = []
        while True:
            try:
                eventos.append(self._eventos.get_nowait())
            except queue.Empty:
                break
        return eventos
