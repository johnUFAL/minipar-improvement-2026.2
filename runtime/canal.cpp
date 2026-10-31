#include "minipar_rt.hpp"

#include <cerrno>
#include <fstream>
#include <map>
#include <sstream>
#include <string>

#ifdef _WIN32
#include <windows.h>
#else
#include <fcntl.h>
#include <netdb.h>
#include <sys/time.h>
#endif

namespace {

struct MiniParHost {
    std::string address;
    int port;
};

struct MiniParConfiguration {
    std::string hosts_path = "minipar.hosts";
    std::string role;
};

MiniParConfiguration& configuration() {
    static MiniParConfiguration value;
    return value;
}

std::string trim(const std::string& value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) {
        return "";
    }
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::map<std::string, MiniParHost> load_hosts() {
    const std::string& path = configuration().hosts_path;
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error(
            "Nao foi possivel abrir o arquivo de hosts '" + path +
            "'. Use --hosts <arquivo> ou crie minipar.hosts."
        );
    }

    std::map<std::string, MiniParHost> hosts;
    std::string line;
    std::size_t line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        const auto comment = line.find('#');
        if (comment != std::string::npos) {
            line.erase(comment);
        }
        line = trim(line);
        if (line.empty()) {
            continue;
        }

        const auto equals = line.find('=');
        if (equals == std::string::npos) {
            throw std::runtime_error(
                "Entrada invalida em '" + path + "', linha " +
                std::to_string(line_number) + "; esperado nome = host:porta."
            );
        }
        const std::string name = trim(line.substr(0, equals));
        const std::string endpoint = trim(line.substr(equals + 1));
        const auto colon = endpoint.rfind(':');
        if (name.empty() || endpoint.empty() || colon == std::string::npos ||
            colon == 0 || colon + 1 == endpoint.size()) {
            throw std::runtime_error(
                "Entrada invalida em '" + path + "', linha " +
                std::to_string(line_number) + "; esperado nome = host:porta."
            );
        }
        const std::string address = trim(endpoint.substr(0, colon));
        const std::string port_text = trim(endpoint.substr(colon + 1));
        std::size_t parsed = 0;
        int port = 0;
        try {
            port = std::stoi(port_text, &parsed);
        } catch (const std::exception&) {
            throw std::runtime_error(
                "Porta invalida em '" + path + "', linha " +
                std::to_string(line_number) + "."
            );
        }
        if (parsed != port_text.size() || port < 1 || port > 65535 ||
            address.empty()) {
            throw std::runtime_error(
                "Host ou porta invalida em '" + path + "', linha " +
                std::to_string(line_number) + "."
            );
        }
        if (!hosts.emplace(name, MiniParHost{address, port}).second) {
            throw std::runtime_error(
                "Nome de computador duplicado em '" + path + "', linha " +
                std::to_string(line_number) + ": " + name + "."
            );
        }
    }
    if (input.bad()) {
        throw std::runtime_error("Falha ao ler o arquivo de hosts '" + path + "'.");
    }
    return hosts;
}

std::string valid_host_names(const std::map<std::string, MiniParHost>& hosts) {
    std::ostringstream result;
    bool first = true;
    for (const auto& [name, _] : hosts) {
        result << (first ? "" : ", ") << name;
        first = false;
    }
    return first ? "(nenhum configurado)" : result.str();
}

void open_logical_channel(
    MiniParChannel& channel,
    const std::string& first_name,
    const std::string& second_name
) {
    const auto hosts = load_hosts();
    const std::string& role = configuration().role;
    const auto local = hosts.find(role);
    if (role.empty() || local == hosts.end()) {
        const std::string detail = role.empty()
            ? "Informe --como <nome>."
            : "Papel '" + role + "' inexistente.";
        throw std::runtime_error(
            detail + " Nomes validos: " + valid_host_names(hosts) + "."
        );
    }
    if (role == first_name) {
        const auto remote = hosts.find(second_name);
        if (remote == hosts.end()) {
            throw std::runtime_error(
                "Computador '" + second_name + "' do canal nao encontrado. "
                "Nomes validos: " + valid_host_names(hosts) + "."
            );
        }
        channel.conectar(remote->second.address, remote->second.port);
    } else if (role == second_name) {
        channel.ouvir(local->second.port);
    } else {
        throw std::runtime_error(
            "Papel '" + role + "' nao participa do canal '" + first_name +
            "'-'" + second_name + "'. Use --como " + first_name + " ou --como " +
            second_name + "."
        );
    }
}

#ifdef _WIN32
constexpr MiniParNativeSocket invalid_socket = INVALID_SOCKET;
using SocketLength = int;

