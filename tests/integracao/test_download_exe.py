from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

from interfaces.web import api

pytestmark = pytest.mark.skipif(
    shutil.which(os.environ.get("CXX", "g++").strip('"')) is None,
    reason="g++ é necessário para gerar o executável",
)

CODIGO = 'seq {\n    print("ola exe");\n}\n'


def test_baixar_exe_devolve_executavel_funcional(tmp_path) -> None:
    resposta = api.app.test_client().post(
        "/api/baixar-exe",
        json={"code": CODIGO, "filename": "dois_computadores/meu prog.mp"},
    )

    assert resposta.status_code == 200
    extensao = ".exe" if sys.platform == "win32" else ""
    assert (
        f'filename="meu_prog{extensao}"'
        in resposta.headers["Content-Disposition"]
    )
    exe = tmp_path / f"baixado{extensao}"
    exe.write_bytes(resposta.data)
    exe.chmod(0o755)
    saida = subprocess.run(
        [str(exe)], capture_output=True, text=True, timeout=30, check=False
    )
    assert saida.returncode == 0
    assert "ola exe" in saida.stdout


def test_baixar_exe_com_erro_retorna_diagnosticos() -> None:
    resposta = api.app.test_client().post(
        "/api/baixar-exe", json={"code": "seq {\n    print(x);\n}\n"}
    )

    assert resposta.status_code == 422
    assert resposta.get_json()["diagnosticos"]


def test_baixar_exe_valida_entrada() -> None:
    cliente = api.app.test_client()

    assert cliente.post("/api/baixar-exe", json={}).status_code == 400
    assert (
        cliente.post(
            "/api/baixar-exe", json={"code": CODIGO, "optimization_level": "O9"}
        ).status_code
        == 400
    )
