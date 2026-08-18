#include <atomic>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <thread>
#include <vector>

namespace
{
constexpr int NUM_THREADS = 8;
constexpr std::size_t N = 8 * 1024;
constexpr int ROUNDS = 1;

std::vector<std::uint64_t> data(N, 0);
std::atomic<int> ready{0};
std::atomic<bool> start{false};

void wait_for_start()
{
    ready.fetch_add(1, std::memory_order_release);

    while (!start.load(std::memory_order_acquire))
    {
        std::this_thread::yield();
    }
}

void perform_work(int id)
{
    const std::size_t chunk = data.size() / NUM_THREADS;
    const std::size_t begin = static_cast<std::size_t>(id) * chunk;

    const std::size_t end =
        (id == NUM_THREADS - 1)
            ? data.size()
            : begin + chunk;

    for (int round = 0; round < ROUNDS; ++round)
    {
        for (std::size_t i = begin; i < end; ++i)
        {
            data[i] += static_cast<std::uint64_t>(id + round + 1);
        }
    }
}

void spawned_worker(int id)
{
    wait_for_start();
    perform_work(id);
}
}

int main()
{
    std::vector<std::thread> workers;
    workers.reserve(NUM_THREADS - 1);

    for (int id = 1; id < NUM_THREADS; ++id)
    {
        workers.emplace_back(spawned_worker, id);
    }

    // Main is worker 0, but it must not wait for itself to set start.
    ready.fetch_add(1, std::memory_order_release);

    while (ready.load(std::memory_order_acquire) != NUM_THREADS)
    {
        std::this_thread::yield();
    }

    start.store(true, std::memory_order_release);

    perform_work(0);

    for (std::thread& worker : workers)
    {
        worker.join();
    }

    std::uint64_t checksum = 0;

    for (const std::uint64_t value : data)
    {
        checksum += value;
    }

    std::cout << "Checksum: " << checksum << '\n';
    return 0;
}