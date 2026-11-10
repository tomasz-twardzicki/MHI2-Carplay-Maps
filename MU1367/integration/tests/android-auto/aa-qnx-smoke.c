/* SPDX-License-Identifier: GPL-3.0-or-later
 * v1.5.0-e QNX smoke for the release aa-most-feeder with the MU1367 factory libc.so.3 / libsocket.so.3.
* Roles by program name: aa-dmdt-stub logs its arguments (stands in for /eso/bin/apps/dmdt); aa-bridge-stub creates the ring as the
 * bridge does and waits for SIGTERM; no argument runs the scenarios and prints AA_FEEDER_QNX_PASS. */
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define RING "/dev/shmem/aa-ring.bin"
#define RING_SIZE 0x1000710u
static volatile sig_atomic_t stop;
static void on_term(int s) { (void)s; stop = 1; }
static void ms(int n) { struct timespec t = { n / 1000, (long)(n % 1000) * 1000000L }; nanosleep(&t, NULL); }
static int fails;
static void check(int ok, const char *m) { printf("%s %s\n", ok ? "ok    " : "FAILED", m); if (!ok) fails++; }
static int slurp(const char *p, char *b, size_t n)
{
    int fd = open(p, O_RDONLY), k, t = 0;
    if (fd < 0) { b[0] = 0; return -1; }
    while (t < (int)n - 1 && (k = (int)read(fd, b + t, n - 1 - (size_t)t)) > 0) t += k;
    close(fd); b[t] = 0; return t;
}
static void put(const char *p, const char *s)
{
    int fd = open(p, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd >= 0) { (void)write(fd, s, strlen(s)); close(fd); }
}
static int run_feeder(const char *self, const char *prefs)
{
    pid_t c;
    int st;
    unlink("/ramdisk/dmdt.log"); unlink("/ramdisk/status.txt"); unlink(RING);
    c = fork();
    if (c == 0) {
        setenv("PMCP_AA_MODE", "most", 1);
        setenv("PMCP_AA_CONF", "/ramdisk/none.conf", 1);
        setenv("PMCP_AA_STATUS", "/ramdisk/status.txt", 1);
        setenv("PMCP_AA_RUNDIR", "/ramdisk", 1);
        setenv("PMCP_AA_RING", RING, 1);
        setenv("PMCP_AA_CACHE_LOCK", "/ramdisk/cache.lock", 1);
        setenv("PMCP_AA_PREF_DIR", prefs, 1);
        setenv("PMCP_AA_AUTO_ENABLE", "/ramdisk/auto", 1);
        setenv("PMCP_AA_BRIDGE", "/proc/boot/aa-bridge-stub", 1);
        setenv("PMCP_AA_DMDT", "/proc/boot/aa-dmdt-stub", 1);
        setenv("PMCP_AA_FLUSH_DEV", "/ramdisk/flush", 1);
        setenv("PMCP_AA_CP_READY", "/ramdisk/cp.ready", 1);
        setenv("PMCP_AA_SETTLE_MS", "0", 1);
        execl("/proc/boot/aa-most-feeder", "aa-most-feeder", "tcp://127.0.0.1:9", (char *)NULL);
        _exit(126);
    }
    (void)self;
    while (waitpid(c, &st, 0) < 0 && errno == EINTR) {}
    return WIFEXITED(st) ? WEXITSTATUS(st) : -1;
}
static int lock_free(void)
{
    struct flock l;
    int fd = open("/ramdisk/cache.lock", O_RDWR | O_CREAT, 0600), r;
    memset(&l, 0, sizeof l); l.l_type = F_WRLCK; l.l_whence = SEEK_SET;
    r = fcntl(fd, F_SETLK, &l) == 0;
    close(fd);
    return r;
}
int main(int argc, char **argv)
{
    char b[4096], d[512];
    int rc, i;
    if (strstr(argv[0], "aa-dmdt-stub") != NULL) {
        int fd = open("/ramdisk/dmdt.log", O_WRONLY | O_CREAT | O_APPEND, 0644);
        for (i = 1; i < argc; ++i) { (void)write(fd, argv[i], strlen(argv[i])); (void)write(fd, i + 1 < argc ? " " : "\n", 1); }
        close(fd); return 0;
    }
    if (strstr(argv[0], "aa-bridge-stub") != NULL) {
        int fd = open(RING, O_RDWR | O_CREAT, 0666);
        volatile uint32_t *m;
        signal(SIGTERM, on_term);
        if (fd < 0 || ftruncate(fd, RING_SIZE) != 0) return 3;
        m = mmap(NULL, RING_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        if (m == MAP_FAILED) return 4;
        m[1] = 1; m[2] = 1; m[3] = 0; m[0] = 0x43505247u;
        while (!stop) ms(20);
        return 0;
    }
    mkdir("/ramdisk/prefs-on", 0755); mkdir("/ramdisk/prefs-off", 0755);
    put("/ramdisk/auto", ""); put("/ramdisk/none.conf", "# empty\n");
    /* format=3, map mask 0: the MU menu turned the cluster map off (crc32 of the body). */
    put("/ramdisk/prefs-off/settings.state", "format=3\nvc_map_mask=0\nvc_mirror_mask=0\ncarplay_information=0\ngeneration=7\ncrc32=" PREF_CRC "\n");
    rc = run_feeder(argv[0], "/ramdisk/prefs-on");
    for (i = 0; i < 100; ++i) { slurp("/ramdisk/dmdt.log", d, sizeof d); if (strstr(d, "sc 4 70")) break; ms(50); }
    slurp("/ramdisk/status.txt", b, sizeof b);
    printf("--- map on: rc=%d\n%s--- dmdt:\n%s", rc, b, d);
    check(rc == 2, "map on: feeder ran on QNX and ended on the unreachable stream (2)");
    check(strstr(b, "PMCP AA FEEDER v10-mu1367.2 mode=most") != NULL, "map on: release version, most mode");
    check(strstr(b, "prefs=0 map_mask=1 auto_enable=1 -> map") != NULL, "map on: policy");
    check(strstr(b, "przejety gen=1") != NULL || strstr(b, "oddawane") != NULL, "map on: ring mapped from /dev/shmem");
    check(strcmp(d, "dc 72\nsc 4 72\ndc 70 33\nsc 4 70\n") == 0, "map on: MOST released, then VW restored by the guardian");
    check(lock_free(), "map on: cache lease released");
    rc = run_feeder(argv[0], "/ramdisk/prefs-off");
    ms(500);
    slurp("/ramdisk/status.txt", b, sizeof b); slurp("/ramdisk/dmdt.log", d, sizeof d);
    printf("--- map off: rc=%d\n%s", rc, b);
    check(strstr(b, "mode=analyze") != NULL && strstr(b, "map_mask=0 auto_enable=1 -> vw") != NULL, "map off: analyze, VW kept");
    check(d[0] == 0 && access(RING, F_OK) != 0, "map off: no dmdt, no ring");
    /* v1.5.1-e: the Android Auto bridge build loads with the factory libraries and runs to its own exit. Its output
     * goes to the console (test-aa-feeder-qnx.py checks it): this fixture's RAM disk is smaller than the 16 MB ring,
     * so it stops at the ring (ENOSPC) and logs its normal completion line; the unit's /ramdisk is 20 MB. */
    /* v1.5.1-e: the CarPlay build of the same source (boot-time MOST reclaim) as well. */
    {
        static const char *const names[2] = {"altscreen-most-bridge-aa", "altscreen-most-bridge"};
        static const char *const tags[2] = {"AA", "CP"};
        unsigned int k;
        for (k = 0; k < 2U; ++k) {
            char path[96];
            pid_t c;
            int st = 0;
            snprintf(path, sizeof path, "/proc/boot/%s", names[k]);
            printf("@@%s-BRIDGE-START@@\n", tags[k]); fflush(stdout);
            c = fork();
            if (c == 0) {
                execl(path, names[k], "/ramdisk/bridge-out.ts", (char *)NULL);
                _exit(126);
            }
            ms(1500);
            kill(c, SIGTERM);
            for (i = 0; i < 50 && waitpid(c, &st, WNOHANG) == 0; ++i) ms(100);
            if (i == 50) { kill(c, SIGKILL); waitpid(c, &st, 0); }
            printf("@@%s-BRIDGE-END@@\n", tags[k]);
            check((WIFEXITED(st) && WEXITSTATUS(st) != 126) || WIFSIGNALED(st), k ? "CarPlay bridge: ran and exited" : "AA bridge: ran and exited");
            unlink("/ramdisk/carplay-alt-ring.bin");
        }
    }
    printf(fails ? "AA_FEEDER_QNX_FAIL %d\n" : "AA_FEEDER_QNX_PASS\n", fails);
    return fails != 0;
}
