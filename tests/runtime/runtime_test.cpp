#include "minipar_rt.hpp"

#include <atomic>
#include <cassert>
#include <chrono>
#include <sstream>

int main(int argc, char** argv) {
    if (argc > 1 && std::string(argv[1]) == "bounds") {
        std::vector<double> values{1.0};
        __minipar_array_at(values, 2);
        return 0;
    }
    if (argc > 1 && std::string(argv[1]) == "division") {
        try {
            __minipar_divide(1, 0);
        } catch (const std::exception& error) {
            std::cerr << "Erro de execucao: " << error.what() << std::endl;
            return 1;
        }
        return 2;
    }
    if (argc > 1 && std::string(argv[1]) == "parallel") {
        const auto start = std::chrono::steady_clock::now();
        minipar_parallel({
            [] { std::this_thread::sleep_for(std::chrono::milliseconds(200)); },
            [] { std::this_thread::sleep_for(std::chrono::milliseconds(200)); },
        });
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - start
        ).count();
        std::cout << elapsed << std::endl;
        return 0;
    }
    if (argc > 1 && std::string(argv[1]) == "parallel-stress") {
        for (int iteration = 0; iteration < 50; ++iteration) {
            minipar_parallel({
                [] { minipar_print("ramo-a", 1); },
                [] { minipar_print(std::string("ramo-b"), 2.0); },
            });
        }
        return 0;
    }
    if (argc > 1 && std::string(argv[1]) == "parallel-exception") {
        std::atomic<bool> other_task_finished{false};
        try {
            minipar_parallel({
                [] { __minipar_divide(1, 0); },
                [&other_task_finished] {
                    std::this_thread::sleep_for(std::chrono::milliseconds(50));
                    other_task_finished = true;
                },
            });
        } catch (const std::exception& error) {
            if (!other_task_finished) {
                return 3;
            }
            std::cerr << "Erro de execucao: " << error.what() << std::endl;
            return 1;
        }
        return 2;
    }

    constexpr double expected_random[] = {
        0.10793783241321232,
        0.52477527946456115,
        0.81862112545344101,
        0.3962752304022551,
        0.76114999817737838,
        0.32933723522784991,
        0.65085451521484861,
        0.48222467931091073,
        0.88703376189201777,
        0.62173242290584951,
    };
    for (double expected : expected_random) {
        assert(std::abs(random_val() - expected) < 1e-15);
    }

    const double uniform = random_uniforme(-2.0, 3.0);
    assert(uniform >= -2.0 && uniform <= 3.0);
    assert(std::abs(std::exp(1.0) - 2.718281828459045) < 1e-12);
    assert(__minipar_max(2, 8, 3) == 8);

    const std::vector<double> values{1.0, 2.0, 3.0};
    assert(__minipar_max(values) == 3.0);
    assert(__minipar_len(values) == 3);
    assert(__minipar_len(std::string("abc")) == 3);
    assert(__minipar_sum(values) == 6.0);

    const double start = agora();
    assert(agora() >= start);
    assert(__minipar_to_int(std::string("42")) == 42);
    assert(__minipar_to_int("42") == 42);
    assert(__minipar_to_float(std::string("2.5")) == 2.5);
    assert(__minipar_to_float("2.5") == 2.5);
    assert(__to_string(42) == "42");
    assert(__minipar_format_float(3.14159, 4) == "3.1416");
    assert(__minipar_concat(std::string("Mini"), "Par") == "MiniPar");
    assert(__minipar_divide(8, 2) == 4);

    auto mutable_values = values;
    __minipar_array_at(mutable_values, 1) = 7.0;
    assert(mutable_values[1] == 7.0);

    std::istringstream input_data("linha de entrada\n");
    auto* previous_input = std::cin.rdbuf(input_data.rdbuf());
    assert(input() == "linha de entrada");
    std::cin.rdbuf(previous_input);

    minipar_print("Máquina de lavar");
    minipar_println("Linha adicional");
    return 0;
}
