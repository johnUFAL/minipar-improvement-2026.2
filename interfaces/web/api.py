import glob
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

from components.lexico.c_lexico import Lexer
from components.codegen.c_gerador_cpp import CppCodeGenerator
from components.codegen.driver_gcc import DriverGCC
from components.semantico.c_semantico import SemanticAnalyzer
from components.sintatico.c_sintatico import Parser, _ParseError
from components.sintatico.ast import Program
from components.tac import TACOptimizer
from components.tac.c_gerador_tac import TACGenerator
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
EXECUTION_TIMEOUT_SECONDS = 30
EXECUTION_OUTPUT_LIMIT_BYTES = 1024 * 1024
MAX_EXECUTION_INPUT_BYTES = 1024 * 1024

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _serialize_diagnostic(diagnostic: Any) -> dict[str, object]:
    phase = getattr(diagnostic.phase, "value", diagnostic.phase)
    severity = getattr(diagnostic.severity, "value", diagnostic.severity)
    return {
        "phase": phase,
        "message": diagnostic.message,
        "line": diagnostic.line,
        "column": diagnostic.column,
        "length": diagnostic.length,
        "severity": severity,
        "header": diagnostic.header,
    }


def _compile_phases(source: str) -> dict[str, object]:
    token_diagnostics = DiagnosticBag(source)
    tokens = Lexer(source, token_diagnostics).tokenize()

    diagnostics = DiagnosticBag(source)
    lexer = Lexer(source, diagnostics)
    try:
        program = Parser(lexer, diagnostics).parse()
    except _ParseError:
        program = Program()
    analyzer = SemanticAnalyzer(diagnostics)
    if not diagnostics.has_errors:
        analyzer.analyze(program)

    serialized_diagnostics: list[dict[str, object]] = []
    seen_diagnostics: set[tuple[object, ...]] = set()
    for diagnostic in (*token_diagnostics.diagnostics, *diagnostics.diagnostics):
        serialized = _serialize_diagnostic(diagnostic)
        key = tuple(serialized.values())
        if key not in seen_diagnostics:
            serialized_diagnostics.append(serialized)
            seen_diagnostics.add(key)

    tac = ""
    cpp = ""
    if not diagnostics.has_errors:
        try:
            tac = TACGenerator().generate_text(program)
            cpp = CppCodeGenerator().generate_source(tac)
        except (NotImplementedError, ValueError) as error:
            diagnostics.error("generation", str(error))
            serialized_diagnostics.append(
                _serialize_diagnostic(diagnostics.diagnostics[-1])
            )

    return {
        "tokens": [
            {
                "type": token.type.name,
                "lexeme": token.lexeme,
                "line": token.line,
                "column": token.column,
                "value": token.value,
            }
            for token in tokens
        ],
        "ast": program.para_dict(),
        "tabela_simbolos": analyzer.symbol_table.export(),
        "tac": tac,
        "cpp": cpp,
        "diagnosticos": serialized_diagnostics,
        "success": not diagnostics.has_errors,
    }


def _run_limited(
    command: list[str],
    *,
    input_text: str = "",
    timeout: float = EXECUTION_TIMEOUT_SECONDS,
    output_limit: int = EXECUTION_OUTPUT_LIMIT_BYTES,
) -> dict[str, object]:
    """Executa um processo, drenando pipes e limitando bytes retidos em memória."""
    started_at = time.monotonic()
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=PROJECT_ROOT,
    )
    output_lock = threading.Lock()
    output_size = 0
    output_exceeded = threading.Event()
    captured: dict[str, list[bytes]] = {"stdout": [], "stderr": []}

    def drain(stream_name: str, stream: Any) -> None:
        nonlocal output_size
        while True:
            chunk = stream.read(8192)
            if not chunk:
                return
            with output_lock:
                remaining = max(0, output_limit - output_size)
                captured[stream_name].append(chunk[:remaining])
                output_size += min(len(chunk), remaining)
                exceeded = len(chunk) > remaining
            if exceeded and not output_exceeded.is_set():
                output_exceeded.set()
                try:
                    process.kill()
                except OSError:
                    pass

    def write_input() -> None:
        if process.stdin is None:
            return
        try:
            process.stdin.write(input_text.encode("utf-8"))
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    readers = [
        threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    writer = threading.Thread(target=write_input, daemon=True)
    writer.start()

    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            process.kill()
        except OSError:
            pass
        process.wait()

    writer.join()
    for reader in readers:
        reader.join()

    return {
        "stdout": b"".join(captured["stdout"]).decode("utf-8", errors="replace"),
        "stderr": b"".join(captured["stderr"]).decode("utf-8", errors="replace"),
        "exit_code": process.returncode,
        "tempo": time.monotonic() - started_at,
        "timed_out": timed_out,
        "output_limited": output_exceeded.is_set(),
    }


def _execution_input(data: dict[str, object]) -> tuple[str | None, str | None]:
    inputs = data.get("inputs", [])
    if not isinstance(inputs, list) or any(
        not isinstance(value, (str, int, float, bool)) for value in inputs
    ):
        return None, "O campo 'inputs' deve ser uma lista de valores simples."
    input_text = "\n".join(str(value) for value in inputs)
    if inputs:
        input_text += "\n"
    if len(input_text.encode("utf-8")) > MAX_EXECUTION_INPUT_BYTES:
        return None, "As entradas excedem o limite permitido."
    return input_text, None


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


@app.route('/api/compilar', methods=['POST'])
def compile_phases():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("code"), str):
        return jsonify({
            "error": "O campo 'code' deve ser texto.", "success": False
        }), 400
    return jsonify(_compile_phases(data["code"]))


