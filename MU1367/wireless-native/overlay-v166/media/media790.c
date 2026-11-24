/* SPDX-License-Identifier: GPL-3.0-or-later
 * Metadata/file-transfer observer for the exact audited 790 receiver.
 * No video, audio, display-info, send, getenv or thread-priority overrides.
 */
#define _POSIX_C_SOURCE 200112L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <errno.h>
#include <signal.h>
#include <pthread.h>
#include <dlfcn.h>
#include <time.h>
#include <sys/stat.h>
#include <fcntl.h>
#ifndef CPMAP_ROOT_PREFIX
#define CPMAP_ROOT_PREFIX ""
#endif
#include "wireless_session.h"
static pthread_mutex_t guard=PTHREAD_MUTEX_INITIALIZER;
static int enabled,reset_pending;
static void *next_fprintf;
static uint64_t media_nonce;
static unsigned media_session;
static uint64_t tap_now(void) {
    struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;
    return (uint64_t)t.tv_sec*1000000+(uint32_t)t.tv_nsec/1000;
}
static unsigned be16(const unsigned char *p){return ((unsigned)p[0]<<8)|p[1];}
static int atomic_file(const char *name,const void *data,size_t size) {
    char path[160],tmp[160];FILE *f;int ok;
    if(snprintf(path,sizeof(path),"/ramdisk/wcp-rg/%s",name)>=(int)sizeof(path)||
       snprintf(tmp,sizeof(tmp),"/ramdisk/wcp-rg/.%s.%ld",name,(long)getpid())>=(int)sizeof(tmp))return 0;
    f=fopen(tmp,"wb");if(!f)return 0;
    ok=fwrite(data,1,size,f)==size;if(fclose(f))ok=0;
    if(ok&&!rename(tmp,path))return 1;
    unlink(tmp);return 0;
}
#include "wcp_media.c"
#include "wcp_media_tap.h"
#include "wcp_bt_request.h"
static int was_accepted;static unsigned bt_counter;
static void publish_tick(void) {
    int accepted=wireless_accepted_pid(0)==getpid()&&access("/dev/ipod0",F_OK)!=0;
    char status[320];int n;
    pthread_mutex_lock(&guard);
    if(reset_pending){was_accepted=0;reset_pending=0;}
    if(accepted&&!was_accepted){if(!++media_session)media_session=1;}
    pthread_mutex_unlock(&guard);
    media_publish(accepted,media_nonce,media_session,was_accepted);
    {char lease[180];int length;if(!++bt_counter)bt_counter=1;
     length=snprintf(lease,sizeof(lease),"WCPRG1\n%ld\n%lu\n%u\n%u\n%d\n",(long)getpid(),(unsigned long)(uint32_t)media_nonce,bt_counter,media_session,accepted);
     if(length>0&&length<(int)sizeof(lease))atomic_file("session.state",lease,(size_t)length);}
    bt_request_publish(accepted,media_nonce,media_session,was_accepted);
    was_accepted=accepted;
    pthread_mutex_lock(&guard);
    n=snprintf(status,sizeof(status),"WCP790MEDIA1 pid=%ld accepted=%u session=%u np5001=%lu np_invalid=%lu cover_copied=%lu cover_dropped=%lu video_changes=0 audio_changes=0\n",
        (long)getpid(),accepted,media_session,media_updates,media_invalid,media_cover_copied,media_cover_dropped);
    pthread_mutex_unlock(&guard);
    if(n>0&&n<(int)sizeof(status))atomic_file("source-status.txt",status,(size_t)n);
}
static void *publisher(void *unused) {
    struct timespec delay;(void)unused;delay.tv_sec=0;delay.tv_nsec=100000000L;
    for(;;){publish_tick();nanosleep(&delay,0);}return 0;
}
void *wcp_tap_fprintf(const uintptr_t *r) {
    if(!next_fprintf)next_fprintf=dlsym(RTLD_NEXT,"fprintf");
    if(!next_fprintf)_exit(126);
    if(enabled)bt_request_observed(r);
    if(enabled&&r[13]==0xecbccU&&r[1]==0x1832aU) {
        const unsigned char *p=(const unsigned char *)r[5];unsigned id=r[2],n=r[3];
        if(p&&n<=WCP_MEDIA_MAX&&be16(p)==0x4040&&be16(p+2)==n+6&&be16(p+4)==id) {
            pthread_mutex_lock(&guard);
            if(id==0xaa05){media_clear_locked();reset_pending=1;}
            else if(id==0x5001){
                if(wcp_media_message(&media,p+6,n)){media_received=tap_now();media_updates++;}
                else media_invalid++;
            }
            pthread_mutex_unlock(&guard);
        }
    }
    if(enabled&&r[13]==0xee6dcU&&r[1]==0x1e171U)media_cover_completed(r);
    if(enabled&&r[13]==0xee5bcU&&r[1]==0x1eb53U)media_cover_clear(r);
    return next_fprintf;
}
__attribute__((constructor)) static void init(void) {
    struct stat st;struct timespec t;pthread_t thread;const char *mode=getenv("CPMAP_WCP_MEDIA790");
    if(enabled||!mode||strcmp(mode,"1"))return;
    next_fprintf=dlsym(RTLD_NEXT,"fprintf");next_memcpy=dlsym(RTLD_NEXT,"memcpy");
    if(!next_fprintf||!next_memcpy)return;
    if(mkdir("/ramdisk/wcp-rg",0700)&&errno!=EEXIST)return;
    if(lstat("/ramdisk/wcp-rg",&st)||!S_ISDIR(st.st_mode))return;
    if(clock_gettime(CLOCK_REALTIME,&t))return;
    media_nonce=((uint64_t)(uint32_t)t.tv_sec<<32)^(uint32_t)t.tv_nsec^(uint32_t)getpid();
    if(!pthread_create(&thread,0,publisher,0)){pthread_detach(thread);enabled=1;}
}
