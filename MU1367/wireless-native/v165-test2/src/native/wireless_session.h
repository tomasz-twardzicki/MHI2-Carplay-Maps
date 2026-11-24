#ifndef MU1367_WIRELESS_SESSION_H
#define MU1367_WIRELESS_SESSION_H
/* SPDX-License-Identifier: GPL-3.0-or-later
 * Read the accepted-session/producer contract of the pinned V3.1 receiver.
 * Discovery and a receiver PID alone never authorize cluster takeover.
 */
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

static int wireless_read(const char *path, char *text, size_t size)
{
    struct stat st;
    FILE *f;
    size_t count;
    if (lstat(path, &st) || !S_ISREG(st.st_mode) ||
        st.st_size <= 0 || (size_t)st.st_size >= size) return 0;
    f = fopen(path, "r");
    if (!f) return 0;
    count = fread(text, 1, size - 1, f);
    if (ferror(f) || count != (size_t)st.st_size || fgetc(f) != EOF) {
        fclose(f); return 0;
    }
    fclose(f);
    if (memchr(text, 0, count)) return 0;
    text[count] = 0;
    return 1;
}

static int wireless_number(const char *text, unsigned long *value)
{
    unsigned long result = 0;
    const unsigned char *p = (const unsigned char *)text;
    if (!*p || (*p == '0' && p[1])) return 0;
    while (*p) {
        if (*p < '0' || *p > '9' || result > (ULONG_MAX - (*p - '0')) / 10)
            return 0;
        result = result * 10 + (*p++ - '0');
    }
    *value = result;
    return 1;
}

static int wireless_lines(char *text, char **lines, unsigned int count)
{
    unsigned int i;
    char *p = text, *end;
    for (i = 0; i < count; ++i) {
        lines[i] = p;
        end = strchr(p, '\n');
        if (!end) return 0;
        *end = 0;
        p = end + 1;
    }
    return !*p;
}

static pid_t wireless_accepted_pid(int require_feed)
{
    char owner[160], grant[100], feed[100], receiver[32], path[512];
    char *o[3], *g[3], *f[4];
    unsigned long pid, grant_pid, feed_pid, grant_generation, feed_generation, receiver_pid;
    const char *prefix = "/ramdisk/.v75-native-";
    struct stat st;
    size_t i, n;
    if (access(CPMAP_ROOT_PREFIX "/mnt/persist/btwcp_off", F_OK) == 0 ||
        !wireless_read(CPMAP_ROOT_PREFIX "/ramdisk/v75-wireless-native.owner", owner, sizeof(owner)) ||
        !wireless_lines(owner, o, 3) || strcmp(o[0], "V75_NATIVE1") ||
        !wireless_number(o[1], &pid) || pid <= 1 || pid > INT_MAX ||
        (kill((pid_t)pid, 0) != 0 && errno != EPERM)) return 0;
    n = strlen(prefix);
    if (strlen(o[2]) != n + 32 || strncmp(o[2], prefix, n)) return 0;
    for (i = n; i < n + 32; ++i)
        if (!strchr("0123456789abcdef", o[2][i])) return 0;
    if (snprintf(path, sizeof(path), "%s%s", CPMAP_ROOT_PREFIX, o[2]) >= (int)sizeof(path) ||
        lstat(path, &st) || !S_ISDIR(st.st_mode)) return 0;
    if (!wireless_read(CPMAP_ROOT_PREFIX "/dev/shmem/wcp_receiver.pid", receiver, sizeof(receiver))) return 0;
    n = strlen(receiver);
    if (n < 2 || receiver[n - 1] != '\n') return 0;
    receiver[n - 1] = 0;
    if (!wireless_number(receiver, &receiver_pid) || receiver_pid != pid ||
        access(CPMAP_ROOT_PREFIX "/dev/shmem/wcp_cp_session", F_OK)) return 0;
    if (snprintf(path, sizeof(path), "%s%s/cluster-session.accepted", CPMAP_ROOT_PREFIX, o[2]) >= (int)sizeof(path) ||
        !wireless_read(path, grant, sizeof(grant)) || !wireless_lines(grant, g, 3) ||
        strcmp(g[0], "V75_GRANT1") || !wireless_number(g[1], &grant_pid) || grant_pid != pid ||
        !wireless_number(g[2], &grant_generation) || !grant_generation || grant_generation > INT_MAX) return 0;
    if (!require_feed) return (pid_t)pid;
    if (snprintf(path, sizeof(path), "%s%s/cluster-feed.state", CPMAP_ROOT_PREFIX, o[2]) >= (int)sizeof(path) ||
        !wireless_read(path, feed, sizeof(feed)) || !wireless_lines(feed, f, 4) ||
        strcmp(f[0], "V75_FEED1") || !wireless_number(f[1], &feed_pid) || feed_pid != pid ||
        !wireless_number(f[2], &feed_generation) || feed_generation != grant_generation || strcmp(f[3], "1")) return 0;
    return (pid_t)pid;
}
static pid_t wireless_session_pid(void) { return wireless_accepted_pid(1); }
#endif
