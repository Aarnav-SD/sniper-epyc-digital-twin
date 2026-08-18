#define _GNU_SOURCE

#include <pthread.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>

typedef struct {
    int thread_id;
    int target_cpu;
} thread_arg_t;

static void *worker(void *arg)
{
    thread_arg_t *a = (thread_arg_t *)arg;

    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(a->target_cpu, &cpuset);

    int rc = pthread_setaffinity_np(
        pthread_self(),
        sizeof(cpu_set_t),
        &cpuset
    );

    if (rc != 0) {
        fprintf(stderr,
                "thread %d: affinity to CPU %d failed: %s\n",
                a->thread_id,
                a->target_cpu,
                strerror(rc));
        return NULL;
    }

    printf("thread %2d requested CPU %3d\n",
           a->thread_id,
           a->target_cpu);

    volatile unsigned long x = 0;

    for (unsigned long i = 0; i < 1000000UL; ++i)
        x += i;

    return NULL;
}

int main(void)
{
    const int nthreads = 16;

    /*
     * First 8 threads -> socket 0
     * Next 8 threads  -> socket 1
     */
    const int cpus[16] = {
        0, 1, 2, 3, 4, 5, 6, 7,
        64, 65, 66, 67, 68, 69, 70, 71
    };

    pthread_t threads[nthreads];
    thread_arg_t args[nthreads];

    for (int i = 0; i < nthreads; ++i) {
        args[i].thread_id = i;
        args[i].target_cpu = cpus[i];

        int rc = pthread_create(
            &threads[i],
            NULL,
            worker,
            &args[i]
        );

        if (rc != 0) {
            fprintf(stderr,
                    "pthread_create failed: %s\n",
                    strerror(rc));
            exit(1);
        }
    }

    for (int i = 0; i < nthreads; ++i)
        pthread_join(threads[i], NULL);

    return 0;
}
