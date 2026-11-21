/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef CPMAP_WCP_CAPTURE_CLOCK_H
#define CPMAP_WCP_CAPTURE_CLOCK_H
#include <stdint.h>
#include <string.h>

/* Capture and arrival are both expressed as local monotonic microseconds,
 * but arrival includes transport/adapter latency. Never substitute an arrival
 * timestamp directly into a presentation timeline anchored to capture time.
 *
 * Deadline capture stays in the real local clock. Only returned presentation
 * time gets an epoch adjustment when a bad/missing timestamp would otherwise
 * jump forward by seconds or run backward. This cannot add a smoothing hold.
 */
struct wcp_capture_clock {
    uint32_t pid,session;
    uint64_t capture_anchor,arrival_anchor,last,period,frames_since_match;
    int64_t adjustment;
    unsigned long fallbacks,repairs,epochs;
};
static uint64_t wcp_ntp_us(uint64_t ntp) {
    return (ntp>>32)*1000000ULL+((ntp&0xffffffffULL)*1000000ULL>>32);
}
static uint64_t wcp_us_ntp(uint64_t us) {
    return (us/1000000ULL<<32)+((us%1000000ULL)<<32)/1000000ULL;
}
static void wcp_capture_clock_clear(struct wcp_capture_clock *c) {
    unsigned long fallbacks=c->fallbacks,repairs=c->repairs,epochs=c->epochs;
    memset(c,0,sizeof(*c));c->fallbacks=fallbacks;c->repairs=repairs;c->epochs=epochs;
}
static void wcp_capture_clock_bind(struct wcp_capture_clock *c,uint32_t pid,uint32_t session) {
    if(c->pid!=pid || (c->session && session && c->session!=session)) {
        wcp_capture_clock_clear(c);c->epochs++;
    }
    c->pid=pid;
    /* A producer can become ready after the first arrival-only frames. That
     * first known session must not throw away their presentation continuity. */
    if(session)c->session=session;
}
static uint64_t wcp_capture_clock_step(struct wcp_capture_clock *c,uint64_t capture,
                                      uint64_t arrival,uint64_t *deadline_capture) {
    uint64_t raw,period=c->period?c->period:25000,output;
    *deadline_capture=0;
    if(c->frames_since_match<1000000)c->frames_since_match++;
    if(capture) {
        if(c->capture_anchor && capture>c->capture_anchor && c->frames_since_match) {
            uint64_t estimate=(capture-c->capture_anchor)/c->frames_since_match;
            if(estimate>=5000 && estimate<=250000)
                c->period=c->period?(c->period*7+estimate)/8:estimate;
        }
        c->capture_anchor=capture;c->arrival_anchor=arrival;c->frames_since_match=0;
        raw=capture;*deadline_capture=capture;
    } else {
        c->fallbacks++;
        if(c->capture_anchor) {
            if(arrival && c->arrival_anchor && arrival>=c->arrival_anchor)
                raw=c->capture_anchor+(arrival-c->arrival_anchor);
            else raw=c->capture_anchor+c->frames_since_match*period;
            *deadline_capture=raw;
        } else raw=arrival?arrival:(c->last?c->last+period:1);
    }
    /* The representable NTP uptime is below 2^53 us. Refuse pathological input
     * before signed adjustment arithmetic; normal monotonic time is much less. */
    if(raw>INT64_MAX/4)raw=c->last?c->last+period:1;
    if(c->last && ((int64_t)raw+c->adjustment<=(int64_t)c->last ||
       (uint64_t)((int64_t)raw+c->adjustment)-c->last>250000)) {
        c->adjustment=(int64_t)(c->last+period)-(int64_t)raw;c->repairs++;
    }
    output=(uint64_t)((int64_t)raw+c->adjustment);
    c->last=output?output:1;
    return c->last;
}
#endif
