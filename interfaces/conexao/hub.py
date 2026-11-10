"""Servidor hub que encontra participantes, cria salas e pareia dois lados.

O hub é o ponto único de encontro: aceita conexões TCP, mantém os
participantes registrados, isola salas privadas e relay as mensagens de
controle e chat. Cada participante pode ficar conectado com no máximo um outro
participante por vez e cada sala privada aceita no máximo dois membros.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, BinaryIO

from .protocolo import (
    MAX_NOME,
    MAX_TEXTO_CHAT,
    SALA_PUBLICA,
    ProtocoloErro,
    Sala,
    codificar,
    decodificar,
    normalizar_contexto_execucao,
    normalizar_convite,
    normalizar_nome,
    normalizar_texto_chat,
)

PORTA_DESCOBERTA = 5011
PEDIDO_DESCOBERTA = b"MINIPAR_HUB_DISCOVER_1"


def _agora() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _digest_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()


CONVITE_TTL = 90.0


@dataclass
class _Convite:
    convite_id: str
    de: str
    sala: str
    dados: dict[str, str]
    alvos: set[str]
    expira: float


@dataclass
class _Conexao:
    peer_id: str
    nome: str
    socket: socket.socket
    arquivo: BinaryIO
    endereco: tuple[str, int]
    estado: str = "disponivel"
    sala: str = SALA_PUBLICA
    parceiro: str | None = None
    execucao: dict[str, Any] | None = None
    enviar_lock: threading.Lock = field(default_factory=threading.Lock)

    def peer_dict(self) -> dict[str, str]:
        return {"id": self.peer_id, "nome": self.nome, "estado": self.estado}


class ServidorHub:
    """Hub TCP para o pareamento 1:1 entre computadores ou sessões."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        porta: int = 5010,
        *,
        inatividade: float = 120.0,
        aviso: float = 30.0,
        convite_ttl: float = CONVITE_TTL,
    ) -> None:
        self.convite_ttl = float(convite_ttl)
        self.host = host
        self.porta = int(porta)
        self.inatividade = float(inatividade)
        self.aviso = min(float(aviso), self.inatividade)
        self._assinatura_salas = ""
        self._vigia: threading.Thread | None = None
        self._lock = threading.RLock()
        self._conexoes: dict[str, _Conexao] = {}
        self._salas: dict[str, Sala] = {
            SALA_PUBLICA: Sala(SALA_PUBLICA, "Sala pública")
        }
        self._solicitacoes: dict[str, tuple[str, str]] = {}
        self._convites: dict[str, _Convite] = {}
        self._listener: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._udp: socket.socket | None = None
        self._udp_thread: threading.Thread | None = None
        self._ativo = threading.Event()

    # ------------------------------------------------------------------ ciclo
    def iniciar(self) -> int:
        """Inicia o servidor em uma thread e devolve a porta efetiva."""
        if self._ativo.is_set():
            return self.porta
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.host, self.porta))
        listener.listen(32)
        listener.settimeout(0.5)
        self._listener = listener
        self.porta = int(listener.getsockname()[1])
        self._ativo.set()
        self._thread = threading.Thread(
            target=self._aceitar,
            name="minipar-hub",
            daemon=True,
        )
        self._thread.start()
        self._iniciar_descoberta()
        self._vigia = threading.Thread(
            target=self._vigiar,
            name="minipar-hub-inatividade",
            daemon=True,
        )
        self._vigia.start()
        return self.porta

    def parar(self) -> None:
        """Encerra o listener e todas as conexões ativas."""
        self._ativo.clear()
        listener = self._listener
        self._listener = None
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        with self._lock:
            conexoes = list(self._conexoes.values())
            self._conexoes.clear()
            self._solicitacoes.clear()
        for conexao in conexoes:
            self._fechar_conexao(conexao)
        udp, self._udp = self._udp, None
        if udp is not None:
            try:
                udp.close()
            except OSError:
                pass
        udp_thread = self._udp_thread
        self._udp_thread = None
        if udp_thread is not None:
            udp_thread.join(timeout=1.0)
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=1.0)
        vigia, self._vigia = self._vigia, None
        if vigia is not None:
            vigia.join(timeout=1.0)

    # ------------------------------------------------------------ inatividade
    def _vigiar(self) -> None:
        intervalo = max(0.02, min(0.5, self.inatividade / 10))
        while self._ativo.is_set():
            time.sleep(intervalo)
            with self._lock:
                self._verificar_inatividade()

    def _verificar_inatividade(self) -> None:
        agora = time.monotonic()
        for convite in list(self._convites.values()):
            if agora >= convite.expira:
                self._encerrar_convite(convite, "expirado")
            else:
                sala_convite = self._salas.get(convite.sala)
                if sala_convite is not None:
                    self._tocar(sala_convite)
        for sala in list(self._salas.values()):
            if sala.codigo == SALA_PUBLICA:
                continue
            em_execucao = any(
                self._conexoes[pid].execucao
                for pid in sala.membros
                if pid in self._conexoes
            )
            if em_execucao:
                self._tocar(sala)
                continue
            ocioso = agora - sala.ultima_atividade
            if ocioso >= self.inatividade:
                self._dissolver_sala(sala, "inatividade")
            elif ocioso >= self.inatividade - self.aviso and not sala.avisada:
                sala.avisada = True
                self._broadcast_sala(sala.codigo)
        self._broadcast_salas()

    def _tocar(self, sala: Sala) -> None:
        sala.ultima_atividade = time.monotonic()
        if sala.avisada:
            sala.avisada = False
            self._broadcast_sala(sala.codigo)

    def _sala_dict(self, sala: Sala) -> dict[str, Any]:
        dados = sala.para_dict()
        fecha_em = None
        if sala.codigo != SALA_PUBLICA and sala.avisada:
            ocioso = time.monotonic() - sala.ultima_atividade
            fecha_em = max(0, int(round(self.inatividade - ocioso)))
        dados["fecha_em"] = fecha_em
        return dados

    def _lista_salas(self) -> list[dict[str, Any]]:
        salas = [
            self._sala_dict(sala)
            for sala in self._salas.values()
            if sala.codigo != SALA_PUBLICA and not sala.automatica
        ]
        for item in salas:
            item.pop("fecha_em", None)
        return sorted(salas, key=lambda item: item["nome"].lower())

    def _broadcast_salas(self, *, forcar: bool = False) -> None:
        salas = self._lista_salas()
        assinatura = json.dumps(salas, sort_keys=True)
        if assinatura == self._assinatura_salas and not forcar:
            return
        self._assinatura_salas = assinatura
        for conexao in list(self._conexoes.values()):
            self._enviar(conexao, {"type": "salas", "salas": salas})

    def _levar_para_publica(self, conexao: _Conexao, motivo: str) -> None:
        publica = self._salas[SALA_PUBLICA]
        conexao.sala = SALA_PUBLICA
        conexao.estado = "disponivel"
        conexao.parceiro = None
        conexao.execucao = None
        publica.membros.add(conexao.peer_id)
        self._cancelar_solicitacoes(conexao.peer_id)
        self._enviar(
            conexao,
            {
                "type": "sala_atual",
                "motivo": motivo,
                "sala": self._sala_dict(publica),
                "peers": self._lista_peers(SALA_PUBLICA, conexao.peer_id),
            },
        )

    def _dissolver_sala(self, sala: Sala, motivo: str) -> None:
        """Fecha a sala e devolve todos os membros para a sala pública."""
        self._salas.pop(sala.codigo, None)
        for pid in list(sala.membros):
            sala.membros.discard(pid)
            membro = self._conexoes.get(pid)
            if membro is None:
                continue
            if membro.parceiro is not None:
                self._encerrar_conexao(membro, notificar=True)
            self._levar_para_publica(membro, motivo)
        self._broadcast_sala(SALA_PUBLICA)
        self._broadcast_salas()

    def _deixar_sala(self, conexao: _Conexao) -> None:
        """Trata a saída da sala atual: o dono encerra, os demais só saem."""
        origem = self._salas.get(conexao.sala)
        if origem is None or origem.codigo == SALA_PUBLICA:
            return
        self._encerrar_conexao(conexao, notificar=True)
        if origem.dono == conexao.peer_id:
            origem.membros.discard(conexao.peer_id)
            self._dissolver_sala(origem, "sala_encerrada")

    # --------------------------------------------------------------- conexões
    def _aceitar(self) -> None:
        listener = self._listener
        if listener is None:
            return
        while self._ativo.is_set():
            try:
                conn, endereco = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._atender,
                args=(conn, endereco),
                name="minipar-hub-peer",
                daemon=True,
            ).start()

    # -------------------------------------------------------------- descoberta
    def _iniciar_descoberta(self) -> None:
        udp: socket.socket | None = None
        try:
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp.bind(("", PORTA_DESCOBERTA))
            udp.settimeout(0.5)
        except OSError:
            if udp is not None:
                try:
                    udp.close()
                except OSError:
                    pass
            return
        self._udp = udp
        self._udp_thread = threading.Thread(
            target=self._responder_descoberta,
            name="minipar-hub-discovery",
            daemon=True,
        )
        self._udp_thread.start()

    def _responder_descoberta(self) -> None:
        udp = self._udp
        if udp is None:
            return
        while self._ativo.is_set():
            try:
                dados, endereco = udp.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if dados.strip() != PEDIDO_DESCOBERTA:
                continue
            resposta = json.dumps({
                "type": "minipar_hub",
                "porta": self.porta,
                "nome": socket.gethostname(),
            }).encode("utf-8")
            try:
                udp.sendto(resposta, endereco)
            except OSError:
                pass

    def _atender(
        self,
        conn: socket.socket,
        endereco: tuple[str, int],
    ) -> None:
        conexao: _Conexao | None = None
        arquivo: BinaryIO | None = None
        try:
            conn.settimeout(120)
            arquivo = conn.makefile("rb")
            conexao = self._registrar(conn, arquivo, endereco)
            while self._ativo.is_set():
                linha = arquivo.readline()
                if not linha:
                    break
                mensagem = decodificar(linha)
                with self._lock:
                    self._tratar(conexao, mensagem)
        except (ProtocoloErro, OSError) as erro:
            if conexao is not None:
                self._enviar(
                    conexao,
                    {"type": "erro", "mensagem": str(erro)},
                )
        finally:
            if conexao is not None:
                self._remover(conexao)
            else:
                try:
                    conn.close()
                except OSError:
                    pass

    def _registrar(
        self,
        conn: socket.socket,
        arquivo: BinaryIO,
        endereco: tuple[str, int],
    ) -> _Conexao:
        mensagem = decodificar(arquivo.readline())
        if mensagem.get("type") != "registrar":
            raise ProtocoloErro("A primeira mensagem deve ser 'registrar'.")
        nome = normalizar_nome(mensagem.get("nome"))
        conexao = _Conexao(
            peer_id=uuid.uuid4().hex[:8],
            nome=nome,
            socket=conn,
            arquivo=arquivo,
            endereco=endereco,
        )
        with self._lock:
            self._conexoes[conexao.peer_id] = conexao
            sala = self._salas[SALA_PUBLICA]
            sala.membros.add(conexao.peer_id)
            self._enviar(
                conexao,
                {
                    "type": "registrado",
                    "peer_id": conexao.peer_id,
                    "nome": conexao.nome,
                    "sala": self._sala_dict(sala),
                    "peers": self._lista_peers(sala.codigo, conexao.peer_id),
                },
            )
            self._broadcast_sala(sala.codigo)
            self._enviar(
                conexao,
                {"type": "salas", "salas": self._lista_salas()},
            )
        return conexao

    def _remover(self, conexao: _Conexao) -> None:
        with self._lock:
            self._encerrar_conexao(conexao, notificar=True)
            self._cancelar_convites(conexao.peer_id)
            self._deixar_sala(conexao)
            self._conexoes.pop(conexao.peer_id, None)
            sala = self._salas.get(conexao.sala)
            if sala is not None:
                sala.membros.discard(conexao.peer_id)
                if (
                    sala.codigo != SALA_PUBLICA
                    and not sala.membros
                ):
                    self._salas.pop(sala.codigo, None)
                else:
                    self._broadcast_sala(sala.codigo)
            self._broadcast_salas()
        self._fechar_conexao(conexao)

    @staticmethod
    def _fechar_conexao(conexao: _Conexao) -> None:
        try:
            conexao.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            conexao.socket.close()
        except OSError:
            pass
        try:
            conexao.arquivo.close()
        except OSError:
            pass

    # ---------------------------------------------------------------- envio
    def _enviar(self, conexao: _Conexao, mensagem: dict[str, Any]) -> None:
        try:
            dados = codificar(mensagem)
        except ProtocoloErro:
            return
        with conexao.enviar_lock:
            try:
                conexao.socket.sendall(dados)
            except OSError:
                pass

    def _lista_peers(self, codigo_sala: str, excluir: str | None) -> list[dict[str, str]]:
        sala = self._salas.get(codigo_sala)
        if sala is None:
            return []
        peers = [
            self._conexoes[pid].peer_dict()
            for pid in sala.membros
            if pid in self._conexoes and pid != excluir
        ]
        return sorted(peers, key=lambda item: item["nome"].lower())

    def _broadcast_sala(self, codigo_sala: str) -> None:
        sala = self._salas.get(codigo_sala)
        if sala is None:
            return
        for pid in list(sala.membros):
            conexao = self._conexoes.get(pid)
            if conexao is None:
                continue
            self._enviar(
                conexao,
                {
                    "type": "peers",
                    "sala": self._sala_dict(sala),
                    "peers": self._lista_peers(sala.codigo, pid),
                },
            )

    # --------------------------------------------------------------- comandos
    def _tratar(self, conexao: _Conexao, mensagem: dict[str, Any]) -> None:
        tipo = mensagem.get("type")
        if tipo == "ping":
            self._enviar(conexao, {"type": "pong"})
        elif tipo == "listar":
            self._enviar(
                conexao,
                {
                    "type": "peers",
                    "sala": self._sala_dict(self._salas[conexao.sala]),
                    "peers": self._lista_peers(conexao.sala, conexao.peer_id),
                },
            )
        elif tipo == "listar_salas":
            self._enviar(
                conexao,
                {"type": "salas", "salas": self._lista_salas()},
            )
        elif tipo == "criar_sala":
            self._criar_sala(conexao, mensagem)
        elif tipo == "entrar_sala":
            self._entrar_sala(conexao, mensagem)
        elif tipo == "sair_sala":
            self._mover_para_sala(conexao, SALA_PUBLICA, "saida")
        elif tipo == "solicitar":
            self._solicitar(conexao, mensagem)
        elif tipo == "responder":
            self._responder(conexao, mensagem)
        elif tipo == "chat":
            self._chat(conexao, mensagem)
        elif tipo == "exec_convidar":
            self._exec_convidar(conexao, mensagem)
        elif tipo == "exec_convite_resposta":
            self._exec_convite_resposta(conexao, mensagem)
        elif tipo == "exec_convite_cancelar":
            self._exec_convite_cancelar(conexao, mensagem)
        elif tipo == "exec_contexto":
            self._exec_contexto(conexao, mensagem)
        elif tipo in (
            "exec_preparado",
            "exec_pronto",
            "exec_fim",
            "exec_erro",
            "exec_parar",
        ):
            self._relay_execucao(conexao, mensagem)
        elif tipo == "desconectar":
            self._encerrar_conexao(conexao, notificar=True)
            if conexao.sala != SALA_PUBLICA:
                self._mover_para_sala(conexao, SALA_PUBLICA, "saida")
            self._enviar(conexao, {"type": "desconectado"})
            self._broadcast_sala(conexao.sala)
        elif tipo == "registrar":
            self._erro(conexao, "Este participante já está registrado.")
        else:
            self._erro(conexao, "Tipo de mensagem desconhecido.")
        if tipo not in ("ping", "chat", "listar", "listar_salas"):
            self._broadcast_salas()

    def _erro(self, conexao: _Conexao, mensagem: str) -> None:
        self._enviar(conexao, {"type": "erro", "mensagem": mensagem})

    def _criar_sala(self, conexao: _Conexao, mensagem: dict[str, Any]) -> None:
        if conexao.estado == "conectado":
            self._erro(conexao, "Desconecte antes de criar outra sala.")
            return
        try:
            nome = normalizar_nome(mensagem.get("nome") or "Sala privada")
        except ProtocoloErro as erro:
            self._erro(conexao, str(erro))
            return
        senha = mensagem.get("senha") or ""
        if not isinstance(senha, str):
            self._erro(conexao, "Senha inválida.")
            return
        codigo = self._novo_codigo()
        sala = Sala(
            codigo=codigo,
            nome=nome,
            privada=True,
            senha=_digest_senha(senha) if senha else "",
            dono=conexao.peer_id,
            dono_nome=conexao.nome,
        )
        self._salas[codigo] = sala
        self._mover_para_sala(conexao, codigo, "criada")

    def _entrar_sala(self, conexao: _Conexao, mensagem: dict[str, Any]) -> None:
        if conexao.estado == "conectado":
            self._erro(conexao, "Desconecte antes de trocar de sala.")
            return
        codigo_bruto = mensagem.get("codigo") or mensagem.get("sala") or ""
        if not isinstance(codigo_bruto, str) or not codigo_bruto.strip():
            self._erro(conexao, "Informe o código da sala.")
            return
        chave = codigo_bruto.strip()
        sala = self._salas.get(chave)
        if sala is None:
            sala = self._salas.get(chave.upper())
        if sala is None:
            for candidata in self._salas.values():
                if candidata.nome.lower() == chave.lower():
                    sala = candidata
                    break
        if sala is None:
            self._erro(conexao, "Sala não encontrada.")
            return
        if sala.privada and sala.senha:
            senha = mensagem.get("senha") or ""
            if not isinstance(senha, str) or _digest_senha(senha) != sala.senha:
                self._erro(conexao, "Senha inválida.")
                return
        if conexao.peer_id in sala.membros:
            self._enviar(
                conexao,
                {
                    "type": "sala_atual",
                    "motivo": "entrada",
                    "sala": self._sala_dict(sala),
                    "peers": self._lista_peers(sala.codigo, conexao.peer_id),
                },
            )
            return
        if sala.lotada():
            self._erro(conexao, "Sala cheia. As salas privadas aceitam dois participantes.")
            return
        self._mover_para_sala(conexao, sala.codigo, "entrada")

    def _mover_para_sala(
        self,
        conexao: _Conexao,
        codigo_destino: str,
        motivo: str,
    ) -> None:
        destino = self._salas.get(codigo_destino)
        if destino is None:
            self._erro(conexao, "Sala não encontrada.")
            return
        if conexao.sala == codigo_destino:
            self._enviar(
                conexao,
                {
                    "type": "sala_atual",
                    "motivo": motivo,
                    "sala": self._sala_dict(destino),
                    "peers": self._lista_peers(destino.codigo, conexao.peer_id),
                },
            )
            return
        self._deixar_sala(conexao)
        origem = self._salas.get(conexao.sala)
        if origem is not None:
            origem.membros.discard(conexao.peer_id)
        destino = self._salas.get(codigo_destino)
        if destino is None:
            destino = self._salas[SALA_PUBLICA]
        destino.membros.add(conexao.peer_id)
        self._tocar(destino)
        conexao.sala = destino.codigo
        conexao.estado = "disponivel"
        conexao.parceiro = None
        conexao.execucao = None
        self._cancelar_solicitacoes(conexao.peer_id)
        self._enviar(
            conexao,
            {
                "type": "sala_atual",
                "motivo": motivo,
                "sala": self._sala_dict(destino),
                "peers": self._lista_peers(destino.codigo, conexao.peer_id),
            },
        )
        if origem is not None:
            if (
                origem.codigo != SALA_PUBLICA
                and not origem.membros
            ):
                self._salas.pop(origem.codigo, None)
            else:
                self._broadcast_sala(origem.codigo)
        self._broadcast_sala(destino.codigo)

    def _solicitar(self, conexao: _Conexao, mensagem: dict[str, Any]) -> None:
        alvo_id = mensagem.get("peer_id") or mensagem.get("alvo")
        if not isinstance(alvo_id, str) or not alvo_id:
            self._erro(conexao, "Informe o participante de destino.")
            return
        alvo = self._conexoes.get(alvo_id)
        if alvo is None:
            self._erro(conexao, "Participante não encontrado.")
            return
        if alvo.peer_id == conexao.peer_id:
            self._erro(conexao, "Não é possível conectar a si mesmo.")
            return
        if alvo.sala != conexao.sala:
            self._erro(conexao, "O participante está em outra sala.")
            return
        if conexao.estado == "conectado" or alvo.estado == "conectado":
            self._erro(conexao, "Participante ocupado em outra conexão.")
            return
        self._tocar(self._salas[conexao.sala])
        request_id = uuid.uuid4().hex[:8]
        self._solicitacoes[request_id] = (conexao.peer_id, alvo.peer_id)
        self._enviar(
            alvo,
            {
                "type": "solicitacao",
                "request_id": request_id,
                "de": conexao.peer_id,
                "nome": conexao.nome,
                "sala": self._sala_dict(self._salas[conexao.sala]),
            },
        )
        self._enviar(
            conexao,
            {
                "type": "aguardando",
                "request_id": request_id,
                "peer": alvo.peer_dict(),
            },
        )

    def _responder(self, conexao: _Conexao, mensagem: dict[str, Any]) -> None:
        request_id = mensagem.get("request_id")
        if not isinstance(request_id, str) or request_id not in self._solicitacoes:
            self._erro(conexao, "Solicitação não encontrada.")
            return
        remetente_id, destinatario_id = self._solicitacoes[request_id]
        if conexao.peer_id != destinatario_id:
            self._erro(conexao, "Somente o destinatário pode responder.")
            return
        self._solicitacoes.pop(request_id, None)
        remetente = self._conexoes.get(remetente_id)
        if remetente is None:
            self._erro(conexao, "O solicitante não está mais disponível.")
            return
        aceitar = bool(mensagem.get("aceitar"))
        if not aceitar:
            self._enviar(
                remetente,
                {
                    "type": "resposta",
                    "request_id": request_id,
                    "aceitar": False,
                    "peer": conexao.peer_dict(),
                },
            )
            self._enviar(
                conexao,
                {
                    "type": "resposta",
                    "request_id": request_id,
                    "aceitar": False,
                    "peer": remetente.peer_dict(),
                },
            )
            return
        if (
            remetente.estado == "conectado"
            or conexao.estado == "conectado"
            or remetente.sala != conexao.sala
        ):
            self._erro(conexao, "Não foi possível concluir a conexão.")
            return
        self._conectar_par(remetente, conexao)

    def _conectar_par(self, remetente: _Conexao, conexao: _Conexao) -> None:
        """Conecta dois participantes, criando a sala privada se preciso."""
        sala = self._salas[conexao.sala]
        veio_da_publica = sala.codigo == SALA_PUBLICA
        if veio_da_publica:
            codigo = self._novo_codigo()
            nome_sala = f"{remetente.nome} e {conexao.nome}"[:MAX_NOME]
            sala = Sala(
                codigo=codigo,
                nome=nome_sala,
                privada=True,
                automatica=True,
                dono=remetente.peer_id,
                dono_nome=remetente.nome,
            )
            self._salas[codigo] = sala
            publica = self._salas[SALA_PUBLICA]
            for participante in (remetente, conexao):
                publica.membros.discard(participante.peer_id)
                sala.membros.add(participante.peer_id)
                participante.sala = codigo
        self._tocar(sala)
        remetente.estado = "conectado"
        conexao.estado = "conectado"
        remetente.parceiro = conexao.peer_id
        conexao.parceiro = remetente.peer_id
        self._cancelar_solicitacoes(remetente.peer_id)
        self._cancelar_solicitacoes(conexao.peer_id)
        self._enviar(
            remetente,
            {
                "type": "conectado",
                "peer": conexao.peer_dict(),
                "sala": self._sala_dict(sala),
            },
        )
        self._enviar(
            conexao,
            {
                "type": "conectado",
                "peer": remetente.peer_dict(),
                "sala": self._sala_dict(sala),
            },
        )
        self._broadcast_sala(sala.codigo)
        if veio_da_publica:
            self._broadcast_sala(SALA_PUBLICA)

    def _exec_convidar(self, conexao: _Conexao, mensagem: dict[str, Any]) -> None:
        try:
            dados = normalizar_convite(mensagem.get("convite"))
        except ProtocoloErro as erro:
            self._erro(conexao, str(erro))
            return
        sala = self._salas.get(conexao.sala)
        if sala is None:
            self._erro(conexao, "Entre em uma sala para convidar.")
            return
        if conexao.estado == "conectado" and conexao.parceiro in self._conexoes:
            alvos = {str(conexao.parceiro)}
        else:
            alvos = {
                pid
                for pid in sala.membros
                if pid != conexao.peer_id
                and pid in self._conexoes
                and self._conexoes[pid].estado != "conectado"
            }
        if not alvos:
            self._erro(
                conexao,
                "Ninguém está disponível na sala para participar da execução.",
            )
            return
        for antigo in [c for c in self._convites.values() if c.de == conexao.peer_id]:
            self._encerrar_convite(antigo, "substituido")
        convite = _Convite(
            convite_id=uuid.uuid4().hex[:8],
            de=conexao.peer_id,
            sala=sala.codigo,
            dados=dados,
            alvos=alvos,
            expira=time.monotonic() + self.convite_ttl,
        )
        self._convites[convite.convite_id] = convite
        self._tocar(sala)
        for pid in alvos:
            self._enviar(
                self._conexoes[pid],
                {
                    "type": "exec_convite",
                    "convite_id": convite.convite_id,
                    "de": conexao.peer_id,
                    "nome": conexao.nome,
                    "dados": dados,
                    "sala": self._sala_dict(sala),
                },
            )
        self._enviar(
            conexao,
            {
                "type": "exec_convite_enviado",
                "convite_id": convite.convite_id,
                "destinatarios": len(alvos),
            },
        )

    def _exec_convite_resposta(
        self,
        conexao: _Conexao,
        mensagem: dict[str, Any],
    ) -> None:
        convite = self._convites.get(str(mensagem.get("convite_id") or ""))
        if convite is None or conexao.peer_id not in convite.alvos:
            self._erro(conexao, "Este convite não está mais disponível.")
            return
        iniciador = self._conexoes.get(convite.de)
        if iniciador is None:
            self._convites.pop(convite.convite_id, None)
            self._erro(conexao, "Quem convidou não está mais disponível.")
            return
        if not bool(mensagem.get("aceitar")):
            convite.alvos.discard(conexao.peer_id)
            self._enviar(
                iniciador,
                {
                    "type": "exec_convite_recusado",
                    "convite_id": convite.convite_id,
                    "peer": conexao.peer_dict(),
                },
            )
            if not convite.alvos:
                self._encerrar_convite(convite, "todos_recusaram")
            return
        ja_conectados = (
            iniciador.estado == "conectado"
            and iniciador.parceiro == conexao.peer_id
        )
        if not ja_conectados and (
            iniciador.estado == "conectado"
            or conexao.estado == "conectado"
            or iniciador.sala != conexao.sala
        ):
            self._erro(conexao, "Não foi possível fechar a conexão para a execução.")
            return
        self._convites.pop(convite.convite_id, None)
        outros = convite.alvos - {conexao.peer_id}
        if not ja_conectados:
            self._conectar_par(iniciador, conexao)
        self._enviar(
            iniciador,
            {
                "type": "exec_convite_aceito",
                "convite_id": convite.convite_id,
                "peer": conexao.peer_dict(),
                "dados": convite.dados,
            },
        )
        self._enviar(
            conexao,
            {
                "type": "exec_convite_confirmado",
                "convite_id": convite.convite_id,
                "de": iniciador.peer_id,
                "nome": iniciador.nome,
                "dados": convite.dados,
            },
        )
        for pid in outros:
            destino = self._conexoes.get(pid)
            if destino is not None:
                self._enviar(
                    destino,
                    {
                        "type": "exec_convite_encerrado",
                        "convite_id": convite.convite_id,
                        "motivo": "aceito",
                        "por": conexao.nome,
                    },
                )

    def _exec_convite_cancelar(
        self,
        conexao: _Conexao,
        mensagem: dict[str, Any],
    ) -> None:
        convite = self._convites.get(str(mensagem.get("convite_id") or ""))
        if convite is None or convite.de != conexao.peer_id:
            return
        self._encerrar_convite(convite, "cancelado")

    def _chat(self, conexao: _Conexao, mensagem: dict[str, Any]) -> None:
        try:
            texto = normalizar_texto_chat(mensagem.get("texto"))
        except ProtocoloErro as erro:
            self._erro(conexao, str(erro))
            return
        sala = self._salas.get(conexao.sala)
        if sala is None:
            self._erro(conexao, "Entre em uma sala para conversar.")
            return
        self._tocar(sala)
        for pid in list(sala.membros):
            if pid == conexao.peer_id:
                continue
            destino = self._conexoes.get(pid)
            if destino is None:
                continue
            self._enviar(
                destino,
                {
                    "type": "chat",
                    "de": conexao.peer_id,
                    "nome": conexao.nome,
                    "texto": texto[:MAX_TEXTO_CHAT],
                    "hora": _agora(),
                    "sala": sala.codigo,
                },
            )

    @staticmethod
    def _assinatura_canais(contexto: dict[str, Any]) -> set[tuple[str, str, str]]:
        canais = contexto.get("canais")
        if not isinstance(canais, list):
            return set()
        return {
            (
                str(canal.get("nome") or ""),
                str(canal.get("conecta") or ""),
                str(canal.get("escuta") or ""),
            )
            for canal in canais
            if isinstance(canal, dict)
        }

    def _validar_execucao(
        self,
        conexao: _Conexao,
        parceiro: _Conexao,
    ) -> None:
        meu = conexao.execucao
        outro = parceiro.execucao
        if not isinstance(meu, dict) or not isinstance(outro, dict):
            return
        mensagem = ""
        if meu.get("papel") == outro.get("papel"):
            mensagem = (
                "Os dois lados escolheram o mesmo papel. "
                "Use um papel que conecta e outro que escuta."
            )
        elif self._assinatura_canais(meu) != self._assinatura_canais(outro):
            mensagem = (
                "Os programas não declaram o mesmo canal. "
                "Abra o cliente em um lado e o servidor no outro."
            )
        if mensagem:
            for destino in (conexao, parceiro):
                self._enviar(
                    destino,
                    {"type": "exec_erro", "mensagem": mensagem, "origem": "hub"},
                )

    def _exec_contexto(
        self,
        conexao: _Conexao,
        mensagem: dict[str, Any],
    ) -> None:
        if conexao.estado != "conectado" or conexao.parceiro is None:
            self._erro(
                conexao,
                "Conecte-se a outro participante antes de preparar a execução.",
            )
            return
        try:
            contexto = normalizar_contexto_execucao(mensagem.get("contexto"))
        except ProtocoloErro as erro:
            self._erro(conexao, str(erro))
            return
        parceiro = self._conexoes.get(conexao.parceiro)
        if parceiro is None:
            self._erro(conexao, "O outro participante não está mais disponível.")
            return
        conexao.execucao = contexto
        self._enviar(
            parceiro,
            {
                "type": "exec_contexto",
                "de": conexao.peer_id,
                "nome": conexao.nome,
                "endereco": conexao.endereco[0],
                "contexto": contexto,
            },
        )
        self._validar_execucao(conexao, parceiro)

    def _relay_execucao(
        self,
        conexao: _Conexao,
        mensagem: dict[str, Any],
    ) -> None:
        if conexao.estado != "conectado" or conexao.parceiro is None:
            self._erro(conexao, "Não há conexão ativa para coordenar a execução.")
            return
        parceiro = self._conexoes.get(conexao.parceiro)
        if parceiro is None:
            self._erro(conexao, "O outro participante não está mais disponível.")
            return
        tipo = str(mensagem.get("type"))
        sala_exec = self._salas.get(conexao.sala)
        if sala_exec is not None:
            self._tocar(sala_exec)
        retorno: dict[str, Any] = {
            "type": tipo,
            "de": conexao.peer_id,
            "nome": conexao.nome,
            "hora": _agora(),
        }
        if tipo == "exec_erro":
            retorno["mensagem"] = str(mensagem.get("mensagem") or "")[
                :MAX_TEXTO_CHAT
            ]
        elif tipo == "exec_fim":
            codigo = mensagem.get("exit_code")
            retorno["exit_code"] = (
                int(codigo)
                if isinstance(codigo, int) and not isinstance(codigo, bool)
                else None
            )
        elif tipo == "exec_parar":
            retorno["motivo"] = str(mensagem.get("motivo") or "")[:MAX_TEXTO_CHAT]
        self._enviar(parceiro, retorno)

    def _encerrar_conexao(
        self,
        conexao: _Conexao,
        *,
        notificar: bool,
    ) -> None:
        parceiro_id = conexao.parceiro
        conexao.parceiro = None
        conexao.estado = "disponivel"
        conexao.execucao = None
        if parceiro_id:
            parceiro = self._conexoes.get(parceiro_id)
            if parceiro is not None:
                parceiro.parceiro = None
                parceiro.estado = "disponivel"
                parceiro.execucao = None
                if notificar:
                    self._enviar(
                        parceiro,
                        {
                            "type": "exec_parar",
                            "motivo": "O outro participante desconectou.",
                            "de": conexao.peer_id,
                            "nome": conexao.nome,
                            "hora": _agora(),
                        },
                    )
                    self._enviar(
                        parceiro,
                        {
                            "type": "peer_desconectou",
                            "peer": conexao.peer_dict(),
                        },
                    )

    def _encerrar_convite(self, convite: _Convite, motivo: str) -> None:
        """Remove o convite e avisa o iniciador e os convidados restantes."""
        self._convites.pop(convite.convite_id, None)
        mensagem = {
            "type": "exec_convite_encerrado",
            "convite_id": convite.convite_id,
            "motivo": motivo,
        }
        for pid in {convite.de, *convite.alvos}:
            destino = self._conexoes.get(pid)
            if destino is not None:
                self._enviar(destino, dict(mensagem))

    def _cancelar_convites(self, peer_id: str, motivo: str = "saiu") -> None:
        for convite in list(self._convites.values()):
            if convite.de == peer_id:
                self._encerrar_convite(convite, motivo)
            elif peer_id in convite.alvos:
                convite.alvos.discard(peer_id)
                if not convite.alvos:
                    self._encerrar_convite(convite, "todos_sairam")

    def _cancelar_solicitacoes(self, peer_id: str) -> None:
        self._cancelar_convites(peer_id)
        for request_id, (remetente, destinatario) in list(
            self._solicitacoes.items()
        ):
            if peer_id not in (remetente, destinatario):
                continue
            self._solicitacoes.pop(request_id, None)

    def _novo_codigo(self) -> str:
        while True:
            codigo = uuid.uuid4().hex[:5].upper()
            if codigo not in self._salas:
                return codigo


