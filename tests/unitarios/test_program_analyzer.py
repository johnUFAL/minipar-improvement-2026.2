from pathlib import Path

from interfaces.program_analyzer import get_program_spec

ROOT = Path(__file__).resolve().parents[2]
PROGRAMS_DIR = ROOT / "programas_teste"


def test_split_pair_declares_roles_and_automatic_execution() -> None:
    for filename in (
        "t01_calculadora_cliente.mp",
        "t01_calculadora_servidor.mp",
    ):
        spec = get_program_spec(
            str(PROGRAMS_DIR / "t01_multiterminal" / filename)
        )
        multi = spec["multi_computer"]

        assert multi is not None
        assert multi["required"] is True
        assert multi["auto_execution"] is True
        assert multi["roles"] == ["computador_1", "computador_2"]
        assert multi["role_modes"] == {
            "computador_1": "conecta",
            "computador_2": "escuta",
        }
        assert multi["channels"][0]["nome"] == "dados"


def test_combined_example_is_now_a_compatibility_stub() -> None:
    spec = get_program_spec(str(PROGRAMS_DIR / "t01_calculadora.mp"))

    assert spec["multi_computer"] is None
    assert spec["channel_count"] == 0


def test_function_form_channel_is_detected_but_not_automatic(tmp_path: Path) -> None:
    source = tmp_path / "fixo.mp"
    source.write_text(
        'seq {\n'
        '    var canal = c_channel("127.0.0.1", 5101);\n'
        '    send(canal, "oi");\n'
        '    receive(canal);\n'
        '}\n',
        encoding="utf-8",
    )

    spec = get_program_spec(str(source))
    multi = spec["multi_computer"]

    assert multi is not None
    assert multi["auto_execution"] is False
    assert multi["channels"][0]["tipo"] == "funcao"
    assert multi["channels"][0]["host"] == "127.0.0.1"
    assert multi["channels"][0]["porta"] == 5101


def test_comments_and_strings_do_not_create_channels(tmp_path: Path) -> None:
    source = tmp_path / "comentarios.mp"
    source.write_text(
        '# c_channel dados computador_1 computador_2\n'
        'seq {\n'
        '    print("c_channel dentro de string");\n'
        '}\n',
        encoding="utf-8",
    )

    spec = get_program_spec(str(source))

    assert spec["channel_count"] == 0
    assert spec["multi_computer"] is None


def test_multiple_declarations_disable_automatic_execution(tmp_path: Path) -> None:
    source = tmp_path / "multiplos.mp"
    source.write_text(
        "c_channel dados computador_1 computador_2\n"
        "c_channel resposta computador_1 computador_2\n"
        "seq {\n"
        "    send(dados, 1);\n"
        "    receive(resposta);\n"
        "}\n",
        encoding="utf-8",
    )

    spec = get_program_spec(str(source))
    multi = spec["multi_computer"]

    assert multi is not None
    assert multi["auto_execution"] is False
    assert len(multi["channels"]) == 2
