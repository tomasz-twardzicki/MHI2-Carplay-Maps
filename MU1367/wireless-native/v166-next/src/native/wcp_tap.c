/* SPDX-License-Identifier: GPL-3.0-or-later
 * Receiver-scoped tap for exactly f195665b... (pinned by the launcher).
 * ARM call-site/register contracts are not portable to another receiver.
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
#include <sys/socket.h>
#include <sys/mman.h>
#include <fcntl.h>
#include "wcp_timing.h"
#include "wcp_rg.h"
#include "wcp_settings.h"
#ifndef CPMAP_ROOT_PREFIX
#define CPMAP_ROOT_PREFIX ""
#endif
#include "wireless_session.h"
static struct wcp_rg guidance;
static pthread_mutex_t guard=PTHREAD_MUTEX_INITIALIZER;
static void *next_fprintf;
static ssize_t (*next_send)(int,const void *,size_t,int);
static int enabled, timed,input_mode;
#include "wcp_priority.h"
static unsigned idr_interval=8,frame_count,frame_session,display_fps=40;
static uint64_t heartbeat;
#define PENDING_COUNT 128U
struct pending_guidance { unsigned id,size;uint64_t received;unsigned char payload[WCP_RG_MAX]; };
static struct pending_guidance pending[PENDING_COUNT];
static unsigned pending_head,pending_count,warmup;
static unsigned long captured[3],pending_dropped;
static uint64_t tap_now(void) {struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;return (uint64_t)t.tv_sec*1000000+(uint64_t)t.tv_nsec/1000;}
static void pending_message(unsigned id,const unsigned char *p,unsigned n) {
    struct pending_guidance *event;
    if(id!=0x5201 && id!=0x5202 && id!=0x5204)return;
    if(pending_count==PENDING_COUNT) {pending_head=(pending_head+1)%PENDING_COUNT;pending_count--;pending_dropped++;}
    captured[id==0x5201?0:id==0x5202?1:2]++;
    event=&pending[(pending_head+pending_count++)%PENDING_COUNT];event->id=id;event->size=n;event->received=tap_now();memcpy(event->payload,p,n);
}
static struct wcp_timing_ring *timing=MAP_FAILED;
static unsigned char mailbox[33120];
#include "wcp_driver_side.h"
static unsigned be16(const unsigned char *p) { return ((unsigned)p[0]<<8)|p[1]; }
static uint32_t be32(const unsigned char *p) { return ((uint32_t)be16(p)<<16)|be16(p+2); }
static int atomic_file(const char *name,const void *p,size_t n) {
    char tmp[160],path[160]; FILE *f; int ok;
    if(snprintf(path,sizeof(path),"/ramdisk/wcp-rg/%s",name)>=(int)sizeof(path) ||
       snprintf(tmp,sizeof(tmp),"/ramdisk/wcp-rg/.%s.%ld",name,(long)getpid())>=(int)sizeof(tmp))return 0;
    f=fopen(tmp,"w"); if(!f)return 0;
    ok=fwrite(p,1,n,f)==n; if(fclose(f))ok=0;
    if(ok && rename(tmp,path)==0)return 1;
    unlink(tmp);return 0;
}
#include "wcp_media.c"
#include "wcp_location_tap.h"
#include "wcp_media_tap.h"
/* The old input cadence remains the fallback until a live accepted receiver
 * has actually installed an IDR marker. A stale receipt cannot disable it. */
