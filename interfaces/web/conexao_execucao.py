"""Gerenciamento das execuções iniciadas pela página de conexão."""
from __future__ import annotations

import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..conexao.cliente import ClienteHub
from ..conexao.execucao import (
    ExecucaoErro,
    ExecucaoProcesso,
    compilar_programa,
    free_port,
    gerar_hosts,
    iniciar_processo,
    remover_diretorio,
    wait_for_listening,
)


@dataclass
class SessaoExecucao:
    client_id: str
    workdir: Path
    filename: str
    canal: dict[str, str]
    papel: str
    modo: str
    host: str
    porta: int
    entradas: str
    timeout: float
    executavel: Path | None = None
    hosts_path: Path | None = None
    processo: ExecucaoProcesso | None = None
    status: str = "preparando"
    erro: str = ""
    compilado: bool = False
    pronto_enviado: bool = False
    parando: bool = False
    lock: threading.RLock = field(default_factory=threading.RLock)


class ExecutorConexao:
    """Mantém uma execução por ``client_id`` da página de conexão."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessoes: dict[str, SessaoExecucao] = {}

    def _obter(self, client_id: str) -> SessaoExecucao:
        sessao = self._sessoes.get(client_id)
        if sessao is None:
            raise ExecucaoErro("Nenhuma execução preparada para esta sessão.")
        return sessao

    def preparar(
        self,
        client_id: str,
        *,
        source: str,
        filename: str,
        canal: dict[str, str],
        papel: str,
        host: str,
        porta: int | None,
        entradas: str,
        timeout: float,
        cliente: ClienteHub,
    ) -> dict[str, Any]:
        """Compila o programa e troca o contexto de execução com o parceiro."""
        self.encerrar(client_id)
        conecta = str(canal.get("conecta") or "").strip()
        escuta = str(canal.get("escuta") or "").strip()
        if papel not in (conecta, escuta):
            raise ExecucaoErro(
                "Escolha um papel válido para o canal declarado."
            )
        modo = "conecta" if papel == conecta else "escuta"
        porta_sessao = int(porta) if porta else 0
        if modo == "escuta" and porta_sessao == 0:
            porta_sessao = free_port()
        workdir = Path(tempfile.mkdtemp(prefix="minipar-conexao-"))
        sessao = SessaoExecucao(
            client_id=client_id,
            workdir=workdir,
            filename=filename,
            canal={
                "nome": str(canal.get("nome") or "dados"),
                "conecta": conecta,
                "escuta": escuta,
            },
            papel=papel,
            modo=modo,
            host=host.strip(),
            porta=porta_sessao,
            entradas=entradas,
            timeout=max(1.0, float(timeout)),
        )
        with self._lock:
            self._sessoes[client_id] = sessao

        try:
            sessao.executavel = compilar_programa(source, workdir)
            sessao.compilado = True
            sessao.status = "preparado"
            cliente.anunciar_execucao(
                filename,
                papel,
                [sessao.canal],
                host=sessao.host if modo == "escuta" else "",
                porta=sessao.porta if modo == "escuta" else None,
                modo=modo,
            )
            cliente.marcar_execucao_preparada()
        except ExecucaoErro as erro:
            sessao.status = "erro"
            sessao.erro = str(erro)
            try:
                cliente.informar_execucao_erro(str(erro))
            except (ConnectionError, ValueError):
                pass
        except (ConnectionError, OSError, ValueError) as erro:
            sessao.status = "erro"
            sessao.erro = f"Falha ao coordenar a execução: {erro}"
        return self.estado(client_id)

    def iniciar(
        self,
        client_id: str,
        *,
        cliente: ClienteHub,
        host_listener: str | None = None,
        porta_listener: int | None = None,
    ) -> dict[str, Any]:
        """Inicia o processo local depois que os dois lados estão prontos."""
        with self._lock:
            sessao = self._obter(client_id)
        with sessao.lock:
            if not sessao.compilado or sessao.executavel is None:
                raise ExecucaoErro("Compile o programa antes de executar.")
            if sessao.processo is not None and sessao.processo.poll() is None:
                return self.estado(client_id)

            snapshot = cliente.snapshot()
            execucao = snapshot.get("execucao") or {}
            peer = execucao.get("peer") or {}
            if sessao.modo == "escuta":
                if not execucao.get("peer_preparado"):
                    raise ExecucaoErro(
                        "Aguarde o outro lado terminar de preparar a execução."
                    )
                host_efetivo = host_listener or sessao.host or "127.0.0.1"
                porta_efetiva = (
                    int(porta_listener)
                    if porta_listener
                    else sessao.porta or free_port()
                )
                sessao.host = host_efetivo
                sessao.porta = porta_efetiva
            else:
                if not execucao.get("peer_pronto"):
                    raise ExecucaoErro(
                        "Aguarde o lado que escuta abrir a porta."
                    )
                host_efetivo = (
                    host_listener
                    or str(peer.get("host") or "")
                    or str(execucao.get("peer_host") or "")
                    or str(execucao.get("peer_endereco") or "")
                )
                porta_efetiva = (
                    int(porta_listener)
                    if porta_listener
                    else int(peer.get("porta") or execucao.get("peer_porta") or 0)
                )
                if not host_efetivo or porta_efetiva <= 0:
                    raise ExecucaoErro(
                        "O endereço do lado que escuta ainda não está disponível."
                    )
                sessao.host = host_efetivo
                sessao.porta = porta_efetiva

            hosts = gerar_hosts(
                sessao.canal,
                sessao.papel,
                host_efetivo,
                porta_efetiva,
            )
            hosts_path = sessao.workdir / "minipar.hosts"
            hosts_path.write_text(hosts, encoding="utf-8")
            sessao.hosts_path = hosts_path
            try:
                processo = iniciar_processo(
                    sessao.executavel,
                    sessao.workdir,
                    hosts_path,
                    sessao.papel,
                )
            except OSError as erro:
                sessao.status = "erro"
                sessao.erro = f"Falha ao iniciar o programa: {erro}"
                try:
                    cliente.informar_execucao_erro(sessao.erro)
                except (ConnectionError, ValueError):
                    pass
                return self.estado(client_id)

            sessao.processo = ExecucaoProcesso(processo)
            sessao.processo.escrever_entradas(sessao.entradas)
            sessao.status = "executando"

        if sessao.modo == "escuta":
            threading.Thread(
                target=self._aguardar_servidor,
                args=(sessao, cliente),
                name="minipar-exec-servidor",
                daemon=True,
            ).start()
        else:
            threading.Thread(
                target=self._monitorar,
                args=(sessao, cliente),
                name="minipar-exec-cliente",
                daemon=True,
            ).start()
        return self.estado(client_id)

    def _aguardar_servidor(
        self,
        sessao: SessaoExecucao,
        cliente: ClienteHub,
    ) -> None:
        processo = sessao.processo
        if processo is None:
            return
        try:
            wait_for_listening(sessao.porta, timeout=sessao.timeout)
        except ExecucaoErro as erro:
            if processo.poll() is None:
                sessao.status = "erro"
                sessao.erro = str(erro)
                processo.parar()
                try:
                    cliente.informar_execucao_erro(str(erro))
                except (ConnectionError, ValueError):
                    pass
            return
        sessao.pronto_enviado = True
        try:
            cliente.marcar_execucao_pronta(
                host=sessao.host,
                porta=sessao.porta,
            )
        except (ConnectionError, ValueError):
            pass
        self._monitorar(sessao, cliente)

    def _monitorar(
        self,
        sessao: SessaoExecucao,
        cliente: ClienteHub,
    ) -> None:
        processo = sessao.processo
        if processo is None:
            return
        try:
            codigo = processo.aguardar()
        except OSError:
            codigo = None
        processo.juntar_threads()
        with sessao.lock:
            if sessao.parando:
                sessao.status = "cancelado"
            elif codigo == 0:
                sessao.status = "concluido"
            else:
                sessao.status = "erro"
                if not sessao.erro:
                    sessao.erro = (
                        f"O programa terminou com código {codigo}."
                        if codigo is not None
                        else "O programa terminou inesperadamente."
                    )
        try:
            cliente.informar_execucao_fim(codigo)
        except (ConnectionError, ValueError):
            pass

    def estado(self, client_id: str) -> dict[str, Any]:
        with self._lock:
            sessao = self._sessoes.get(client_id)
        if sessao is None:
            return {"ativo": False}
        with sessao.lock:
            processo = sessao.processo.estado() if sessao.processo else None
            return {
                "ativo": True,
                "status": sessao.status,
                "papel": sessao.papel,
                "modo": sessao.modo,
                "host": sessao.host,
                "porta": sessao.porta,
                "compilado": sessao.compilado,
                "pronto_enviado": sessao.pronto_enviado,
                "erro": sessao.erro,
                "processo": processo,
            }

    def parar(
        self,
        client_id: str,
        *,
        cliente: ClienteHub | None = None,
        motivo: str = "",
        notificar: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            sessao = self._sessoes.get(client_id)
        if sessao is None:
            return {"ativo": False}
        with sessao.lock:
            sessao.parando = True
            if sessao.processo is not None:
                sessao.processo.parar()
                sessao.processo.juntar_threads()
            sessao.status = "cancelado"
        if notificar and cliente is not None:
            try:
                cliente.parar_execucao(motivo)
            except (ConnectionError, ValueError):
                pass
        return self.estado(client_id)

    def encerrar(self, client_id: str) -> None:
        with self._lock:
            sessao = self._sessoes.pop(client_id, None)
        if sessao is None:
            return
        with sessao.lock:
            sessao.parando = True
            if sessao.processo is not None:
                sessao.processo.parar()
                sessao.processo.juntar_threads()
        remover_diretorio(sessao.workdir)

    def encerrar_tudo(self) -> None:
        with self._lock:
            clientes = list(self._sessoes)
        for client_id in clientes:
            self.encerrar(client_id)
