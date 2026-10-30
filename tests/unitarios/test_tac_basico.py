from pathlib import Path

from components.lexico import Lexer
from components.sintatico.c_sintatico import Parser
from components.tac import TACExecutor, TACGenerator, imprimir_tac


ROOT = Path(__file__).resolve().parents[2]


def parse(source: str):
    return Parser(Lexer(source)).parse()


def test_quicksort_program_runs_from_ast() -> None:
    source = (ROOT / "programas_teste" / "t07_quicksort_iterativo_tac.mp").read_text(
        encoding="utf-8"
    )
    program = parse(source)
    tac = TACGenerator().generate_text(program)

    variables, output = TACExecutor().execute(tac)

    assert variables["ordenado"] == [5, 12, 33, 61, 98]
    assert output[-1] == "[5, 12, 33, 61, 98]"
    assert "PARTITION_LOOP" not in tac
    assert "call quicksort_iterativo, 1" in tac


def test_recursive_factorial_returns_ten_factorial() -> None:
    program = parse(
        "def factorial(n):\n"
        "    if n <= 1:\n"
        "        return 1\n"
        "    return n * factorial(n - 1)\n"
        "\n"
        "SEQ\n"
        "    result = factorial(10)\n"
    )
    tac = TACGenerator().generate_text(program)

    variables, _ = TACExecutor().execute(tac)

    assert variables["result"] == 3628800
    assert "ret " in tac


def test_for_in_iterable_is_lowered_to_index_loop() -> None:
    program = parse(
        "SEQ\n"
        "    total = 0\n"
        "    for value in [2, 3, 4]:\n"
        "        total = total + value\n"
    )

    variables, _ = TACExecutor().execute(TACGenerator().generate_text(program))

    assert variables["total"] == 9


def test_generation_is_deterministic_and_printable() -> None:
    program = parse("SEQ\n    values = [3, 1]\n    print(values[0])\n")
    generator = TACGenerator()

    first = generator.generate_text(program)
    second = generator.generate_text(program)

    assert first == second
    assert imprimir_tac(first) == first
    assert "t0:list =" in first


def test_executor_supports_input_array_writes_and_typed_temporaries() -> None:
    tac = """values:list = [0]
item:int = input()
values[0] = item
print values[0]
"""

    variables, output = TACExecutor().execute(tac, inputs=[42])

    assert variables["values"] == [42]
    assert output == ["42"]
