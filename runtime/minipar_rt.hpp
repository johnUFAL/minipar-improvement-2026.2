#pragma once

#include <chrono>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
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
#include <tuple>
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

#ifdef _WIN32
using MiniParNativeSocket = SOCKET;
#else
using MiniParNativeSocket = int;
#endif

namespace minipar_channel_detail {

enum class Type : std::uint8_t {
    integer = 1,
    floating = 2,
    string = 3,
    boolean = 4,
};

struct Field {
    Type type;
    std::vector<std::uint8_t> bytes;
};

inline void append_u32(std::vector<std::uint8_t>& output, std::uint32_t value) {
    output.push_back(static_cast<std::uint8_t>(value >> 24));
    output.push_back(static_cast<std::uint8_t>(value >> 16));
    output.push_back(static_cast<std::uint8_t>(value >> 8));
    output.push_back(static_cast<std::uint8_t>(value));
}

inline void append_u64(std::vector<std::uint8_t>& output, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8) {
        output.push_back(static_cast<std::uint8_t>(value >> shift));
    }
}

inline std::uint64_t read_u64(const std::vector<std::uint8_t>& bytes) {
    std::uint64_t value = 0;
    for (std::uint8_t byte : bytes) {
        value = (value << 8) | byte;
    }
    return value;
}

inline Field encode(bool value) {
    return {Type::boolean, {static_cast<std::uint8_t>(value ? 1 : 0)}};
}

template<typename T, std::enable_if_t<
    std::is_integral_v<T> && !std::is_same_v<std::decay_t<T>, bool>, int> = 0>
Field encode(T value) {
    if constexpr (std::is_unsigned_v<T>) {
        if (value > static_cast<T>(std::numeric_limits<std::int64_t>::max())) {
            throw std::out_of_range("Inteiro fora do intervalo suportado pelo canal.");
        }
    }
    const auto signed_value = static_cast<std::int64_t>(value);
    std::vector<std::uint8_t> bytes;
    append_u64(bytes, static_cast<std::uint64_t>(signed_value));
    return {Type::integer, std::move(bytes)};
}

template<typename T, std::enable_if_t<std::is_floating_point_v<T>, int> = 0>
Field encode(T value) {
    const double wire_value = static_cast<double>(value);
    std::uint64_t bits = 0;
    static_assert(sizeof(bits) == sizeof(wire_value), "double deve ter 64 bits");
    std::memcpy(&bits, &wire_value, sizeof(bits));
    std::vector<std::uint8_t> bytes;
    append_u64(bytes, bits);
    return {Type::floating, std::move(bytes)};
}

inline Field encode(const std::string& value) {
    return {
        Type::string,
        std::vector<std::uint8_t>(value.begin(), value.end()),
    };
}

inline Field encode(const char* value) {
    if (value == nullptr) {
        throw std::invalid_argument("Nao e possivel enviar uma string nula.");
    }
    return encode(std::string(value));
}

template<typename T>
T decode(const Field& field) {
    if constexpr (std::is_same_v<T, std::string>) {
        if (field.type != Type::string) {
            throw std::runtime_error("Tipo recebido pelo canal nao corresponde a string.");
        }
        return std::string(field.bytes.begin(), field.bytes.end());
    } else if constexpr (std::is_same_v<T, bool>) {
        if (field.type != Type::boolean || field.bytes.size() != 1 ||
            field.bytes[0] > 1) {
            throw std::runtime_error("Campo bool invalido recebido pelo canal.");
        }
        return field.bytes[0] == 1;
    } else if constexpr (std::is_integral_v<T>) {
        if (field.type != Type::integer || field.bytes.size() != 8) {
            throw std::runtime_error("Tipo recebido pelo canal nao corresponde a int.");
        }
        const auto bits = read_u64(field.bytes);
        std::int64_t value = 0;
        std::memcpy(&value, &bits, sizeof(value));
        if constexpr (std::is_unsigned_v<T>) {
            if (value < 0 ||
                static_cast<std::uint64_t>(value) >
                    static_cast<std::uint64_t>(std::numeric_limits<T>::max())) {
                throw std::out_of_range("Inteiro recebido fora do intervalo do tipo destino.");
            }
        } else if (value < static_cast<std::int64_t>(std::numeric_limits<T>::lowest()) ||
                   value > static_cast<std::int64_t>(std::numeric_limits<T>::max())) {
            throw std::out_of_range("Inteiro recebido fora do intervalo do tipo destino.");
        }
        return static_cast<T>(value);
    } else if constexpr (std::is_floating_point_v<T>) {
        if (field.type != Type::floating || field.bytes.size() != 8) {
            throw std::runtime_error("Tipo recebido pelo canal nao corresponde a float.");
        }
        const std::uint64_t bits = read_u64(field.bytes);
        double value = 0;
        std::memcpy(&value, &bits, sizeof(value));
        return static_cast<T>(value);
    } else {
        static_assert(!sizeof(T), "Tipo nao suportado pelo canal MiniPar.");
    }
}

}  // namespace minipar_channel_detail

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
    MiniParChannel();
    MiniParChannel(std::string host, int port);
    MiniParChannel(std::string first_host, std::string second_host);
    ~MiniParChannel();
    MiniParChannel(const MiniParChannel&) = delete;
    MiniParChannel& operator=(const MiniParChannel&) = delete;

    void ouvir(int port);
    void conectar(const std::string& host, int port);
    void setTimeout(std::chrono::milliseconds timeout);
    void close() noexcept;

    template<typename... Values>
    void enviar(const Values&... values) {
        static_assert(sizeof...(Values) > 0, "Uma mensagem deve conter campos.");
        std::vector<minipar_channel_detail::Field> fields;
        fields.reserve(sizeof...(Values));
        (fields.push_back(minipar_channel_detail::encode(values)), ...);
        sendFrame(fields);
    }

    template<typename... Types>
    auto receber() {
        static_assert(sizeof...(Types) > 0, "Informe os tipos esperados.");
        const auto fields = receiveFrame();
        if (fields.size() != sizeof...(Types)) {
            throw std::runtime_error("Numero de campos recebido pelo canal inesperado.");
        }
        return receiveValues<Types...>(fields, std::index_sequence_for<Types...>{});
    }

    void sendData(std::string message);
    std::string receiveData();

private:
    static constexpr std::size_t max_field_size = 16 * 1024 * 1024;
    static constexpr std::size_t max_frame_size = 64 * 1024 * 1024;
    static constexpr std::uint32_t max_field_count = 1024;
    MiniParNativeSocket socket_;
    std::chrono::milliseconds timeout_{5000};
    std::mutex send_mutex_;
    std::mutex receive_mutex_;

    void sendFrame(const std::vector<minipar_channel_detail::Field>& fields);
    std::vector<minipar_channel_detail::Field> receiveFrame();

    template<typename... Types, std::size_t... Indices>
    static auto receiveValues(
        const std::vector<minipar_channel_detail::Field>& fields,
        std::index_sequence<Indices...>
    ) {
        if constexpr (sizeof...(Types) == 1) {
            using Value = std::tuple_element_t<0, std::tuple<Types...>>;
            return minipar_channel_detail::decode<Value>(fields[0]);
        } else {
            return std::make_tuple(
                minipar_channel_detail::decode<Types>(fields[Indices])...
            );
        }
    }
};

void minipar_parallel(const std::vector<std::function<void()>>& tasks);
