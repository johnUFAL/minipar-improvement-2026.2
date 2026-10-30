from pathlib import Path

from components.lexico import Lexer
from components.sintatico.c_sintatico import Parser
from components.tac import TACExecutor, TACGenerator


ROOT = Path(__file__).resolve().parents[2]


def parse(source: str):
    parser = Parser(Lexer(source))
    program = parser.parse()
    assert not parser.diagnostics, parser.diagnostics
    return program


def test_neuronio_runs_in_tac_and_converges_after_51_iterations() -> None:
    source = (ROOT / "programas_teste" / "t03_neuronio.mp").read_text(
        encoding="utf-8"
    )
    tac = TACGenerator().generate_text(parse(source))

    _, output = TACExecutor().execute(tac)

    iteration_line = output.index("Iteracoes totais:")
    assert output[iteration_line + 1] == "51"
    assert " = alloc 8" in tac
    assert " = getfield " in tac
    assert "setfield " in tac
    assert "call Neuronio_ativacao, 2" in tac


def test_parallel_factorial_and_fibonacci_have_distinct_tac_branches() -> None:
    source = (ROOT / "programas_teste" / "t02_fatorial_fibonacci_par.mp").read_text(
        encoding="utf-8"
    )
    tac = TACGenerator().generate_text(parse(source))

    _, output = TACExecutor().execute(tac)

    assert "par_begin 2" in tac
    branches = [
        line.split(",")[-1].strip()
        for line in tac.splitlines()
        if line.startswith("fork ")
    ]
    assert len(branches) == 2
    assert branches[0] != branches[1]
    assert "120" in output
    assert all(str(value) in output for value in (0, 1, 2, 3, 5, 8, 13))


def test_calculator_uses_send_recv_and_simulated_fifo_channels() -> None:
    source = (ROOT / "programas_teste" / "t01_calculadora.mp").read_text(
        encoding="utf-8"
    )
    tac = TACGenerator().generate_text(parse(source))

    _, output = TACExecutor().execute(tac, inputs=["+", "2", "3"])

    assert "send requisicao, operacao" in tac
    assert "send requisicao, operando1" in tac
    assert "t10 = recv requisicao" in tac
    assert "t19 = recv resposta" in tac
    result_line = output.index("Resultado:")
    assert output[result_line + 1] == "5"


def test_fork_core_and_host_targets_are_lowered_and_joined() -> None:
    program = parse(
        "SEQ\n"
        "    fork worker_core em core(2):\n"
        "        print(\"core\")\n"
        "    fork worker_host em host(\"computador_2\"):\n"
        "        print(\"host\")\n"
        "    join worker_core, worker_host\n"
    )
    tac = TACGenerator().generate_text(program)

    _, output = TACExecutor().execute(tac)

    assert "fork worker_core, core, 2," in tac
    assert "fork worker_host, host, 'computador_2'," in tac
    assert "join worker_core, worker_host" in tac
    assert sorted(output) == ["core", "host"]


def test_inherited_fields_methods_and_constructor_are_lowered() -> None:
    program = parse(
        "class Base {\n"
        "    var amount = 1;\n"
        "    func init(value) {\n"
        "        this.amount = value;\n"
        "    }\n"
        "    func doubled() {\n"
        "        return this.amount * 2;\n"
        "    }\n"
        "}\n"
        "class Derived extends Base {\n"
        "    var extra = 3;\n"
        "    func total() {\n"
        "        return this.amount + this.extra;\n"
        "    }\n"
        "}\n"
        "seq {\n"
        "    var obj = new Derived(4);\n"
        "    print(obj.doubled());\n"
        "    print(obj.total());\n"
        "}\n"
    )
    tac = TACGenerator().generate_text(program)

    _, output = TACExecutor().execute(tac)

    assert "call Base_init, 2" in tac
    assert "call Base_doubled, 1" in tac
    assert output == ["8", "7"]
