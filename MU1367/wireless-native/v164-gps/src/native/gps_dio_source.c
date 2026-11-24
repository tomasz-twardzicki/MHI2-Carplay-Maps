/* SPDX-License-Identifier: GPL-3.0-or-later
 * Experimental passive NMEA source. The two callback slots belong exclusively
 * to CNMEAProvider in the EXACT K4525/P4521 executable. No service state,
 * subscription, sensor setting, serial port or on-disk OEM file is changed.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
#include <pthread.h>
#include <dlfcn.h>
#include <sys/stat.h>
#include "wcp_sha.h"
#include "wcp_location_source.h"
#include "wcp_location_options.h"
#define GPS_DIO_SHA "ead570d45071bb4dafe4a4667003bb9f82a72f58178f30dc86a08f11ce62a3ae"
static struct wcp_location_source gps_source;
static pthread_mutex_t gps_lock=PTHREAD_MUTEX_INITIALIZER;
static unsigned gps_sequence,gps_callbacks,gps_rejected;
static void (*gps_utf8)(void *,const void *);
static void (*gps_utf8_destroy)(void *);
static void (*gps_original)(void *,const void *,int);
static void (*gps_reply_original)(void *,const void *,int);
static uint64_t gps_now(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;return (uint64_t)t.tv_sec*1000000+t.tv_nsec/1000;}
static void gps_capture_line(const char *p,size_t n,uint64_t stamp){
    unsigned type;struct wcp_location_source_record *r;
    if(n<7||n>128)return;
    if(!memcmp(p,"$GPGGA,",7))type=0;else if(!memcmp(p,"$GPRMC,",7))type=1;else return;
    pthread_mutex_lock(&gps_lock);r=&gps_source.record[type];
    /* No checksum/fix alteration here. Consumer must see no-fix updates too. */
    if(++gps_sequence==0)++gps_sequence;r->sequence=gps_sequence;r->captured=stamp;r->size=(unsigned)n;
    memcpy(r->sentence,p,n);pthread_mutex_unlock(&gps_lock);
}
static void gps_capture(const void *shared){
    /* Exact native utf8 ScopeGuard ABI, observed at 1649e8..164a74.
     * shared = two-word util::SharedPtr<UnicodeString8>. Native temporary has
     * 40 bytes, storage selector at +6, inline/heap storage at +12 and mutex +32.
     * Never retain either borrowed Unicode or temporary ASCII pointer. */
    unsigned char temporary[40] __attribute__((aligned(8)));char line[1024];
    const uintptr_t *object=shared;const char *text;size_t n,start,i,limit;uint64_t stamp=gps_now();
    pthread_mutex_lock(&gps_lock);gps_callbacks++;pthread_mutex_unlock(&gps_lock);
    if(!object||!object[0]||!object[1]||!stamp)return;
    gps_utf8(temporary,(const void *)object[1]);
    if(pthread_mutex_lock((pthread_mutex_t *)(temporary+32))){gps_utf8_destroy(temporary);return;}
    if(temporary[6]&1){uintptr_t storage=*(uintptr_t *)(temporary+12);text=storage?*(const char **)storage:0;limit=sizeof(line);}
    else{text=(const char *)(temporary+12);limit=20;}
    if(text){for(n=0;n<limit&&text[n];n++){} if(n==limit)n=sizeof(line);}else n=sizeof(line);
    if(n<sizeof(line))memcpy(line,text,n);
    pthread_mutex_unlock((pthread_mutex_t *)(temporary+32));gps_utf8_destroy(temporary);
    if(n==sizeof(line)){pthread_mutex_lock(&gps_lock);gps_rejected++;pthread_mutex_unlock(&gps_lock);return;}
    start=0;for(i=0;i<n;i++)if(line[i]=='\n'){gps_capture_line(line+start,i+1-start,stamp);start=i+1;}
    if(start<n)gps_capture_line(line+start,n-start,stamp);
}
static void gps_primary_hook(void *self,const void *text,int type){gps_capture(text);gps_original(self,text,type);}
static void gps_reply_hook(void *self,const void *text,int type){gps_capture(text);gps_reply_original(self,text,type);}
static int gps_write(const char *name,const void *bytes,size_t n){
    char path[128],stage[128];FILE *f;int ok;
    snprintf(path,sizeof(path),"/ramdisk/wcp-location/%s",name);snprintf(stage,sizeof(stage),"/ramdisk/wcp-location/.%s.%ld",name,(long)getpid());
    f=fopen(stage,"wb");if(!f)return 0;ok=fwrite(bytes,1,n,f)==n;if(fclose(f))ok=0;
    if(ok&&!rename(stage,path))return 1;unlink(stage);return 0;
}
static void *gps_publish(void *unused){
    struct timespec pause={0,100000000};(void)unused;
    for(;;){unsigned char bytes[WCP_LOCATION_SOURCE_BYTES];char text[256];unsigned callbacks,rejected;int n;
        pthread_mutex_lock(&gps_lock);if(++gps_source.heartbeat==0)++gps_source.heartbeat;gps_source.published=gps_now();
        gps_source_encode(&gps_source,bytes);callbacks=gps_callbacks;rejected=gps_rejected;pthread_mutex_unlock(&gps_lock);
        gps_write("latest.bin",bytes,sizeof(bytes));
        n=snprintf(text,sizeof(text),"WGPS_SOURCE1 pid=%ld callbacks=%u rejected=%u gga=%u rmc=%u passive=1 subscription_changed=0\n",(long)getpid(),callbacks,rejected,gps_get32(bytes+32),gps_get32(bytes+176));
        if(n>0&&n<(int)sizeof(text))gps_write("source.status",text,(size_t)n);
        nanosleep(&pause,0);
    }return 0;
}
#ifndef CPMAP_GPS_SOURCE_NO_CONSTRUCTOR
__attribute__((constructor))static void gps_init(void){
    uintptr_t *vtable;struct stat st;pthread_t thread;const char *enabled=getenv("CPMAP_GPS_DIO");
    if(!enabled||strcmp(enabled,"164")||!gps_option_enabled(WCP_LOCATION_ENABLE_FILE))return;
    if(!wcp_hash_matches("/mnt/app/carplaymaps/stock_first/dio_manager.real",GPS_DIO_SHA))return;
    vtable=dlsym(RTLD_DEFAULT,"_ZTVN3dio13CNMEAProviderE");
    if((uintptr_t)vtable!=0x1a43d8U||vtable[12]!=0x1649c0U||vtable[42]!=0x1649b8U)return;
    if(mkdir("/ramdisk/wcp-location",0700)&&errno!=EEXIST)return;
    if(lstat("/ramdisk/wcp-location",&st)||!S_ISDIR(st.st_mode))return;
    gps_source.pid=(unsigned)getpid();gps_source.epoch=gps_now();if(!gps_source.epoch)return;
    gps_utf8=(void (*)(void *,const void *))0x112a88;gps_utf8_destroy=(void (*)(void *))0x1331cc;
    gps_original=(void (*)(void *,const void *,int))vtable[12];gps_reply_original=(void (*)(void *,const void *,int))vtable[42];
    if(pthread_create(&thread,0,gps_publish,0))return;pthread_detach(thread);
    /* This native vtable is in the executable's writable .data segment. Only
     * the two exact NMEA callbacks change, before any provider construction. */
    __sync_synchronize();vtable[12]=(uintptr_t)gps_primary_hook;vtable[42]=(uintptr_t)gps_reply_hook;__sync_synchronize();
}
#endif