static int receiver_cadence_active(void) {
    char text[160],tail;unsigned long pid;unsigned session;
    unsigned long long stamp;uint64_t now=tap_now();pid_t accepted=wireless_accepted_pid(0);
    if(accepted<=1 || !wireless_read("/ramdisk/wcp-rg/idr.state",text,sizeof(text)))return 0;
    if(sscanf(text,"WCPIDR1\n%lu\n%u\n%llu\n%c",&pid,&session,&stamp,&tail)!=3)return 0;
    return pid==(unsigned long)accepted && session && stamp && now>=stamp && now-stamp<=1000000;
}
#include "wcp_bt_request.h"
static void *publisher(void *unused) {
    struct timespec delay; (void)unused;
    delay.tv_sec=0;delay.tv_nsec=100000000L;
    for(;;) {
        int accepted=wireless_accepted_pid(0)==getpid() && access("/dev/ipod0",F_OK)!=0;
        char status[320]; size_t n; uint64_t nonce; unsigned session;int was_accepted;
        pthread_mutex_lock(&guard);
        was_accepted=guidance.accepted;
        if(guidance.accepted && !accepted)pending_count=pending_head=0;
        if(!guidance.accepted && accepted)warmup=5;
        wcp_rg_accept(&guidance,accepted);
        /* Keep short pre-grant phone bursts, but publish only after acceptance.
         * Rate-limit replay so the HMI's 100ms poll cannot miss the route head
         * behind a burst of prefetched maneuvers/lanes in a 16-event mailbox.
         * Empty heartbeats first let the new source establish its baseline. */
        if(accepted && !warmup) {
            unsigned drained=0;uint64_t now=tap_now();
            while(pending_count && drained<4) {
                struct pending_guidance *event=&pending[pending_head];
                if(now>=event->received && now-event->received<=2000000) {
                    wcp_rg_message(&guidance,event->id,event->payload,event->size);drained++;
                }
                pending_head=(pending_head+1)%PENDING_COUNT;pending_count--;
            }
        }
        if(warmup)warmup--;
        if(!accepted) {
            if(timing!=MAP_FAILED)timing->magic=0;
            unlink("/ramdisk/wcp-rg/idr.state");
        }
        n=wcp_rg_mailbox(&guidance,mailbox,sizeof(mailbox));
        nonce=guidance.nonce;session=guidance.session;
        pthread_mutex_unlock(&guard);
        media_publish(accepted,nonce,session,was_accepted);
        bt_request_publish(accepted,nonce,session,was_accepted);
        location_poll();media_trace_publish();
        /* Serialized by this single writer; callback never performs file I/O. */
        if(n && atomic_file("latest.bin",mailbox,n)) {
            int length=snprintf(status,sizeof(status),"WCPRG1\n%ld\n%lu\n%lu\n%u\n%u\n",(long)getpid(),
                (unsigned long)(uint32_t)nonce,(unsigned long)++heartbeat,session,accepted);
            if(length>0 && length<(int)sizeof(status))atomic_file("session.state",status,(size_t)length);
            pthread_mutex_lock(&guard);
            length=snprintf(status,sizeof(status),"WCP162 fps=%u idr=%u rg5201=%lu rg5202=%lu lanes5204=%lu pending=%u dropped=%lu np5001=%lu np_invalid=%lu cover_copied=%lu cover_dropped=%lu\n",display_fps,idr_interval,captured[0],captured[1],captured[2],pending_count,pending_dropped,media_updates,media_invalid,media_cover_copied,media_cover_dropped);
            pthread_mutex_unlock(&guard);
            if(length>0 && length<(int)sizeof(status))atomic_file("source-status.txt",status,(size_t)length);
        }
        nanosleep(&delay,0);
    }
    return 0;
}
static void wcp_alt_display_fps(void *array,unsigned fps) {
    int count=((int (*)(void *))0x51d6c)(array),i;
    void *alt_type;
    if(count!=2)return;
    alt_type=((void *(*)(uint64_t))0x58fb0)(111);
    if(!alt_type)return;
    for(i=0;i<count;i++) {
        void *dict=((void *(*)(void *,int))0x51d90)(array,i),*type,*uuid;
        if(!dict)continue;
        type=((void *(*)(void *,void *))0x520ac)(dict,(void *)0x3fb6e);
        uuid=((void *(*)(void *,void *))0x520ac)(dict,(void *)0x3fb7b);
        /* Exact pinned alt-display type and UUID. The native main dictionary
         * retains its own 30-FPS maximum; unknown displays remain untouched. */
        if(type && uuid && ((int (*)(void *,void *))0x51cec)(type,alt_type) &&
           ((int (*)(void *,void *))0x51cec)(uuid,(void *)0x3fb88))
            ((int (*)(void *,void *,int64_t))0x5ada0)(dict,(void *)0x3fc0b,(int64_t)fps);
    }
    wcp_cf_release(alt_type);
}
void *wcp_tap_fprintf(const uintptr_t *r) {
    if(!next_fprintf)next_fprintf=dlsym(RTLD_NEXT,"fprintf");
    if(!next_fprintf)_exit(126);
    if(enabled && r[13]==0xe88c4U && r[1]==0x1cf35U && r[0])
        ((int (*)(FILE *,const char *,...))next_fprintf)((FILE *)r[0],
            "[cpmap][audio] t_us=%llu ",(unsigned long long)tap_now());
    if(enabled && r[13]==0xe4c00U && r[1]==0x1ceafU && r[4] && r[8]) {
        /* The actual display provider has appended the alternate dictionary.
         * Main-screen getenv FPS is hard-clamped to 30 in the pinned binary. */
        void *array=(void *)r[4];struct wcp_settings settings;unsigned fps;
        int settings_ok=wcp_settings_read(WCP_SETTINGS_PATH,&settings)==0;
        pthread_mutex_lock(&guard);
        if(settings_ok){display_fps=settings.fps;idr_interval=settings.idr;}
        fps=display_fps;
        pthread_mutex_unlock(&guard);
        wcp_alt_display_fps(array,fps);
    }
    if(enabled && r[13]==0xecbccU && r[1]==0x1832aU) {
        const unsigned char *p=(const unsigned char *)r[5]; unsigned id=r[2],n=r[3];
        if(n<=(id==0x5001?WCP_MEDIA_MAX:WCP_RG_MAX) && p && be16(p)==0x4040 && be16(p+2)==n+6 && be16(p+4)==id) {
            pthread_mutex_lock(&guard);
            location_message_locked(id,p+6,n);
            if(id==0xaa05) { wcp_rg_accept(&guidance,0);pending_count=pending_head=0;media_clear_locked(); }
            else if(id==0x5001) {
                if(wcp_media_message(&media,p+6,n)){media_received=tap_now();media_updates++;if(media.diag_md)media_trace_locked(1,media.diag_change,0);}else media_invalid++;
            }
            else pending_message(id,p+6,n);
            pthread_mutex_unlock(&guard);
        }
    }
    if(enabled)bt_request_observed(r);
    if(enabled && r[13]==0xee6dcU && r[1]==0x1e171U)media_cover_completed(r);
    if(enabled && r[13]==0xee5bcU && r[1]==0x1eb53U)media_cover_clear(r);
    return next_fprintf;
}
ssize_t wcp_tap_send(const uintptr_t *r) {
    if(!next_send)next_send=dlsym(RTLD_NEXT,"send");
    int fd=(int)r[0]; const void *data=(const void *)r[1]; size_t size=r[2]; int flags=r[3];
    /* The pinned input adapter sends a periodic OOB K every five AUs.
     * Suppress ONLY that call site. Startup, resume, corruption and bridge
     * recovery requests retain their original behavior. The receiver tap now
     * owns the separately selected wireless periodic cadence. */
    if(input_mode && r[13]==0x101b40U && r[17]==0x102a58U && size==1 &&
       flags==0x80 && data && *(const unsigned char *)data=='K' && receiver_cadence_active())return 1;
    if(timed && r[13]==0xe7300U) {
        const uint32_t *context=(const uint32_t *)r[5];
        const unsigned char *node=(const unsigned char *)r[10];
        /* The pinned sender receives parent+136, not the parent object.
         * Its own port is +64 and header-stripping flag is +112. The parent's
         * alt flag at +132 must never be read as sender+132 (parent+268).
         * That unrelated field changes across stream restarts and used to
         * disable both timing publication and the receiver IDR cadence. */
        if(context && node && context[64/4]==9997 && context[112/4] && data==node+24) {
            uint32_t total; uint64_t timestamp;
            struct wcp_fingerprint fp;
            memcpy(&total,node+4,4);
            timestamp=((uint64_t)be32(node+16)<<32)|be32(node+20);
            if(total>=16 && total-16==size && size<=256U*1024U && timestamp &&
               timing!=MAP_FAILED && wcp_fingerprint_annexb(&fp,data,size)) {
                /* Single alternate-video sender; session mutation is guarded. */
                pthread_mutex_lock(&guard);
                if(guidance.accepted) {
                    uint32_t sequence=timing->sequence+1;
                    if(frame_session!=guidance.session) {frame_count=0;frame_session=guidance.session;}
                    if(++frame_count % idr_interval==0) {
                        /* The audited alternate sender consumes this RAM marker
                         * and sends its native forceKeyFrame command next loop. */
                        int marker=open("/dev/shmem/alt_force_idr",O_WRONLY|O_CREAT,0600);
                        if(marker>=0) {
                            char receipt[128];int n;close(marker);
                            n=snprintf(receipt,sizeof(receipt),"WCPIDR1\n%lu\n%u\n%llu\n",(unsigned long)getpid(),guidance.session,(unsigned long long)tap_now());
                            if(n>0 && n<(int)sizeof(receipt))atomic_file("idr.state",receipt,n);
                        }
                    }
                    struct wcp_timing_event *e;
                    if(!sequence)sequence=1;
                    if(timing->session!=guidance.session) {
                        timing->magic=0;__sync_synchronize();
                        timing->session=guidance.session;timing->sequence=0;sequence=1;
                    }
                    e=&timing->events[(sequence-1)%WCP_TIMING_COUNT];e->committed=0;
                    e->fingerprint=fp;e->timestamp_lo=(uint32_t)timestamp;e->timestamp_hi=(uint32_t)(timestamp>>32);
                    __sync_synchronize();e->committed=sequence;__sync_synchronize();
                    timing->sequence=sequence;timing->magic=WCP_TIMING_MAGIC;
                }
                pthread_mutex_unlock(&guard);
            }
        }
    }
    if(!next_send) {errno=ENOSYS;return -1;}
    return next_send(fd,data,size,flags);
}
__attribute__((constructor)) static void init(void) {
    struct timespec t; pthread_t thread; struct stat st; struct wcp_settings settings;
    if(enabled)return;
    next_fprintf=dlsym(RTLD_NEXT,"fprintf");next_send=dlsym(RTLD_NEXT,"send");next_fopen=dlsym(RTLD_NEXT,"fopen");
    if(!next_fprintf || !next_send || !next_fopen)_exit(126);
    if(getenv("CPMAP_WCP_INPUT") && !strcmp(getenv("CPMAP_WCP_INPUT"),"162")) {input_mode=1;wcp_priority_floor("input-main");return;}
    /* Only the owned, hash-verifying receiver launcher enables this preload. */
    if(!getenv("CPMAP_WCP_TAP") || strcmp(getenv("CPMAP_WCP_TAP"),"162"))return;
    location_enabled=getenv("CPMAP_WCP_LOCATION")&&!strcmp(getenv("CPMAP_WCP_LOCATION"),"164");
    if(wcp_settings_read(WCP_SETTINGS_PATH,&settings))return;
    idr_interval=settings.idr;display_fps=settings.fps;
    if(mkdir("/ramdisk/wcp-rg",0700) && errno!=EEXIST)return;
    if(lstat("/ramdisk/wcp-rg",&st) || !S_ISDIR(st.st_mode))return;
    unlink("/ramdisk/wcp-rg/idr.state");
    clock_gettime(CLOCK_REALTIME,&t);
    wcp_rg_init(&guidance,((uint64_t)(uint32_t)t.tv_sec<<32)^(uint32_t)t.tv_nsec^(uint32_t)getpid(),(uint32_t)t.tv_sec,(uint32_t)t.tv_nsec);
    timed=getenv("CPMAP_WCP_TIMED_INPUT") && !strcmp(getenv("CPMAP_WCP_TIMED_INPUT"),"1");
    if(timed) {
        /* Publish a fully initialized new inode. Truncating the old inode
         * underneath a surviving bridge's mmap can cause SIGBUS on restart. */
        char path[160];int fd;
        snprintf(path,sizeof(path),WCP_TIMING_PATH ".%ld",(long)getpid());
        fd=open(path,O_RDWR|O_CREAT|O_EXCL,0600);
        if(fd>=0) {
            if(!ftruncate(fd,sizeof(*timing)))timing=mmap(0,sizeof(*timing),PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
            close(fd);
            if(timing!=MAP_FAILED) {
                memset(timing,0,sizeof(*timing));timing->version=1;timing->pid=getpid();
                if(rename(path,WCP_TIMING_PATH)) {munmap(timing,sizeof(*timing));timing=MAP_FAILED;}
            }
            unlink(path);
        }
    }
    if(!pthread_create(&thread,0,publisher,0)) {pthread_detach(thread);enabled=1;}
}
