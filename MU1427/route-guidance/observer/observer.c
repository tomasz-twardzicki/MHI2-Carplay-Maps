/* SPDX-License-Identifier: GPL-3.0-or-later
 * C4 diagnostic reader. Separate process; no driver writes or HMI output.
 * A supervised worker contains all potentially blocking device operations.
 */
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/select.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <errno.h>

#define SNAP 33088u
#define SLOTS 16u
#define STRIDE 2064u
#ifndef LIMIT
#define LIMIT (8u * 1024u * 1024u)
#endif
#define POLL_MS 100u
#define DEADLINE_MS 1500u
#ifndef STALE_MS
#define STALE_MS 5000u
#endif
#define HEARTBEAT_MS 1000u

/* RGJ1 records: snapshot, invalidate, stale, heartbeat, end. */
enum { SNAPSHOT=1, INVALIDATE=2, STALE=3, HEARTBEAT=4, END=5 };
enum { SOURCE_OPEN=1, SOURCE_READ=2, SHORT_READ=3, BAD_SNAPSHOT=4,
       WORKER_TIMEOUT=5, WORKER_EOF=6 };
enum { DURATION=0, STOP=1, CAPACITY=2, WORKER_FAILED=3, OUTPUT_FAILED=4 };
static volatile sig_atomic_t stopping;
static unsigned char frame[8 + SNAP], compact[SNAP];

static uint32_t u32(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static unsigned u16(const unsigned char *p) { return p[0] | (unsigned)p[1]<<8; }
static unsigned be16(const unsigned char *p) { return (unsigned)p[0]<<8 | p[1]; }
static void put32(unsigned char *p, uint32_t v) {
    unsigned i; for (i=0; i<4; ++i) p[i]=(unsigned char)(v>>(8*i));
}
static uint64_t now_ms(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) return UINT64_MAX;
    return (uint64_t)ts.tv_sec*1000u + (unsigned long)ts.tv_nsec/1000000u;
}
static void signal_stop(int sig) { (void)sig; stopping=1; }
static int write_all(int fd, const void *data, size_t length) {
    const unsigned char *p=data;
    while (length) {
        ssize_t n=write(fd,p,length);
        if (n<0 && errno==EINTR) continue;
        if (n<=0) return -1;
        p+=n; length-=(size_t)n;
    }
    return 0;
}

/* Validate the complete envelope before journaling any slot. Semantic field
 * widths, UTF-8 and state transitions are checked by the host decoder. */
static size_t pack_snapshot(const unsigned char *b) {
    uint32_t seq=u32(b+20), count=u32(b+24), session=u32(b+16);
    unsigned i, p; size_t used=64;
    if (memcmp(b,"RGI1",4) || u32(b+4)!=1 || u32(b+8)!=SNAP ||
        (u32(b+12)&1) || u32(b+28)>1 || u32(b+32) || u32(b+36)>1 ||
        u32(b+44)>=1000000000u || count!=(seq<SLOTS?seq:SLOTS) ||
        (!u32(b+36) && seq) || (u32(b+36) && !session)) return 0;
    for (i=48; i<64; i+=4) if (u32(b+i)) return 0;
    memcpy(compact,b,64);
    for (i=0; i<count; ++i) {
        uint32_t s=seq-count+1+i;
        const unsigned char *slot=b+64+((s-1)&15)*STRIDE;
        unsigned id=u16(slot+4), length=u16(slot+6), tlvs=0;
        if (u32(slot)!=s || u32(slot+8)!=session || u32(slot+12) ||
            length>2048 || (id!=0x5201 && id!=0x5202 && id!=0x5204)) return 0;
        for (p=0; p<length;) {
            unsigned n;
            if (length-p<4 || ++tlvs>256) return 0;
            n=be16(slot+16+p);
            if (n<4 || n>length-p) return 0;
            p+=n;
        }
        memcpy(compact+used,slot,16+length); used+=16+length;
    }
    return used;
}

