from __future__ import annotations

from pathlib import Path

from tools import rodar_todos


def test_slugify_normalizes_names() -> None:
    assert (
        rodar_todos.slugify("T1 — Calculadora cliente-servidor")
        == "t1_calculadora_cliente_servidor"
    )
    assert (
        rodar_todos.slugify("T8: Avaliação em 4 núcleos")
        == "t8_avalia_o_em_4_n_cleos"
    )


def test_write_index_lists_results_and_screenshots(
    tmp_path: Path,
) -> None:
    results = [
        {
            "id": "t1",
            "name": "Calculadora",
            "elapsed": "1.00s",
            "ok": True,
            "evidence": "terminal/01_t1.txt",
        },
        {
            "id": "t2",
            "name": "Fibonacci",
            "elapsed": "2.00s",
            "ok": False,
            "evidence": "terminal/02_t2.txt",
        },
    ]
    web = tmp_path / "web"
    web.mkdir()
    (web / "01_t1.png").write_bytes(b"png")

    rodar_todos.write_index(results, evidence_dir=tmp_path)

    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "1/2 testes passaram" in text
    assert "terminal/01_t1.txt" in text
    assert "web/01_t1.png" in text
    assert "Pendente de execucao em duas maquinas reais" in text
