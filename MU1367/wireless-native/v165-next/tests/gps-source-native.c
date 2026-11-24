/* SPDX-License-Identifier: GPL-3.0-or-later. QNX/32-bit ABI boundary fixture. */
#define CPMAP_GPS_SOURCE_NO_CONSTRUCTOR
#include "gps_dio_source.c"
static unsigned forwarded,converted,destroyed;
static const char *ascii;
static void check(int ok,const char *why){if(!ok){printf("GPS_SOURCE_FAIL=%s\n",why);fflush(stdout);_exit(81);}}
/* Only the native Unicode conversion/lifetime boundary is controlled. The
 * production capture, locking, snapshot publisher and codec execute unchanged. */
static void convert(void *p,const void *unicode){
    unsigned char *b=p;check(unicode==(void *)23,"Unicode input ownership");
    memset(b,0,40);
    if(strlen(ascii)<20)memcpy(b+12,ascii,strlen(ascii)+1);
    else{b[6]=1;*(uintptr_t *)(b+12)=(uintptr_t)&ascii;}
    check(!pthread_mutex_init((pthread_mutex_t *)(b+32),0),"temporary mutex init");converted++;
}
static void destroy(void *p){check(!pthread_mutex_destroy((pthread_mutex_t *)((unsigned char *)p+32)),"temporary mutex released");destroyed++;}
static void original(void *self,const void *p,int type){(void)p;check(self==(void *)42&&type==17,"native callback arguments preserved");forwarded++;}
int main(void){
    uintptr_t shared[2]={1,23};struct wcp_location_source decoded;unsigned char bytes[WCP_LOCATION_SOURCE_BYTES];
    char oversized[1024];FILE *f;unsigned i;pthread_t thread;struct timespec pause={0,120000000};
    check(sizeof(void *)==4,"ARM ABI");gps_utf8=convert;gps_utf8_destroy=destroy;gps_original=original;gps_reply_original=original;
    gps_source.pid=(unsigned)getpid();gps_source.epoch=gps_now();
    ascii="$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n";
    gps_primary_hook((void *)42,shared,17);
    check(forwarded==1&&converted==1&&destroyed==1&&gps_source.record[0].size==strlen(ascii),"passive primary capture");
    check(!memcmp(gps_source.record[0].sentence,ascii,strlen(ascii)),"unchanged NMEA bytes");
    ascii="$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A\r\n";
    gps_reply_hook((void *)42,shared,17);
    check(forwarded==2&&converted==destroyed&&gps_source.record[1].size==strlen(ascii),"reply capture and lifetime");
    memset(oversized,'x',sizeof(oversized));ascii=oversized;gps_primary_hook((void *)42,shared,17);
    check(gps_rejected==1&&forwarded==3&&converted==destroyed,"oversized source rejected without changing OEM callback");
    gps_reply_hook((void *)42,0,17);check(forwarded==4&&converted==destroyed,"null input forwarded");
    ascii="noop";gps_primary_hook((void *)42,shared,17);check(forwarded==5&&converted==destroyed,"native short-string layout safely ignored");
    check(!mkdir("/ramdisk/wcp-location",0700)||errno==EEXIST,"source RAM directory");
    check(!pthread_create(&thread,0,gps_publish,0),"publisher starts");
    for(i=0;i<10;i++){nanosleep(&pause,0);f=fopen(WCP_LOCATION_SOURCE_PATH,"rb");if(f)break;}
    check(f!=0,"publisher atomic snapshot");check(fread(bytes,1,sizeof(bytes),f)==sizeof(bytes)&&fgetc(f)==EOF&&!fclose(f),"bounded snapshot size");
    check(gps_source_decode(&decoded,bytes,sizeof(bytes),gps_now()),"production snapshot decodes");
    check(decoded.pid==(unsigned)getpid()&&decoded.epoch==gps_source.epoch&&decoded.record[0].sequence&&decoded.record[1].sequence,"source identity and timestamps retained");
    puts("GPS_SOURCE_PASS production_capture=1 unicode_boundary_stubbed=1 original_callbacks=1 publisher=1 raw_bytes_unchanged=1");fflush(stdout);_exit(0);
}