static void worker(int output, const char *source) {
    struct timespec delay={0,POLL_MS*1000000u};
    signal(SIGTERM,SIG_DFL); signal(SIGINT,SIG_DFL); signal(SIGPIPE,SIG_DFL);
    for (;;) {
        int fd=open(source,O_RDONLY|O_NONBLOCK), saved=0; ssize_t n=0;
        if (fd<0) saved=errno;
        else {
            do { n=read(fd,frame+8,SNAP); } while (n<0 && errno==EINTR);
            if (n<0) { saved=errno; n=0; }
            /* The supervisor's deadline includes close as well as open/read. */
            if (close(fd) && !saved) saved=errno;
        }
        put32(frame,(uint32_t)saved);
        put32(frame+4,fd<0?SOURCE_OPEN:(saved?SOURCE_READ:(n==SNAP?0:SHORT_READ)));
        if (saved || n!=SNAP) memset(frame+8,0,SNAP);
        {
            size_t at;
            /* Keep individual writes within POSIX's minimum atomic pipe
             * capacity; do not depend on a large QNX pipe write completing. */
            for (at=0; at<sizeof(frame); at+=512) {
                size_t n=sizeof(frame)-at; if (n>512) n=512;
                if (write_all(output,frame+at,n)) _exit(1);
            }
        }
        delay.tv_sec=0; delay.tv_nsec=POLL_MS*1000000u;
        if (nanosleep(&delay,NULL) && errno!=EINTR) _exit(1);
    }
}

struct journal { int fd; uint32_t bytes; uint64_t started; };
static int record(struct journal *j, unsigned kind, unsigned detail,
                  const unsigned char *payload, size_t n, uint64_t now) {
    unsigned char h[32]={0};
    if (j->bytes+32u+n+(kind==END?0:32)>LIMIT) return 1;
    put32(h,kind); put32(h+4,(uint32_t)(now-j->started));
    put32(h+8,(uint32_t)n); put32(h+12,detail);
    if (write_all(j->fd,h,sizeof(h)) || (n && write_all(j->fd,payload,n))) return -1;
    j->bytes+=(uint32_t)(sizeof(h)+n); return 0;
}

static int status_file(const char *state, uint32_t polls,
                       uint32_t good, uint32_t bad, uint32_t seq,
                       uint32_t bytes, unsigned reason) {
    FILE *f=fopen("status.tmp","w"); int failed;
    if (!f) return -1;
    failed=fprintf(f,"C4 status=%s polls=%u valid=%u invalid=%u sequence=%u bytes=%u reason=%u\n",
                   state,polls,good,bad,seq,bytes,reason)<0;
    if (fclose(f)) failed=1;
    return failed?-1:rename("status.tmp","status.txt");
}