void initialize_sockets() {
    class SocketRuntime {
    public:
        SocketRuntime() {
            WSADATA data{};
            if (WSAStartup(MAKEWORD(2, 2), &data) != 0) {
                throw std::runtime_error("Falha ao inicializar Winsock.");
            }
        }

        ~SocketRuntime() {
            WSACleanup();
        }
    };
    static SocketRuntime runtime;
    (void)runtime;
}

std::string socket_error(const std::string& operation) {
    return operation + " (Winsock " + std::to_string(WSAGetLastError()) + ").";
}

bool is_timeout_error() {
    const int error = WSAGetLastError();
    return error == WSAETIMEDOUT || error == WSAEWOULDBLOCK;
}

bool is_connection_closed_error() {
    const int error = WSAGetLastError();
    return error == WSAECONNRESET || error == WSAECONNABORTED ||
           error == WSAESHUTDOWN;
}

void set_socket_timeout(MiniParNativeSocket socket, std::chrono::milliseconds timeout) {
    const DWORD value = static_cast<DWORD>(timeout.count());
    if (setsockopt(socket, SOL_SOCKET, SO_RCVTIMEO,
                   reinterpret_cast<const char*>(&value), sizeof(value)) == SOCKET_ERROR ||
        setsockopt(socket, SOL_SOCKET, SO_SNDTIMEO,
                   reinterpret_cast<const char*>(&value), sizeof(value)) == SOCKET_ERROR) {
        throw std::runtime_error(socket_error("Falha ao configurar timeout do socket"));
    }
}
#else
constexpr MiniParNativeSocket invalid_socket = -1;
using SocketLength = socklen_t;

void initialize_sockets() {}

std::string socket_error(const std::string& operation) {
    return operation + " (" + std::strerror(errno) + ").";
}

bool is_timeout_error() {
    return errno == EAGAIN || errno == EWOULDBLOCK || errno == ETIMEDOUT;
}

bool is_connection_closed_error() {
    return errno == ECONNRESET || errno == ECONNABORTED;
}

void set_socket_timeout(MiniParNativeSocket socket, std::chrono::milliseconds timeout) {
#ifdef SO_NOSIGPIPE
    int no_sigpipe = 1;
    if (setsockopt(socket, SOL_SOCKET, SO_NOSIGPIPE, &no_sigpipe, sizeof(no_sigpipe)) < 0) {
        throw std::runtime_error(socket_error("Falha ao configurar socket"));
    }
#endif
    timeval value{};
    value.tv_sec = static_cast<decltype(value.tv_sec)>(timeout.count() / 1000);
    value.tv_usec = static_cast<decltype(value.tv_usec)>(
        (timeout.count() % 1000) * 1000
    );
    if (setsockopt(socket, SOL_SOCKET, SO_RCVTIMEO, &value, sizeof(value)) < 0 ||
        setsockopt(socket, SOL_SOCKET, SO_SNDTIMEO, &value, sizeof(value)) < 0) {
        throw std::runtime_error(socket_error("Falha ao configurar timeout do socket"));
    }
}
#endif

bool wait_for_socket(
    MiniParNativeSocket socket,
    bool writable,
    std::chrono::milliseconds timeout
) {
    fd_set sockets;
    FD_ZERO(&sockets);
    FD_SET(socket, &sockets);
    timeval value{};
    value.tv_sec = static_cast<decltype(value.tv_sec)>(timeout.count() / 1000);
    value.tv_usec = static_cast<decltype(value.tv_usec)>(
        (timeout.count() % 1000) * 1000
    );
    const int result = select(
#ifdef _WIN32
        0,
#else
        socket + 1,
#endif
        writable ? nullptr : &sockets,
        writable ? &sockets : nullptr,
        nullptr,
        &value
    );
    if (result == 0) {
        return false;
    }
    if (result < 0) {
        throw std::runtime_error(socket_error("Falha aguardando atividade no socket"));
    }
    return true;
}

void set_nonblocking(MiniParNativeSocket socket, bool enabled) {
#ifdef _WIN32
    u_long mode = enabled ? 1UL : 0UL;
    if (ioctlsocket(socket, FIONBIO, &mode) == SOCKET_ERROR) {
        throw std::runtime_error(socket_error("Falha ao configurar socket"));
    }
#else
    const int flags = fcntl(socket, F_GETFL, 0);
    if (flags < 0 || fcntl(
            socket, F_SETFL, enabled ? (flags | O_NONBLOCK) : (flags & ~O_NONBLOCK)
        ) < 0) {
        throw std::runtime_error(socket_error("Falha ao configurar socket"));
    }
#endif
}

