/* SPDX-License-Identifier: GPL-3.0-or-later
 * Phone presentation time, already mapped into receiver UpTicks by AirPlay.
 * Correlate unchanged VCL NALs across the existing Annex B -> AVCC adapter.
 */
#ifndef CPMAP_WCP_TIMING_H
#define CPMAP_WCP_TIMING_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define WCP_TIMING_PATH "/ramdisk/wcp-video-timing.bin"
#define WCP_TIMING_MAGIC 0x31544357U
#define WCP_TIMING_COUNT 256U
struct wcp_fingerprint { uint32_t hash, second, bytes, nals; };
struct wcp_timing_event {
    volatile uint32_t committed;
    struct wcp_fingerprint fingerprint;
    uint32_t timestamp_lo,timestamp_hi;
};
struct wcp_timing_ring {
    volatile uint32_t magic;
    uint32_t version,pid,session;
    volatile uint32_t sequence;
    struct wcp_timing_event events[WCP_TIMING_COUNT];
};
static void wcp_fingerprint_init(struct wcp_fingerprint *f) {
    memset(f,0,sizeof(*f));f->hash=2166136261U;f->second=5381U;
}
static void wcp_fingerprint_nal(struct wcp_fingerprint *f,const unsigned char *p,size_t n) {
    size_t i;unsigned type;
    if(!n)return;type=p[0]&31;
    if(type<1 || type>5)return;
    /* Annex B permits trailing_zero_8bits; normalize both representations. */
    while(n>1 && p[n-1]==0)--n;
    f->bytes+=(uint32_t)n;f->nals++;
    for(i=0;i<n;i++) {f->hash=(f->hash^p[i])*16777619U;f->second=(f->second*33U)^p[i];}
    f->hash=(f->hash^(uint32_t)n)*16777619U;
    f->second=(f->second*33U)^(uint32_t)n;
}
static size_t wcp_start_code(const unsigned char *p,size_t n,size_t at,size_t *prefix) {
    for(;at+3<=n;at++)if(!p[at] && !p[at+1]) {
        if(p[at+2]==1) {*prefix=3;return at;}
        if(at+4<=n && !p[at+2] && p[at+3]==1) {*prefix=4;return at;}
    }
    *prefix=0;return n;
}
static int wcp_fingerprint_annexb(struct wcp_fingerprint *f,const unsigned char *p,size_t n) {
    size_t prefix,at=wcp_start_code(p,n,0,&prefix);
    wcp_fingerprint_init(f);
    while(prefix) {size_t next_prefix,next=wcp_start_code(p,n,at+prefix,&next_prefix);
        wcp_fingerprint_nal(f,p+at+prefix,next-at-prefix);at=next;prefix=next_prefix;}
    return f->nals>0;
}
static int wcp_fingerprint_avcc(struct wcp_fingerprint *f,const unsigned char *p,size_t n,unsigned length_size) {
    size_t at=0;wcp_fingerprint_init(f);
    if(length_size<1 || length_size>4)return 0;
    while(at<n) {size_t size=0;unsigned i;
        if(n-at<length_size)return 0;
        for(i=0;i<length_size;i++)size=(size<<8)|p[at++];
        if(!size || size>n-at)return 0;
        wcp_fingerprint_nal(f,p+at,size);at+=size;
    }
    return f->nals>0;
}
static int wcp_fingerprint_equal(const struct wcp_fingerprint *a,const struct wcp_fingerprint *b) {
    return a->hash==b->hash && a->second==b->second && a->bytes==b->bytes && a->nals==b->nals;
}
#endif
