/* SPDX-License-Identifier: GPL-3.0-or-later
 * One supervised artwork fetch. No stock consuming artwork request is made.
 * Decoder and device/file I/O are confined to a child with a five-second lease.
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
static void stop_fetch(int s){(void)s;stopped=1;}
static uint64_t millis(void){
    struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return UINT64_MAX;
    return (uint64_t)t.tv_sec*1000u+(unsigned long)t.tv_nsec/1000000u;
}
static int number(const char *s,unsigned base,uint64_t maximum,uint64_t *v){
    unsigned n=0;uint64_t r=0;
    while(*s){unsigned c=(unsigned char)*s++,d;
        if(++n>20)return 0;
        if(c>='0'&&c<='9')d=c-'0';else if(c>='a'&&c<='f')d=c-'a'+10;else return 0;
        if(d>=base || r>(maximum-d)/base)return 0;r=r*base+d;
    }
    if(!n)return 0;*v=r;return 1;
}
static int valid(const unsigned char *b,size_t n,uint64_t uid,unsigned id,unsigned bytes){
    unsigned i;
    if(n!=128u+bytes || memcmp(b,"N4AR",4) || n3_u32(b+4,1)!=1 || n3_u32(b+8,1)!=128 ||
       n3_u32(b+16,1) || n3_u32(b+20,1)!=bytes ||
       (n3_u32(b+24,1)!=1 && n3_u32(b+24,1)!=2) ||
       n3_u32(b+36,1)!=n3_u32(b+64,1) || n3_u32(b+68,1)!=1 ||
       n3_u32(b+40,1)!=id || n3_u32(b+44,1)!=1 ||
       n3_u32(b+48,1)!=(uint32_t)uid || n3_u32(b+52,1)!=(uint32_t)(uid>>32) ||
       n3_u32(b+76,1)>=1000000000u)return 0;
    for(i=56;i<64;i+=4)if(n3_u32(b+i,1))return 0;
    for(i=80;i<128;i+=4)if(n3_u32(b+i,1))return 0;
    return uid && bytes>=8 && bytes<=800000;
}
static ssize_t snapshot(const char *device,unsigned char *b){
    int fd=open(device,O_RDONLY|O_NONBLOCK);ssize_t n;
    if(fd<0)return -1;
    do{n=read(fd,b,800128);}while(n<0 && errno==EINTR);
    if(close(fd))return -1;return n;
}
static int fetch(const char *device,const char *png,uint64_t uid,unsigned id,unsigned size){
    unsigned char *first=malloc(800128),*last=malloc(800128);ssize_t n;
    struct n3_image_info info;int rc=1;
    if(!first || !last)goto done;
    n=snapshot(device,first);
    if(n<0 || !valid(first,(size_t)n,uid,id,size))goto done;
    if(!n3_decode(first+128,size,png,&info))goto done;
    n=snapshot(device,last);
    if(n<0 || !valid(last,(size_t)n,uid,id,size) ||
       memcmp(first,last,128))goto done; /* includes session, instance, generation */
    rc=0;
done:free(first);free(last);return rc;
}
int main(int argc,char **argv){
    uint64_t uid,id,size,start;struct stat st;int pipes[2],reaped=0,status=0,result=1;
    unsigned i;pid_t child;char answer=1;ssize_t count=0;
    if(argc!=7 || !number(argv[4],16,UINT64_MAX,&uid) || !uid ||
       !number(argv[5],10,255,&id) || !id || !number(argv[6],10,800000,&size) || size<8){
        puts("ARTWORK_ERROR=ARGUMENTS");return 1;
    }
    if(!lstat(argv[3],&st) || errno!=ENOENT){puts("ARTWORK_ERROR=OUTPUT_EXISTS");return 1;}
    if(mkdir(argv[2],0700)){puts("ARTWORK_ERROR=LOCK_OR_STALE_CHILD_REBOOT");return 1;}
    start=millis();if(start==UINT64_MAX || pipe(pipes))goto clean;
    if(pipes[0]>=FD_SETSIZE){close(pipes[0]);close(pipes[1]);goto clean;}
    child=fork();if(child<0){close(pipes[0]);close(pipes[1]);goto clean;}
    if(!child){
        char rc;close(pipes[0]);signal(SIGTERM,SIG_DFL);signal(SIGINT,SIG_DFL);
        rc=(char)fetch(argv[1],argv[3],uid,(unsigned)id,(unsigned)size);
        do{count=write(pipes[1],&rc,1);}while(count<0 && errno==EINTR);
        close(pipes[1]);_exit(count==1?0:1);
    }
    close(pipes[1]);signal(SIGTERM,stop_fetch);signal(SIGINT,stop_fetch);
    while(!stopped){
        fd_set set;struct timeval timeout;int ready;uint64_t t=millis();
        if(t==UINT64_MAX || t<start || t-start>=5000)break;
        FD_ZERO(&set);FD_SET(pipes[0],&set);timeout.tv_sec=0;timeout.tv_usec=50000;
        ready=select(pipes[0]+1,&set,0,0,&timeout);
        if(ready<0 && errno==EINTR)continue;if(ready<0)break;
        if(ready>0){do{count=read(pipes[0],&answer,1);}while(count<0 && errno==EINTR);break;}
    }
    close(pipes[0]);kill(child,SIGKILL);
    for(i=0;i<25;i++){
        struct timespec pause={0,10000000};pid_t p=waitpid(child,&status,WNOHANG);
        if(p==child || (p<0 && errno==ECHILD)){reaped=1;break;}nanosleep(&pause,NULL);
    }
    if(!reaped){puts("ARTWORK_ERROR=CHILD_NOT_REAPED_LOCK_RETAINED_REBOOT");return 1;}
    if(count==1 && !answer)result=0;
    if(result)unlink(argv[3]);
clean:
    if(rmdir(argv[2]))return 1;
    puts(result?"ARTWORK_ERROR=CAPTURE_IDENTITY_OR_TIMEOUT":"ARTWORK_FETCH_OK");return result;
}
