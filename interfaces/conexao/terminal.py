"""Menu de conexão do modo terminal do MiniPar (sem chat).

O terminal usa o mesmo hub e as mesmas salas da interface gráfica. A diferença
proposital é que aqui não existe troca de mensagens de chat: o menu cobre
apenas registro, salas privadas, pedido de conexão e aceite/rejeição.
"""
from __future__ import annotations

import os
import socket
import time
from typing import Any

from .cliente import ClienteHub
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


def _menu_sessao(cliente: ClienteHub) -> None:
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
        elif opcao == "0":
            return
        else:
            print("  [ERRO] Opcao invalida.")
        time.sleep(0.3)


def _conectar_como_cliente(host: str, porta: int) -> bool:
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
        _menu_sessao(cliente)
    finally:
        cliente.fechar()
    return True


def executar_menu_conexao(spec: dict[str, Any] | None = None) -> None:
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
                _conectar_como_cliente("127.0.0.1", porta_efetiva)
            finally:
                hub.parar()
            return
        if opcao == "2":
            host = input("  Endereco do hub [127.0.0.1]: ").strip() or "127.0.0.1"
            porta = _ler_porta(5010)
            if _conectar_como_cliente(host, porta):
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
