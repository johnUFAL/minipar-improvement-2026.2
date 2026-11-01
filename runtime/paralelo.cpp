#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include "minipar_rt.hpp"

#include <cerrno>
#include <cstdlib>
#include <cstring>

#ifndef _WIN32
#include <pthread.h>
#include <sched.h>
#endif

namespace {

std::mutex& diagnostic_mutex() {
    static std::mutex mutex;
    return mutex;
}

void warn(const std::string& message) {
    std::lock_guard<std::mutex> lock(diagnostic_mutex());
    std::cerr << "Aviso: " << message << std::endl;
}

std::vector<unsigned int> available_cpus(std::string& error) {
    std::vector<unsigned int> cpus;
#ifdef _WIN32
    DWORD_PTR process_mask = 0;
    DWORD_PTR system_mask = 0;
    if (!GetProcessAffinityMask(
            GetCurrentProcess(), &process_mask, &system_mask
        )) {
        error = "nao foi possivel consultar a afinidade de CPU do processo: "
            + std::to_string(GetLastError());
        return cpus;
    }
    for (unsigned int cpu = 0; cpu < sizeof(DWORD_PTR) * 8; ++cpu) {
        if ((process_mask & (static_cast<DWORD_PTR>(1) << cpu)) != 0) {
            cpus.push_back(cpu);
        }
    }
#elif defined(__linux__)
    cpu_set_t allowed_cpus;
    CPU_ZERO(&allowed_cpus);
    if (sched_getaffinity(0, sizeof(allowed_cpus), &allowed_cpus) != 0) {
        error = "nao foi possivel consultar a afinidade de CPU: "
            + std::string(std::strerror(errno));
        return cpus;
    }
    for (unsigned int cpu = 0; cpu < CPU_SETSIZE; ++cpu) {
        if (CPU_ISSET(cpu, &allowed_cpus)) {
            cpus.push_back(cpu);
        }
    }
#else
    const unsigned int count = std::thread::hardware_concurrency();
    for (unsigned int cpu = 0; cpu < count; ++cpu) {
        cpus.push_back(cpu);
    }
    if (cpus.empty()) {
        error = "numero de CPUs disponiveis desconhecido";
    }
#endif
    if (cpus.empty() && error.empty()) {
        error = "nenhuma CPU disponivel foi encontrada";
    }
    return cpus;
}

bool set_thread_affinity(unsigned int cpu, std::string& error) {
#ifdef _WIN32
    const DWORD_PTR mask = static_cast<DWORD_PTR>(1) << cpu;
    if (SetThreadAffinityMask(GetCurrentThread(), mask) == 0) {
        error = "SetThreadAffinityMask falhou: "
            + std::to_string(GetLastError());
        return false;
    }
    return true;
#elif defined(__linux__)
    cpu_set_t selected_cpu;
    CPU_ZERO(&selected_cpu);
    CPU_SET(cpu, &selected_cpu);
    const int result = pthread_setaffinity_np(
        pthread_self(), sizeof(selected_cpu), &selected_cpu
    );
    if (result != 0) {
        error = "pthread_setaffinity_np falhou: "
            + std::string(std::strerror(result));
        return false;
    }
    return true;
#else
    (void)cpu;
    error = "afinidade de CPU nao e suportada nesta plataforma";
    return false;
#endif
}

std::string current_cpu() {
#ifdef _WIN32
    return std::to_string(GetCurrentProcessorNumber());
#elif defined(__linux__)
    const int cpu = sched_getcpu();
    return cpu < 0 ? "desconhecido" : std::to_string(cpu);
#else
    return "desconhecido";
#endif
}

bool trace_cores_enabled() {
    const char* value = std::getenv("MINIPAR_TRACE_CORES");
    return value != nullptr && value[0] != '\0' && std::string(value) != "0";
}

}

void minipar_parallel(
    const std::vector<std::function<void()>>& tasks,
    const std::vector<std::int64_t>& core_indices,
    const std::vector<std::string>& task_names
) {
    if (!core_indices.empty() && core_indices.size() != tasks.size()) {
        throw std::invalid_argument(
            "Numero de destinos core diferente do numero de tarefas."
        );
    }
    if (!task_names.empty() && task_names.size() != tasks.size()) {
        throw std::invalid_argument(
            "Numero de nomes diferente do numero de tarefas."
        );
    }

    std::vector<unsigned int> cpus;
    bool affinity_available = false;
    if (std::any_of(
            core_indices.begin(), core_indices.end(),
            [](std::int64_t core) { return core > 0; }
        )) {
        std::string error;
        cpus = available_cpus(error);
        affinity_available = !cpus.empty();
        if (!affinity_available) {
            warn(
                "afinidade nao aplicada; as tarefas serao executadas sem "
                "restricao. " + error
            );
        }
    }

    std::vector<std::thread> threads;
    threads.reserve(tasks.size());
    std::exception_ptr thread_creation_error;
    std::exception_ptr task_error;
    std::mutex task_error_mutex;

    try {
        for (std::size_t index = 0; index < tasks.size(); ++index) {
            const auto& task = tasks[index];
            const std::int64_t core = core_indices.empty()
                ? 0
                : core_indices[index];
            const std::string task_name = task_names.empty()
                ? "tarefa " + std::to_string(index + 1)
                : task_names[index];
            threads.emplace_back(
                [task, core, task_name, &cpus, affinity_available,
                 &task_error, &task_error_mutex]() {
                    if (core != 0) {
                        if (core < 1) {
                            warn(
                                "core(" + std::to_string(core)
                                + ") invalido para " + task_name
                                + "; executando sem afinidade."
                            );
                        } else if (affinity_available
                                   && static_cast<std::uint64_t>(core)
                                       > cpus.size()) {
                            warn(
                                "core(" + std::to_string(core)
                                + ") solicitado por " + task_name
                                + ", mas existem apenas "
                                + std::to_string(cpus.size())
                                + " CPUs disponiveis; executando sem "
                                  "afinidade."
                            );
                        } else if (affinity_available) {
                            std::string error;
                            const unsigned int cpu = cpus[
                                static_cast<std::size_t>(core - 1)
                            ];
                            if (!set_thread_affinity(cpu, error)) {
                                warn(
                                    "nao foi possivel fixar " + task_name
                                    + " no core(" + std::to_string(core)
                                    + "); executando sem afinidade. " + error
                                );
                            }
                        }
                    }

                    try {
                        task();
                    } catch (...) {
                        std::lock_guard<std::mutex> lock(task_error_mutex);
                        if (!task_error) {
                            task_error = std::current_exception();
                        }
                    }

                    if (trace_cores_enabled()) {
                        std::lock_guard<std::mutex> lock(diagnostic_mutex());
                        std::cerr << "MiniPar: tarefa " << task_name
                                  << " executou no CPU " << current_cpu()
                                  << std::endl;
                    }
                }
            );
        }
    } catch (...) {
        thread_creation_error = std::current_exception();
    }

    for (auto& thread : threads) {
        if (thread.joinable()) {
            thread.join();
        }
    }

    if (thread_creation_error) {
        std::rethrow_exception(thread_creation_error);
    }
    if (task_error) {
        std::rethrow_exception(task_error);
    }
}