bool connect_in_time(
    MiniParNativeSocket socket,
    const sockaddr* address,
    SocketLength address_length,
    std::chrono::milliseconds timeout
) {
    set_nonblocking(socket, true);
    const int result = connect(socket, address, address_length);
    if (result == 0) {
        set_nonblocking(socket, false);
        return true;
    }
#ifdef _WIN32
    const int connect_error = WSAGetLastError();
    if (connect_error != WSAEWOULDBLOCK && connect_error != WSAEINPROGRESS) {
        set_nonblocking(socket, false);
        return false;
    }
#else
    if (errno != EINPROGRESS) {
        set_nonblocking(socket, false);
        return false;
    }
#endif
    if (!wait_for_socket(socket, true, timeout)) {
        set_nonblocking(socket, false);
        return false;
    }
    int error = 0;
    SocketLength error_length = sizeof(error);
    if (getsockopt(socket, SOL_SOCKET, SO_ERROR,
#ifdef _WIN32
                   reinterpret_cast<char*>(&error),
#else
                   &error,
#endif
                   &error_length) != 0) {
        set_nonblocking(socket, false);
        return false;
    }
    set_nonblocking(socket, false);
    return error == 0;
}

void send_exact(
    MiniParNativeSocket socket,
    const std::uint8_t* data,
    std::size_t size
) {
    std::size_t offset = 0;
    while (offset < size) {
#ifdef _WIN32
        const int sent = send(
            socket,
            reinterpret_cast<const char*>(data + offset),
            static_cast<int>(std::min<std::size_t>(
                size - offset, static_cast<std::size_t>(std::numeric_limits<int>::max())
            )),
            0
        );
        if (sent == SOCKET_ERROR) {
#else
        const auto sent = send(
            socket,
            data + offset,
            size - offset,
#ifdef MSG_NOSIGNAL
            MSG_NOSIGNAL
#else
            0
#endif
        );
        if (sent < 0) {
#endif
            if (is_timeout_error()) {
                throw std::runtime_error("Timeout ao enviar dados pelo canal.");
            }
            throw std::runtime_error(socket_error("Falha ao enviar dados pelo canal"));
        }
        if (sent == 0) {
            throw std::runtime_error("Conexao encerrada durante o envio pelo canal.");
        }
        offset += static_cast<std::size_t>(sent);
    }
}

void receive_exact(
    MiniParNativeSocket socket,
    std::uint8_t* data,
    std::size_t size
) {
    std::size_t offset = 0;
    while (offset < size) {
#ifdef _WIN32
        const int received = recv(
            socket,
            reinterpret_cast<char*>(data + offset),
            static_cast<int>(std::min<std::size_t>(
                size - offset, static_cast<std::size_t>(std::numeric_limits<int>::max())
            )),
            0
        );
        if (received == SOCKET_ERROR) {
#else
        const auto received = recv(socket, data + offset, size - offset, 0);
        if (received < 0) {
#endif
            if (is_timeout_error()) {
                throw std::runtime_error("Timeout ao receber dados pelo canal.");
            }
            if (is_connection_closed_error()) {
                throw std::runtime_error(
                    "Conexao encerrada no meio de uma mensagem do canal."
                );
            }
            throw std::runtime_error(socket_error("Falha ao receber dados pelo canal"));
        }
        if (received == 0) {
            throw std::runtime_error(
                "Conexao encerrada no meio de uma mensagem do canal."
            );
        }
        offset += static_cast<std::size_t>(received);
    }
}

std::uint32_t read_u32(const std::array<std::uint8_t, 4>& bytes) {
    return (static_cast<std::uint32_t>(bytes[0]) << 24) |
           (static_cast<std::uint32_t>(bytes[1]) << 16) |
           (static_cast<std::uint32_t>(bytes[2]) << 8) |
           static_cast<std::uint32_t>(bytes[3]);
}

void append_u32(std::vector<std::uint8_t>& output, std::uint32_t value) {
    output.push_back(static_cast<std::uint8_t>(value >> 24));
    output.push_back(static_cast<std::uint8_t>(value >> 16));
    output.push_back(static_cast<std::uint8_t>(value >> 8));
    output.push_back(static_cast<std::uint8_t>(value));
}

void validate_port(int port) {
    if (port < 1 || port > 65535) {
        throw std::invalid_argument("A porta do canal deve estar entre 1 e 65535.");
    }
}

}  // namespace

MiniParChannel::MiniParChannel() : socket_(invalid_socket) {}

MiniParChannel::MiniParChannel(std::string host, int port)
    : MiniParChannel() {
    conectar(host, port);
}

MiniParChannel::MiniParChannel(std::string first_host, std::string second_host)
    : MiniParChannel() {
    if (first_host.empty() || second_host.empty()) {
        throw std::invalid_argument("Os computadores do canal nao podem ser vazios.");
    }
    open_logical_channel(*this, first_host, second_host);
}

MiniParChannel::~MiniParChannel() {
    close();
}

void MiniParChannel::setTimeout(std::chrono::milliseconds timeout) {
    if (timeout.count() <= 0) {
        throw std::invalid_argument("O timeout do canal deve ser maior que zero.");
    }
    if (socket_ != invalid_socket) {
        set_socket_timeout(socket_, timeout);
    }
    timeout_ = timeout;
}

void MiniParChannel::close() noexcept {
    if (socket_ != invalid_socket) {
        CLOSE_SOCK(socket_);
        socket_ = invalid_socket;
    }
}

void MiniParChannel::ouvir(int port) {
    validate_port(port);
    if (socket_ != invalid_socket) {
        throw std::logic_error("O canal ja possui uma conexao ativa.");
    }
    initialize_sockets();

    addrinfo hints{};
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_flags = AI_PASSIVE;
    addrinfo* addresses = nullptr;
    const std::string service = std::to_string(port);
    const int lookup = getaddrinfo(nullptr, service.c_str(), &hints, &addresses);
    if (lookup != 0) {
#ifdef _WIN32
        throw std::runtime_error(
            "Falha ao resolver endereco local (Winsock " +
            std::to_string(lookup) + ")."
        );
#else
        throw std::runtime_error(
            std::string("Falha ao resolver endereco local: ") + gai_strerror(lookup)
        );
#endif
    }

    MiniParNativeSocket listener = invalid_socket;
    for (addrinfo* current = addresses; current != nullptr; current = current->ai_next) {
        listener = socket(current->ai_family, current->ai_socktype, current->ai_protocol);
        if (listener == invalid_socket) {
            continue;
        }
        int reuse = 1;
        setsockopt(listener, SOL_SOCKET, SO_REUSEADDR,
#ifdef _WIN32
                   reinterpret_cast<const char*>(&reuse),
#else
                   &reuse,
#endif
                   sizeof(reuse));
        if (bind(listener, current->ai_addr,
                 static_cast<SocketLength>(current->ai_addrlen)) == 0 &&
            listen(listener, 1) == 0) {
            break;
        }
        CLOSE_SOCK(listener);
        listener = invalid_socket;
    }
    freeaddrinfo(addresses);
    if (listener == invalid_socket) {
        throw std::runtime_error(socket_error("Nao foi possivel abrir a porta do canal"));
    }

    try {
        if (!wait_for_socket(listener, false, timeout_)) {
            throw std::runtime_error("Timeout aguardando conexao no canal.");
        }
        socket_ = accept(listener, nullptr, nullptr);
        if (socket_ == invalid_socket) {
            throw std::runtime_error(socket_error("Falha ao aceitar conexao do canal"));
        }
        set_socket_timeout(socket_, timeout_);
    } catch (...) {
        CLOSE_SOCK(listener);
        close();
        throw;
    }
    CLOSE_SOCK(listener);
}

void MiniParChannel::conectar(const std::string& host, int port) {
    validate_port(port);
    if (host.empty()) {
        throw std::invalid_argument("O host do canal nao pode ser vazio.");
    }
    if (socket_ != invalid_socket) {
        throw std::logic_error("O canal ja possui uma conexao ativa.");
    }
    initialize_sockets();

    addrinfo hints{};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    addrinfo* addresses = nullptr;
    const std::string service = std::to_string(port);
    const int lookup = getaddrinfo(host.c_str(), service.c_str(), &hints, &addresses);
    if (lookup != 0) {
#ifdef _WIN32
        throw std::runtime_error(
            "Falha ao resolver host do canal (Winsock " +
            std::to_string(lookup) + ")."
        );
#else
        throw std::runtime_error(
            std::string("Falha ao resolver host do canal: ") + gai_strerror(lookup)
        );
#endif
    }

    for (addrinfo* current = addresses; current != nullptr; current = current->ai_next) {
        MiniParNativeSocket candidate = socket(
            current->ai_family, current->ai_socktype, current->ai_protocol
        );
        if (candidate == invalid_socket) {
            continue;
        }
        if (connect_in_time(
                candidate,
                current->ai_addr,
                static_cast<SocketLength>(current->ai_addrlen),
                timeout_
            )) {
            socket_ = candidate;
            break;
        }
        CLOSE_SOCK(candidate);
    }
    freeaddrinfo(addresses);
    if (socket_ == invalid_socket) {
        throw std::runtime_error(
            "Nao foi possivel conectar ao canal (conexao recusada ou timeout)."
        );
    }
    set_socket_timeout(socket_, timeout_);
}

void minipar_init(int argc, char** argv) {
    MiniParConfiguration parsed;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--como" || argument == "--hosts") {
            if (index + 1 >= argc || argv[index + 1][0] == '\0') {
                throw std::invalid_argument(
                    "A flag " + argument + " exige um argumento."
                );
            }
            const std::string value = argv[++index];
            if (argument == "--como") {
                parsed.role = value;
            } else {
                parsed.hosts_path = value;
            }
        } else {
            throw std::invalid_argument(
                "Argumento desconhecido: " + argument +
                ". Opcoes: --como <nome> --hosts <arquivo>."
            );
        }
    }
    configuration() = std::move(parsed);
}

