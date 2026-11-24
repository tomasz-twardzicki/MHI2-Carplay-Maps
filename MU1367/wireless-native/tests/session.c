/* SPDX-License-Identifier: GPL-3.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include "wireless_session.h"

static unsigned int checks;
#define CHECK(x) do { ++checks; if (!(x)) { fprintf(stderr, "SESSION_FAIL line=%d\n", __LINE__); return 1; } } while (0)
static const char *scope = "/ramdisk/.v75-native-0123456789abcdef0123456789abcdef";
static void put(const char *suffix, const char *body)
{
    char path[512];
    FILE *f;
    snprintf(path, sizeof(path), "%s%s", CPMAP_ROOT_PREFIX, suffix);
    f = fopen(path, "w");
    if (!f || fwrite(body, 1, strlen(body), f) != strlen(body) || fclose(f)) exit(90);
}
static void remove_file(const char *suffix)
{
    char path[512];
    snprintf(path, sizeof(path), "%s%s", CPMAP_ROOT_PREFIX, suffix);
    unlink(path);
}
static void fixture(pid_t pid)
{
    char text[256], path[256];
    snprintf(text, sizeof(text), "V75_NATIVE1\n%ld\n%s\n", (long)pid, scope);
    put("/ramdisk/v75-wireless-native.owner", text);
    snprintf(text, sizeof(text), "%ld\n", (long)pid);
    put("/dev/shmem/wcp_receiver.pid", text);
    put("/dev/shmem/wcp_cp_session", "1\n");
    snprintf(text, sizeof(text), "V75_GRANT1\n%ld\n7\n", (long)pid);
    snprintf(path, sizeof(path), "%s/cluster-session.accepted", scope);
    put(path, text);
    snprintf(text, sizeof(text), "V75_FEED1\n%ld\n7\n1\n", (long)pid);
    snprintf(path, sizeof(path), "%s/cluster-feed.state", scope);
    put(path, text);
}
int main(void)
{
    char path[256], text[256];
    pid_t child;
    int status;
    CHECK(wireless_session_pid() == 0);
    fixture(getpid());
    CHECK(wireless_session_pid() == getpid());
    snprintf(path, sizeof(path), "%s/cluster-session.accepted", scope);
    remove_file(path);
    CHECK(wireless_session_pid() == 0); /* Discovery/media without acceptance. */
    fixture(getpid());
    snprintf(path, sizeof(path), "%s/cluster-feed.state", scope);
    snprintf(text, sizeof(text), "V75_FEED1\n%ld\n8\n1\n", (long)getpid()); put(path, text);
    CHECK(wireless_session_pid() == 0); /* Stale generation after reconnect. */
    fixture(getpid());
    snprintf(text, sizeof(text), "V75_FEED1\n%ld\n7\n0\n", (long)getpid()); put(path, text);
    CHECK(wireless_session_pid() == 0);
    fixture(getpid());
    snprintf(text, sizeof(text), "V75_FEED1\n%ld\n7\n1\n", (long)getpid() + 1); put(path, text);
    CHECK(wireless_session_pid() == 0);
    fixture(getpid());
    remove_file("/dev/shmem/wcp_cp_session");
    CHECK(wireless_session_pid() == 0);
    fixture(getpid());
    put("/mnt/persist/btwcp_off", "1\n");
    CHECK(wireless_session_pid() == 0);
    remove_file("/mnt/persist/btwcp_off");
    CHECK(wireless_session_pid() == getpid());
    put("/ramdisk/v75-wireless-native.owner", "V75_NATIVE1\n2\n/ramdisk/../etc\n");
    CHECK(wireless_session_pid() == 0);
    fixture(getpid());
    snprintf(text, sizeof(text), "V75_NATIVE1\n%ld\n%s\nextra\n", (long)getpid(), scope);
    put("/ramdisk/v75-wireless-native.owner", text);
    CHECK(wireless_session_pid() == 0);
    fixture(getpid());
    snprintf(text, sizeof(text), "V75_NATIVE1\n0%ld\n%s\n", (long)getpid(), scope);
    put("/ramdisk/v75-wireless-native.owner", text);
    CHECK(wireless_session_pid() == 0);
    fixture(getpid());
    put("/dev/shmem/wcp_receiver.pid", "1\n");
    CHECK(wireless_session_pid() == 0);
    child = fork();
    CHECK(child >= 0);
    if (!child) _exit(0);
    CHECK(waitpid(child, &status, 0) == child);
    fixture(child);
    CHECK(wireless_session_pid() == 0);
    fixture(getpid());
    CHECK(wireless_session_pid() == getpid());
    printf("WIRELESS_SESSION_PASS checks=%u\n", checks);
    return 0;
}
