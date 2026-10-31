from components.codegen.c_gerador_cpp import CppCodeGenerator


def test_cpp_generator_translates_handwritten_tac_without_ast() -> None:
    tac = """goto MAIN
func factorial(n:int) -> int:
# source: 4
if n <= 1 goto BASE
t0:int = n - 1
param t0
t1:int = call factorial, 1
t2:int = n * t1
ret t2
BASE:
ret 1
endfunc
MAIN:
param 5
t3:int = call factorial, 1
print t3
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert '#include "minipar_rt.hpp"' in generated
    assert "std::int64_t factorial(" in generated
    assert "goto BASE;" in generated
    assert "// MiniPar line 4" in generated
    assert "std::int64_t t0{};" in generated
    assert "minipar_print(t3);" in generated


def test_cpp_generator_lowers_fork_branches_to_runtime_threads() -> None:
    tac = """counter:int = 0
par_begin 1
fork worker, simulated, 0, BRANCH
join worker
goto END
BRANCH:
counter = counter + 1
print 'parallel'
join worker
END:
par_end
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert "_minipar_tasks.emplace_back([&]() {" in generated
    assert "minipar_parallel(_minipar_tasks);" in generated
    assert "_minipar_local_2_counter = counter;" in generated
    assert "counter = _minipar_result_2_counter;" in generated
    assert "goto BRANCH;" not in generated


def test_cpp_generator_uses_runtime_helpers_for_string_addition_and_division() -> None:
    tac = """t0:string = 'valor='
t1:string = t0 + 10
t2:float = 1 / 2
print t1
print t2
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert 't1 = __minipar_concat(t0, 10);' in generated
    assert "t2 = __minipar_divide(1, 2);" in generated
    assert CppCodeGenerator._cpp_type("Canal*") == "std::shared_ptr<MiniParChannel>"
