"""Menu de conexão do modo terminal do MiniPar (sem chat).

O terminal usa o mesmo hub e as mesmas salas da interface gráfica. A diferença
proposital é que aqui não existe troca de mensagens de chat: o menu cobre
apenas registro, salas privadas, pedido de conexão e aceite/rejeição.
"""
from __future__ import annotations

import os
import re
import socket
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from .cliente import ClienteHub
from .execucao import (
    ExecucaoErro,
    ExecucaoProcesso,
    compilar_programa,
    free_port,
    gerar_hosts,
    iniciar_processo,
    remover_diretorio,
    wait_for_listening,
)
from .hub import ServidorHub, _ip_local


def _separador(char: str = "=", largura: int = 55) -> None:
    print(char * largura)


def _nome_padrao() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def _ler_porta(padrao: int) -> int:
    texto = input(f"  Porta [{padrao}]: ").strip()
    if not texto:
        return padrao
    try:
        porta = int(texto)
    except ValueError:
        print("  [ERRO] Porta invalida. Usando o valor padrao.")
        return padrao
    if not 1 <= porta <= 65535:
        print("  [ERRO] Porta fora do intervalo. Usando o valor padrao.")
        return padrao
    return porta


def _mostrar_sala(cliente: ClienteHub) -> None:
    snap = cliente.snapshot()
    sala = snap.get("sala") or {}
    estado = snap.get("estado", "desconectado")
    parceiro = snap.get("conectado_com") or {}
    print("\n" + "-" * 55)
    print(f"  Participante : {snap.get('nome') or '?'} ({snap.get('peer_id') or '?'})")
    print(f"  Estado       : {estado}")
    if sala:
        limite = sala.get("maximo")
        lotacao = f"{sala.get('lotacao', 0)}/{limite}" if limite else str(sala.get("lotacao", 0))
        privacidade = "privada" if sala.get("privada") else "publica"
        print(
            f"  Sala         : {sala.get('nome')} "
            f"[{sala.get('codigo')}] ({privacidade}, {lotacao})"
        )
    if parceiro:
        print(f"  Conectado com: {parceiro.get('nome')} ({parceiro.get('id')})")
    peers = snap.get("peers") or []
    if peers:
        print("  Participantes na sala:")
        for peer in peers:
            marca = " [ocupado]" if peer.get("estado") == "conectado" else ""
            print(f"    - {peer.get('nome')} ({peer.get('id')}){marca}")
    else:
        print("  Participantes na sala: nenhum")
    print("-" * 55)


def _drenar_eventos(cliente: ClienteHub) -> None:
    for evento in cliente.drenar_eventos():
        tipo = evento.get("type")
        if tipo == "solicitacao":
            nome = evento.get("nome") or "?"
            peer_id = evento.get("de") or "?"
            print(f"\n  [PEDIDO] {nome} ({peer_id}) quer se conectar.")
            resposta = input("  Aceitar? (s/n): ").strip().lower()
            cliente.responder(
                str(evento.get("request_id") or ""),
                resposta in ("s", "sim", "y", "yes"),
            )
        elif tipo == "aguardando":
            peer = evento.get("peer") or {}
            print(f"\n  [INFO] Aguardando resposta de {peer.get('nome')}...")
        elif tipo == "conectado":
            peer = evento.get("peer") or {}
            print(f"\n  [OK] Conectado a {peer.get('nome')} ({peer.get('id')}).")
        elif tipo == "resposta":
            peer = evento.get("peer") or {}
            if evento.get("aceitar"):
                print(f"\n  [OK] {peer.get('nome')} aceitou a conexao.")
            else:
                print(f"\n  [INFO] {peer.get('nome')} recusou a conexao.")
        elif tipo == "peer_desconectou":
            peer = evento.get("peer") or {}
            print(f"\n  [INFO] {peer.get('nome')} desconectou.")
        elif tipo == "sala_atual":
            sala = evento.get("sala") or {}
            motivo = evento.get("motivo", "entrada")
            print(f"\n  [SALA] {motivo}: {sala.get('nome')} [{sala.get('codigo')}]")
        elif tipo == "exec_contexto":
            contexto = evento.get("contexto") or {}
            print(
                f"\n  [EXEC] Parceiro preparou o papel {contexto.get('papel') or '?'}."
            )
        elif tipo == "exec_preparado":
            print("\n  [EXEC] O outro lado terminou de preparar a execução.")
        elif tipo == "exec_pronto":
            print(
                f"\n  [EXEC] O outro lado abriu a porta "
                f"{evento.get('porta') or '?'}."
            )
        elif tipo == "exec_fim":
            codigo = evento.get("exit_code")
            print(f"\n  [EXEC] O outro lado terminou com código {codigo or '?'}.")
        elif tipo == "exec_erro":
            print(f"\n  [ERRO] Execução: {evento.get('mensagem') or '?'}")
        elif tipo == "exec_parar":
            print(
                f"\n  [EXEC] Execução encerrada: {evento.get('motivo') or '?'}."
            )
        elif tipo == "erro":
            print(f"\n  [ERRO] {evento.get('mensagem')}")


