#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <pthread.h>

#define ARRAY_SIZE (8 * 1024 * 1024)   // 8 MiB per thread
#define STRIDE 64

typedef struct {
    int id;
    uint8_t *array;
    uint64_t result;
} thread_arg_t;

static void *worker(void *ptr)
{
    thread_arg_t *arg = (thread_arg_t *)ptr;
    uint64_t sum = 0;

    /*
     * Touch one byte per cache line.
     * Dataset is intentionally much larger than private caches.
     */
    for (size_t i = 0; i < ARRAY_SIZE; i += STRIDE)
        sum += arg->array[i];

    arg->result = sum;
    return NULL;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <threads>\n", argv[0]);
        return 1;
    }

    int nthreads = atoi(argv[1]);

    if (nthreads < 1 || nthreads > 64) {
        fprintf(stderr, "threads must be 1..64\n");
        return 1;
    }

    pthread_t *threads = calloc(nthreads, sizeof(*threads));
    thread_arg_t *args = calloc(nthreads, sizeof(*args));

    if (!threads || !args)
        return 1;

    for (int t = 0; t < nthreads; ++t) {
        if (posix_memalign((void **)&args[t].array, 64, ARRAY_SIZE))
            return 1;

        /*
         * Initialize before worker creation so the measured workers
         * predominantly perform reads.
         */
        for (size_t i = 0; i < ARRAY_SIZE; i += STRIDE)
            args[t].array[i] = (uint8_t)(i + t);

        args[t].id = t;
        args[t].result = 0;
    }

    for (int t = 0; t < nthreads; ++t)
        pthread_create(&threads[t], NULL, worker, &args[t]);

    uint64_t checksum = 0;

    for (int t = 0; t < nthreads; ++t) {
        pthread_join(threads[t], NULL);
        checksum += args[t].result;
    }

    printf("threads=%d checksum=%llu\n",
           nthreads,
           (unsigned long long)checksum);

    for (int t = 0; t < nthreads; ++t)
        free(args[t].array);

    free(args);
    free(threads);

    return 0;
}