void MiniParChannel::sendData(std::string message) {
    enviar(message);
}

std::string MiniParChannel::receiveData() {
    const auto fields = receiveFrame();
    if (fields.size() != 1) {
        throw std::runtime_error(
            "receiveData espera uma mensagem com exatamente um campo."
        );
    }
    return minipar_channel_detail::decode<std::string>(fields[0]);
}

void MiniParChannel::sendFrame(
    const std::vector<minipar_channel_detail::Field>& fields
) {
    if (fields.empty() || fields.size() > max_field_count) {
        throw std::invalid_argument("Numero de campos invalido para mensagem do canal.");
    }
    std::vector<std::uint8_t> frame;
    append_u32(frame, static_cast<std::uint32_t>(fields.size()));
    for (const auto& field : fields) {
        if (field.bytes.size() > max_field_size ||
            field.bytes.size() > std::numeric_limits<std::uint32_t>::max()) {
            throw std::length_error("Campo excede o tamanho maximo do canal.");
        }
        if (frame.size() > max_frame_size - 5 ||
            field.bytes.size() > max_frame_size - frame.size() - 5) {
            throw std::length_error("Mensagem excede o tamanho maximo do canal.");
        }
        frame.push_back(static_cast<std::uint8_t>(field.type));
        append_u32(frame, static_cast<std::uint32_t>(field.bytes.size()));
        frame.insert(frame.end(), field.bytes.begin(), field.bytes.end());
    }

    std::lock_guard<std::mutex> lock(send_mutex_);
    if (socket_ == invalid_socket) {
        throw std::runtime_error("Canal sem conexao: chame ouvir() ou conectar() primeiro.");
    }
    send_exact(socket_, frame.data(), frame.size());
}

