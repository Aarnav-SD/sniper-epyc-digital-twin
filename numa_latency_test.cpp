#define _GNU_SOURCE

#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "sim_api.h"

#define CACHELINE   64ULL
#define SIZE_MB     64ULL
#define NUM_LINES   ((SIZE_MB * 1024ULL * 1024ULL) / CACHELINE)

#define TRAVERSALS  1ULL
#define STEPS       (NUM_LINES * TRAVERSALS)

#define JUMP        131071ULL

#define NUMA_MARK_FIRST_TOUCH_BEGIN 0xE001
#define NUMA_MARK_FIRST_TOUCH_END   0xE002
#define NUMA_MARK_CHASE_BEGIN       0xE003
#define NUMA_MARK_CHASE_END         0xE004

typedef struct __attribute__((aligned(64)))
{
    uint64_t next;
    unsigned char padding[56];
} Node;

static Node *nodes;
static pthread_barrier_t barrier;

/*
 * Modes:
 *
 * 0 = LOCAL0
 *     core 0 initializes
 *     core 0 reads
 *
 * 1 = REMOTE0
 *     core 64 initializes
 *     core 0 reads
 *
 * 2 = LOCAL1
 *     core 64 initializes
 *     core 64 reads
 *
 * 3 = REMOTE1
 *     core 0 initializes
 *     core 64 reads
 */
static int mode;

typedef struct
{
    int cpu;
} ThreadArg;

static void pin_cpu(int cpu)
{
    cpu_set_t set;

    CPU_ZERO(&set);
    CPU_SET(cpu, &set);

    int rc = pthread_setaffinity_np(
        pthread_self(),
        sizeof(set),
        &set
    );

    if (rc != 0)
    {
        fprintf(stderr,
                "Affinity to CPU %d failed: %s\n",
                cpu,
                strerror(rc));
        exit(1);
    }
}

static int is_initializer(int cpu)
{
    switch (mode)
    {
        case 0: return cpu == 0;   /* LOCAL0  */
        case 1: return cpu == 64;  /* REMOTE0 */
        case 2: return cpu == 64;  /* LOCAL1  */
        case 3: return cpu == 0;   /* REMOTE1 */
    }

    return 0;
}

static int is_reader(int cpu)
{
    switch (mode)
    {
        case 0: return cpu == 0;   /* LOCAL0  */
        case 1: return cpu == 0;   /* REMOTE0 */
        case 2: return cpu == 64;  /* LOCAL1  */
        case 3: return cpu == 64;  /* REMOTE1 */
    }

    return 0;
}

static void initialize_memory(void)
{
    for (uint64_t i = 0; i < NUM_LINES; ++i)
    {
        nodes[i].next =
            (i + JUMP) & (NUM_LINES - 1);
    }
}

static uint64_t pointer_chase(void)
{
    volatile uint64_t index = 0;

    for (uint64_t i = 0; i < STEPS; ++i)
        index = nodes[index].next;

    return index;
}

static void *worker(void *arg)
{
    ThreadArg *a = (ThreadArg *)arg;

    pin_cpu(a->cpu);

    printf("worker pinned to core %d\n", a->cpu);
    fflush(stdout);

    /*
     * Both workers now exist and are permanently pinned.
     */
    pthread_barrier_wait(&barrier);

    /*
     * Only the designated owner first-touches the buffer.
     */
    if (is_initializer(a->cpu))
    {
        printf("core %d beginning first-touch\n", a->cpu);
        fflush(stdout);

        SimMarker(NUMA_MARK_FIRST_TOUCH_BEGIN, a->cpu);

        initialize_memory();

        SimMarker(NUMA_MARK_FIRST_TOUCH_END, a->cpu);

        printf("core %d first-touch complete\n", a->cpu);
        fflush(stdout);
    }

    /*
     * Reader cannot begin until initialization has completely
     * finished.
     */
    pthread_barrier_wait(&barrier);

    if (is_reader(a->cpu))
    {
        printf("=== BEGIN POINTER-CHASE ROI ===\n");
        printf("core %d beginning pointer chase\n", a->cpu);
        fflush(stdout);

        SimMarker(NUMA_MARK_CHASE_BEGIN, a->cpu);

        SimRoiStart();

        uint64_t final_index = pointer_chase();

        SimRoiEnd();

        SimMarker(NUMA_MARK_CHASE_END, a->cpu);

        printf("core %d pointer chase complete; final index=%lu\n",
            a->cpu,
            (unsigned long)final_index);
        printf("=== END POINTER-CHASE ROI ===\n");
        fflush(stdout);
    }

    /*
     * Keep both pthreads alive until the measurement finishes.
     */
    pthread_barrier_wait(&barrier);

    return NULL;
}

int main(int argc, char **argv)
{
    if (argc != 2)
    {
        fprintf(stderr,
                "usage: %s <mode>\n"
                "  0 = LOCAL0\n"
                "  1 = REMOTE0\n"
                "  2 = LOCAL1\n"
                "  3 = REMOTE1\n",
                argv[0]);

        return 1;
    }

    mode = atoi(argv[1]);

    if (mode < 0 || mode > 3)
    {
        fprintf(stderr, "invalid mode\n");
        return 1;
    }

    const char *names[] = {
        "LOCAL0",
        "REMOTE0",
        "LOCAL1",
        "REMOTE1"
    };

    size_t bytes =
        NUM_LINES * sizeof(Node);

    if (posix_memalign(
            (void **)&nodes,
            4096,
            bytes) != 0)
    {
        perror("posix_memalign");
        return 1;
    }

    printf("[BENCH ARRAY] base=%p end=%p bytes=%zu\n",
        (void *)nodes,
        (void *)((char *)nodes + bytes),
        bytes);
    fflush(stdout);

    printf("experiment  = %s\n", names[mode]);
    printf("working set = %zu MiB\n",
           bytes / (1024 * 1024));
    fflush(stdout);

    /*
     * main + two workers do not all participate:
     * barrier only synchronizes the two worker threads.
     */
    pthread_barrier_init(&barrier, NULL, 2);

    pthread_t t0;
    pthread_t t64;

    ThreadArg a0  = { .cpu = 0 };
    ThreadArg a64 = { .cpu = 64 };

    int rc;

    rc = pthread_create(&t0, NULL, worker, &a0);
    if (rc != 0)
    {
        fprintf(stderr, "pthread_create t0: %s\n",
                strerror(rc));
        return 1;
    }

    rc = pthread_create(&t64, NULL, worker, &a64);
    if (rc != 0)
    {
        fprintf(stderr, "pthread_create t64: %s\n",
                strerror(rc));
        return 1;
    }

    pthread_join(t0, NULL);
    pthread_join(t64, NULL);

    pthread_barrier_destroy(&barrier);
    free(nodes);

    return 0;
}