static int observe(const char *source, unsigned seconds, int ready) {
    int channel[2], flags, result=0, reason=DURATION, invalid=0, stale=0;
    int last_error=-1, last_reason=-1, append=0;
    pid_t child; size_t have=0;
    uint32_t polls=0, good=0, bad=0, sequence=0;
    unsigned char last_header[64]={0}, header[16]={0};
    uint64_t now=now_ms(), received=now, changed=now, heartbeat=now;
    struct journal j;
    if (now==UINT64_MAX) return 1;
    j.started=now; j.bytes=16;
    j.fd=open("events.rgj",O_WRONLY|O_CREAT|O_EXCL,0600);
    if (j.fd<0) return 1;
    memcpy(header,"RGJ1",4); put32(header+4,1); put32(header+8,SNAP); put32(header+12,POLL_MS);
    if (write_all(j.fd,header,sizeof(header)) || pipe(channel)) { close(j.fd); return 1; }
    child=fork();
    if (child<0) { close(channel[0]); close(channel[1]); close(j.fd); return 1; }
    if (!child) { close(j.fd); close(channel[0]); if (ready>=0) close(ready); worker(channel[1],source); _exit(1); }
    close(channel[1]);
    flags=fcntl(channel[0],F_GETFL);
    if (flags<0 || fcntl(channel[0],F_SETFL,flags|O_NONBLOCK)<0 ||
        status_file("running",0,0,0,0,j.bytes,0)) { reason=OUTPUT_FAILED; result=1; goto done; }
    if (ready>=0) { unsigned char ok=1; (void)write_all(ready,&ok,1); close(ready); ready=-1; }
    /* Output setup can take longer than the device deadline. Start that
     * deadline when the supervisor is ready to drain the worker pipe. */
    received=now_ms();
    if (received==UINT64_MAX) { reason=WORKER_FAILED; result=1; goto done; }
    changed=heartbeat=received;
    while (!stopping && access("stop",F_OK)) {
        fd_set fds; struct timeval timeout={0,100000}; int rc;
        now=now_ms();
        if (now==UINT64_MAX || now<j.started) { result=1; reason=WORKER_FAILED; break; }
        if (now-j.started>=(uint64_t)seconds*1000) break;
        if (now-received>=DEADLINE_MS) {
            append=record(&j,INVALIDATE,WORKER_TIMEOUT,NULL,0,now);
            result=1; reason=WORKER_FAILED; break;
        }
        if (now-changed>=STALE_MS && !stale) {
            append=record(&j,STALE,STALE_MS,NULL,0,now); stale=1;
            if (append) { result=append<0; reason=append<0?OUTPUT_FAILED:CAPACITY; break; }
        }
        if (now-heartbeat>=HEARTBEAT_MS) {
            heartbeat=now; append=record(&j,HEARTBEAT,sequence,NULL,0,now);
            if (append || status_file(invalid?"unavailable":stale?"stale":"running",polls,good,bad,sequence,j.bytes,0)) {
                result=append!=1; reason=append==1?CAPACITY:OUTPUT_FAILED; break;
            }
        }
        {
            ssize_t n=read(channel[0],frame+have,sizeof(frame)-have);
            if (n<0 && errno==EINTR) continue;
            if (n<0 && errno==EAGAIN) {
                /* Drain before arming readiness. A notification is advisory;
                 * also retry after timeout, including for a pending writer. */
                FD_ZERO(&fds); FD_SET(channel[0],&fds);
                rc=select(channel[0]+1,&fds,NULL,NULL,&timeout);
                if (rc<0 && errno!=EINTR) { result=1; reason=WORKER_FAILED; break; }
                continue;
            }
            if (n<=0) {
                append=record(&j,INVALIDATE,WORKER_EOF,NULL,0,now);
                result=1; reason=WORKER_FAILED; break;
            }
            have+=(size_t)n;
        }
        if (have<sizeof(frame)) continue;
        have=0; received=now=now_ms(); ++polls;
        if (now==UINT64_MAX) { result=1; reason=WORKER_FAILED; break; }
        {
            int error=(int)u32(frame), why=(int)u32(frame+4);
            size_t n=why?0:pack_snapshot(frame+8);
            if (!n) {
                ++bad; invalid=1;
                if (!why) why=BAD_SNAPSHOT;
                if (why!=last_reason || error!=last_error) {
                    unsigned char e[4]; put32(e,(unsigned)error);
                    append=record(&j,INVALIDATE,(unsigned)why,e,4,now);
                }
                last_reason=why; last_error=error;
            } else {
                ++good;
                /* Recovery of a read alone is not fresh guidance. After an
                 * invalidation/stale deadline, an unchanged header must not
                 * replay the old window and revive the previous route. */
                if (memcmp(last_header,frame+8,64)) {
                    append=record(&j,SNAPSHOT,0,compact,n,now);
                    memcpy(last_header,frame+8,64); sequence=u32(frame+28);
                    changed=now; stale=0;
                }
                invalid=0; last_reason=last_error=-1;
            }
            if (append) { result=append<0; reason=append<0?OUTPUT_FAILED:CAPACITY; break; }
        }
    }
    if (stopping || !access("stop",F_OK)) reason=STOP;
done:
    if (ready>=0) close(ready);
    /* Do not use blocking waitpid: even a failed device request cannot keep
     * the supervisor alive indefinitely during shutdown. */
    kill(child,SIGKILL);
    {
        unsigned i; struct timespec delay={0,10000000};
        for (i=0;i<20;++i) {
            if (waitpid(child,NULL,WNOHANG)!=0) break;
            nanosleep(&delay,NULL);
        }
    }
    close(channel[0]); now=now_ms();
    if (now==UINT64_MAX) now=j.started;
    if (record(&j,END,(unsigned)reason,NULL,0,now)) result=1;
    if (close(j.fd)) result=1;
    if (status_file("ended",polls,good,bad,sequence,j.bytes,(unsigned)reason)) result=1;
    return result;
}

