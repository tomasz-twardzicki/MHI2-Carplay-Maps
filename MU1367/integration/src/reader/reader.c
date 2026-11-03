/* SPDX-License-Identifier: GPL-3.0-or-later
 * MU1367 reader-recovery test, forked from the pinned release reader
 * fa4b4ed62ab1969a9b32cdbeb78cdb01292b8c68d5f3ea7008b1a54d8cf2bc8d.
 * Wire format/validation unchanged. No driver writes or HMI output.
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
#define BUILD "MU1367-reader-v1.4.3-e"
#define MAX_RESTARTS 3u
#define BACKOFF_MS 1000u

/* RGJ1 records: snapshot, invalidate, stale, heartbeat, end. */
enum { SNAPSHOT=1, INVALIDATE=2, STALE=3, HEARTBEAT=4, END=5 };
enum { SOURCE_OPEN=1, SOURCE_READ=2, SHORT_READ=3, BAD_SNAPSHOT=4,
       WORKER_TIMEOUT=5, WORKER_EOF=6 };
enum { DURATION=0, STOP=1, CAPACITY=2, WORKER_FAILED=3, OUTPUT_FAILED=4 };
static volatile sig_atomic_t stopping;
static unsigned char frame[8 + SNAP], compact[SNAP], retained[SNAP];
static unsigned retained_kind=2, retained_detail=1;
static size_t retained_size;
static uint32_t serial;
enum { PHASE_OPEN=1, PHASE_READ=2, PHASE_CLOSE=3, PHASE_PIPE=4, PHASE_SLEEP=5 };
struct worker_state {
    pid_t pid;
    int data, trace, phase, reaped, child_status, kill_error, wait_error;
};
static struct worker_state child_state;
static unsigned restarts;
static const char *last_failure="none";

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

static void phase(int trace, unsigned char value) {
    /* Advisory only: the nonblocking trace pipe can never stall device reads. */
    (void)write(trace,&value,1);
}
static void worker(int output, int trace, const char *source) {
    struct timespec delay={0,POLL_MS*1000000u};
    signal(SIGTERM,SIG_DFL); signal(SIGINT,SIG_DFL); signal(SIGPIPE,SIG_DFL);
    for (;;) {
        int fd, saved=0; ssize_t n=0;
        phase(trace,PHASE_OPEN);
        fd=open(source,O_RDONLY|O_NONBLOCK);
        if (fd<0) saved=errno;
        else {
            phase(trace,PHASE_READ);
            do { n=read(fd,frame+8,SNAP); } while (n<0 && errno==EINTR);
            if (n<0) { saved=errno; n=0; }
            /* The supervisor's deadline includes close as well as open/read. */
            phase(trace,PHASE_CLOSE);
            if (close(fd) && !saved) saved=errno;
        }
        put32(frame,(uint32_t)saved);
        put32(frame+4,fd<0?SOURCE_OPEN:(saved?SOURCE_READ:(n==SNAP?0:SHORT_READ)));
        if (saved || n!=SNAP) memset(frame+8,0,SNAP);
        phase(trace,PHASE_PIPE);
        {
            size_t at;
            /* Keep individual writes within POSIX's minimum atomic pipe
             * capacity; do not depend on a large QNX pipe write completing. */
            for (at=0; at<sizeof(frame); at+=512) {
                size_t n=sizeof(frame)-at; if (n>512) n=512;
                if (write_all(output,frame+at,n)) _exit(1);
            }
        }
        phase(trace,PHASE_SLEEP);
        delay.tv_sec=0; delay.tv_nsec=POLL_MS*1000000u;
        if (nanosleep(&delay,NULL) && errno!=EINTR) _exit(1);
    }
}

struct journal { int fd; uint32_t bytes; uint64_t started; };
static int record(struct journal *j, unsigned kind, unsigned detail,
                  const unsigned char *payload, size_t n, uint64_t now) {
    unsigned char h[32]={0}; int fd, failed;
    (void)now;
    if (kind!=HEARTBEAT) {
        retained_kind=kind; retained_detail=detail; retained_size=n;
        if (n) memcpy(retained,payload,n);
    }
    if (retained_size>SNAP || serial==UINT32_MAX) return -1;
    memcpy(h,"RGM1",4); put32(h+4,1); put32(h+8,(uint32_t)(32+retained_size));
    put32(h+12,++serial); put32(h+16,retained_kind); put32(h+20,retained_detail);
    put32(h+24,(uint32_t)j->started); put32(h+28,(uint32_t)(j->started>>32));
    fd=open("latest.tmp",O_WRONLY|O_CREAT|O_TRUNC,0600);
    if (fd<0) return -1;
    failed=write_all(fd,h,sizeof(h)) || (retained_size && write_all(fd,retained,retained_size));
    if (close(fd)) failed=1;
    if (failed) { unlink("latest.tmp"); return -1; }
    if (rename("latest.tmp","latest.bin")) return -1;
    j->bytes=(uint32_t)(32+retained_size);
    return 0;
}

