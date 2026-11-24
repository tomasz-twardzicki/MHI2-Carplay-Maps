/* SPDX-License-Identifier: GPL-3.0-or-later
 * WGPS-v1 source side only. The independent ASI transport is not implemented by
 * this header. Call configure only after the real per-client configuration ACK.
 */
#ifndef CPMAP_GPS_PROVIDER_CORE_H
#define CPMAP_GPS_PROVIDER_CORE_H
#include "wcp_location_source.h"

struct gps_provider_core {
    struct wcp_location_source snapshot;
    struct wcp_location qualification;
    unsigned sequence, callbacks, accepted, rejected;
    int configured;
};
static void gps_provider_init(struct gps_provider_core *s,unsigned pid,uint64_t epoch) {
    memset(s,0,sizeof(*s));
    s->snapshot.pid=pid;s->snapshot.epoch=epoch;
    wcp_location_reset(&s->qualification,epoch);
}
static int gps_provider_configure(struct gps_provider_core *s,int acknowledged,
                                 int map_positioning,int dead_reckoning) {
    /* Initial GGA/RMC-only trial is raw GNSS. Estimated/sensor aiding is a
     * separate protocol stage, not data we label autonomous GNSS here. */
    s->configured=acknowledged==1&&map_positioning==0&&dead_reckoning==0;
    s->qualification.slot[0].size=s->qualification.slot[1].size=0;
    s->snapshot.published=0;
    return s->configured;
}
static int gps_provider_offer(struct gps_provider_core *s,const char *line,size_t n,
                              uint64_t captured,uint64_t now) {
    unsigned type;struct wcp_location_source_record *r;
    s->callbacks++;
    if(!s->configured||!line||n<7||n>128||!captured||now<captured)goto reject;
    if(!memcmp(line,"$GPGGA,",7))type=0;
    else if(!memcmp(line,"$GPRMC,",7))type=1;
    else return 0;
    if(++s->sequence==0) {
        /* Never wrap and accidentally replay an old sequence. */
        s->configured=0;goto reject;
    }
    if(!wcp_location_offer(&s->qualification,s->sequence,captured,now,line,n))goto reject;
    r=&s->snapshot.record[type];r->sequence=s->sequence;r->captured=captured;
    r->size=(unsigned)n;memcpy(r->sentence,line,n);s->accepted++;return 1;
reject:
    s->qualification.slot[0].size=s->qualification.slot[1].size=0;
    s->snapshot.published=0;s->rejected++;return 0;
}
static int gps_provider_encode(struct gps_provider_core *s,uint64_t now,
                                unsigned char bytes[WCP_LOCATION_SOURCE_BYTES]) {
    unsigned i;int ready=s->configured&&s->snapshot.pid>1&&s->snapshot.epoch&&now;
    for(i=0;i<2;i++) {
        const struct wcp_location_slot *q=&s->qualification.slot[i];
        if(!q->size||!q->received||now<q->received||now-q->received>WCP_LOCATION_AGE_US)ready=0;
    }
    if(++s->snapshot.heartbeat==0)++s->snapshot.heartbeat;
    /* Heartbeats never change sentence capture timestamps or GNSS UTC. A dead
     * or unqualified source deliberately emits an invalid lease, even while
     * its process is alive. The existing receiver then clears its fix cache. */
    s->snapshot.published=ready?now:0;
    gps_source_encode(&s->snapshot,bytes);return ready;
}
#endif
