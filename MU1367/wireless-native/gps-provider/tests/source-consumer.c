/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "source_core.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned checks;
#define CHECK(x) do { checks++; if(!(x)){fprintf(stderr,"failed line %d: %s\n",__LINE__,#x);exit(1);} } while(0)
static size_t sentence(char *out,size_t capacity,const char *body) {
    unsigned sum=0;size_t i;
    for(i=0;body[i];i++)sum^=(unsigned char)body[i];
    return (size_t)snprintf(out,capacity,"$%s*%02X\r\n",body,sum);
}
static void pair(struct gps_provider_core *s,unsigned second,uint64_t now) {
    char body[128],line[140];size_t n;
    snprintf(body,sizeof(body),"GPGGA,1200%02u.00,5100.0000,N,00100.0000,W,1,10,0.8,10.0,M,0,M,,",second);
    n=sentence(line,sizeof(line),body);CHECK(gps_provider_offer(s,line,n,now,now));
    snprintf(body,sizeof(body),"GPRMC,1200%02u.00,A,5100.0000,N,00100.0000,W,10.0,90.0,241126,,,A",second);
    n=sentence(line,sizeof(line),body);CHECK(gps_provider_offer(s,line,n,now,now));
}
int main(void) {
    struct gps_provider_core s;struct wcp_location_source decoded;
    struct wcp_location phone;unsigned char bytes[320],packet[512];
    unsigned char ident[2048]={0x40,0x40,0,14,0x1d,1,0,4,0,6,0,4,0,7};
    const unsigned char request[]={0,6,0,0,4,210,0,4,0,1,0,4,0,2};
    size_t size=14,n;char line[160];unsigned i,j;uint64_t now=1000000;
    gps_provider_init(&s,2345,100);
    CHECK(!gps_provider_encode(&s,now,bytes));CHECK(!gps_source_decode(&decoded,bytes,320,now));
    CHECK(!gps_provider_configure(&s,0,0,0));CHECK(!gps_provider_configure(&s,1,1,0));
    CHECK(!gps_provider_configure(&s,1,0,1));CHECK(gps_provider_configure(&s,1,0,0));
    pair(&s,0,now);CHECK(gps_provider_encode(&s,now,bytes));
    CHECK(gps_source_decode(&decoded,bytes,320,now));
    wcp_location_reset(&phone,99);
    for(i=0;i<2;i++)CHECK(wcp_location_offer(&phone,decoded.record[i].sequence,decoded.record[i].captured,now,decoded.record[i].sentence,decoded.record[i].size));
    CHECK(wcp_location_identify(&phone,1,now,ident,&size,sizeof(ident))==1);
    CHECK(phone.advertised==1);CHECK(wcp_location_control(&phone,0xfffa,request,sizeof(request))==1);
    for(i=0;i<2;i++) {
        n=wcp_location_packet(&phone,1,now,packet,sizeof(packet));CHECK(n==11+decoded.record[i].size);
        CHECK(!memcmp(packet+10,decoded.record[i].sentence,decoded.record[i].size));
    }
    CHECK(!wcp_location_packet(&phone,1,now,packet,sizeof(packet)));
    /* Advancing heartbeat does not make an old capture fresh. */
    CHECK(!gps_provider_encode(&s,now+1500001,bytes));
    CHECK(!gps_source_decode(&decoded,bytes,320,now+1500001));
    CHECK(s.snapshot.record[0].captured==now);
    now+=2000000;pair(&s,2,now);CHECK(gps_provider_encode(&s,now,bytes));
    /* Replay at a new local arrival time is not a new GNSS sample. */
    n=sentence(line,sizeof(line),"GPGGA,120002.00,5100.0000,N,00100.0000,W,1,10,0.8,10.0,M,0,M,,");
    CHECK(!gps_provider_offer(&s,line,n,now+100,now+100));CHECK(!gps_provider_encode(&s,now+100,bytes));
    now+=1000000;pair(&s,3,now);
    n=sentence(line,sizeof(line),"GPRMC,120004.00,V,5100.0000,N,00100.0000,W,10.0,90.0,241126,,,N");
    CHECK(!gps_provider_offer(&s,line,n,now+1000000,now+1000000));CHECK(!gps_provider_encode(&s,now+1000000,bytes));
    now+=2000000;pair(&s,5,now);
    n=sentence(line,sizeof(line),"GPRMC,120006.00,A,5100.0000,N,00100.0000,W,10.0,90.0,241126,,,E");
    CHECK(!gps_provider_offer(&s,line,n,now+1000000,now+1000000));CHECK(!gps_provider_encode(&s,now+1000000,bytes));
    now+=2000000;pair(&s,7,now);
    n=sentence(line,sizeof(line),"GPGGA,120008.00,5100.0000,N,00100.0000,W,0,00,99.9,10.0,M,0,M,,");
    CHECK(!gps_provider_offer(&s,line,n,now+1000000,now+1000000));CHECK(!gps_provider_encode(&s,now+1000000,bytes));
    now+=2000000;pair(&s,9,now);
    n=sentence(line,sizeof(line),"GPGGA,120010.00,5100.0000,N,00100.0000,W,1,10,0.8,10.0,M,0,M,,");
    line[12]^=1;CHECK(!gps_provider_offer(&s,line,n,now+1000000,now+1000000));
    CHECK(!gps_provider_encode(&s,now+1000000,bytes));
    now+=2000000;pair(&s,11,now);CHECK(gps_provider_encode(&s,now,bytes));
    CHECK(!gps_provider_configure(&s,0,0,0));CHECK(!gps_provider_encode(&s,now,bytes));
    CHECK(!gps_source_decode(&decoded,bytes,320,now));
    /* Bounds/malformed inputs must never produce a valid source lease. */
    CHECK(gps_provider_configure(&s,1,0,0));srand(17);
    for(i=0;i<50000;i++) {
        n=(unsigned)rand()%sizeof(line);
        for(j=0;j<n;j++)line[j]=(char)rand();
        gps_provider_offer(&s,line,n,now,now);
        CHECK(!gps_provider_encode(&s,now,bytes));
    }
    printf("GPS_PROVIDER_CONSUMER_PASS checks=%u malformed=50000 unchanged_consumer=1 utc_not_synthesized=1 transport_bound=0\n",checks);
    return 0;
}