static int nonblock(int fd) {
    int flags=fcntl(fd,F_GETFL);
    return flags<0?-1:fcntl(fd,F_SETFL,flags|O_NONBLOCK);
}
static int start_worker(const char *source, int ready) {
    int data[2], trace[2], saved;
    if (pipe(data)) return -1;
    if (pipe(trace)) { saved=errno; close(data[0]); close(data[1]); errno=saved; return -1; }
    if (nonblock(data[0]) || nonblock(trace[0]) || nonblock(trace[1])) goto failed;
    child_state.pid=fork();
    if (child_state.pid<0) goto failed;
    if (!child_state.pid) {
        close(data[0]); close(trace[0]); if (ready>=0) close(ready);
        worker(data[1],trace[1],source); _exit(1);
    }
    close(data[1]); close(trace[1]);
    child_state.data=data[0]; child_state.trace=trace[0]; child_state.phase=0;
    child_state.reaped=0; child_state.child_status=-1;
    child_state.kill_error=child_state.wait_error=0;
    return 0;
failed:
    saved=errno;
    close(data[0]); close(data[1]); close(trace[0]); close(trace[1]);
    errno=saved; return -1;
}
static void drain_trace(void) {
    unsigned char values[64]; unsigned i, pass;
    for (pass=0; pass<4 && child_state.trace>=0; ++pass) {
        ssize_t n=read(child_state.trace,values,sizeof(values));
        if (n<0 && errno==EINTR) continue;
        if (n<=0) break;
        for (i=0;i<(unsigned)n;++i)
            if (values[i]>=PHASE_OPEN && values[i]<=PHASE_SLEEP) child_state.phase=values[i];
    }
}
static int reap_worker(void) {
    unsigned i;
    if (child_state.pid<=0 || child_state.reaped) return child_state.reaped;
    for (i=0;i<=20;++i) {
        int status; pid_t got=waitpid(child_state.pid,&status,WNOHANG);
        if (got==child_state.pid) { child_state.child_status=status; child_state.reaped=1; return 1; }
        if (got<0 && errno!=EINTR) {
            child_state.wait_error=errno;
            /* ECHILD also confirms that no owned child remains to duplicate. */
            if (errno==ECHILD) child_state.reaped=1;
            return child_state.reaped;
        }
        if (!i && kill(child_state.pid,SIGKILL)) child_state.kill_error=errno;
        if (i<20) { struct timespec delay={0,10000000}; nanosleep(&delay,NULL); }
    }
    return 0;
}
static void close_worker(void) {
    drain_trace();
    if (child_state.data>=0) close(child_state.data);
    if (child_state.trace>=0) close(child_state.trace);
    child_state.data=child_state.trace=-1;
}
static int first_failure(const char *cause, int error, uint64_t time,
                         uint64_t received, size_t partial, uint32_t polls,
                         uint32_t good, uint32_t bad, uint32_t sequence, int retry) {
    FILE *f; int failed;
    if (!access("reader-failure-first.txt",F_OK)) return 0;
    f=fopen("reader-failure-first.tmp","w"); if (!f) return -1;
    failed=fprintf(f,"format=1 build=%s cause=%s errno=%d at_ms=%llu last_response_ms=%llu response_age_ms=%llu partial_bytes=%u worker_pid=%ld phase=%d child_reaped=%d child_status=%d kill_errno=%d wait_errno=%d polls=%u valid=%u invalid=%u sequence=%u restarts=%u recovery_allowed=%d\n",
        BUILD,cause,error,(unsigned long long)time,(unsigned long long)received,
        (unsigned long long)(time>=received?time-received:0),(unsigned)partial,
        (long)child_state.pid,child_state.phase,child_state.reaped,child_state.child_status,
        child_state.kill_error,child_state.wait_error,polls,good,bad,sequence,restarts,retry)<0;
    if (fclose(f)) failed=1;
    if (failed) { unlink("reader-failure-first.tmp"); return -1; }
    return rename("reader-failure-first.tmp","reader-failure-first.txt");
}