int main(int argc, char **argv) {
    char *tail; unsigned long seconds; int start, ack[2]; pid_t pid;
    if (argc==3 && !strcmp(argv[1],"stop")) {
        unsigned i; int fd;
        if (chdir(argv[2])) return 1;
        fd=open("stop",O_CREAT|O_WRONLY,0600);
        if (fd<0 || close(fd)) return 1;
        for (i=0;i<30;++i) {
            char line[256]; FILE *f=fopen("status.txt","r"); int ended=0;
            struct timespec delay={0,100000000};
            if (f) { ended=fgets(line,sizeof(line),f) && !strncmp(line,"C4 status=ended ",16); fclose(f); }
            if (ended) { puts("CPMAP_RGI_C4_STOPPED"); return 0; }
            nanosleep(&delay,NULL);
        }
        fputs("CPMAP_RGI_C4_FAIL=STOP_NOT_CONFIRMED\n",stderr); return 1;
    }
    if (argc!=5 || ((start=strcmp(argv[1],"start")==0)==0 && strcmp(argv[1],"run"))) {
        fputs("usage: rgi-observer run|start ABSOLUTE_SOURCE NEW_OUTPUT_DIR SECONDS\n",stderr); return 2;
    }
    seconds=strtoul(argv[4],&tail,10);
    if (!*argv[4] || *tail || seconds<1 || seconds>600 || argv[2][0]!='/') return 2;
    umask(077); signal(SIGPIPE,SIG_IGN);
    signal(SIGTERM,signal_stop); signal(SIGINT,signal_stop);
    if (mkdir(argv[3],0700) || chdir(argv[3])) { perror("output directory"); return 1; }
    if (!start) return observe(argv[2],(unsigned)seconds,-1);
    if (pipe(ack)) return 1;
    pid=fork();
    if (pid<0) { close(ack[0]); close(ack[1]); return 1; }
    if (pid) {
        fd_set fds; struct timeval timeout={3,0}; unsigned char ok=0; int rc;
        close(ack[1]); FD_ZERO(&fds); FD_SET(ack[0],&fds);
        rc=select(ack[0]+1,&fds,NULL,NULL,&timeout);
        if (rc>0 && read(ack[0],&ok,1)==1 && ok==1) {
            close(ack[0]); puts("CPMAP_RGI_C4_STARTED"); return 0;
        }
        close(ack[0]); kill(pid,SIGTERM); return 1;
    }
    close(ack[0]);
    if (setsid()<0) _exit(1);
    {
        int fd=open("/dev/null",O_RDWR);
        if (fd<0) _exit(1);
        if (dup2(fd,0)<0 || dup2(fd,1)<0 || dup2(fd,2)<0) _exit(1);
        if (fd>2) close(fd);
    }
    _exit(observe(argv[2],(unsigned)seconds,ack[1]));
}