def _solicitar_conexao(cliente: ClienteHub) -> None:
    snap = cliente.snapshot()
    peers = [
        peer for peer in snap.get("peers") or []
        if peer.get("estado") != "conectado"
    ]
    if not peers:
        print("\n  Nenhum participante disponivel nesta sala.")
        return
    print("\n  Participantes disponiveis:")
    for indice, peer in enumerate(peers, start=1):
        print(f"    [{indice}] {peer.get('nome')} ({peer.get('id')})")
    escolha = input("  Numero do participante (ENTER cancela): ").strip()
    if not escolha:
        return
    try:
        indice = int(escolha)
    except ValueError:
        print("  [ERRO] Numero invalido.")
        return
    if not 1 <= indice <= len(peers):
        print("  [ERRO] Numero invalido.")
        return
    cliente.solicitar(str(peers[indice - 1].get("id")))


def _criar_sala(cliente: ClienteHub) -> None:
    nome = input("  Nome da sala [Sala privada]: ").strip() or "Sala privada"
    senha = input("  Senha (opcional): ").strip()
    cliente.criar_sala(nome, privada=True, senha=senha)


def _entrar_sala(cliente: ClienteHub) -> None:
    codigo = input("  Codigo ou nome da sala: ").strip()
    if not codigo:
        print("  [ERRO] Informe o codigo da sala.")
        return
    senha = input("  Senha (se houver): ").strip()
    cliente.entrar_sala(codigo, senha)


def _ler_entradas_terminal(spec: dict[str, Any] | None) -> str:
    valores: list[str] = []
    if not (spec or {}).get("requires_input"):
        return ""
    print("  Digite as operacoes no formato: operacao, operando1, operando2")
    print("  Use 'sair' para encerrar a execucao.")
    while True:
        try:
            linha = input("  Operacao (ENTER cancela; 'sair' encerra): ").strip()
        except EOFError:
            break
        if not linha:
            continue
        partes = [parte for parte in re.split(r"[,\s]+", linha) if parte]
        if partes and partes[0].lower() == "sair":
            valores.append("sair")
            break
        if len(partes) >= 2:
            valores.extend(partes[:3])
    return "\n".join(valores) + ("\n" if valores else "")


def _iniciar_com_entradas(
    executavel: Path,
    workdir: Path,
    hosts_path: Path,
    papel: str,
    entradas: str,
) -> ExecucaoProcesso:
    processo = iniciar_processo(executavel, workdir, hosts_path, papel)
    executacao = ExecucaoProcesso(processo)
    executacao.escrever_entradas(entradas)
    return executacao


def _aguardar_e_finalizar(
    processo: ExecucaoProcesso,
    cliente: ClienteHub,
    executavel: Path,
    workdir: Path,
) -> None:
    try:
        codigo = processo.aguardar()
    except OSError:
        codigo = None
    processo.juntar_threads()
    if codigo == 0:
        print("[EXEC] Programa terminou com sucesso.")
    else:
        print(f"[EXEC] Programa terminou com codigo {codigo}.")
    try:
        cliente.informar_execucao_fim(codigo)
    except (ConnectionError, ValueError):
        pass
    remover_diretorio(workdir)


def _aguardar_e_finalizar_com_execucao(
    processo: ExecucaoProcesso,
    cliente: ClienteHub,
    executavel: Path,
    workdir: Path,
) -> None:
    _aguardar_e_finalizar(processo, cliente, executavel, workdir)


