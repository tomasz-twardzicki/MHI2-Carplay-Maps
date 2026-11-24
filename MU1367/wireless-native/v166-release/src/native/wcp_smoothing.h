/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef CPMAP_WCP_SMOOTHING_H
#define CPMAP_WCP_SMOOTHING_H
#include <stdint.h>
#include "altscreen_frame_protocol.h"
struct wcp_smoothing { uint64_t base,delay,last_late,last_decay; };
static void wcp_smoothing_init(struct wcp_smoothing *s,unsigned ms) {
    s->base=s->delay=(uint64_t)ms*1000;s->last_late=s->last_decay=0;
}
/* Local clock and SDK-mapped presentation time are both CLOCK_MONOTONIC us.
 * Return this frame's slot; adapt only future frames. Never delay a late AU.
 */
static uint64_t wcp_smoothing_slot(struct wcp_smoothing *s,uint64_t capture,uint64_t now) {
    uint64_t slot;
    if(!s->base)return now;
    slot=capture+s->delay;
    if(now>slot) {
        uint64_t increment=now-slot;
        if(increment>10000)increment=10000;
        s->delay+=increment;if(s->delay>250000)s->delay=250000;
        s->last_late=s->last_decay=now;
        return now;
    }
    if(now>s->last_late && now-s->last_late>30000000 && now>s->last_decay && now-s->last_decay>=1000000 && s->delay>s->base) {
        uint64_t from=s->last_decay>s->last_late+30000000?s->last_decay:s->last_late+30000000;
        uint64_t steps=(now-from)/1000000,decay=steps*1000;
        if(decay>s->delay-s->base)decay=s->delay-s->base;
        s->delay-=decay;s->last_decay=from+steps*1000000;
    }
    return slot;
}
/* Skip encoded reference frames only through a queued, independent IDR.
 * A codec config boundary must be processed in order. */
static uint32_t wcp_smoothing_newer_idr(const AltFrameRing *ring,uint32_t current) {
    uint32_t at,available=ring->write_sequence,skip=0;
    for(at=current+1;at && at<=available && at-current<ALT_FRAME_RING_SLOT_COUNT;at++) {
        const AltFrameRingSlot *next=&ring->slots[(at-1)%ALT_FRAME_RING_SLOT_COUNT];
        uint32_t type,flags;
        if(next->committed_sequence!=at)break;
        __sync_synchronize();type=next->type;flags=next->flags;__sync_synchronize();
        if(next->committed_sequence!=at || type==ALT_FRAME_TYPE_CONFIG)break;
        if(type==ALT_FRAME_TYPE_VIDEO && (flags&ALT_FRAME_FLAG_KEYFRAME))skip=at;
    }
    return skip;
}
#endif
