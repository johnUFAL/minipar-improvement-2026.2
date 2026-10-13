#include "minipar_rt.hpp"

void minipar_parallel(const std::vector<std::function<void()>>& tasks) {
    std::vector<std::thread> threads;
    threads.reserve(tasks.size());
    for (const auto& task : tasks) {
        threads.emplace_back(task);
    }
    for (auto& thread : threads) {
        thread.join();
    }
}
