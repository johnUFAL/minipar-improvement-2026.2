#include "minipar_rt.hpp"

MiniParChannel::MiniParChannel(std::string address, int channel_port)
    : ip(std::move(address)), port(channel_port) {}

void MiniParChannel::sendData(std::string message) {
    int socket_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (socket_fd < 0) {
        return;
    }

    sockaddr_in server_address{};
    server_address.sin_family = AF_INET;
    server_address.sin_port = htons(port);
    inet_pton(AF_INET, ip.c_str(), &server_address.sin_addr);

    for (int attempt = 0; attempt < 50; ++attempt) {
        if (connect(socket_fd, reinterpret_cast<sockaddr*>(&server_address),
                    sizeof(server_address)) >= 0) {
            send(socket_fd, message.c_str(), message.length(), 0);
            break;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    CLOSE_SOCK(socket_fd);
}

std::string MiniParChannel::receiveData() {
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        return "";
    }

    int option = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR,
               reinterpret_cast<const char*>(&option), sizeof(option));

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port);

    if (bind(server_fd, reinterpret_cast<sockaddr*>(&address),
             sizeof(address)) < 0) {
        CLOSE_SOCK(server_fd);
        return "";
    }
    if (listen(server_fd, 3) < 0) {
        CLOSE_SOCK(server_fd);
        return "";
    }

    int client_fd = accept(server_fd, nullptr, nullptr);
    if (client_fd < 0) {
        CLOSE_SOCK(server_fd);
        return "";
    }

    char buffer[4096]{};
    recv(client_fd, buffer, sizeof(buffer), 0);
    std::string result(buffer);
    CLOSE_SOCK(client_fd);
    CLOSE_SOCK(server_fd);
    return result;
}
