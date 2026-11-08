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

    assert "_minipar_tasks.emplace_back([=, &_minipar_result_2_counter]() mutable {" in generated
    assert (
        "minipar_parallel("
        "_minipar_tasks, _minipar_cores, _minipar_task_names);"
    ) in generated
    assert "_minipar_local_2_counter = counter;" in generated
    assert "counter = _minipar_result_2_counter;" in generated
    assert "goto BRANCH;" not in generated


def test_cpp_generator_maps_string_and_file_builtins_to_runtime() -> None:
    tac = """texto:string = 'abc'
param texto
param 0
t0:char = call char_at, 2
print t0
param texto
param 0
param 2
t1:string = call substring, 3
print t1
param texto
t2:int = call len, 1
print t2
param 1.5
param 2
t3:string = call format_float, 2
print t3
param 'saida.txt'
param texto
t4:int = call write_file, 2
print t4
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert "t0 = __minipar_char_at(texto, 0);" in generated
    assert "t1 = __minipar_substring(texto, 0, 2);" in generated
    assert "t2 = __minipar_len(texto);" in generated
    assert "t3 = __minipar_format_float(1.5, 2);" in generated
    assert 't4 = __minipar_write_file("saida.txt", texto);' in generated
    assert 'std::string t0{};' in generated


def test_cpp_generator_represents_char_as_one_character_string() -> None:
    tac = """letra:char = 'x'
param letra
t0:bool = call is_alpha, 1
print t0
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert '[[maybe_unused]] std::string letra{};' in generated
    assert 'letra = "x";' in generated
    assert "t0 = __minipar_is_alpha(letra);" in generated


def test_cpp_generator_concatenates_string_literal_followed_by_operator() -> None:
    tac = """t0:string = '[' + name
t1:string = t0 + '] fim'
print t1
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert '__minipar_concat("[", name)' in generated
    assert '__minipar_concat(t0, "] fim")' in generated


def test_cpp_generator_updates_property_arrays_in_place() -> None:
    tac = """goto MAIN
MAIN:
t0:list = getfield self, 0
t0[1] = 42
goto END
END:
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert "__minipar_array_set(self->field_0, 1, 42);" in generated
    assert "__minipar_array_set(t0, 1, 42);" not in generated


def test_cpp_generator_maps_parse_ints_to_runtime_helper() -> None:
    tac = """goto MAIN
MAIN:
param texto
t0:list = call parse_ints, 1
goto END
END:
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert "t0 = __parse_ints(texto);" in generated


def test_cpp_generator_maps_input_validation_builtins() -> None:
    tac = """goto MAIN
MAIN:
param texto
t0:list<string> = call dividir, 1
param texto
t1:bool = call eh_inteiro, 1
goto END
END:
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert "t0 = __minipar_dividir(texto);" in generated
    assert "t1 = __minipar_eh_inteiro(texto);" in generated


def test_cpp_generator_preserves_fork_core_target() -> None:
    tac = """par_begin 1
fork worker, core, requested_core, BRANCH
join worker
goto END
BRANCH:
print 'running'
join worker
END:
par_end
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert (
        "_minipar_cores.push_back(requested_core);"
    ) in generated
    assert '_minipar_task_names.emplace_back("worker");' in generated
    assert (
        "minipar_parallel("
        "_minipar_tasks, _minipar_cores, _minipar_task_names);"
    ) in generated


def test_cpp_generator_copies_collection_inputs_into_parallel_branches() -> None:
    tac = """values:list<int> = [1, 2]
par_begin 1
fork worker, simulated, 0, BRANCH
join worker
goto END
BRANCH:
values[0] = 9
join worker
END:
par_end
print values[0]
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert "[=, &_minipar_result_2_values]() mutable {" in generated
    assert "auto _minipar_local_2_values = values;" in generated
    assert "__minipar_array_set(_minipar_local_2_values, 0, 9);" in generated
    assert "values = _minipar_result_2_values;" in generated


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


def test_cpp_generator_preserves_text_send_and_typed_channel_send() -> None:
    tac = """send legacy, 42
send_typed typed, 42, true
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert "legacy->sendData(__to_string(42));" in generated
    assert "typed->enviar(42, true);" in generated


def test_cpp_generator_infers_var_parameter_from_numeric_call() -> None:
    tac = """goto MAIN
func derivada_sigmoid(saida:var) -> int:
t0 = saida * (1 - saida)
ret t0
endfunc
MAIN:
valor:float = 0.5
param valor
resultado = call derivada_sigmoid, 1
print resultado
"""

    generated = CppCodeGenerator._generate_cpp(tac)

    assert "std::int64_t derivada_sigmoid([[maybe_unused]] double saida);" in generated
    assert "std::shared_ptr<var>" not in generated
