from __future__ import annotations

import os
import shutil

import pytest

from interfaces.web import api

pytestmark = pytest.mark.skipif(
    shutil.which(os.environ.get("CXX", "g++").strip('"')) is None,
    reason="g++ é necessário para executar os programas",
)


def _executar(codigo: str) -> dict:
    return api.app.test_client().post("/api/executar", json={"code": codigo}).get_json()


def test_do_while_executa_o_corpo_ao_menos_uma_vez() -> None:
    resultado = _executar(
        'SEQ\n    var i = 10\n    do:\n        print(i)\n        i = i + 1\n    while i < 3\n    print("fim", i)\n'
    )

    assert resultado["success"]
    assert resultado["stdout"].split() == ["10", "fim", "11"]


def test_do_while_respeita_break_e_continue() -> None:
    resultado = _executar(
        "seq {\n    var i = 0;\n    do {\n        i = i + 1;\n"
        "        if (i == 2) { continue; }\n        if (i == 4) { break; }\n"
        "        print(i);\n    } while (i < 10);\n}\n"
    )

    assert resultado["success"]
    assert resultado["stdout"].split() == ["1", "3"]


def test_for_in_range_executa() -> None:
    resultado = _executar("SEQ\n    for x in range(3):\n        print(x)\n")

    assert resultado["success"]
    assert resultado["stdout"].split() == ["0", "1", "2"]
