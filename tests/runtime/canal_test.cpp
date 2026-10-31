#include "minipar_rt.hpp"

#include <cassert>
#include <iostream>

int main(int argc, char** argv) {
    try {
        if (argc < 2) {
            throw std::invalid_argument("Modo de teste ausente.");
        }
        const std::string mode = argv[1];
        if (mode == "server") {
            MiniParChannel channel;
            channel.setTimeout(std::chrono::milliseconds(std::stoi(argv[2])));
            channel.ouvir(std::stoi(argv[3]));

            const auto [integer, floating, text, boolean] =
                channel.receber<std::int64_t, double, std::string, bool>();
            assert(integer == -1234567890123LL);
            assert(std::abs(floating - 3.141592653589793) < 1e-14);
            assert(text == "Olá, MiniPar — UTF-8");
            assert(boolean);
            for (std::int64_t expected = 0; expected < 1000; ++expected) {
                assert(channel.receber<std::int64_t>() == expected);
            }
            channel.enviar("received");
            return 0;
        }
        if (mode == "client") {
            MiniParChannel channel;
            channel.setTimeout(std::chrono::milliseconds(std::stoi(argv[2])));
            bool connected = false;
            for (int attempt = 0; attempt < 50 && !connected; ++attempt) {
                try {
                    channel.conectar("127.0.0.1", std::stoi(argv[3]));
                    connected = true;
                } catch (const std::runtime_error&) {
                    if (attempt == 49) {
                        throw;
                    }
                    std::this_thread::sleep_for(std::chrono::milliseconds(20));
                }
            }
            channel.enviar(
                std::int64_t{-1234567890123LL},
                3.141592653589793,
                std::string("Olá, MiniPar — UTF-8"),
                true
            );
            for (std::int64_t value = 0; value < 1000; ++value) {
                channel.enviar(value);
            }
            assert(channel.receber<std::string>() == "received");
            return 0;
        }
        if (mode == "receive") {
            MiniParChannel channel;
            channel.setTimeout(std::chrono::milliseconds(std::stoi(argv[2])));
            channel.conectar("127.0.0.1", std::stoi(argv[3]));
            (void)channel.receber<std::int64_t>();
            return 0;
        }
        if (mode == "legacy-server") {
            MiniParChannel channel;
            channel.setTimeout(std::chrono::milliseconds(std::stoi(argv[2])));
            channel.ouvir(std::stoi(argv[3]));
            assert(channel.receiveData() == "legacy");
            channel.sendData("ack");
            return 0;
        }
        if (mode == "legacy-client") {
            MiniParChannel channel;
            channel.setTimeout(std::chrono::milliseconds(std::stoi(argv[2])));
            bool connected = false;
            for (int attempt = 0; attempt < 50 && !connected; ++attempt) {
                try {
                    channel.conectar("127.0.0.1", std::stoi(argv[3]));
                    connected = true;
                } catch (const std::runtime_error&) {
                    if (attempt == 49) {
                        throw;
                    }
                    std::this_thread::sleep_for(std::chrono::milliseconds(20));
                }
            }
            channel.sendData("legacy");
            assert(channel.receiveData() == "ack");
            return 0;
        }
        if (mode == "connect") {
            MiniParChannel channel;
            channel.setTimeout(std::chrono::milliseconds(std::stoi(argv[2])));
            channel.conectar("127.0.0.1", std::stoi(argv[3]));
            return 0;
        }
        if (mode == "legacy") {
            MiniParChannel channel("computer_a", "computer_b");
            channel.sendData("legacy");
            return 0;
        }
        throw std::invalid_argument("Modo de teste desconhecido: " + mode);
    } catch (const std::exception& error) {
        std::cerr << "Erro de execucao: " << error.what() << '\n';
        return 1;
    }
}
