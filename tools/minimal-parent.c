/* minimal-parent.c: start a command from a process that holds almost no
 * memory, wait for it, and report its own resource use, for
 * tools/pull-scale-test.py (den#114). A child's peak resident set
 * (ru_maxrss) starts at its parent's, so a command started straight from the
 * Python runner reads at least the runner's own peak; started from this
 * process, it reads its own.
 *
 * Usage: minimal-parent REPORT COMMAND [ARG...]
 * The command inherits stdin, stdout and stderr. REPORT receives one line,
 * "STATUS MAXRSS_KIB USER_S SYSTEM_S WALL_S"; STATUS is the exit status, or
 * minus the signal number. Own code; no implementation's source. */
#include <stdio.h>
#include <sys/resource.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 3) return 64;
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    pid_t pid = fork();
    if (pid < 0) return 71;
    if (pid == 0) {
        execvp(argv[2], argv + 2);
        _exit(127);
    }
    int status = 0;
    struct rusage usage;
    if (wait4(pid, &status, 0, &usage) < 0) return 71;
    clock_gettime(CLOCK_MONOTONIC, &end);
    long maxrss = usage.ru_maxrss;
#ifdef __APPLE__
    maxrss /= 1024; /* bytes there, KiB on Linux */
#endif
    int code = WIFEXITED(status) ? WEXITSTATUS(status) : -WTERMSIG(status);
    FILE *report = fopen(argv[1], "w");
    if (!report) return 73;
    fprintf(report, "%d %ld %.6f %.6f %.6f\n", code, maxrss,
            usage.ru_utime.tv_sec + usage.ru_utime.tv_usec / 1e6,
            usage.ru_stime.tv_sec + usage.ru_stime.tv_usec / 1e6,
            (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9);
    return fclose(report) == 0 ? 0 : 74;
}