def ips_locais() -> list[str]:
    """Lista os endereços IPv4 desta máquina, sem repetição.

    A primeira posição é o endereço usado pela rota padrão (quando disponível),
    seguida dos demais endereços resolvidos pelo nome da máquina. O loopback é
    incluído no final para permitir conexões locais.
    """
    enderecos: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonda:
            sonda.connect(("8.8.8.8", 80))
            rota = sonda.getsockname()[0]
        if rota:
            enderecos.append(rota)
    except OSError:
        pass
    try:
        _, _, resolvidos = socket.gethostbyname_ex(socket.gethostname())
    except OSError:
        resolvidos = []
    for endereco in resolvidos:
        if endereco not in enderecos:
            enderecos.append(endereco)
    if "127.0.0.1" not in enderecos:
        enderecos.append("127.0.0.1")
    return enderecos or ["127.0.0.1"]


def _ip_local() -> str:
    return ips_locais()[0]


def descobrir_hubs(timeout: float = 0.6) -> list[dict[str, Any]]:
    """Procura hubs MiniPar na rede local via UDP broadcast."""
    locais = ips_locais()
    destinos: set[tuple[str, int]] = {
        ("255.255.255.255", PORTA_DESCOBERTA),
        ("127.0.0.1", PORTA_DESCOBERTA),
    }
    for endereco in locais:
        if endereco == "127.0.0.1":
            continue
        partes = endereco.split(".")
        if len(partes) == 4:
            destinos.add((".".join([*partes[:3], "255"]), PORTA_DESCOBERTA))

    resultados: list[dict[str, Any]] = []
    vistos: set[tuple[str, int]] = set()
    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", 0))
        sock.settimeout(0.15)
        for destino in destinos:
            try:
                sock.sendto(PEDIDO_DESCOBERTA, destino)
            except OSError:
                pass
        limite = time.monotonic() + max(0.1, timeout)
        while time.monotonic() < limite:
            try:
                dados, origem = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                resposta = json.loads(dados.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(resposta, dict) or resposta.get("type") != "minipar_hub":
                continue
            valor_porta = resposta.get("porta")
            if not isinstance(valor_porta, (int, str)):
                continue
            try:
                porta = int(valor_porta)
            except (TypeError, ValueError):
                continue
            if not 1 <= porta <= 65535:
                continue
            host = origem[0] if origem[0] != "0.0.0.0" else "127.0.0.1"
            chave = (host, porta)
            if chave in vistos:
                continue
            vistos.add(chave)
            nome = resposta.get("nome")
            resultados.append({
                "nome": nome if isinstance(nome, str) and nome else host,
                "host": host,
                "porta": porta,
                "ativo": True,
                "local": host in locais,
                "descoberto": True,
            })
    finally:
        if sock is not None:
            sock.close()
    return resultados


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hub de conexão MiniPar entre dois computadores ou sessões."
    )
    parser.add_argument("--host", default="0.0.0.0", help="endereço de escuta")
    parser.add_argument("--porta", type=int, default=5010, help="porta TCP")
    args = parser.parse_args()

    hub = ServidorHub(host=args.host, porta=args.porta)
    porta = hub.iniciar()
    print("=" * 55)
    print("  MINIPAR — HUB DE CONEXÃO")
    print("=" * 55)
    print(f"\n  Escutando em {args.host}:{porta}")
    if args.host in ("0.0.0.0", ""):
        for endereco in ips_locais():
            print(f"  Endereço para os outros computadores: {endereco}:{porta}")
    else:
        print(f"  Endereço para os outros computadores: {args.host}:{porta}")
    print("\n  Pressione Ctrl+C para encerrar.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Encerrando hub...")
    finally:
        hub.parar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
