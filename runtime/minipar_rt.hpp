#pragma once

#include <chrono>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <type_traits>
#include <utility>
#include <vector>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#define CLOSE_SOCK closesocket
#else
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>
#define CLOSE_SOCK close
#endif

template<typename T>
std::ostream& operator<<(std::ostream& stream, const std::vector<T>& values);

inline void minipar_init_console() {
#ifdef _WIN32
    SetConsoleOutputCP(CP_UTF8);
#endif
}

inline std::uint32_t& __minipar_random_state() {
    static std::uint32_t state = 123456789u;
    return state;
}

inline std::mutex& __minipar_random_mutex() {
    static std::mutex mutex;
    return mutex;
}

inline double random_val() {
    std::lock_guard<std::mutex> lock(__minipar_random_mutex());
    auto& state = __minipar_random_state();
    state = (state * 1103515245u + 12345u) & 0x7fffffffu;
    return static_cast<double>(state) / 2147483647.0;
}

inline double random_uniforme(double minimum, double maximum) {
    return minimum + (maximum - minimum) * random_val();
}

inline double agora() {
    using clock = std::chrono::steady_clock;
    static const auto start = clock::now();
    return std::chrono::duration<double>(clock::now() - start).count();
}

inline std::string input() {
    std::string value;
    if (!std::getline(std::cin, value)) {
        if (std::cin.eof()) {
            throw std::runtime_error("Fim da entrada ao aguardar uma linha.");
        }
        throw std::runtime_error("Falha ao ler entrada.");
    }
    return value;
}

inline std::string input(const std::string& prompt) {
    std::cout << prompt;
    std::cout.flush();
    return input();
}

inline std::string __minipar_format_float(double value, int precision) {
    if (precision < 0 || precision > 1000) {
        throw std::invalid_argument(
            "A precisao de format_float deve estar entre 0 e 1000."
        );
    }
    std::ostringstream stream;
    stream << std::fixed << std::setprecision(precision) << value;
    return stream.str();
}

template<typename T>
std::string __to_string(const T& value) {
    if constexpr (std::is_same_v<std::decay_t<T>, std::string>) {
        return value;
    } else if constexpr (std::is_same_v<std::decay_t<T>, const char*> ||
                         std::is_same_v<std::decay_t<T>, char*>) {
        return value;
    } else if constexpr (std::is_same_v<std::decay_t<T>, bool>) {
        return value ? "true" : "false";
    } else if constexpr (std::is_integral_v<std::decay_t<T>>) {
        return std::to_string(value);
    } else if constexpr (std::is_floating_point_v<std::decay_t<T>>) {
        std::ostringstream stream;
        stream << std::setprecision(std::numeric_limits<T>::max_digits10) << value;
        return stream.str();
    } else {
        std::ostringstream stream;
        stream << value;
        return stream.str();
    }
}

template<typename Left, typename Right>
std::string __minipar_concat(const Left& left, const Right& right) {
    return __to_string(left) + __to_string(right);
}

inline int __minipar_to_int(const std::string& value) {
    std::size_t parsed = 0;
    const auto result = std::stoi(value, &parsed);
    if (parsed != value.size()) {
        throw std::invalid_argument("Valor invalido para int: " + value);
    }
    return result;
}

inline int __minipar_to_int(const char* value) {
    return __minipar_to_int(std::string(value));
}

template<typename T, std::enable_if_t<std::is_arithmetic_v<T>, int> = 0>
int __minipar_to_int(T value) {
    const auto numeric = static_cast<long double>(value);
    if (!std::isfinite(numeric) ||
        numeric < std::numeric_limits<int>::lowest() ||
        numeric > std::numeric_limits<int>::max()) {
        throw std::out_of_range("Valor fora do intervalo de int.");
    }
    return static_cast<int>(value);
}

inline double __minipar_to_float(const std::string& value) {
    std::size_t parsed = 0;
    const auto result = std::stod(value, &parsed);
    if (parsed != value.size()) {
        throw std::invalid_argument("Valor invalido para float: " + value);
    }
    return result;
}

inline double __minipar_to_float(const char* value) {
    return __minipar_to_float(std::string(value));
}

template<typename T, std::enable_if_t<std::is_arithmetic_v<T>, int> = 0>
double __minipar_to_float(T value) {
    return static_cast<double>(value);
}

template<typename... Values>
void minipar_print(const Values&... values) {
    minipar_init_console();
    bool first = true;
    ((std::cout << (first ? "" : " ") << values, first = false), ...);
    std::cout << std::endl;
}

