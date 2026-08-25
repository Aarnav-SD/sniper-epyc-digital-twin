#define _GNU_SOURCE

#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <pthread.h>
#include <sched.h>
#include <sys/mman.h>

#include "sim_api.h"

static constexpr size_t ARRAY_SIZE = 16ULL * 1024 * 1024;  // 16 MiB/thread
static constexpr size_t CACHE_LINE = 64;
static constexpr size_t PAGE_SIZE  = 4096;

enum PlacementMode
{
    SOCKET0,
    SOCKET1,
    BOTH
};

struct ThreadArg
{
    int tid;
    int core;
    uint8_t *array;
    uint64_t result;

    uint64_t start_time_fs;
    uint64_t end_time_fs;

    pthread_barrier_t *touch_done;
    pthread_barrier_t *stream_start;
    pthread_barrier_t *stream_done;
};

static void pin_to_core(int core)
{
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(core, &cpuset);

    int rc = pthread_setaffinity_np(
        pthread_self(),
        sizeof(cpu_set_t),
        &cpuset
    );

    if (rc != 0)
    {
        std::fprintf(
            stderr,
            "Affinity to simulated CPU %d failed: %s\n",
            core,
            std::strerror(rc)
        );
        std::exit(1);
    }
}

static void *worker(void *ptr)
{
    ThreadArg *arg = static_cast<ThreadArg *>(ptr);

    pin_to_core(arg->core);

    /*
     * NUMA placement phase.
     *
     * Touch exactly one cache line per 4 KiB page.
     *
     * This establishes first-touch placement on the worker's NUMA node
     * without populating every line that will later be streamed.
     *
     * Only 1/64 of each page's cache lines are touched here.
     */
    for (size_t i = 0; i < ARRAY_SIZE; i += PAGE_SIZE)
        arg->array[i] = static_cast<uint8_t>(arg->tid + 1);

    pthread_barrier_wait(arg->touch_done);

    /*
     * Wait until main starts the measurement interval.
     */
    pthread_barrier_wait(arg->stream_start);

    arg->start_time_fs = SimMagic0(SIM_CMD_GET_SIM_TIME);

    uint64_t sum = 0;

    for (size_t i = 0; i < ARRAY_SIZE; i += CACHE_LINE)
        sum += arg->array[i];

    arg->end_time_fs = SimMagic0(SIM_CMD_GET_SIM_TIME);

    arg->result = sum;

    pthread_barrier_wait(arg->stream_done);

    return nullptr;
}

static PlacementMode parse_mode(const char *s)
{
    if (std::strcmp(s, "socket0") == 0)
        return SOCKET0;

    if (std::strcmp(s, "socket1") == 0)
        return SOCKET1;

    if (std::strcmp(s, "both") == 0)
        return BOTH;

    std::fprintf(
        stderr,
        "mode must be socket0, socket1, or both\n"
    );

    std::exit(1);
}

