#include "minipar_rt.hpp"

#include <cstdlib>
#include <map>

namespace {

std::map<std::string, MiniParTaskHandler>& task_handlers() {
    static std::map<std::string, MiniParTaskHandler> handlers;
    return handlers;
}

std::chrono::milliseconds remote_timeout() {
    const char* configured = std::getenv("MINIPAR_TIMEOUT_MS");
    if (configured == nullptr || configured[0] == '\0') {
        return std::chrono::milliseconds(5000);
    }

    std::size_t parsed_characters = 0;
    long long value = 0;
    try {
        value = std::stoll(configured, &parsed_characters);
    } catch (const std::exception&) {
        throw std::invalid_argument(
            "MINIPAR_TIMEOUT_MS deve ser um inteiro positivo."
        );
    }
    if (parsed_characters != std::string(configured).size() || value <= 0) {
        throw std::invalid_argument(
            "MINIPAR_TIMEOUT_MS deve ser um inteiro positivo."
        );
    }
    return std::chrono::milliseconds(value);
}

std::vector<minipar_channel_detail::Field> failure_response(
    const std::string& message
) {
    return {
        minipar_channel_detail::encode(false),
        minipar_channel_detail::encode(message),
    };
}

}

void minipar_register_task(std::string name, MiniParTaskHandler handler) {
    if (name.empty() || !handler) {
        throw std::invalid_argument("Registro de subtarefa remota invalido.");
    }
    if (!task_handlers().emplace(std::move(name), std::move(handler)).second) {
        throw std::invalid_argument("Nome de subtarefa remota duplicado.");
    }
}

std::vector<minipar_channel_detail::Field> minipar_remote_call(
    const std::string& host,
    const std::string& task,
    const std::vector<minipar_channel_detail::Field>& arguments
) {
    const auto [address, port] = minipar_resolve_host(host);
    MiniParChannel channel;
    channel.setTimeout(remote_timeout());
    channel.conectar(address, port);

    std::vector<minipar_channel_detail::Field> request;
    request.reserve(arguments.size() + 1);
    request.push_back(minipar_channel_detail::encode(task));
    request.insert(request.end(), arguments.begin(), arguments.end());
    channel.sendFields(request);

    const auto response = channel.receiveFields();
    if (response.size() < 2) {
        throw std::runtime_error(
            "Resposta incompleta do worker para a subtarefa '" + task + "'."
        );
    }
    const bool succeeded =
        minipar_channel_detail::decode<bool>(response[0]);
    const std::string message =
        minipar_channel_detail::decode<std::string>(response[1]);
    if (!succeeded) {
        throw std::runtime_error(
            "Falha na subtarefa remota '" + task + "': " + message
        );
    }
    return {response.begin() + 2, response.end()};
}

bool minipar_run_worker_if_requested() {
    if (!minipar_worker_requested()) {
        return false;
    }

    for (;;) {
        MiniParChannel channel;
        channel.setTimeout(std::chrono::hours(24));
        channel.ouvir(minipar_worker_port());
        try {
            const auto request = channel.receiveFields();
            if (request.empty()) {
                throw std::runtime_error("Pedido remoto sem nome de subtarefa.");
            }
            const std::string task =
                minipar_channel_detail::decode<std::string>(request.front());
            const auto handler = task_handlers().find(task);
            if (handler == task_handlers().end()) {
                channel.sendFields(failure_response(
                    "Subtarefa desconhecida: " + task + "."
                ));
                continue;
            }

            const std::vector<minipar_channel_detail::Field> arguments(
                request.begin() + 1, request.end()
            );
            std::vector<minipar_channel_detail::Field> response;
            try {
                const auto results = handler->second(arguments);
                response = {
                    minipar_channel_detail::encode(true),
                    minipar_channel_detail::encode(std::string{}),
                };
                response.insert(response.end(), results.begin(), results.end());
            } catch (const std::exception& error) {
                response = failure_response(error.what());
            } catch (...) {
                response = failure_response(
                    "Erro nao identificado durante a subtarefa."
                );
            }
            channel.sendFields(response);
        } catch (const std::exception& error) {
            std::cerr << "Erro ao atender pedido remoto: "
                      << error.what() << std::endl;
        }
    }
}