static int status_file(const char *state, uint32_t polls,
                       uint32_t good, uint32_t bad, uint32_t seq,
                       uint32_t bytes, unsigned reason) {
    FILE *f=fopen("status.tmp","w"); int failed;
    if (!f) return -1;
    failed=fprintf(f,"RG status=%s polls=%u valid=%u invalid=%u sequence=%u bytes=%u reason=%u build=%s restarts=%u last_failure=%s worker_pid=%ld phase=%d child_reaped=%d\n",
                   state,polls,good,bad,seq,bytes,reason,BUILD,restarts,last_failure,
                   (long)child_state.pid,child_state.phase,child_state.reaped)<0;
    if (fclose(f)) failed=1;
    return failed?-1:rename("status.tmp","status.txt");
}

static int observe(const char *source, unsigned seconds, int ready) {
    int result=0, reason=DURATION, invalid=0, stale=0;
    int last_error=-1, last_reason=-1, append=0, fault_error=0, retryable=0;
    unsigned fault_detail=WORKER_EOF;
    const char *fault="none";
    size_t have=0;
    uint32_t polls=0, good=0, bad=0, sequence=0;
    unsigned char last_header[64]={0};
    uint64_t now=now_ms(), received=now, changed=now, heartbeat=now, retry_at=0;
    uint64_t started=now;
    struct journal j;
    memset(&child_state,0,sizeof(child_state));
    child_state.pid=-1; child_state.data=child_state.trace=-1; child_state.child_status=-1;
    if (now==UINT64_MAX) return 1;
    j.started=now; j.bytes=16; j.fd=-1;
    if (start_worker(source,ready)) {
        fault="spawn"; fault_error=errno; goto fatal_worker;
    }
    if (status_file("running",0,0,0,0,j.bytes,0)) { reason=OUTPUT_FAILED; result=1; goto done; }
    if (ready>=0) { unsigned char ok=1; (void)write_all(ready,&ok,1); close(ready); ready=-1; }
    received=now_ms();
    if (received==UINT64_MAX) { fault="clock"; fault_error=errno; goto fatal_worker; }
    changed=heartbeat=received;
    while (!stopping && access("stop",F_OK)) {
        fd_set fds; struct timeval timeout={0,100000}; int rc;
        now=now_ms();
        if (now==UINT64_MAX || now<started) { fault="clock"; fault_error=errno; goto fatal_worker; }
        if (seconds && now-started>=(uint64_t)seconds*1000) break;
        if (retry_at && now>=retry_at) {
            /* A new mailbox instance forces the existing Java reader to
             * baseline. An unchanged old window can never reacquire output. */
            j.started=now>j.started?now:j.started+1;
            retained_kind=INVALIDATE; retained_detail=SOURCE_OPEN; retained_size=0;
            memset(last_header,0,sizeof(last_header));
            if (start_worker(source,-1)) { fault="spawn"; fault_error=errno; goto fatal_worker; }
            ++restarts; retry_at=0; have=0;
            received=changed=heartbeat=now;
            invalid=1; stale=0; last_reason=last_error=-1; append=0;
            if (record(&j,INVALIDATE,SOURCE_OPEN,NULL,0,now) ||
                status_file("unavailable",polls,good,bad,sequence,j.bytes,0)) {
                reason=OUTPUT_FAILED; result=1; break;
            }
        }
        if (retry_at) {
            struct timespec delay={0,100000000};
            if (now-heartbeat>=HEARTBEAT_MS) {
                heartbeat=now;
                if (record(&j,HEARTBEAT,sequence,NULL,0,now) ||
                    status_file("recovering",polls,good,bad,sequence,j.bytes,0)) {
                    reason=OUTPUT_FAILED; result=1; break;
                }
            }
            nanosleep(&delay,NULL); continue;
        }
        drain_trace();
        if (now-received>=DEADLINE_MS) {
            fault="timeout"; fault_error=0; fault_detail=WORKER_TIMEOUT; retryable=1; goto worker_fault;
        }
        if (now-changed>=STALE_MS && !stale) {
            append=record(&j,STALE,STALE_MS,NULL,0,now); stale=1;
            if (append) { result=1; reason=OUTPUT_FAILED; break; }
        }
        if (now-heartbeat>=HEARTBEAT_MS) {
            heartbeat=now; append=record(&j,HEARTBEAT,sequence,NULL,0,now);
            if (append || status_file(invalid?"unavailable":stale?"stale":"running",polls,good,bad,sequence,j.bytes,0)) {
                result=1; reason=OUTPUT_FAILED; break;
            }
        }
        {
            ssize_t n=read(child_state.data,frame+have,sizeof(frame)-have);
            if (n<0 && errno==EINTR) continue;
            if (n<0 && errno==EAGAIN) {
                FD_ZERO(&fds); FD_SET(child_state.data,&fds);
                rc=select(child_state.data+1,&fds,NULL,NULL,&timeout);
                if (rc<0 && errno!=EINTR) { fault="pipe-select"; fault_error=errno; goto fatal_worker; }
                continue;
            }
            if (n<=0) {
                fault=n==0?"eof":"pipe-read"; fault_error=n<0?errno:0;
                fault_detail=WORKER_EOF; retryable=1; goto worker_fault;
            }
            have+=(size_t)n;
        }
        if (have<sizeof(frame)) continue;
        have=0; received=now=now_ms(); ++polls;
        if (now==UINT64_MAX) { fault="clock"; fault_error=errno; goto fatal_worker; }
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
                if (memcmp(last_header,frame+8,64)) {
                    append=record(&j,SNAPSHOT,0,compact,n,now);
                    memcpy(last_header,frame+8,64); sequence=u32(frame+28);
                    changed=now; stale=0;
                }
                invalid=0; last_reason=last_error=-1;
            }
            if (append) { result=1; reason=OUTPUT_FAILED; break; }
        }
        continue;
