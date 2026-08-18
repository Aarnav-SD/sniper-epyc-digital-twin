#define _GNU_SOURCE

#include <pthread.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#define SIZE_MB 64
#define STRIDE 64

static unsigned char *buf0;
static unsigned char *buf1;

static pthread_barrier_t barrier;

static void pin_to_cpu(int cpu)
{
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(cpu, &set);

    int rc = pthread_setaffinity_np(
        pthread_self(),
        sizeof(set),
        &set
    );

    if (rc != 0) {
        fprintf(stderr,
                "Affinity to CPU %d failed: %s\n",
                cpu,
                strerror(rc));
        exit(1);
    }
}

static uint64_t sweep(unsigned char *buf, size_t size)
{
    uint64_t sum = 0;

    for (size_t i = 0; i < size; i += STRIDE)
        sum += buf[i];

    return sum;
}

static void *thread0(void *arg)
{
    const size_t size = SIZE_MB * 1024ULL * 1024ULL;

    pin_to_cpu(0);

    printf("T0 pinned to core 0\n");

    /* First-touch buf0 on NUMA node 0 */
    for (size_t i = 0; i < size; i += STRIDE)
        buf0[i] = 1;

    pthread_barrier_wait(&barrier);

    /* LOCAL */
    uint64_t local_sum = sweep(buf0, size);

    pthread_barrier_wait(&barrier);

    /* REMOTE: buf1 was first-touched by core 64 */
    uint64_t remote_sum = sweep(buf1, size);

    printf("T0 local=%lu remote=%lu\n",
           local_sum,
           remote_sum);

    return NULL;
}

static void *thread1(void *arg)
{
    const size_t size = SIZE_MB * 1024ULL * 1024ULL;

    pin_to_cpu(64);

    printf("T1 pinned to core 64\n");

    /* First-touch buf1 on NUMA node 1 */
    for (size_t i = 0; i < size; i += STRIDE)
        buf1[i] = 2;

    pthread_barrier_wait(&barrier);

    /* LOCAL */
    uint64_t local_sum = sweep(buf1, size);

    pthread_barrier_wait(&barrier);

    /* REMOTE: buf0 was first-touched by core 0 */
    uint64_t remote_sum = sweep(buf0, size);

    printf("T1 local=%lu remote=%lu\n",
           local_sum,
           remote_sum);

    return NULL;
}

int main(void)
{
    const size_t size = SIZE_MB * 1024ULL * 1024ULL;

    if (posix_memalign((void **)&buf0, 4096, size) != 0)
        return 1;

    if (posix_memalign((void **)&buf1, 4096, size) != 0)
        return 1;

    pthread_barrier_init(&barrier, NULL, 2);

    pthread_t t0, t1;

    pthread_create(&t0, NULL, thread0, NULL);
    pthread_create(&t1, NULL, thread1, NULL);

    pthread_join(t0, NULL);
    pthread_join(t1, NULL);

    pthread_barrier_destroy(&barrier);

    free(buf0);
    free(buf1);

    return 0;
}
