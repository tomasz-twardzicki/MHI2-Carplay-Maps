/* SPDX-License-Identifier: GPL-3.0-or-later
 * Receiver f195665b only. Called from the existing tap, with guard held where
 * indicated. File reads remain on publisher; native serial iAP2 queue owns all
 * location state and outbound native packet sequence/framing.
 */
#include "wcp_location_source.h"
static struct wcp_location location;
static struct wcp_location_source location_source;
static int location_enabled,location_source_valid,location_queued,location_accepted;
static unsigned location_epoch,location_source_pid;
static uint64_t location_source_epoch;
static uintptr_t location_context;
static unsigned long location_sent,location_invalid;
static int location_source_matches(void){return location_source_valid&&location_source_pid==location_source.pid&&location_source_epoch==location_source.epoch;}
static void location_offer_locked(uint64_t now){
    unsigned i;
    if(!location_source_matches()){location.slot[0].size=location.slot[1].size=0;return;}
    for(i=0;i<2;i++){
        struct wcp_location_source_record *r=&location_source.record[i];
        if(r->size)wcp_location_offer(&location,r->sequence,r->captured,now,r->sentence,r->size);
    }
}
/* Native parser's incoming CSM callback, before it handles the same message. */
static void location_message_locked(unsigned id,const unsigned char *p,unsigned n){
    if(!location_enabled)return;
    if(id==0x1d00){
        if(++location_epoch==0)++location_epoch;
        wcp_location_reset(&location,((uint64_t)(unsigned)getpid()<<32)|location_epoch);
        location_context=*(uintptr_t *)0x112aec;location_accepted=0;
        location_source_pid=location_source_valid?location_source.pid:0;
        location_source_epoch=location_source_valid?location_source.epoch:0;
        location_offer_locked(tap_now());
    }else if(id==WCP_LOCATION_START||id==WCP_LOCATION_STOP){
        if(!wcp_location_control(&location,id,p,n))location_invalid++;
    }else if(id==0xaa05){
        wcp_location_reset(&location,0);location_context=0;location_accepted=0;
    }
}
/* Exact native framer memcpy at LR edd9c, called by eddd8 whose saved caller
 * LR is original-SP+44 = register-array index25. Identification caller ed5dc
 * excludes CSM/FT ACKs. Native framing has already written its header, so
 * adjust its three length registers and header checksum before copying. */
static void location_identity_frame(uintptr_t *r){
    unsigned char *csm,*frame;size_t old,size;unsigned i,sum=0;
    if(!location_enabled||r[13]!=0xedd9cU||r[25]!=0xed5dcU||r[1]!=0x135608U||r[7]!=0x133e08U)return;
    csm=(unsigned char *)r[1];frame=(unsigned char *)r[7];old=size=r[2];
    if(old<6||old>2000||be16(csm)!=0x4040||be16(csm+2)!=old||be16(csm+4)!=0x1d01||r[5]!=old||r[4]!=old+10||r[8]!=old+10||r[0]!=r[7]+9)return;
    pthread_mutex_lock(&guard);location_offer_locked(tap_now());
    if(wcp_location_identify(&location,1,tap_now(),csm,&size,2038)==1){
        r[2]=r[5]=size;r[4]=r[8]=size+10;frame[2]=(unsigned char)((size+10)>>8);frame[3]=(unsigned char)(size+10);
        for(i=0;i<8;i++)sum+=frame[i];frame[8]=(unsigned char)-sum;
    }
    pthread_mutex_unlock(&guard);
}
static void location_tick(void *unused){
    unsigned char packets[2][160];size_t sizes[2]={0,0};unsigned i;uintptr_t context;
    (void)unused;pthread_mutex_lock(&guard);location_queued=0;
    context=*(uintptr_t *)0x112aec;
    if(!location_enabled||!location.owner||!context||context!=location_context||*(int *)0x110a14!=2){
        pthread_mutex_unlock(&guard);return;
    }
    if(!guidance.accepted){
        if(location_accepted){wcp_location_reset(&location,0);location_context=0;location_accepted=0;}
        pthread_mutex_unlock(&guard);return;
    }
    location_accepted=1;location_offer_locked(tap_now());
    for(i=0;i<2;i++)sizes[i]=wcp_location_packet(&location,1,tap_now(),packets[i],sizeof(packets[i]));
    pthread_mutex_unlock(&guard);
    for(i=0;i<2;i++)if(sizes[i]){
        /* This callback runs on the native iAP2 SERIAL queue, as do ec5ec and
         * its eddd8 callers. Never send control data from publisher/video. */
        if(*(uintptr_t *)0x112aec!=context||*(int *)0x110a14!=2)return;
        ((void (*)(int,const void *,unsigned))0xeddd8)(10,packets[i],(unsigned)sizes[i]);
        pthread_mutex_lock(&guard);location_sent++;pthread_mutex_unlock(&guard);
    }
}
static void location_poll(void){
    unsigned char bytes[WCP_LOCATION_SOURCE_BYTES+1];struct wcp_location_source value;struct stat st;FILE *f;size_t n=0;int valid=0,queue=0;
    uintptr_t native_queue;char status[320];int length;
    if(!location_enabled)return;
    if(!lstat(WCP_LOCATION_SOURCE_PATH,&st)&&S_ISREG(st.st_mode)&&st.st_size==WCP_LOCATION_SOURCE_BYTES){
        f=fopen(WCP_LOCATION_SOURCE_PATH,"rb");
        if(f){n=fread(bytes,1,sizeof(bytes),f);if(fclose(f)==0)valid=gps_source_decode(&value,bytes,n,tap_now());}
    }
    if(valid&&kill((pid_t)value.pid,0)&&errno==ESRCH)valid=0;
    pthread_mutex_lock(&guard);location_source_valid=valid;if(valid)memcpy(&location_source,&value,sizeof(value));
    /* ec468 creates this default SERIAL queue at most once. Its only other
     * references are ec584's dispatch and the native delayed subscription;
     * no release/replacement exists in the pinned receiver. */
    native_queue=*(uintptr_t *)0x112ae8;
    if(native_queue&&!location_queued){location_queued=1;queue=1;}
    length=snprintf(status,sizeof(status),"WGPS_RECEIVER1 pid=%ld source=%d source_pid=%u source_matches=%d epoch=%u advertised=%u requested=%u accepted=%d queued=%d sent=%lu invalid=%lu\n",(long)getpid(),valid,valid?value.pid:0,location_source_matches(),location_epoch,location.advertised,location.requested,guidance.accepted,location_queued,location_sent,location_invalid);
    pthread_mutex_unlock(&guard);
    if(length>0&&length<(int)sizeof(status))atomic_file("location.status",status,(size_t)length);
    if(queue)((void (*)(void *,void *,void (*)(void *)))0x5ecb8)((void *)native_queue,0,location_tick);
}
