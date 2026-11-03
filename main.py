import os
import sys

from components.controle.c_controle import compile_file


def start_interactive():
    """Inicia a tela de seleção inicial do sistema."""
    from interfaces.test_orchestrator import (
        _load_session,
        check_active_session_for_new_terminal,
        get_terminal_id,
        join_session,
        run_joiner_progress_monitor,
    )

    # Segundo terminal detectou sessão ativa — entra como participante antes do menu
    action, session = check_active_session_for_new_terminal()
    if action == "join" and session:
        join_session(session)
        session = _load_session() or session
        print("\n" + "=" * 45)
        print("  MINIPAR — PARTICIPANTE DE TESTE")
        print("=" * 45)
        print(f"\n  Terminal identificado: {get_terminal_id()}")
        print(f"  Teste em andamento: {session.get('titulo', session.get('test_file', ''))}")
        print("\n  Monitor de progresso iniciado...\n")
        run_joiner_progress_monitor(session)
    elif action == "independent":
        print("\n  [INFO] Sessão em andamento ignorada — modo independente.\n")

    print("\n" + "=" * 45)
    print("      MINIPAR COMPILER & IDE")
    print("=" * 45)
    print("\nComo você deseja rodar o sistema?\n")
    print("[1] - Modo Terminal (Menu Interativo)")
    print("[2] - Modo Web Interface (IDE no Navegador)\n")

    escolha = input("Digite a sua escolha (1 ou 2): ").strip()

    if escolha == '1':
        print("\nIniciando modo Terminal...\n")
        try:
            from interfaces.cli import exibir_menu
            exibir_menu()
        except ImportError as e:
            print(f"[ERRO] Falha ao carregar o menu: {e}")

    elif escolha == '2':
        print("\nIniciando Web Interface IDE...")
        print("Servidor inicializado! Acesse no navegador: http://127.0.0.1:5000\n")
        try:
            from interfaces.web.api import app
            app.run(host="127.0.0.1", port=5000, debug=False)
        except ImportError as e:
            print(f"[ERRO] Falha ao carregar a interface web: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"[ERRO] Erro ao iniciar o servidor Flask: {e}")
    else:
        print("\n[ERRO] Escolha inválida. Finalizando o sistema.")


def main() -> int:
    arguments = sys.argv[1:]
    if not arguments:
        start_interactive()
        return 0

    if arguments[0] in {
        "compilar", "tokens", "ast", "tac", "cpp", "build", "run", "--help"
    }:
        from interfaces.command_line import run

        return run(arguments)

    # Caso o script seja chamado via subprocesso pela IDE (passando arquivo como
    # argumento)
    source_path = arguments[0]

    # Se não passarem o nome da saída manualmente, extraímos do nome do próprio arquivo
    # Minipar
    if len(arguments) > 1:
        output_name = arguments[1]
    else:
        base_file = os.path.basename(source_path)
        output_name = os.path.splitext(base_file)[0]

    print("=== Compilador MiniPar ===")
    success = compile_file(source_path, output_name)

    if success:
        print("=== Processo Finalizado ===")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
