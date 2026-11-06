"""Segunda interface Web do MiniPar 2026.2 (didatica).

Execute com:
    python -m interfaces.web2.app

A porta padrao e 5001 e pode ser alterada com MINIPAR_WEB2_PORT.
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from . import service

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR / "templates"),
    static_folder=str(FRONTEND_DIR / "static"),
)


def _error(message: str, status: int = 400):
    return jsonify({"success": False, "error": message}), status


def _source_from_request() -> str | None:
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("code"), str):
        return None
    return data["code"]


@app.get("/")
def index():
    return render_template(
        "index.html",
        web1_url=os.environ.get("MINIPAR_WEB1_URL", "http://127.0.0.1:5000"),
        port=os.environ.get("MINIPAR_WEB2_PORT", "5001"),
    )


@app.get("/api/exemplos")
def exemplos():
    return jsonify({"success": True, "exemplos": service.list_examples()})


@app.get("/api/exemplo/<name>")
def exemplo(name: str):
    source = service.read_example(name)
    if source is None:
        return _error("Exemplo nao encontrado.", 404)
    return jsonify({"success": True, "code": source})


@app.post("/api/analisar")
def analisar():
    source = _source_from_request()
    if source is None:
        return _error("O campo 'code' deve ser texto.")
    return jsonify(service.analyze(source))


@app.post("/api/compilar")
def compilar():
    data = request.get_json(silent=True)
    source = _source_from_request()
    if source is None:
        return _error("O campo 'code' deve ser texto.")
    optimization = str(data.get("optimization", "O2")).upper()
    if optimization not in {"O0", "O1", "O2", "O3"}:
        return _error("Nivel de otimizacao invalido.")
    return jsonify(service.compile_for_download(source, optimization))


@app.post("/api/executar")
def executar():
    data = request.get_json(silent=True)
    source = _source_from_request()
    if source is None:
        return _error("O campo 'code' deve ser texto.")
    input_text = data.get("input", "")
    if not isinstance(input_text, str):
        return _error("O campo 'input' deve ser texto.")
    optimization = str(data.get("optimization", "O2")).upper()
    if optimization not in {"O0", "O1", "O2", "O3"}:
        return _error("Nivel de otimizacao invalido.")
    return jsonify(service.execute(source, input_text, optimization))


@app.get("/api/artefato/<token>")
def artefato(token: str):
    path = service.artifact_path(token)
    if path is None:
        return _error("Executavel expirado ou inexistente.", 404)
    return send_file(path, as_attachment=True, download_name=path.name)


@app.post("/api/gerar_arm")
def gerar_arm():
    return jsonify(service.generate_arm())


@app.get("/api/arm/<name>")
def baixar_arm(name: str):
    path = service.arm_file(name)
    if path is None:
        return _error("Arquivo .arm nao encontrado.", 404)
    return send_file(path, as_attachment=True, download_name=name)


@app.get("/api/ambiente")
def ambiente():
    return jsonify({"success": True, **service.environment_info()})


@app.get("/health")
def health():
    return jsonify({"success": True, "service": "minipar-web2"})


def main() -> None:
    host = os.environ.get("MINIPAR_WEB2_HOST", "127.0.0.1")
    port = int(os.environ.get("MINIPAR_WEB2_PORT", "5001"))
    print(f"MiniPar Didatico disponivel em http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
