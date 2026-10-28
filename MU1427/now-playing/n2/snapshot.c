/* SPDX-License-Identifier: GPL-3.0-or-later
 * One bounded metadata-only snapshot. All device I/O is in one supervised
 * child. An unreaped child leaves the RAM lock in place until reboot.
 */
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/select.h>
#include <sys/wait.h>
#include <stdint.h>
#include <signal.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <errno.h>

static volatile sig_atomic_t stopped;
static void stop(int sig) { (void)sig; stopped=1; }
static uint32_t get32(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static uint64_t now(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC,&t)) return UINT64_MAX;
    return (uint64_t)t.tv_sec*1000u+(unsigned long)t.tv_nsec/1000000u;
}
static int validate(const unsigned char *b) {
    unsigned i;
    if (memcmp(b,"N2AO",4) || get32(b+4)!=1 || get32(b+8)!=128 ||
        (get32(b+12)&1) || get32(b+16)>1 || get32(b+68)>1 ||
        get32(b+76)>=1000000000u) return 0;
    for (i=60;i<64;i+=4) if (get32(b+i)) return 0;
    for (i=80;i<128;i+=4) if (get32(b+i)) return 0;
    return 1;
}
int main(int argc,char **argv) {
    struct { int error; unsigned char data[128]; } packet;
    int fd[2],status=0,received=0,reaped=0,result=1;
    pid_t child;
    uint64_t start,deadline;
    unsigned i;
    const char *names[]={"sequence","fault","associations","setups","data_calls",
        "completed","jpeg_signatures","png_signatures","oversize_setups",
        "setup_not_receiving","other_signatures","last_size"};
    if (argc!=3) { puts("N2_ERROR=ARGUMENTS"); return 1; }
    if (mkdir(argv[2],0700)) { puts("N2_ERROR=READER_LOCK_OR_STALE_CHILD_REBOOT"); return 1; }
    start=now(); if (start==UINT64_MAX) goto clean;
    if (pipe(fd)) goto clean;
    if (fd[0]>=FD_SETSIZE) { close(fd[0]);close(fd[1]);goto clean; }
    child=fork();
    if (child<0) { close(fd[0]);close(fd[1]);goto clean; }
    if (!child) {
        ssize_t n; int device;
        close(fd[0]); memset(&packet,0,sizeof(packet));
        signal(SIGTERM,SIG_DFL);signal(SIGINT,SIG_DFL);
        device=open(argv[1],O_RDONLY|O_NONBLOCK);
        if (device<0) packet.error=1;
        else {
            do { n=read(device,packet.data,128); } while (n<0 && errno==EINTR);
            if (n!=128) packet.error=2;
            if (close(device)) packet.error=3;
        }
        n=write(fd[1],&packet,sizeof(packet));
        close(fd[1]); _exit(n==(ssize_t)sizeof(packet)?0:1);
    }
    close(fd[1]); signal(SIGTERM,stop);signal(SIGINT,stop);
    deadline=start+1500;
    while (!stopped) {
        fd_set set; struct timeval timeout;
        uint64_t t=now(); int ready;
        if (t==UINT64_MAX || t>=deadline) break;
        FD_ZERO(&set);FD_SET(fd[0],&set);timeout.tv_sec=0;timeout.tv_usec=50000;
        ready=select(fd[0]+1,&set,0,0,&timeout);
        if (ready<0 && errno==EINTR) continue;
        if (ready<0) break;
        if (ready>0) {
            ssize_t n=read(fd[0],&packet,sizeof(packet));
            received=n==(ssize_t)sizeof(packet);
            break;
        }
    }
    close(fd[0]);
    /* Cleanup is bounded too. Never spawn another worker over a child whose
     * death/reaping has not been confirmed; the lock deliberately remains. */
    kill(child,SIGKILL);
    for (i=0;i<25;i++) {
        struct timespec pause={0,10000000};
        pid_t p=waitpid(child,&status,WNOHANG);
        if (p==child) { reaped=1; break; }
        if (p<0 && errno==ECHILD) { reaped=1; break; }
        nanosleep(&pause,0);
    }
    if (!reaped) { puts("N2_ERROR=CHILD_NOT_REAPED_LOCK_RETAINED_REBOOT"); return 1; }
    if (!received) puts("N2_ERROR=DEVICE_TIMEOUT_OR_SHORT_WORKER_REPLY");
    else if (packet.error) printf("N2_ERROR=DEVICE_IO_%d\n",packet.error);
    else if (!validate(packet.data)) puts("N2_ERROR=SNAPSHOT_SCHEMA");
    else {
        printf("format=1 observer=N2 bytes=128");
        for (i=0;i<12;i++) printf(" %s=%lu",names[i],(unsigned long)get32(packet.data+12+4*i));
        printf(" session=%lu enabled=%lu instance_sec=%lu instance_nsec=%lu\n",
            (unsigned long)get32(packet.data+64),(unsigned long)get32(packet.data+68),
            (unsigned long)get32(packet.data+72),(unsigned long)get32(packet.data+76));
        result=0;
    }
clean:
    if (rmdir(argv[2])) { puts("N2_ERROR=LOCK_REMOVE"); return 1; }
    return result;
}