@app.route('/api/executar', methods=['POST'])
def execute_code():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("code"), str):
        return jsonify({
            "error": "O campo 'code' deve ser texto.", "success": False
        }), 400

    input_text, input_error = _execution_input(data)
    if input_error:
        return jsonify({"error": input_error, "success": False}), 400

    compilation = _compile_phases(data["code"])
    if not compilation["success"]:
        return jsonify({
            "stdout": "",
            "stderr": "\n".join(
                diagnostic["header"] for diagnostic in compilation["diagnosticos"]
            ),
            "exit_code": None,
            "tempo": 0.0,
            "timed_out": False,
            "output_limited": False,
            "success": False,
            "diagnosticos": compilation["diagnosticos"],
        })

    with tempfile.TemporaryDirectory(prefix="minipar-web-") as work_dir:
        work_path = Path(work_dir)
        cpp_path = work_path / "program.cpp"
        executable_path = work_path / "program"
        cpp_path.write_text(str(compilation["cpp"]), encoding="utf-8")
        compiled = DriverGCC().compile(cpp_path, executable_path)
        if not compiled:
            return jsonify({
                "stdout": "",
                "stderr": (
                    "Falha ao compilar o programa C++. Consulte o log do servidor "
                    "para os detalhes do compilador."
                ),
                "exit_code": None,
                "tempo": 0.0,
                "timed_out": False,
                "output_limited": False,
                "success": False,
                "diagnosticos": compilation["diagnosticos"],
            })

        executable = executable_path
        if sys.platform == "win32":
            executable = executable.with_suffix(".exe")
        try:
            result = _run_limited([str(executable)], input_text=input_text or "")
        except OSError as error:
            return jsonify({
                "stdout": "",
                "stderr": f"Falha ao iniciar o programa: {error}",
                "exit_code": None,
                "tempo": 0.0,
                "timed_out": False,
                "output_limited": False,
                "success": False,
                "diagnosticos": compilation["diagnosticos"],
            })

    result["success"] = (
        result["exit_code"] == 0
        and not result["timed_out"]
        and not result["output_limited"]
    )
    result["diagnosticos"] = compilation["diagnosticos"]
    if result["timed_out"]:
        result["stderr"] += "\nTempo limite de execução excedido."
    if result["output_limited"]:
        result["stderr"] += "\nLimite de saída excedido."
    return jsonify(result)


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
    optimize_tac = data.get('optimize_tac', False)

    if not isinstance(code, str) or not isinstance(filename, str):
        return jsonify({
            "error": "Os campos 'code' e 'filename' devem ser texto.", "success": False
        }), 400
    if not isinstance(user_inputs, list):
        return jsonify({
            "error": "O campo 'inputs' deve ser uma lista.", "success": False
        }), 400
    if not isinstance(optimize_tac, bool):
        return jsonify({
            "error": "O campo 'optimize_tac' deve ser booleano.", "success": False
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
                    execution = _run_limited(
                        [os.path.abspath(exe_path)],
                        input_text=stdin_data,
                        timeout=EXECUTION_TIMEOUT_SECONDS,
                    )
                    full_output += str(execution["stdout"])
                    if execution["stderr"]:
                        full_output += "\n[ERRO NA EXECUÇÃO]:\n" + str(
                            execution["stderr"]
                        )
                    record_execution_output(str(execution["stdout"]) or "")
                    if execution["timed_out"]:
                        full_output += "\n[ERRO] Tempo limite de execução excedido."
                        success = False
                    if execution["output_limited"]:
                        full_output += "\n[ERRO] Limite de saída excedido."
                        success = False
                    if execution["exit_code"] != 0:
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
        optimized_tac = TACOptimizer().optimize(tac_code) if optimize_tac else ""

        return jsonify({
            "stdout": full_output if success else "",
            "stderr": full_output if not success else "",
            "cpp": cpp_code,
            "tac": tac_code,
            "tac_optimized": optimized_tac,
            "tac_instruction_counts": {
                "original": TACOptimizer.instruction_count(tac_code),
                "optimized": TACOptimizer.instruction_count(optimized_tac),
            } if optimize_tac else None,
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
