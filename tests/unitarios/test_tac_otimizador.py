from pathlib import Path
import re

import pytest

from components.lexico import Lexer
from components.sintatico.c_sintatico import Parser
from components.tac import TACExecutor, TACGenerator, TACOptimizer


ROOT = Path(__file__).resolve().parents[2]


def parse(source: str):
    return Parser(Lexer(source)).parse()


def observable_execution(tac: str):
    variables, output = TACExecutor().execute(tac)
    return (
        {name: value for name, value in variables.items() if not re.fullmatch(r"t\d+", name)},
        output,
    )


def test_folds_constants_propagates_copies_and_removes_dead_temporaries() -> None:
    tac = "t0:int = 2 + 3\nt1:int = t0\nprint t1\n"

    optimized = TACOptimizer().optimize(tac)

    assert optimized == "print 5\n"
    assert observable_execution(tac) == observable_execution(optimized)


def test_removes_jump_to_following_label() -> None:
    tac = "goto NEXT\nNEXT:\nprint 42\n"

    optimized = TACOptimizer().optimize(tac)

    assert "goto NEXT" not in optimized
    assert observable_execution(tac) == observable_execution(optimized)


def test_preserves_effectful_and_non_scalar_temporary_assignments() -> None:
    tac = """t0:list = [1, 2]
t1 = input()
t2 = call side_effect, 0
print t0
"""

    optimized = TACOptimizer().optimize(tac)

    assert "t0:list = [1, 2]" in optimized
    assert "t1 = input()" in optimized
    assert "t2 = call side_effect, 0" in optimized


def test_preserves_unused_expression_that_would_raise() -> None:
    tac = "t0 = 1 / 0\nprint 7\n"

    optimized = TACOptimizer().optimize(tac)

    assert "t0 = 1 / 0" in optimized
    with pytest.raises(ZeroDivisionError):
        TACExecutor().execute(tac)
    with pytest.raises(ZeroDivisionError):
        TACExecutor().execute(optimized)


def test_optimized_quicksort_tac_has_identical_execution_result() -> None:
    source = (
        ROOT / "programas_teste" / "t07_quicksort_iterativo_tac.mp"
    ).read_text(encoding="utf-8")
    tac = TACGenerator().generate_text(parse(source))
    optimized = TACOptimizer().optimize(tac)

    assert TACExecutor().execute(tac) == TACExecutor().execute(optimized)
    assert observable_execution(tac) == observable_execution(optimized)


def test_instruction_count_records_reduction_from_three_to_one() -> None:
    original = "t0 = 2 + 3\nt1 = t0\nprint t1\n"
    optimized = TACOptimizer().optimize(original)

    assert TACOptimizer.instruction_count(original) == 3
    assert TACOptimizer.instruction_count(optimized) == 1
