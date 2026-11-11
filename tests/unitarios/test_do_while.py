from __future__ import annotations

from components.lexico import Lexer
from components.sintatico.ast import DoWhileStmt
from components.sintatico.c_sintatico import Parser
from components.tac.c_gerador_tac import TACGenerator
from erros.diagnosticos import DiagnosticBag


def _parse(source: str):
    diagnostics = DiagnosticBag(source)
    program = Parser(Lexer(source, diagnostics), diagnostics).parse()
    return program, diagnostics


def _primeiro_do(program) -> DoWhileStmt | None:
    pilha = [program]
    while pilha:
        no = pilha.pop()
        if isinstance(no, DoWhileStmt):
            return no
        pilha.extend(
            valor
            for valor in vars(no).values()
            if hasattr(valor, "__dataclass_fields__")
        )
        for valor in vars(no).values():
            if isinstance(valor, (list, tuple)):
                pilha.extend(
                    item for item in valor if hasattr(item, "__dataclass_fields__")
                )
    return None


def test_do_while_com_chaves_gera_no_da_ast() -> None:
    programa, diagnosticos = _parse(
        "seq {\n    var i = 0;\n    do {\n        i = i + 1;\n    } while (i < 3);\n}\n"
    )

    assert not diagnosticos.has_errors
    assert _primeiro_do(programa) is not None


def test_do_while_por_indentacao() -> None:
    programa, diagnosticos = _parse(
        "SEQ\n    var i = 0\n    do:\n        i = i + 1\n    while i < 3\n"
    )

    assert not diagnosticos.has_errors
    assert _primeiro_do(programa) is not None


def test_do_while_vira_rotulos_no_tac() -> None:
    programa, diagnosticos = _parse(
        "seq {\n    var i = 0;\n    do {\n        i = i + 1;\n    } while (i < 3);\n}\n"
    )

    tac = TACGenerator().generate_text(programa)

    assert not diagnosticos.has_errors
    assert "DO_" in tac and "ENDDO" in tac


def test_do_sem_while_e_erro_sintatico() -> None:
    _, diagnosticos = _parse("seq {\n    do {\n        print(1);\n    }\n}\n")

    assert diagnosticos.has_errors