std::vector<minipar_channel_detail::Field> MiniParChannel::receiveFrame() {
    std::lock_guard<std::mutex> lock(receive_mutex_);
    if (socket_ == invalid_socket) {
        throw std::runtime_error("Canal sem conexao: chame ouvir() ou conectar() primeiro.");
    }
    std::array<std::uint8_t, 4> count_bytes{};
    receive_exact(socket_, count_bytes.data(), count_bytes.size());
    const std::uint32_t count = read_u32(count_bytes);
    if (count == 0 || count > max_field_count) {
        throw std::runtime_error("Numero de campos invalido na mensagem do canal.");
    }

    std::vector<minipar_channel_detail::Field> fields;
    fields.reserve(count);
    std::size_t frame_size = count_bytes.size();
    for (std::uint32_t i = 0; i < count; ++i) {
        std::uint8_t type_byte = 0;
        receive_exact(socket_, &type_byte, 1);
        if (type_byte < static_cast<std::uint8_t>(minipar_channel_detail::Type::integer) ||
            type_byte > static_cast<std::uint8_t>(minipar_channel_detail::Type::boolean)) {
            throw std::runtime_error("Tipo de campo desconhecido na mensagem do canal.");
        }
        std::array<std::uint8_t, 4> size_bytes{};
        receive_exact(socket_, size_bytes.data(), size_bytes.size());
        const std::uint32_t size = read_u32(size_bytes);
        if (size > max_field_size) {
            throw std::runtime_error("Campo excede o tamanho maximo da mensagem do canal.");
        }
        if (frame_size > max_frame_size - 5 ||
            size > max_frame_size - frame_size - 5) {
            throw std::runtime_error("Mensagem excede o tamanho maximo do canal.");
        }
        frame_size += 5 + size;
        minipar_channel_detail::Field field{
            static_cast<minipar_channel_detail::Type>(type_byte),
            std::vector<std::uint8_t>(size),
        };
        if (size != 0) {
            receive_exact(socket_, field.bytes.data(), size);
        }
        fields.push_back(std::move(field));
    }
    return fields;
}
