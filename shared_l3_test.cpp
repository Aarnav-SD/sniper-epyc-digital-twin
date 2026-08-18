#include <atomic>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <thread>
#include <vector>

constexpr std::size_t N = 16 * 1024;
constexpr int NUM_THREADS = 4;
constexpr int ROUNDS = 2;

std::vector<std::uint64_t> data(N, 0);
std::atomic<int> ready{0};
std::atomic<bool> start{false};

void worker(int id)
{
    const std::size_t chunk = data.size() / NUM_THREADS;
    const std::size_t begin = static_cast<std::size_t>(id) * chunk;
    const std::size_t end =
        (id == NUM_THREADS - 1) ? data.size() : begin + chunk;

    ready.fetch_add(1, std::memory_order_release);

    while (!start.load(std::memory_order_acquire))
    {
        std::this_thread::yield();
    }

    for (int round = 0; round < ROUNDS; ++round)
    {
        for (std::size_t i = begin; i < end; ++i)
        {
            data[i] += static_cast<std::uint64_t>(id + round + 1);
        }
    }
}

int main()
{
    std::thread t1(worker, 1);
    std::thread t2(worker, 2);
    std::thread t3(worker, 3);

    // Main thread is the fourth application thread.
    ready.fetch_add(1, std::memory_order_release);

    while (ready.load(std::memory_order_acquire) != NUM_THREADS)
    {
        std::this_thread::yield();
    }

    start.store(true, std::memory_order_release);

    // Main thread executes worker 0's memory loop directly.
    const std::size_t chunk = data.size() / NUM_THREADS;
    const std::size_t begin = 0;
    const std::size_t end = chunk;

    for (int round = 0; round < ROUNDS; ++round)
    {
        for (std::size_t i = begin; i < end; ++i)
        {
            data[i] += static_cast<std::uint64_t>(round + 1);
        }
    }

    t1.join();
    t2.join();
    t3.join();

    std::uint64_t checksum = 0;

    for (const std::uint64_t value : data)
    {
        checksum += value;
    }

    std::cout << "Checksum: " << checksum << '\n';
    return 0;
}