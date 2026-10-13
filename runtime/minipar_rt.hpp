#pragma once

#include <chrono>
#include <cmath>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <thread>
#include <type_traits>
#include <utility>
#include <vector>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#define CLOSE_SOCK closesocket
#else
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>
#define CLOSE_SOCK close
#endif

inline double random_val() {
    return static_cast<double>(std::rand()) / RAND_MAX;
}

inline std::string input() {
    std::string value;
    std::getline(std::cin, value);
    return value;
}

inline std::string input(const std::string& prompt) {
    std::cout << prompt;
    return input();
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
        return T{};
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
std::string __to_string(const T& value) {
    if constexpr (std::is_constructible_v<std::string, T>) {
        return std::string(value);
    } else {
        return std::to_string(value);
    }
}

template<typename T>
auto __make_matrix(int rows, int cols, T initial_value) {
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
