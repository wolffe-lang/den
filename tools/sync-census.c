/* sync-census.c: an LD_PRELOAD census of a process tree's sync calls, for
 * tools/wire-gaps-test.py's clone-syncs row (Linux). Each fsync, fdatasync,
 * sync_file_range, syncfs, sync and msync made through the C library appends
 * one line, "CALL PATH", to the file named by DEN_SYNC_LOG (PATH is the
 * descriptor's /proc/self/fd target), and each process the library loads into
 * appends "load EXE", so a census of a program the library never reached
 * cannot pass for one with no syncs. Own code; no implementation's source. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

static void line(const char *call, const char *path) {
    const char *log = getenv("DEN_SYNC_LOG");
    if (!log) return;
    char text[4400];
    int n = snprintf(text, sizeof text, "%s %s\n", call, path);
    if (n < 0) return;
    if (n >= (int)sizeof text) n = sizeof text - 1;
    int out = open(log, O_WRONLY | O_APPEND | O_CREAT | O_CLOEXEC, 0644);
    if (out < 0) return;
    ssize_t ignored = write(out, text, (size_t)n);
    (void)ignored;
    close(out);
}

static void note(const char *call, int fd) {
    char link[64], path[4096];
    snprintf(link, sizeof link, "/proc/self/fd/%d", fd);
    ssize_t n = readlink(link, path, sizeof path - 1);
    path[n < 0 ? 0 : n] = 0;
    line(call, path);
}

__attribute__((constructor)) static void loaded(void) {
    char path[4096];
    ssize_t n = readlink("/proc/self/exe", path, sizeof path - 1);
    path[n < 0 ? 0 : n] = 0;
    line("load", path);
}

#define REAL(type, name, params) \
    static type(*real) params;   \
    if (!real) real = (type(*) params)dlsym(RTLD_NEXT, name)

int fsync(int fd) {
    REAL(int, "fsync", (int));
    note("fsync", fd);
    return real(fd);
}

int fdatasync(int fd) {
    REAL(int, "fdatasync", (int));
    note("fdatasync", fd);
    return real(fd);
}

int sync_file_range(int fd, off_t offset, off_t count, unsigned int flags) {
    REAL(int, "sync_file_range", (int, off_t, off_t, unsigned int));
    note("sync_file_range", fd);
    return real(fd, offset, count, flags);
}

int syncfs(int fd) {
    REAL(int, "syncfs", (int));
    note("syncfs", fd);
    return real(fd);
}

void sync(void) {
    REAL(void, "sync", (void));
    line("sync", "");
    real();
}

int msync(void *addr, size_t length, int flags) {
    REAL(int, "msync", (void *, size_t, int));
    line("msync", "");
    return real(addr, length, flags);
}