template<typename... Values>
void minipar_println(const Values&... values) {
    minipar_print(values...);
}

template<typename T>
std::size_t __minipar_len(const T& value) {
    return value.size();
}

template<typename T>
T __minipar_sum(const std::vector<T>& values) {
    return std::accumulate(values.begin(), values.end(), T{});
}

template<typename T>
T __minipar_max(T value) {
    return value;
}

template<typename T>
T __minipar_max(const std::vector<T>& values) {
    if (values.empty()) {
        throw std::invalid_argument("max() nao aceita uma colecao vazia.");
    }
    return *std::max_element(values.begin(), values.end());
}

template<typename First, typename Second, typename... Rest>
auto __minipar_max(First first, Second second, Rest... rest) {
    auto result = first < second ? second : first;
    ((result = result < rest ? rest : result), ...);
    return result;
}

template<typename Left, typename Right>
auto __minipar_divide(Left left, Right right) {
    if (right == 0) {
        std::cerr << "Erro de execucao: divisao por zero." << std::endl;
        std::exit(EXIT_FAILURE);
    }
    return left / right;
}

template<typename Container, typename Index>
decltype(auto) __minipar_array_at(Container& values, Index index) {
    bool invalid = false;
    if constexpr (std::is_floating_point_v<Index>) {
        invalid = !std::isfinite(index) || std::floor(index) != index || index < 0;
    } else if constexpr (std::is_signed_v<Index>) {
        invalid = index < 0;
    }

    if (invalid) {
        std::cerr << "Erro de execucao: indice " << index
                  << " fora dos limites (tamanho " << values.size() << ")."
                  << std::endl;
        std::exit(EXIT_FAILURE);
    }
    const auto converted = static_cast<std::size_t>(index);
    if (converted >= values.size()) {
        std::cerr << "Erro de execucao: indice " << index
                  << " fora dos limites (tamanho " << values.size() << ")."
                  << std::endl;
        std::exit(EXIT_FAILURE);
    }
    return values[converted];
}

template<typename Container, typename Index, typename Value>
void __minipar_array_set(Container& values, Index index, Value&& value) {
    bool invalid = false;
    if constexpr (std::is_floating_point_v<Index>) {
        invalid = !std::isfinite(index) || std::floor(index) != index || index < 0;
    } else if constexpr (std::is_signed_v<Index>) {
        invalid = index < 0;
    }

    if (invalid) {
        std::cerr << "Erro de execucao: indice " << index
                  << " invalido para atribuicao em array." << std::endl;
        std::exit(EXIT_FAILURE);
    }
    const auto converted = static_cast<std::size_t>(index);
    if (converted >= values.size()) {
        values.resize(converted + 1);
    }
    values[converted] = std::forward<Value>(value);
}

inline std::vector<double> __parse_ints(const std::string& text) {
    std::vector<double> result;
    std::istringstream stream(text);
    double value;
    while (stream >> value) {
        result.push_back(value);
    }
    return result;
}

inline std::vector<int> __minipar_range(int end) {
    std::vector<int> values;
    for (int i = 0; i < end; ++i) {
        values.push_back(i);
    }
    return values;
}

inline std::vector<int> __minipar_range(int start, int end) {
    std::vector<int> values;
    for (int i = start; i < end; ++i) {
        values.push_back(i);
    }
    return values;
}

template<typename T>
auto __array_pop(std::vector<T>& values) {
    if (values.empty()) {
        throw std::out_of_range("pop() nao pode ser usado em uma lista vazia.");
    }
    auto value = values.back();
    values.pop_back();
    return value;
}

template<typename T>
std::ostream& operator<<(std::ostream& stream, const std::vector<T>& values) {
    stream << "[";
    for (size_t i = 0; i < values.size(); ++i) {
        stream << values[i];
        if (i + 1 != values.size()) {
            stream << ", ";
        }
    }
    return stream << "]";
}

template<typename T>
auto __make_matrix(int rows, int cols, T initial_value) {
    if (rows < 0 || cols < 0) {
        throw std::invalid_argument("Dimensoes da matriz nao podem ser negativas.");
    }
    using ValueType = std::conditional_t<
        std::is_same_v<std::decay_t<T>, const char*>, std::string, T>;
    return std::vector<std::vector<ValueType>>(
        rows, std::vector<ValueType>(cols, initial_value));
}

class MiniParChannel {
public:
    std::string ip;
    int port;

    MiniParChannel(std::string ip, int port);
    void sendData(std::string message);
    std::string receiveData();
};

void minipar_parallel(const std::vector<std::function<void()>>& tasks);