def _iniciar_e_aguardar_escuta(
    processo: ExecucaoProcesso,
    cliente: ClienteHub,
    executavel: Path,
    workdir: Path,
    host: str,
    porta: int,
) -> None:
    try:
        wait_for_listening(porta, timeout=60)
        cliente.marcar_execucao_pronta(host=host, porta=porta)
    except ExecucaoErro as erro:
        processo.parar()
        processo.juntar_threads()
        try:
            cliente.informar_execucao_erro(str(erro))
        except (ConnectionError, ValueError):
            pass
        remover_diretorio(workdir)
        return
    _aguardar_e_finalizar(processo, cliente, executavel, workdir)


def _executar_com_pareamento(
    cliente: ClienteHub,
    source_path: str,
    spec: dict[str, Any] | None,
) -> None:
    snap = cliente.snapshot()
    if snap.get("estado") != "conectado" or not snap.get("conectado_com"):
        print("\n  [EXEC] Conecte-se a um parceiro antes de executar.")
        return
    multi = (spec or {}).get("multi_computer") or {}
    if not multi.get("auto_execution"):
        print("\n  [EXEC] Este programa nao tem execucao automatica.")
        return
    canais = multi.get("channels") or []
    if len(canais) != 1 or not isinstance(canais[0], dict):
        print("\n  [EXEC] Use um programa com um canal declarativo.")
        return
    canal = canais[0]
    basename = Path(source_path).name.lower()
    papel = "escuta" if "servidor" in basename or "server" in basename else "conecta"
    host = _ip_local()
    porta = free_port() if papel == "escuta" else None
    source = Path(source_path).read_text(encoding="utf-8")
    workdir = Path(tempfile.mkdtemp(prefix="minipar-terminal-"))
    try:
        executavel = compilar_programa(source, workdir)
    except ExecucaoErro as erro:
        print(f"\n  [ERRO] Compilacao falhou: {erro}")
        remover_diretorio(workdir)
        return
    entradas = _ler_entradas_terminal(spec)
    cliente.anunciar_execucao(
        source_path,
        papel,
        [canal],
        host=host if papel == "escuta" else "",
        porta=porta if papel == "escuta" else None,
        modo=papel,
    )
    cliente.marcar_execucao_preparada()

    if papel == "escuta":
        hosts_path = workdir / "minipar.hosts"
        hosts_path.write_text(
            gerar_hosts(canal, papel, host, porta or 1),
            encoding="utf-8",
        )
        processo = _iniciar_com_entradas(
            executavel, workdir, hosts_path, papel, entradas
        )
        thread = threading.Thread(
            target=_iniciar_e_aguardar_escuta,
            args=(processo, cliente, executavel, workdir, host, int(porta or 1)),
            name="minipar-terminal-exec-escuta",
            daemon=True,
        )
        thread.start()
        thread.join()
        return

    inicio = time.monotonic()
    pronto = False
    while time.monotonic() - inicio < 30.0:
        execucao = cliente.snapshot().get("execucao") or {}
        if execucao.get("peer_pronto"):
            pronto = True
            break
        if execucao.get("parar_solicitado"):
            break
        time.sleep(0.05)
    if not pronto:
        print("\n  [ERRO] O lado que escuta nao abriu a porta a tempo.")
        remover_diretorio(workdir)
        return

    peer = cliente.snapshot().get("execucao") or {}
    peer_contexto = peer.get("peer") or {}
    host_parceiro = str(peer_contexto.get("host") or "")
    porta_parceiro = int(peer_contexto.get("porta") or 0)
    if not host_parceiro or porta_parceiro <= 0:
        print("\n  [ERRO] Endereco do lado que escuta indisponivel.")
        remover_diretorio(workdir)
        return
    hosts_path = workdir / "minipar.hosts"
    hosts_path.write_text(
        gerar_hosts(canal, papel, host_parceiro, porta_parceiro),
        encoding="utf-8",
    )
    processo = _iniciar_com_entradas(
        executavel, workdir, hosts_path, papel, entradas
    )
    thread = threading.Thread(
        target=_aguardar_e_finalizar,
        args=(processo, cliente, executavel, workdir),
        name="minipar-terminal-exec-cliente",
        daemon=True,
    )
    thread.start()
    thread.join()


