import glob
import os
import subprocess
import sys

from flask import Flask, jsonify, render_template, request

from components.lexico.c_lexico import Lexer
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser
from erros.diagnosticos import DiagnosticBag

from ..program_analyzer import get_program_spec
from ..test_orchestrator import (
    _load_session,
    _save_session,
    append_session_log,
    check_active_session_for_new_terminal,
    clear_session,
    create_session,
    finalize_test_execution,
    get_spec_summary,
    get_terminal_id,
    join_session,
    record_execution_output,
    set_session_phase,
)

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "interfaces", "web", "frontend")
app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, "templates"),
    static_folder=os.path.join(FRONTEND_DIR, "static"),
)

# Configuração de Diretórios
TESTS_DIR = os.path.join(PROJECT_ROOT, "programas_teste")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
TEMP_DIR = os.path.join(PROJECT_ROOT, "temp_code")

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/tests', methods=['GET'])
def get_tests():
    # Retorna os testes ordenados alfabeticamente
    tests = [os.path.basename(f) for f in glob.glob(os.path.join(TESTS_DIR, '*.mp'))]
    return jsonify({"tests": sorted(tests)})


@app.route('/api/get_test', methods=['POST'])
def get_test():
    filename = request.json.get('filename')
    filepath = os.path.join(TESTS_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return jsonify({"code": f.read()})
    return jsonify({"error": "Arquivo não encontrado"}), 404


@app.route('/api/test_spec', methods=['POST'])
def get_test_spec_api():
    """Requisitos detectados automaticamente pelo program_analyzer."""
    filename = request.json.get('filename')
    spec = get_spec_summary(filename)
    if spec:
        return jsonify(spec)
    return jsonify({"requires_input": False, "multi_computer": None})


@app.route('/api/session', methods=['GET'])
def get_session():
    action, session = check_active_session_for_new_terminal()
    if session:
        return jsonify({
            "active": session.get("status") not in ("completed", "cancelled"),
            "session": session,
            "terminal_id": get_terminal_id(),
            "needs_choice": action is not None,
        })
    return jsonify({"active": False, "terminal_id": get_terminal_id()})


@app.route('/api/session/join', methods=['POST'])
def session_join():
    _, session = check_active_session_for_new_terminal()
    if session:
        join_session(session)
        return jsonify({"success": True, "session": session})
    return jsonify({"success": False, "error": "Nenhuma sessão ativa"}), 404


@app.route('/api/session/create', methods=['POST'])
def session_create():
    filename = request.json.get('filename')
    path = os.path.join(TESTS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "Arquivo não encontrado"}), 404
    spec = get_program_spec(path)
    if not spec.get('multi_computer'):
        return jsonify({
            "success": False, "error": "Programa não requer multi-terminal"
        }), 400
    session = create_session(path, spec)
    return jsonify({"success": True, "session": session})


@app.route('/api/session/ready', methods=['POST'])
def session_ready():
    session = _load_session()
    if session:
        session["status"] = "running"
        _save_session(session)
        return jsonify({"success": True})
    return jsonify({"success": False}), 404


@app.route('/api/session/clear', methods=['POST'])
def session_clear():
    clear_session()
    return jsonify({"success": True})


@app.route('/api/symbols', methods=['POST'])
def analyze_symbols():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("code"), str):
        return jsonify({
            "error": "O campo 'code' deve ser texto.", "success": False
        }), 400

    diagnostics = DiagnosticBag()
    lexer = Lexer(data["code"], diagnostics)
    parser = Parser(lexer, diagnostics)
    program = parser.parse()
    analyzer = SemanticAnalyzer(diagnostics)
    analyzer.analyze(program)
    return jsonify({
        "success": not diagnostics.has_errors,
        "symbols": analyzer.symbol_table.export(),
        "diagnostics": [diagnostic.header for diagnostic in diagnostics.diagnostics],
    })


