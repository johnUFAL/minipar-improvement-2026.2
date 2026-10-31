#include "minipar_rt.hpp"

void minipar_parallel(const std::vector<std::function<void()>>& tasks) {
    std::vector<std::thread> threads;
    threads.reserve(tasks.size());
    std::exception_ptr thread_creation_error;
    std::exception_ptr task_error;
    std::mutex task_error_mutex;

    try {
        for (const auto& task : tasks) {
            threads.emplace_back([task, &task_error, &task_error_mutex]() {
                try {
                    task();
                } catch (...) {
                    std::lock_guard<std::mutex> lock(task_error_mutex);
                    if (!task_error) {
                        task_error = std::current_exception();
                    }
                }
            });
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
