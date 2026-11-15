/* minimal-parent.c: start a command from a process that holds almost no
 * memory, wait for it, and report its own resource use (den#114). A child's
 * peak resident set (ru_maxrss) starts at its parent's, so a command started
 * straight from the Python runner reads at least the runner's own peak;
 * started from this process, it reads its own.
 *
 * Usage: minimal-parent [--timeout SECONDS] REPORT COMMAND [ARG...]
 * The command inherits stdin, stdout and stderr. REPORT receives one line,
 * "STATUS MAXRSS_KIB USER_S SYSTEM_S WALL_S"; STATUS is the exit status, or
 * minus the signal number. With --timeout, a sixth field is 1 only when this
 * parent killed its own unreaped child at the deadline. Existing callers keep
 * the five-field report. Own code; no implementation's source. */
#include <errno.h>
#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t expired;

static void alarm_ready(int sig) {
    (void)sig;
    expired = 1;
}

static void child_ready(int sig) {
    (void)sig;
}

int main(int argc, char **argv) {
    int first = 1;
    double timeout = 0;
    if (argc > 1 && strcmp(argv[1], "--timeout") == 0) {
        if (argc < 5) return 64;
        char *end;
        errno = 0;
        timeout = strtod(argv[2], &end);
        if (errno || *end || !isfinite(timeout) || timeout <= 0 || timeout > 86400)
            return 64;
        first = 3;
    }
    if (argc < first + 2) return 64;

    sigset_t oldmask, waitmask;
    struct itimerval timer = {0};
    if (timeout > 0) {
        struct sigaction action = {0};
        sigemptyset(&action.sa_mask);
        action.sa_handler = alarm_ready;
        if (sigaction(SIGALRM, &action, NULL) < 0) return 71;
        action.sa_handler = child_ready;
        if (sigaction(SIGCHLD, &action, NULL) < 0) return 71;
        sigset_t blocked;
        sigemptyset(&blocked);
        sigaddset(&blocked, SIGALRM);
        sigaddset(&blocked, SIGCHLD);
        if (sigprocmask(SIG_BLOCK, &blocked, &oldmask) < 0) return 71;
        waitmask = oldmask;
        sigdelset(&waitmask, SIGALRM);
        sigdelset(&waitmask, SIGCHLD);
        timer.it_value.tv_sec = (time_t)timeout;
        timer.it_value.tv_usec = (suseconds_t)((timeout - timer.it_value.tv_sec) * 1e6);
        if (!timer.it_value.tv_sec && !timer.it_value.tv_usec)
            timer.it_value.tv_usec = 1;
    }

    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    pid_t pid = fork();
    if (pid < 0) return 71;
    if (pid == 0) {
        if (timeout > 0 && sigprocmask(SIG_SETMASK, &oldmask, NULL) < 0) _exit(71);
        execvp(argv[first + 1], argv + first + 1);
        _exit(127);
    }
    int status = 0, timed_out = 0;
    struct rusage usage;
    if (timeout > 0) {
        if (setitimer(ITIMER_REAL, &timer, NULL) < 0) {
            kill(pid, SIGKILL);
            while (wait4(pid, &status, 0, &usage) < 0 && errno == EINTR) {}
            return 71;
        }
        for (;;) {
            /* Both notifications stay blocked between checking and sleeping,
             * so a child exit or a deadline cannot be missed. Only wait4 reaps
             * this child; a deadline can never signal a reused pid. */
            pid_t result = wait4(pid, &status, WNOHANG, &usage);
            if (result == pid) break;
            if (result < 0) {
                if (errno == EINTR) continue;
                return 71;
            }
            if (expired && !timed_out) {
                if (kill(pid, SIGKILL) < 0 && errno != ESRCH) return 71;
                timed_out = 1;
            }
            sigsuspend(&waitmask);
        }
        struct itimerval off = {0};
        if (setitimer(ITIMER_REAL, &off, NULL) < 0) return 71;
        if (sigprocmask(SIG_SETMASK, &oldmask, NULL) < 0) return 71;
    } else {
        pid_t result;
        do { result = wait4(pid, &status, 0, &usage); } while (result < 0 && errno == EINTR);
        if (result != pid) return 71;
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    long maxrss = usage.ru_maxrss;
#ifdef __APPLE__
    maxrss /= 1024; /* bytes there, KiB on Linux */
#endif
    int code = WIFEXITED(status) ? WEXITSTATUS(status) : -WTERMSIG(status);
    FILE *report = fopen(argv[first], "w");
    if (!report) return 73;
    fprintf(report, "%d %ld %.6f %.6f %.6f", code, maxrss,
            usage.ru_utime.tv_sec + usage.ru_utime.tv_usec / 1e6,
            usage.ru_stime.tv_sec + usage.ru_stime.tv_usec / 1e6,
            (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9);
    if (timeout > 0) fprintf(report, " %d", timed_out);
    fputc('\n', report);
    return fclose(report) == 0 ? 0 : 74;
}
