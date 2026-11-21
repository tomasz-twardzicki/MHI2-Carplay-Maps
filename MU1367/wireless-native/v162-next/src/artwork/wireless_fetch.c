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
struct wireless_identity {uint32_t pid,session,generation,id,serial,size;uint64_t nonce,uid;};
static int wireless_valid(const unsigned char *b,size_t n,const struct wireless_identity *i) {
    unsigned at;
    if(n!=64+i->size || memcmp(b,"WCA1",4) || n3_u32(b+4,1)!=1 || n3_u32(b+8,1)!=n ||
       n3_u32(b+12,1)!=i->pid || n3_u32(b+16,1)!=(uint32_t)i->nonce || n3_u32(b+20,1)!=(uint32_t)(i->nonce>>32) ||
       n3_u32(b+24,1)!=i->session || n3_u32(b+28,1)!=i->generation ||
       n3_u32(b+32,1)!=(uint32_t)i->uid || n3_u32(b+36,1)!=(uint32_t)(i->uid>>32) ||
       n3_u32(b+40,1)!=i->id || n3_u32(b+44,1)!=i->serial || n3_u32(b+48,1)!=i->size)return 0;
    for(at=52;at<64;at++)if(b[at])return 0;return 1;
}
static ssize_t wireless_snapshot(const char *path,unsigned char *b) {
    struct stat before,opened;int fd;size_t at=0;ssize_t n=-1;
    if(lstat(path,&before) || !S_ISREG(before.st_mode) || before.st_size<72 || before.st_size>800064)return -1;
    fd=open(path,O_RDONLY);if(fd<0)return -1;
    if(fstat(fd,&opened) || !S_ISREG(opened.st_mode) || opened.st_ino!=before.st_ino || opened.st_dev!=before.st_dev || opened.st_size!=before.st_size)goto done;
    while(at<(size_t)opened.st_size) {
        ssize_t r=read(fd,b+at,(size_t)opened.st_size-at);
        if(r<0 && errno==EINTR)continue;if(r<=0)goto done;at+=r;
    }
    n=(ssize_t)at;
done:if(close(fd))n=-1;return n;
}
static int wireless_fetch(const char *device,const char *png,const struct wireless_identity *identity) {
    unsigned char *first=malloc(800064),*last=malloc(800064);ssize_t n;struct n3_image_info info;int rc=1;
    if(!first || !last)goto done;
    n=wireless_snapshot(device,first);if(n<0 || !wireless_valid(first,n,identity))goto done;
    if(!n3_decode(first+64,identity->size,png,&info))goto done;
    n=wireless_snapshot(device,last);if(n<0 || !wireless_valid(last,n,identity) || memcmp(first,last,64))goto done;
    rc=0;
done:free(first);free(last);return rc;
}
int main(int argc,char **argv){
    uint64_t values[8],start;struct stat st;int pipes[2],reaped=0,status=0,result=1;
    unsigned i;pid_t child;char answer=1;ssize_t count=0;struct wireless_identity identity;
    const unsigned bases[8]={10,16,10,10,16,10,10,10};
    const uint64_t maxima[8]={2147483647,UINT64_MAX,UINT32_MAX,UINT32_MAX,UINT64_MAX,255,UINT32_MAX,800000};
    if(argc!=12){puts("ARTWORK_ERROR=ARGUMENTS");return 1;}
    for(i=0;i<8;i++)if(!number(argv[i+4],bases[i],maxima[i],&values[i]) || !values[i]){puts("ARTWORK_ERROR=ARGUMENTS");return 1;}
    if(values[0]<=1 || values[7]<8)return 1;
    identity.pid=values[0];identity.nonce=values[1];identity.session=values[2];identity.generation=values[3];
    identity.uid=values[4];identity.id=values[5];identity.serial=values[6];identity.size=values[7];
    if(!lstat(argv[3],&st) || errno!=ENOENT){puts("ARTWORK_ERROR=OUTPUT_EXISTS");return 1;}
    if(mkdir(argv[2],0700)){puts("ARTWORK_ERROR=LOCK_OR_STALE_CHILD_REBOOT");return 1;}
    start=millis();if(start==UINT64_MAX || pipe(pipes))goto clean;
    if(pipes[0]>=FD_SETSIZE){close(pipes[0]);close(pipes[1]);goto clean;}
    child=fork();if(child<0){close(pipes[0]);close(pipes[1]);goto clean;}
    if(!child){
        char rc;close(pipes[0]);signal(SIGTERM,SIG_DFL);signal(SIGINT,SIG_DFL);
        rc=(char)wireless_fetch(argv[1],argv[3],&identity);
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