int main(int argc, char **argv)
{
    if (argc != 3)
    {
        std::fprintf(
            stderr,
            "Usage: %s <threads> <socket0|socket1|both>\n",
            argv[0]
        );
        return 1;
    }

    int nthreads = std::atoi(argv[1]);
    PlacementMode mode = parse_mode(argv[2]);

    if (nthreads < 1 || nthreads > 128)
    {
        std::fprintf(stderr, "threads must be 1..128\n");
        return 1;
    }

    if ((mode == SOCKET0 || mode == SOCKET1) &&
        nthreads > 64)
    {
        std::fprintf(
            stderr,
            "single-socket experiments support at most 64 threads\n"
        );
        return 1;
    }

    pthread_t *threads =
        static_cast<pthread_t *>(
            std::calloc(nthreads, sizeof(pthread_t))
        );

    ThreadArg *args =
        static_cast<ThreadArg *>(
            std::calloc(nthreads, sizeof(ThreadArg))
        );

    if (!threads || !args)
        return 1;

    /*
     * Main participates in all barriers.
     */
    pthread_barrier_t touch_done;
    pthread_barrier_t stream_start;
    pthread_barrier_t stream_done;

    pthread_barrier_init(&touch_done, nullptr, nthreads + 1);
    pthread_barrier_init(&stream_start, nullptr, nthreads + 1);
    pthread_barrier_init(&stream_done, nullptr, nthreads + 1);

    for (int t = 0; t < nthreads; ++t)
    {
        /*
         * Anonymous mmap gives zero-initialized memory.
         *
         * We intentionally do NOT memset the entire array here because
         * that would both establish placement on the main thread and
         * populate the cache hierarchy.
         */
        void *p = mmap(
            nullptr,
            ARRAY_SIZE,
            PROT_READ | PROT_WRITE,
            MAP_PRIVATE | MAP_ANONYMOUS,
            -1,
            0
        );

        if (p == MAP_FAILED)
        {
            std::perror("mmap");
            return 1;
        }

        args[t].tid = t;
        args[t].array = static_cast<uint8_t *>(p);
        args[t].result = 0;
        args[t].start_time_fs = 0;
        args[t].end_time_fs = 0;

        /*
         * Core mapping.
         */
        if (mode == SOCKET0)
        {
            args[t].core = t;
        }
        else if (mode == SOCKET1)
        {
            args[t].core = 64 + t;
        }
        else
        {
            /*
             * Spread threads evenly between sockets.
             *
             * t=0 -> core 0
             * t=1 -> core 64
             * t=2 -> core 1
             * t=3 -> core 65
             * ...
             */
            if ((t & 1) == 0)
                args[t].core = t / 2;
            else
                args[t].core = 64 + (t / 2);
        }

        args[t].touch_done   = &touch_done;
        args[t].stream_start = &stream_start;
        args[t].stream_done  = &stream_done;

        pthread_create(
            &threads[t],
            nullptr,
            worker,
            &args[t]
        );
    }

    /*
     * Wait until every worker has completed NUMA first-touch placement.
     */
    pthread_barrier_wait(&touch_done);

    std::printf(
        "=== BEGIN DRAM BANDWIDTH ROI ===\n"
        "threads=%d mode=%s bytes_per_thread=%zu\n",
        nthreads,
        argv[2],
        ARRAY_SIZE
    );

    /*
     * Start the measured region only AFTER placement.
     */
    SimRoiStart();

    pthread_barrier_wait(&stream_start);

    /*
     * Wait until every streaming worker is finished.
     */
    pthread_barrier_wait(&stream_done);

    SimRoiEnd();

    std::printf("=== END DRAM BANDWIDTH ROI ===\n");

    uint64_t checksum = 0;

    for (int t = 0; t < nthreads; ++t)
    {
        pthread_join(threads[t], nullptr);
        checksum += args[t].result;
    }

    /*
     * Number of cache-line bytes requested by the streaming phase.
     *
     * Each one-byte load brings a 64-byte cache line through the
     * hierarchy on a miss, so this is the relevant DRAM-side byte count.
     */
    uint64_t stream_bytes =
        static_cast<uint64_t>(nthreads) *
        static_cast<uint64_t>(ARRAY_SIZE);

    uint64_t earliest_start = UINT64_MAX;
    uint64_t latest_end = 0;

    for (int t = 0; t < nthreads; ++t)
    {
        if (args[t].start_time_fs < earliest_start)
            earliest_start = args[t].start_time_fs;

        if (args[t].end_time_fs > latest_end)
            latest_end = args[t].end_time_fs;
    }

    uint64_t duration_fs = latest_end - earliest_start;

    double duration_seconds =
        static_cast<double>(duration_fs) * 1.0e-15;

    double bandwidth_gbps =
        static_cast<double>(stream_bytes) /
        duration_seconds /
        1.0e9;

    std::printf(
        "STREAM RESULT "
        "threads=%d "
        "mode=%s "
        "bytes=%llu "
        "start_fs=%llu "
        "end_fs=%llu "
        "duration_fs=%llu "
        "duration_us=%.3f "
        "bandwidth_GBps=%.3f "
        "checksum=%llu\n",
        nthreads,
        argv[2],
        static_cast<unsigned long long>(stream_bytes),
        static_cast<unsigned long long>(earliest_start),
        static_cast<unsigned long long>(latest_end),
        static_cast<unsigned long long>(duration_fs),
        duration_seconds * 1.0e6,
        bandwidth_gbps,
        static_cast<unsigned long long>(checksum)
    );

    for (int t = 0; t < nthreads; ++t)
        munmap(args[t].array, ARRAY_SIZE);

    pthread_barrier_destroy(&touch_done);
    pthread_barrier_destroy(&stream_start);
    pthread_barrier_destroy(&stream_done);

    std::free(args);
    std::free(threads);

    return 0;
}
