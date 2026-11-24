/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "wcp_location.c"
#include "wcp_location_source.h"
#include <stdio.h>
#include <stdlib.h>
#define CHECK(x) do{checks++;if(!(x)){fprintf(stderr,"location check line=%d\n",__LINE__);exit(1);}}while(0)
static unsigned checks;
static const unsigned char identity[]={0x40,0x40,0,22,0x1d,1,0,6,0,6,0x52,0,0,10,0,7,0x52,1,0x52,2,0x50,1};
static const unsigned char start[]={0,6,0,0,4,210,0,4,0,1,0,4,0,2};
static size_t nmea(char *out,const char *body){unsigned x=0,i;for(i=0;body[i];i++)x^=(unsigned char)body[i];return (size_t)snprintf(out,160,"$%s*%02X\r\n",body,x);}
int main(void){
    struct wcp_location s;unsigned char id[2048],original[2048],packet[256];char line[160];size_t size,n;unsigned i,j;
    wcp_location_reset(&s,123);memset(id,0,sizeof(id));memcpy(id,identity,sizeof(identity));size=sizeof(identity);
    CHECK(!wcp_location_identify(&s,1,1000000,id,&size,sizeof(id)));
    n=nmea(line,"GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,");
    CHECK(wcp_location_offer(&s,1,1000000,1000010,line,n));
    CHECK(!wcp_location_identify(&s,0,1000100,id,&size,sizeof(id)));
    memcpy(original,id,sizeof(id));CHECK(wcp_location_identify(&s,1,1000100,id,&size,sizeof(identity))==-1);
    CHECK(!memcmp(id,original,sizeof(id))&&size==sizeof(identity));
    CHECK(wcp_location_identify(&s,1,1000100,id,&size,sizeof(id))==1);
    CHECK(size==sizeof(identity)+37&&loc_be16(id+2)==size&&loc_be16(id+8)==6);
    CHECK(loc_be16(id+6)==8&&loc_be16(id+12)==WCP_LOCATION_DATA);
    CHECK(loc_be16(id+14)==14&&loc_be16(id+24)==WCP_LOCATION_START&&loc_be16(id+26)==WCP_LOCATION_STOP);
    CHECK(loc_be16(id+28)==31&&loc_be16(id+30)==22);
    CHECK(loc_be16(id+53)==17&&loc_be16(id+57)==18); // OEM table at 0x27db0, not Start IDs 1/2
    CHECK(!wcp_location_packet(&s,1,1000200,packet,sizeof(packet)));
    CHECK(wcp_location_control(&s,WCP_LOCATION_START,start,sizeof(start)));
    CHECK(!wcp_location_packet(&s,0,1000200,packet,sizeof(packet)));CHECK(s.requested==6);
    CHECK(!wcp_location_packet(&s,1,1000200,packet,8));
    size=wcp_location_packet(&s,1,1000200,packet,sizeof(packet));
    CHECK(size==n+11&&loc_be16(packet+4)==WCP_LOCATION_DATA&&loc_be16(packet+6)==n+5);
    CHECK(!memcmp(packet+10,line,n+1));CHECK(!wcp_location_packet(&s,1,1000300,packet,sizeof(packet)));
    CHECK(!wcp_location_offer(&s,2,1100000,1100010,line,n)); // cached UTC isn't a new fix
    n=nmea(line,"GPRMC,123520,A,4807.038,N,01131.000,E,022.4,084.4,201126,003.1,W");
    CHECK(wcp_location_offer(&s,3,1200000,1200010,line,n));
    CHECK(!wcp_location_packet(&s,1,2800000,packet,sizeof(packet))); // source silent
    CHECK(wcp_location_packet(&s,1,1200020,packet,sizeof(packet))==n+11);
    n=nmea(line,"GPGGA,123521,4807.038,N,01131.000,E,0,00,99.9,,,,,,");
    CHECK(!wcp_location_offer(&s,4,1300000,1300010,line,n));CHECK(!s.slot[0].size&&!s.slot[1].size);
    CHECK(wcp_location_control(&s,WCP_LOCATION_STOP,0,0));CHECK(!s.requested);
    CHECK(!wcp_location_control(&s,WCP_LOCATION_START,start,sizeof(start)-1));CHECK(!s.requested);
    CHECK(wcp_location_control(&s,WCP_LOCATION_START,start,sizeof(start)));
    CHECK(!wcp_location_control(&s,0x5001,0,0)&&s.requested==6);
    wcp_location_reset(&s,456);CHECK(!s.advertised&&!s.requested&&!s.slot[0].sequence);
    n=nmea(line,"GPRMC,123522,A,4807.038,N,01131.000,E,0,0,201126,,,E");
    CHECK(!wcp_location_offer(&s,1,1400000,1400010,line,n)); // estimated
    n=nmea(line,"GPRMC,123522,A,4807.038,N,01131.000,E,0,0,311126,,,A");
    CHECK(!wcp_location_offer(&s,2,1400000,1400010,line,n)); // impossible date
    n=nmea(line,"GPGGA,123522,9060.000,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,");
    CHECK(!wcp_location_offer(&s,3,1400000,1400010,line,n)); // invalid coordinates
    wcp_location_reset(&s,789);
    n=nmea(line,"GPGGA,235958,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,");
    CHECK(wcp_location_offer(&s,4,1400000,1400010,line,n));
    n=nmea(line,"GPGGA,000000,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,");
    CHECK(wcp_location_offer(&s,5,3400000,3400010,line,n)); // midnight with missing sample
    CHECK(!wcp_location_offer(&s,6,3500000,3499999,line,n)); // future producer clock
    {
        struct wcp_location_source producer,decoded;unsigned char bytes[WCP_LOCATION_SOURCE_BYTES];
        memset(&producer,0,sizeof(producer));producer.pid=42;producer.epoch=123;producer.heartbeat=1;producer.published=1000000;
        producer.record[0].sequence=1;producer.record[0].captured=990000;producer.record[0].size=(unsigned)n;memcpy(producer.record[0].sentence,line,n);
        gps_source_encode(&producer,bytes);CHECK(gps_source_decode(&decoded,bytes,sizeof(bytes),1000100));
        CHECK(decoded.pid==42&&decoded.epoch==123&&decoded.record[0].captured==990000&&!memcmp(decoded.record[0].sentence,line,n));
        CHECK(!gps_source_decode(&decoded,bytes,sizeof(bytes)-1,1000100));
        CHECK(!gps_source_decode(&decoded,bytes,sizeof(bytes),999999));
        CHECK(!gps_source_decode(&decoded,bytes,sizeof(bytes),3000000));
        gps_put32(bytes+44,129);CHECK(!gps_source_decode(&decoded,bytes,sizeof(bytes),1000100));
    }
    /* Truncation/mutation corpus, including packet/TLV length edges. */
    for(i=0;i<=sizeof(identity);i++)for(j=0;j<256;j++){
        wcp_location_reset(&s,123);n=nmea(line,"GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,");
        CHECK(wcp_location_offer(&s,1,1000000,1000010,line,n));memcpy(id,identity,sizeof(identity));size=i;
        if(i)id[i-1]=(unsigned char)j;
        (void)wcp_location_identify(&s,1,1000020,id,&size,sizeof(id));
        (void)wcp_location_control(&s,WCP_LOCATION_START,id,i);
        (void)wcp_location_offer(&s,2,1100000,1100010,(const char *)id,i);
    }
    printf("LOCATION_CORE_PASS checks=%u source_connected=0 receiver_send_hook=0\n",checks);return 0;
}