def _menu_sessao(
    cliente: ClienteHub,
    source_path: str | None = None,
    spec: dict[str, Any] | None = None,
) -> None:
    while True:
        _drenar_eventos(cliente)
        _mostrar_sala(cliente)
        print("  [1] Atualizar participantes")
        print("  [2] Solicitar conexao")
        print("  [3] Ver pedidos pendentes")
        print("  [4] Desconectar conexao ativa")
        print("  [5] Criar sala privada")
        print("  [6] Entrar em uma sala")
        print("  [7] Sair da sala (voltar a publica)")
        if source_path and spec and (spec.get("multi_computer") or {}).get("auto_execution"):
            print("  [8] Preparar/executar programa")
        print("  [0] Encerrar conexao com o hub")
        opcao = input("  Escolha: ").strip()
        if opcao == "1":
            cliente.listar()
        elif opcao == "2":
            _solicitar_conexao(cliente)
        elif opcao == "3":
            continue
        elif opcao == "4":
            cliente.desconectar()
        elif opcao == "5":
            _criar_sala(cliente)
        elif opcao == "6":
            _entrar_sala(cliente)
        elif opcao == "7":
            cliente.sair_sala()
        elif opcao == "8":
            if source_path and spec:
                _executar_com_pareamento(cliente, source_path, spec)
            else:
                print("  [ERRO] Execucao indisponivel sem um programa de conexao.")
        elif opcao == "0":
            return
        else:
            print("  [ERRO] Opcao invalida.")
        time.sleep(0.3)


def _conectar_como_cliente(
    host: str,
    porta: int,
    source_path: str | None = None,
    spec: dict[str, Any] | None = None,
) -> bool:
    nome = input(f"  Nome deste participante [{_nome_padrao()}]: ").strip()
    cliente = ClienteHub()
    try:
        cliente.conectar(host, porta, nome or _nome_padrao())
    except (OSError, ValueError, TimeoutError, ConnectionError) as erro:
        print(f"  [ERRO] Nao foi possivel conectar: {erro}")
        cliente.fechar()
        return False
    print(f"\n  [OK] Conectado ao hub {host}:{porta}.")
    try:
        _menu_sessao(cliente, source_path, spec)
    finally:
        cliente.fechar()
    return True


def executar_menu_conexao(
    spec: dict[str, Any] | None = None,
    source_path: str | None = None,
) -> None:
    """Menu principal do hub no modo terminal."""
    _separador()
    print("  MINIPAR — HUB DE CONEXAO (MODO TERMINAL)")
    if spec:
        resumo_programa(spec)
    _separador()
    while True:
        print("\n  [1] Iniciar hub nesta maquina")
        print("  [2] Conectar a um hub existente")
        print("  [0] Voltar")
        opcao = input("  Escolha: ").strip()
        if opcao == "0":
            return
        if opcao == "1":
            porta = _ler_porta(5010)
            hub = ServidorHub(host="0.0.0.0", porta=porta)
            try:
                porta_efetiva = hub.iniciar()
            except OSError as erro:
                print(f"  [ERRO] Nao foi possivel iniciar o hub: {erro}")
                continue
            print(f"\n  [OK] Hub iniciado na porta {porta_efetiva}.")
            print(f"  Outros computadores devem usar: {_ip_local()}:{porta_efetiva}")
            print("  Este terminal sera conectado ao hub local para participar.\n")
            try:
                _conectar_como_cliente("127.0.0.1", porta_efetiva, source_path, spec)
            finally:
                hub.parar()
            return
        if opcao == "2":
            host = input("  Endereco do hub [127.0.0.1]: ").strip() or "127.0.0.1"
            porta = _ler_porta(5010)
            if _conectar_como_cliente(host, porta, source_path, spec):
                return
        else:
            print("  [ERRO] Opcao invalida.")


def resumo_programa(spec: dict[str, Any]) -> None:
    """Mostra o contexto do programa que exigiu a conexão."""
    if not spec:
        return
    multi = spec.get("multi_computer") or {}
    _separador("-")
    print(f"  Programa: {spec.get('titulo', '')}")
    if multi:
        print(f"  Terminais previstos: {multi.get('count', '?')}")
        papeis = ", ".join(multi.get("roles", []))
        if papeis:
            print(f"  Papeis: {papeis}")
    print(f"  {'-' * 50}")


if __name__ == "__main__":
    executar_menu_conexao()
