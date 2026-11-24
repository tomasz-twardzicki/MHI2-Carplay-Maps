/* SPDX-License-Identifier: GPL-3.0-or-later. Shared bounded RAM snapshot. */
#ifndef CPMAP_LOCATION_SOURCE_H
#define CPMAP_LOCATION_SOURCE_H
#include <stdint.h>
#include <string.h>
#include "wcp_location.h"
#define WCP_LOCATION_SOURCE_BYTES 320
#define WCP_LOCATION_SOURCE_PATH "/ramdisk/wcp-location/latest.bin"
struct wcp_location_source_record {unsigned sequence,size;uint64_t captured;char sentence[128];};
struct wcp_location_source {
    unsigned pid,heartbeat;
    uint64_t epoch,published;
    struct wcp_location_source_record record[2];
};
static uint32_t gps_get32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void gps_put32(unsigned char *p,uint32_t n){p[0]=n;p[1]=n>>8;p[2]=n>>16;p[3]=n>>24;}
static uint64_t gps_get64(const unsigned char *p){return gps_get32(p)|(uint64_t)gps_get32(p+4)<<32;}
static void gps_put64(unsigned char *p,uint64_t n){gps_put32(p,(uint32_t)n);gps_put32(p+4,(uint32_t)(n>>32));}
static void gps_source_encode(const struct wcp_location_source *s,unsigned char *b){
    unsigned i;memset(b,0,WCP_LOCATION_SOURCE_BYTES);memcpy(b,"WGPS",4);gps_put32(b+4,1);gps_put32(b+8,s->pid);
    gps_put64(b+12,s->epoch);gps_put32(b+20,s->heartbeat);gps_put64(b+24,s->published);
    for(i=0;i<2;i++){const struct wcp_location_source_record *r=&s->record[i];unsigned char *p=b+32+i*144;
        gps_put32(p,r->sequence);gps_put64(p+4,r->captured);gps_put32(p+12,r->size);
        if(r->size<=128)memcpy(p+16,r->sentence,r->size);
    }
}
static int gps_source_decode(struct wcp_location_source *s,const unsigned char *b,size_t n,uint64_t now){
    struct wcp_location_source value;unsigned i;
    if(n!=WCP_LOCATION_SOURCE_BYTES||memcmp(b,"WGPS",4)||gps_get32(b+4)!=1)return 0;
    memset(&value,0,sizeof(value));value.pid=gps_get32(b+8);value.epoch=gps_get64(b+12);value.heartbeat=gps_get32(b+20);value.published=gps_get64(b+24);
    if(value.pid<=1||value.pid>0x7fffffffU||!value.epoch||!value.heartbeat||!value.published||now<value.published||now-value.published>WCP_LOCATION_AGE_US)return 0;
    for(i=0;i<2;i++){struct wcp_location_source_record *r=&value.record[i];const unsigned char *p=b+32+i*144;
        r->sequence=gps_get32(p);r->captured=gps_get64(p+4);r->size=gps_get32(p+12);
        if(r->size>128||(r->size&&(!r->sequence||!r->captured||r->captured>value.published)))return 0;
        memcpy(r->sentence,p+16,r->size);
    }
    memcpy(s,&value,sizeof(value));return 1;
}
#endif