@app.route('/api/compile', methods=['POST'])
def compile_code():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "error": "Corpo JSON ausente ou inválido.", "success": False
        }), 400

    code = data.get('code')
    filename = data.get('filename', 'ide_temp.mp')
    user_inputs = data.get('inputs', [])

    if not isinstance(code, str) or not isinstance(filename, str):
        return jsonify({
            "error": "Os campos 'code' e 'filename' devem ser texto.", "success": False
        }), 400
    if not isinstance(user_inputs, list):
        return jsonify({
            "error": "O campo 'inputs' deve ser uma lista.", "success": False
        }), 400
    if os.path.basename(filename) != filename:
        return jsonify({"error": "Nome de arquivo inválido.", "success": False}), 400

    # Salva o código recebido da IDE em um arquivo temporário
    file_path = os.path.join(TEMP_DIR, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)

    base_name = os.path.splitext(filename)[0]
    stdin_lines = user_inputs

    try:
        set_session_phase("compiling", "Compilando código MiniPar...", percent=60)
        append_session_log("Compilação iniciada via IDE Web.")

        # 1. FASE DE COMPILAÇÃO (Gera TAC e C++)
        process = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "main.py"), file_path],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=PROJECT_ROOT,
            check=False,
        )

        full_output = process.stdout
        if process.stderr:
            full_output += "\n" + process.stderr

        success = process.returncode == 0

        # 2. FASE DE EXECUÇÃO (Roda o Binário C++)
        if success:
            set_session_phase("compiling", "Compilação concluída.", percent=80)
            append_session_log("Compilação concluída — executando binário.")
            exe_ext = ".exe" if sys.platform == "win32" else ""
            exe_path = os.path.join(OUTPUT_DIR, f"{base_name}{exe_ext}")

            if os.path.exists(exe_path):
                full_output += f"\n--- Executando {base_name} ---\n"
                set_session_phase("executing", f"Executando {base_name}...", percent=90)
                try:
                    stdin_data = "\n".join(str(value) for value in stdin_lines)
                    if stdin_lines:
                        stdin_data += "\n"
                    exe_proc = subprocess.run(
                        [os.path.abspath(exe_path)],
                        input=stdin_data,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False
                    )
                    full_output += exe_proc.stdout
                    if exe_proc.stderr:
                        full_output += "\n[ERRO NA EXECUÇÃO]:\n" + exe_proc.stderr
                    record_execution_output(exe_proc.stdout or "")
                except subprocess.TimeoutExpired:
                    full_output += "\n[ERRO] Tempo limite de execução excedido."
                    success = False
                except (subprocess.SubprocessError, OSError) as e:
                    full_output += f"\n[ERRO] Falha ao executar binário: {e}"
                    success = False

                full_output += "\n" + "-" * 40

                if filename.endswith('.mp'):
                    test_source = os.path.join(TESTS_DIR, filename)
                    if os.path.exists(test_source):
                        finalize_test_execution(test_source, full_output)
            else:
                full_output += f"\n[ERRO] Binário esperado não foi criado: {exe_path}"
                success = False

        # 3. COLETA DOS ARQUIVOS GERADOS
        cpp_file = os.path.join(OUTPUT_DIR, f"{base_name}.cpp")
        tac_file = os.path.join(OUTPUT_DIR, f"{base_name}.tac")
        cpp_code = ""
        tac_code = ""

        if os.path.exists(cpp_file):
            with open(cpp_file, 'r', encoding='utf-8') as f:
                cpp_code = f.read()
        if os.path.exists(tac_file):
            with open(tac_file, 'r', encoding='utf-8') as f:
                tac_code = f.read()

        return jsonify({
            "stdout": full_output if success else "",
            "stderr": full_output if not success else "",
            "cpp": cpp_code,
            "tac": tac_code,
            "success": success
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            "error": "Tempo limite do compilador excedido.", "success": False
        }), 500
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e), "success": False}), 500


if __name__ == '__main__':
    # Roda a IDE silenciosamente
    app.run(debug=False, port=5000)