worker_fault:
        last_failure=fault;
        /* Invalidate before cleanup/backoff. Never heartbeat a retained route. */
        if (record(&j,INVALIDATE,fault_detail,NULL,0,now)) {
            reason=OUTPUT_FAILED; result=1; break;
        }
        invalid=1;
        (void)reap_worker(); close_worker();
        retryable=retryable && child_state.reaped && restarts<MAX_RESTARTS && !stopping;
        if (first_failure(fault,fault_error,now,received,have,polls,good,bad,sequence,retryable)) {
            reason=OUTPUT_FAILED; result=1; break;
        }
        if (!retryable) { reason=WORKER_FAILED; result=1; break; }
        retry_at=now+((uint64_t)BACKOFF_MS<<restarts);
        heartbeat=now;
        if (status_file("recovering",polls,good,bad,sequence,j.bytes,0)) {
            reason=OUTPUT_FAILED; result=1; break;
        }
    }
    if (stopping || !access("stop",F_OK)) reason=STOP;
    goto done;
fatal_worker:
    last_failure=fault; result=1; reason=WORKER_FAILED;
    (void)reap_worker(); close_worker();
    if (first_failure(fault,fault_error,now==UINT64_MAX?started:now,received,have,polls,good,bad,sequence,0)) reason=OUTPUT_FAILED;
done:
    if (ready>=0) close(ready);
    (void)reap_worker(); close_worker();
    now=now_ms(); if (now==UINT64_MAX) now=j.started;
    if (record(&j,END,(unsigned)reason,NULL,0,now)) result=1;
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
            if (f) { ended=fgets(line,sizeof(line),f) && !strncmp(line,"RG status=ended ",16); fclose(f); }
            if (ended) { puts("CPMAP_GUIDANCE_STOPPED"); return 0; }
            nanosleep(&delay,NULL);
        }
        fputs("CPMAP_GUIDANCE_FAIL=STOP_NOT_CONFIRMED\n",stderr); return 1;
    }
    if (argc==4 && (!strcmp(argv[1],"serve") || !strcmp(argv[1],"start-live"))) {
        start=!strcmp(argv[1],"start-live"); seconds=0;
        if (argv[2][0]!='/') return 2;
    } else {
        if (argc!=5 || ((start=strcmp(argv[1],"start")==0)==0 && strcmp(argv[1],"run"))) {
            fputs("usage: guidance-reader serve|start-live ABSOLUTE_SOURCE NEW_RAM_DIR\n",stderr); return 2;
        }
        seconds=strtoul(argv[4],&tail,10);
        if (!*argv[4] || *tail || seconds<1 || seconds>600 || argv[2][0]!='/') return 2;
    }
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
            close(ack[0]); puts("CPMAP_GUIDANCE_STARTED"); return 0;
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
