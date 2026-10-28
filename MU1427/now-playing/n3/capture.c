/* SPDX-License-Identifier: GPL-3.0-or-later
 * Manual image diagnostic. Device I/O, decoding and file writes run only in
 * one supervised child. No HMI/driver callbacks, daemon or cluster output.
 */
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/select.h>
#include <sys/wait.h>
#include <signal.h>
#include <time.h>
#include "image.c"

static volatile sig_atomic_t stopped;
static void n3_stop(int s){(void)s;stopped=1;}
static uint64_t n3_now(void) {
    struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return UINT64_MAX;
    return (uint64_t)t.tv_sec*1000u+(unsigned long)t.tv_nsec/1000000u;
}
static int n3_validate(const unsigned char *b,size_t n) {
    unsigned i;uint32_t len;
    if(n<128 || memcmp(b,"N3AR",4) || n3_u32(b+4,1)!=1 || n3_u32(b+8,1)!=128 ||
       n3_u32(b+16,1)!=0 || n3_u32(b+68,1)>1 || n3_u32(b+76,1)>=1000000000u)return 0;
    len=n3_u32(b+20,1);if(len>800000 || n!=128u+len)return 0;
    if(!len){if(n3_u32(b+24,1))return 0;}
    else if(len<8 || (n3_u32(b+24,1)!=1 && n3_u32(b+24,1)!=2) ||
        n3_u32(b+36,1)!=n3_u32(b+64,1) || n3_u32(b+68,1)!=1)return 0;
    if(len && ((n3_u32(b+24,1)==1 && memcmp(b+128,"\x89PNG\r\n\x1a\n",8)) ||
        (n3_u32(b+24,1)==2 && (b[128]!=255 || b[129]!=216 || b[130]!=255))))return 0;
    for(i=40;i<64;i+=4)if(n3_u32(b+i,1))return 0;
    for(i=80;i<128;i+=4)if(n3_u32(b+i,1))return 0;
    return 1;
}
struct n3_result {
    int error,io_errno;
    uint32_t generation,bytes,kind,copied,rejected,capture_session,session,enabled,sec,nsec;
    unsigned width,height,orientation;uint32_t peak,elapsed;
};
static void n3_child(const char *device,const char *out,struct n3_result *r) {
    unsigned char *b=malloc(800128);int fd;ssize_t n;uint64_t start=n3_now();
    char raw[1024],png[1024];struct n3_image_info info;
    memset(r,0,sizeof(*r));
    if(!b){r->error=1;return;}
    fd=open(device,O_RDONLY|O_NONBLOCK);
    if(fd<0){r->error=2;r->io_errno=errno;goto done;}
    do{n=read(fd,b,800128);}while(n<0 && errno==EINTR);
    if(n<0){r->error=3;r->io_errno=errno;}
    if(close(fd)){r->error=4;r->io_errno=errno;}
    if(r->error)goto done;
    if(!n3_validate(b,(size_t)n)){r->error=5;goto done;}
    r->generation=n3_u32(b+12,1);r->bytes=n3_u32(b+20,1);r->kind=n3_u32(b+24,1);
    r->copied=n3_u32(b+28,1);r->rejected=n3_u32(b+32,1);r->capture_session=n3_u32(b+36,1);
    r->session=n3_u32(b+64,1);r->enabled=n3_u32(b+68,1);r->sec=n3_u32(b+72,1);r->nsec=n3_u32(b+76,1);
    if(!r->bytes)goto done;
    if(snprintf(raw,sizeof(raw),"%s/original.bin",out)>=(int)sizeof(raw) ||
       snprintf(png,sizeof(png),"%s/cover.png",out)>=(int)sizeof(png)){r->error=6;goto done;}
    if(!n3_write(raw,b+128,r->bytes)){r->error=7;r->io_errno=errno;goto done;}
    if(!n3_decode(b+128,r->bytes,png,&info)){r->error=8;goto done;}
    r->width=info.width;r->height=info.height;r->orientation=info.orientation;r->peak=(uint32_t)info.peak;
done:
    if(start!=UINT64_MAX) {uint64_t end=n3_now();if(end!=UINT64_MAX && end>=start)r->elapsed=(uint32_t)(end-start);}
    free(b);
}
int main(int argc,char **argv) {
    struct n3_result r;struct stat st;int pipefd[2],received=0,reaped=0,status=0,result=1;pid_t child;
    uint64_t start;unsigned i;size_t have=0;
    if(argc!=4){puts("N3_ERROR=ARGUMENTS");return 1;}
    if(lstat(argv[3],&st) || !S_ISDIR(st.st_mode)){puts("N3_ERROR=OUTPUT_DIRECTORY");return 1;}
    if(mkdir(argv[2],0700)){puts("N3_ERROR=LOCK_OR_STALE_CHILD_REBOOT");return 1;}
    start=n3_now();if(start==UINT64_MAX)goto clean;
    if(pipe(pipefd))goto clean;
    if(pipefd[0]>=FD_SETSIZE){close(pipefd[0]);close(pipefd[1]);goto clean;}
    child=fork();if(child<0){close(pipefd[0]);close(pipefd[1]);goto clean;}
    if(!child) {
        ssize_t n;close(pipefd[0]);signal(SIGTERM,SIG_DFL);signal(SIGINT,SIG_DFL);
        n3_child(argv[1],argv[3],&r);
        do{n=write(pipefd[1],&r,sizeof(r));}while(n<0 && errno==EINTR);
        close(pipefd[1]);_exit(n==(ssize_t)sizeof(r)?0:1);
    }
    close(pipefd[1]);signal(SIGTERM,n3_stop);signal(SIGINT,n3_stop);
    while(!stopped) {
        fd_set set;struct timeval timeout;int ready;uint64_t t=n3_now();
        if(t==UINT64_MAX || t>=start+5000)break;
        FD_ZERO(&set);FD_SET(pipefd[0],&set);timeout.tv_sec=0;timeout.tv_usec=50000;
        ready=select(pipefd[0]+1,&set,0,0,&timeout);
        if(ready<0 && errno==EINTR)continue;if(ready<0)break;
        if(ready>0) {
            ssize_t n=read(pipefd[0],(unsigned char *)&r+have,sizeof(r)-have);
            if(n<0 && errno==EINTR)continue;if(n<=0)break;
            have+=(size_t)n;if(have==sizeof(r)){received=1;break;}
        }
    }
    close(pipefd[0]);kill(child,SIGKILL);
    for(i=0;i<25;i++) {
        struct timespec pause={0,10000000};pid_t p=waitpid(child,&status,WNOHANG);
        if(p==child || (p<0 && errno==ECHILD)){reaped=1;break;}nanosleep(&pause,NULL);
    }
    if(!reaped){puts("N3_ERROR=CHILD_NOT_REAPED_LOCK_RETAINED_REBOOT");return 1;}
    if(!received)puts("N3_ERROR=DEVICE_DECODE_OR_WRITE_TIMEOUT");
    else if(r.error)printf("N3_ERROR=CAPTURE_%d errno=%d\n",r.error,r.io_errno);
    else {
        printf("format=1 observer=N3 generation=%lu bytes=%lu kind=%lu copied=%lu rejected=%lu capture_session=%lu session=%lu enabled=%lu instance_sec=%lu instance_nsec=%lu width=%u height=%u orientation=%u decoder_peak=%lu worker_ms=%lu track_identity_verified=0 cluster_output=0\n",
            (unsigned long)r.generation,(unsigned long)r.bytes,(unsigned long)r.kind,(unsigned long)r.copied,
            (unsigned long)r.rejected,(unsigned long)r.capture_session,(unsigned long)r.session,
            (unsigned long)r.enabled,(unsigned long)r.sec,(unsigned long)r.nsec,r.width,r.height,r.orientation,
            (unsigned long)r.peak,(unsigned long)r.elapsed);
        result=0;
    }
clean:
    if(rmdir(argv[2])){puts("N3_ERROR=LOCK_REMOVE");return 1;}return result;
}
