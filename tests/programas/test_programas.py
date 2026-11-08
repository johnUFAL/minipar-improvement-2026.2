from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from scripts import run_testes_2026_2 as runner

pytestmark = pytest.mark.slow


@pytest.mark.parametrize("test_id", ("t2", "t3", "t4", "t5", "t6", "t7"))
def test_programa_de_aceitacao(test_id: str) -> None:
    compiler = os.environ.get("CXX", "g++").strip('"')
    if shutil.which(compiler) is None:
        pytest.skip(f"Compilador C++ nao encontrado: {compiler}")

    test = next(item for item in runner.TESTS if item["id"] == test_id)
    with tempfile.TemporaryDirectory(prefix=f"minipar-{test_id}-") as directory:
        result, _ = runner.run_local(test, Path(directory), timeout=180)

    checks = runner.check_local(test, result)
    failures = [label for label, passed in checks if not passed]
    assert not failures, "; ".join(failures)
