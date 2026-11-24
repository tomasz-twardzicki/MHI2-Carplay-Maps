#!/usr/bin/env python3
"""Run the pinned receiver's real iAP2 parser through the production ARM tap."""
import importlib.util,json,plistlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
native=HERE.parent/'src/native'
p=HERE.parents[1]/'tests/receiver-alt-gate.py'
spec=importlib.util.spec_from_file_location('fixture',p);fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
source=r'''
#pragma clang diagnostic ignored "-Wunused-function"
#include "@NATIVE@/wcp_tap.c"
#include "@NATIVE@/wcp_rg.c"
#include "@NATIVE@/wcp_location.c"
#include <ucontext.h>
@ASM@
extern WcpObject fixture_info_tail(WcpObject,void *);
__asm__(".text\n.arm\n.global fixture_info_tail\nfixture_info_tail:\n push {r4-r10,lr}\n sub sp,sp,#1056\n mov r5,r0\n mov r6,r1\n mov r7,#0\n mov r8,#0\n mov r9,#0\n movw r12,#0xecf0\n movt r12,#0xc\n bx r12\n");
static void fault(int sig,siginfo_t *info,void *context) {ucontext_t *u=context;char text[200];int n=snprintf(text,sizeof(text),"FAULT sig=%d pc=%x lr=%x address=%p\n",sig,(unsigned)u->uc_mcontext.cpu.gpr[15],(unsigned)u->uc_mcontext.cpu.gpr[14],info->si_addr);write(2,text,n);_exit(90);}
static void check(int ok,const char *what) {if(!ok){printf("TAP_FAILED=%s errno=%d\n",what,errno);fflush(stdout);_exit(81);}}
static void put(const char *path,const char *text) {FILE *f=fopen(path,"w");check(f!=0,path);fputs(text,f);check(!fclose(f),"close");}
static void pause_test(void) {struct timespec t;t.tv_sec=0;t.tv_nsec=300000000;nanosleep(&t,0);}
static int fake_send_calls;
static ssize_t fake_send(int fd,const void *p,size_t n,int flags) {fake_send_calls++;(void)fd;(void)p;(void)flags;return n;}
static unsigned media_sequence=4;
static void parse_file(const unsigned char *payload,unsigned size) {
    unsigned total=size+10,i,sum=0;unsigned char *item=calloc(1,total+4),*packet=item+4;
    check(item!=0,"file allocation");*(uint32_t *)item=total;
    packet[0]=0xff;packet[1]=0x5a;packet[2]=total>>8;packet[3]=total;packet[4]=0x40;packet[5]=media_sequence++;packet[7]=0x0c;
    for(i=0;i<8;i++)sum+=packet[i];packet[8]=(unsigned char)-sum;memcpy(packet+9,payload,size);
    sum=0;for(i=9;i<total-1;i++)sum+=packet[i];packet[total-1]=(unsigned char)-sum;
    ((void (*)(void *))0xec5ec)(item);
}
static void parse_media(const unsigned char *payload,unsigned size) {
    unsigned total=size+16,i,sum=0;unsigned char *item=calloc(1,total+4),*packet=item+4;
    check(item!=0,"media allocation");*(uint32_t *)item=total;
    packet[0]=0xff;packet[1]=0x5a;packet[2]=total>>8;packet[3]=total;packet[4]=0x40;packet[5]=media_sequence++;packet[7]=0x0a;
    for(i=0;i<8;i++)sum+=packet[i];packet[8]=(unsigned char)-sum;
    packet[9]=packet[10]=0x40;packet[11]=(size+6)>>8;packet[12]=size+6;packet[13]=0x50;packet[14]=1;
    memcpy(packet+15,payload,size);sum=0;for(i=9;i<total-1;i++)sum+=packet[i];packet[total-1]=(unsigned char)-sum;
    ((void (*)(void *))0xec5ec)(item);
}
static void *priority_probe(void *unused) {int policy;struct sched_param p;(void)unused;check(!pthread_getschedparam(pthread_self(),&policy,&p),"priority readback");return (void *)(uintptr_t)p.sched_priority;}
static void parse(unsigned id,unsigned seq) {
    /* One valid TLV. The real parser owns/frees its queued input buffer. */
    unsigned char *item=calloc(1,26),*packet=item+4;unsigned i,sum=0;
    check(item!=0,"allocation");*(uint32_t *)item=22;
    packet[0]=0xff;packet[1]=0x5a;packet[3]=22;packet[4]=0x40;packet[5]=seq;packet[7]=0x0a;
    for(i=0;i<8;i++)sum+=packet[i];packet[8]=(unsigned char)-sum;
    packet[9]=0x40;packet[10]=0x40;packet[12]=12;packet[13]=id>>8;packet[14]=id;
    packet[16]=6;packet[19]=0;packet[20]=1;sum=0;
    for(i=9;i<21;i++)sum+=packet[i];packet[21]=(unsigned char)-sum;
    ((void (*)(void *))0xec5ec)(item);
}
__attribute__((constructor)) static void exercise(void) {
    struct sigaction sa;memset(&sa,0,sizeof(sa));sa.sa_sigaction=fault;sa.sa_flags=SA_SIGINFO;sigaction(SIGBUS,&sa,0);sigaction(SIGSEGV,&sa,0);
    char text[256];const char *scope="/ramdisk/.v75-native-0123456789abcdef0123456789abcdef";
    uint64_t sdk,mapped,now;struct timespec t;
    unsigned i;unsigned char bytes[33120];size_t n;
    write(2,"TAP_EXERCISE_ENTER\n",19);
    check(getenv("MU1367_GATE_ONLY")!=0,"fixture only");
    if(!enabled)init();write(2,"TAP_INIT_DONE\n",14);check(enabled,"tap enabled");
    check(!mkdir(scope,0700) || errno==EEXIST,"scope");
    /* Initialize only the parser's sync/sequence state, not radio/MFi/video. */
    *(int *)0x110a14=2;*(unsigned char *)0x112af1=0;*(int *)0x112aec=0;
    for(i=0;i<3;i++)parse(i==0?0x5201:i==1?0x5202:0x5204,i+1);
    check(!guidance.accepted && guidance.sequence==0 && pending_count==3,"pre-grant burst retained without publication");
    snprintf(text,sizeof(text),"V75_NATIVE1\n%ld\n%s\n",(long)getpid(),scope);put("/ramdisk/v75-wireless-native.owner",text);
    snprintf(text,sizeof(text),"%ld\n",(long)getpid());put("/dev/shmem/wcp_receiver.pid",text);put("/dev/shmem/wcp_cp_session","1\n");
    snprintf(text,sizeof(text),"V75_GRANT1\n%ld\n1\n",(long)getpid());put("/ramdisk/.v75-native-0123456789abcdef0123456789abcdef/cluster-session.accepted",text);
    unlink("/dev/shmem/wcp_receiver.pid");pause_test();
    check(!guidance.accepted,"v3 missing PID reproduces rejection");
    snprintf(text,sizeof(text),"%ld\n",(long)getpid());put("/dev/shmem/wcp_receiver.pid",text);
    pause_test();check(guidance.accepted,"accepted without map feed");
    for(i=0;i<6 && guidance.sequence!=3;i++)pause_test();
    check(guidance.sequence==3,"real CSM callback captured all IDs");
    check(guidance.events[0].id==0x5201 && guidance.events[1].id==0x5202 && guidance.events[2].id==0x5204,"payload IDs");
    check(guidance.events[0].size==6 && guidance.events[0].payload[5]==1,"exact payload");
    n=wcp_rg_mailbox(&guidance,bytes,sizeof(bytes));check(n==162,"compact envelope size");
    /* Execute actual SDK UpTicks and timestamp conversion, then compare its
     * mapped microseconds with the firmware CLOCK_MONOTONIC clock. */
    sdk=((uint64_t (*)(void))0x70a04)();mapped=((uint64_t (*)(uint64_t))0x70bd0)(sdk);
    clock_gettime(CLOCK_MONOTONIC,&t);now=(uint64_t)t.tv_sec*1000000+t.tv_nsec/1000;
    printf("CLOCK sdk=%llu mapped=%llu local=%llu\n",(unsigned long long)sdk,(unsigned long long)mapped,(unsigned long long)now);fflush(stdout);
    check(now>=mapped && now-mapped<100000,"SDK timestamp clock mapping");
    {
        /* Real receiver queue header -> production sender tap, preserving the
         * original payload and phone-derived timestamp across the adapter. */
        static const unsigned char frame[]={0,0,0,1,0x65,1,2,3};
        unsigned char *node=((void *(*)(unsigned,unsigned,uint64_t,unsigned))0xe6f00)(2,1,mapped,80);
        uint64_t parent[64];uint32_t *context=(uint32_t *)((unsigned char *)parent+136);uintptr_t regs[18];struct wcp_fingerprint fp;
        check(node!=0,"real video queue allocation");memset(parent,0,sizeof(parent));memset(regs,0,sizeof(regs));
        *(uint32_t *)(node+4)=16+sizeof(frame);memcpy(node+24,frame,sizeof(frame));
        ((uint32_t *)parent)[132/4]=1;context[64/4]=9997;context[112/4]=1;regs[0]=99;regs[1]=(uintptr_t)(node+24);regs[2]=sizeof(frame);regs[5]=(uintptr_t)context;regs[10]=(uintptr_t)node;regs[13]=0xe7300;
        unlink("/dev/shmem/alt_force_idr");next_send=fake_send;check(wcp_tap_send(regs)==sizeof(frame),"original send size preserved");
        check(timing!=MAP_FAILED && timing->sequence==1,"timing event committed");
        check((((uint64_t)timing->events[0].timestamp_hi<<32)|timing->events[0].timestamp_lo)==mapped,"actual queue timestamp retained");
        wcp_fingerprint_annexb(&fp,frame,sizeof(frame));check(wcp_fingerprint_equal(&fp,&timing->events[0].fingerprint),"timing payload identity");
        for(i=1;i<8;i++) {check(access("/dev/shmem/alt_force_idr",F_OK)!=0,"no early periodic IDR");check(wcp_tap_send(regs)==sizeof(frame),"next video send");}
        check(access("/dev/shmem/alt_force_idr",F_OK)==0,"periodic IDR marker at selected eighth frame");unlink("/dev/shmem/alt_force_idr");
        free(node);
        /* Suppression requires an actual fresh cadence receipt. */
        input_mode=1;fake_send_calls=0;regs[13]=0x101b40;regs[17]=0x102a58;regs[1]=(uintptr_t)"K";regs[2]=1;regs[3]=0x80;
        check(wcp_tap_send(regs)==1 && fake_send_calls==0,"five-frame periodic request suppressed");
        regs[17]=0x102aec;check(wcp_tap_send(regs)==1 && fake_send_calls==1,"recovery request forwarded");input_mode=0;
        input_mode=1;regs[17]=0x102a58;unlink("/ramdisk/wcp-rg/idr.state");
        check(wcp_tap_send(regs)==1 && fake_send_calls==2,"missing cadence falls back to old periodic IDR");
        put("/ramdisk/wcp-rg/idr.state","WCPIDR1\n23\n1\n1\n");
        check(wcp_tap_send(regs)==1 && fake_send_calls==3,"stale or different receiver receipt falls back");
        snprintf(text,sizeof(text),"WCPIDR1\n%lu\n%u\n%llu\n",(unsigned long)getpid(),guidance.session,(unsigned long long)(tap_now()-1100000));put("/ramdisk/wcp-rg/idr.state",text);
        check(wcp_tap_send(regs)==1 && fake_send_calls==4,"expired same-receiver cadence falls back");
        snprintf(text,sizeof(text),"WCPIDR1\n%lu\n%u\n%llu\n",(unsigned long)getpid(),guidance.session,(unsigned long long)tap_now());put("/ramdisk/wcp-rg/idr.state",text);
        unlink("/dev/shmem/wcp_receiver.pid");
        check(wcp_tap_send(regs)==1 && fake_send_calls==5,"missing PID cannot suppress fallback even with fresh receipt");
        snprintf(text,sizeof(text),"%ld\n",(long)getpid());put("/dev/shmem/wcp_receiver.pid",text);
        input_mode=0;
    }
    {
        void *array;int error=0,index;unsigned fps;
        put("/dev/shmem/wcp_alt_probe","1\n");
        for(fps=20;fps<=40;fps+=5) {
            if(fps==35)continue;
            snprintf(text,sizeof(text),"WCP161\nfps=%u\nidr=8\nsmoothing_ms=150\n",fps);put(WCP_SETTINGS_PATH,text);
            array=((void *(*)(void *,int *))0xe44f8)((void *)0x3fa3c,&error);
            check(array!=0 && error==0,"actual display provider");
            check(((int (*)(void *))0x51d6c)(array)==2,"both displays returned");
            for(index=0;index<2;index++) {
                void *dict=((void *(*)(void *,int))0x51d90)(array,index);
                void *value=((void *(*)(void *,void *))0x520ac)(dict,(void *)0x3fc0b);
                void *uuid=((void *(*)(void *,void *))0x520ac)(dict,(void *)0x3fb7b);
                int alt=uuid && ((int (*)(void *,void *))0x51cec)(uuid,(void *)0x3fb88);
                void *expected=((void *(*)(uint64_t))0x58fb0)(alt?fps:30);
                check(((int (*)(void *,void *))0x51cec)(value,expected),"actual main30 and selected alternate maxFPS");
                ((void (*)(void *))0x51ce8)(expected);
            }
            ((void (*)(void *))0x51ce8)(array);
        }
        array=((void *(*)(void *,int *))0xe44f8)((void *)0x3fa3c,&error);
        {
            void *alt=((void *(*)(void *,int))0x51d90)(array,1),*expected,*value;
            ((int (*)(void *,void *,int64_t))0x5ada0)(alt,(void *)0x3fb6e,112);
            ((int (*)(void *,void *,int64_t))0x5ada0)(alt,(void *)0x3fc0b,17);
            wcp_alt_display_fps(array,20);
            expected=((void *(*)(uint64_t))0x58fb0)(17);value=((void *(*)(void *,void *))0x520ac)(alt,(void *)0x3fc0b);
            check(((int (*)(void *,void *))0x51cec)(value,expected),"unknown display type is preserved");wcp_cf_release(expected);
            ((int (*)(void *,void *,int64_t))0x5ada0)(alt,(void *)0x3fb6e,111);
            ((void (*)(void *,void *,void *))0x520d0)(alt,(void *)0x3fb7b,(void *)0x3fb41);
            wcp_alt_display_fps(array,25);
            expected=((void *(*)(uint64_t))0x58fb0)(17);value=((void *(*)(void *,void *))0x520ac)(alt,(void *)0x3fc0b);
            check(((int (*)(void *,void *))0x51cec)(value,expected),"unknown display identity is preserved");wcp_cf_release(expected);
            ((void (*)(void *,void *,void *))0x520d0)(alt,(void *)0x3fb7b,(void *)0x3fb88);
            ((void (*)(void *,void *))0x51db4)(array,alt);
            wcp_alt_display_fps(array,30);
            expected=((void *(*)(uint64_t))0x58fb0)(17);value=((void *(*)(void *,void *))0x520ac)(alt,(void *)0x3fc0b);
            check(((int (*)(void *,void *))0x51cec)(value,expected),"unknown display array count is preserved");wcp_cf_release(expected);
        }
        ((void (*)(void *))0x51ce8)(array);
    }
    {
        static const unsigned char original_config[]={@CONFIG@};
        puts("TAP_RHD_CONFIG_BEGIN");fflush(stdout);
        const char *path="/mnt/persist/airplay.conf";
        WcpObject raw,dict,value,expected;FILE *f;unsigned char unchanged[sizeof(original_config)];int side;
        setenv("WCP_DATA","/mnt/persist",1);unlink(path);
        for(side=2;side>=1;side--) {
            put("/ramdisk/cpmap-driver-side.state",side==2?"CPDS1\n2\n":"CPDS1\n1\n");
            raw=((WcpObject (*)(const char *,void *))0x595e4)(path,0);check(raw!=0,"RHD RAM config supplied");
            dict=((WcpObject (*)(WcpObject,WcpObject,int,void *,void *))0x524a0)(0,raw,0,0,0);check(dict!=0,"RHD RAM binary plist parsed");
            value=((WcpObject (*)(WcpObject,WcpObject))0x520ac)(dict,(WcpObject)0x3eaf2);
            check(value==*(WcpObject *)(side==2?0x110418:0x110424),"OEM rightHandDrive boolean");wcp_cf_release(dict);wcp_cf_release(raw);
            if(side==2) {
                check(access(path,F_OK)!=0,"absent per-unit config remains absent");
                f=next_fopen(path,"w");check(f!=0,"unit config create");check(fwrite(original_config,1,sizeof(original_config),f)==sizeof(original_config) && !fclose(f),"unit config write");
            }
        }
        f=next_fopen(path,"r");check(f && fread(unchanged,1,sizeof(unchanged),f)==sizeof(unchanged) && !fclose(f),"original config read");
        check(!memcmp(unchanged,original_config,sizeof(unchanged)),"original config byte-identical");
        raw=((WcpObject (*)(const char *,void *))0x595e4)(path,0);dict=((WcpObject (*)(WcpObject,WcpObject,int,void *,void *))0x524a0)(0,raw,0,0,0);
        expected=((WcpObject (*)(WcpObject,const char *,unsigned))0x52220)(0,"fixtureUnrelated",0x80000100);
        value=((WcpObject (*)(WcpObject,WcpObject))0x520ac)(dict,expected);check(value!=0,"unrelated property retained");wcp_cf_release(expected);wcp_cf_release(dict);wcp_cf_release(raw);
        put("/ramdisk/cpmap-driver-side.state","CPDS1\n0\n");
        raw=((WcpObject (*)(const char *,void *))0x595e4)(path,0);dict=((WcpObject (*)(WcpObject,WcpObject,int,void *,void *))0x524a0)(0,raw,0,0,0);
        value=((WcpObject (*)(WcpObject,WcpObject))0x520ac)(dict,(WcpObject)0x3eaf2);
        check(value==*(WcpObject *)0x110418,"unknown OEM coding preserves original config");wcp_cf_release(dict);wcp_cf_release(raw);
        put("/mnt/persist/cpmap-driver-side.state","CPDS1\n2\n");unlink("/ramdisk/cpmap-driver-side.state");
        puts("TAP_RHD_CACHE_BEGIN");fflush(stdout);
        check(wcp_driver_side()==2,"last-known RHD available before HMI boot");
        put("/ramdisk/cpmap-driver-side.state","CPDS1\n1\n");check(wcp_driver_side()==1,"live coding takes priority over cache");
        {
            uintptr_t regs[14];unsigned char server[2048];WcpObject response=wcp_cf_empty_dict(),config;
            raw=((WcpObject (*)(const char *,void *))0x595e4)(path,0);
            /* The server parses its startup plist with options=0. Exercise
             * that exact dictionary implementation, not just a fresh mutable
             * test dictionary, when replacing stale in-memory coding. */
            config=((WcpObject (*)(WcpObject,WcpObject,int,void *,void *))0x524a0)(0,raw,0,0,0);
            wcp_cf_release(raw);check(config!=0,"server-style config dictionary");
            memset(server,0,sizeof(server));memset(regs,0,sizeof(regs));*(WcpObject *)(server+124)=config;
            regs[1]=0x1bef2;regs[2]=1025;regs[5]=(uintptr_t)response;regs[6]=(uintptr_t)server;regs[13]=0xce990;
            wcp_tap_strlcpy(regs);
            check(((WcpObject (*)(WcpObject,WcpObject))0x520ac)(response,(WcpObject)0x3eaf2)==*(WcpObject *)0x110424,"late LHD /info refresh");
            put("/ramdisk/cpmap-driver-side.state","CPDS1\n2\n");wcp_tap_strlcpy(regs);
            check(((WcpObject (*)(WcpObject,WcpObject))0x520ac)(response,(WcpObject)0x3eaf2)==*(WcpObject *)0x110418,"late RHD /info refresh");
            check(((WcpObject (*)(WcpObject,WcpObject))0x520ac)(config,(WcpObject)0x3eaf2)==*(WcpObject *)0x110418,"stale in-memory config updated");
            {
                /* Run the actual RHD-to-/info tail, after the unrelated CF
                 * preference subsystem that requires receiver hardware main. */
                WcpObject actual=fixture_info_tail(response,server);
                check(actual==response && ((WcpObject (*)(WcpObject,WcpObject))0x520ac)(actual,(WcpObject)0x3eaf2)==*(WcpObject *)0x110418,"actual receiver /info RHD tail");
                put("/ramdisk/cpmap-driver-side.state","CPDS1\n1\n");wcp_tap_strlcpy(regs);
                actual=fixture_info_tail(response,server);
                check(actual==response && ((WcpObject (*)(WcpObject,WcpObject))0x520ac)(actual,(WcpObject)0x3eaf2)==*(WcpObject *)0x110424,"actual /info tail changes cached RHD to live LHD");
            }
            wcp_cf_release(response);wcp_cf_release(config);
        }
    }
    {
        WcpObject key=((WcpObject (*)(WcpObject,const char *,unsigned))0x52220)(0,"oemIconLabel",0x80000100);
        WcpObject expected=((WcpObject (*)(WcpObject,const char *,unsigned))0x52220)(0,"Volkswagen",0x80000100);
        WcpObject raw,dict,value,response=wcp_cf_empty_dict();uintptr_t regs[14];unsigned char server[2048];
        unlink("/ramdisk/cpmap-driver-side.state");unlink("/mnt/persist/cpmap-driver-side.state");
        raw=((WcpObject (*)(const char *,void *))0x595e4)("/mnt/persist/airplay.conf",0);
        dict=((WcpObject (*)(WcpObject,WcpObject,int,void *,void *))0x524a0)(0,raw,0,0,0);
        value=((WcpObject (*)(WcpObject,WcpObject))0x520ac)(dict,key);
        check(value&&((int (*)(WcpObject,WcpObject))0x51cec)(value,expected),"Volkswagen RAM label without coding");
        memset(server,0,sizeof(server));memset(regs,0,sizeof(regs));*(WcpObject *)(server+124)=dict;
        regs[1]=0x1bef2;regs[2]=1025;regs[5]=(uintptr_t)response;regs[6]=(uintptr_t)server;regs[13]=0xce990;wcp_tap_strlcpy(regs);
        value=((WcpObject (*)(WcpObject,WcpObject))0x520ac)(response,key);
        check(value&&((int (*)(WcpObject,WcpObject))0x51cec)(value,expected),"Volkswagen /info label without coding");
        wcp_cf_release(response);wcp_cf_release(dict);wcp_cf_release(raw);wcp_cf_release(key);wcp_cf_release(expected);
    }
    {
        uint32_t context[64];pthread_t worker;pthread_attr_t attr;struct sched_param param;void *value;
        memset(context,0,sizeof(context));context[16]=9997;
        check(wcp_promote_thread((void *(*)(void *))0xe6fcc,context),"select pinned alternate sender port 9997");
        context[16]=7101;check(!wcp_promote_thread((void *(*)(void *))0xe6fcc,context),"exclude main sender port 7101");
        context[16]=9997;check(!wcp_promote_thread(priority_probe,context),"exclude other receiver threads");
        pthread_attr_init(&attr);pthread_attr_setinheritsched(&attr,PTHREAD_EXPLICIT_SCHED);pthread_attr_setschedpolicy(&attr,SCHED_RR);
        for(i=10;i<=20;i+=10) {
            memset(&param,0,sizeof(param));param.sched_priority=i;pthread_attr_setschedparam(&attr,&param);input_mode=1;
            check(!pthread_create(&worker,&attr,priority_probe,0),"priority worker create");pthread_join(worker,&value);input_mode=0;
            check((uintptr_t)value==(i<14?14:i),"priority14 floor and preserve higher priorities");
        }
        pthread_attr_destroy(&attr);
    }
    {
        uint64_t stream[64];uint32_t *fields=(uint32_t *)stream;pthread_t worker;pthread_attr_t attr;struct sched_param param;void *value;
        memset(stream,0,sizeof(stream));fields[72/4]=102;
        check(wcp_promote_thread((void *(*)(void *))0xe83d0,stream),"select native MainHigh output");
        fields[72/4]=101;check(!wcp_promote_thread((void *(*)(void *))0xe83d0,stream),"exclude auxiliary audio output");
        fields[72/4]=102;fields[76/4]=1;check(!wcp_promote_thread((void *(*)(void *))0xe83d0,stream),"validate complete 64-bit type");fields[76/4]=0;
        check(!wcp_promote_thread((void *(*)(void *))0xd89b0,stream),"preserve native SDK receive scheduling");
        fields[32/4]=48000;fields[52/4]=4;fields[56/4]=2;fields[60/4]=16;
        memcpy((char *)stream+84,"media",6);
        pthread_attr_init(&attr);pthread_attr_setinheritsched(&attr,PTHREAD_EXPLICIT_SCHED);pthread_attr_setschedpolicy(&attr,SCHED_RR);
        memset(&param,0,sizeof(param));param.sched_priority=10;pthread_attr_setschedparam(&attr,&param);
        /* Native 20-ms audio loop, with all read/output callbacks and hardware
         * connections absent. Let its native ten-second stats site execute. */
        check(!pthread_create(&worker,&attr,(void *(*)(void *))0xe83d0,stream),"native audio worker");
        {struct timespec delay;delay.tv_sec=11;delay.tv_nsec=0;nanosleep(&delay,0);}
        fields[176/4]=1;check(!pthread_join(worker,&value) && !value,"native audio worker exits without hardware");
        param.sched_priority=20;pthread_attr_setschedparam(&attr,&param);
        check(!pthread_create(&worker,&attr,(void *(*)(void *))0xe83d0,stream),"native audio higher-priority worker");
        check(!pthread_join(worker,&value) && !value,"higher-priority native worker exits");pthread_attr_destroy(&attr);
    }
    {
        static const unsigned char metadata[]={0,41,0,0, 0,12,0,0,0,0,0,0,0,0,0,42, 0,10,0,1,'F','i','x','t','u','r', 0,10,0,12,'A','r','t','i','s','t', 0,5,0,26,0x84};
        static const unsigned char playback[]={0,17,0,1, 0,5,0,0,1, 0,8,0,1,0,0,3,232};
        static const unsigned char image[]={@IMAGE@};
        unsigned char packet[sizeof(image)+2],ack[8],header[]={0x84,4,0,0,0,0,0,0,0,0};
        unsigned char snap[WCP_MEDIA_MAX];FILE *f;size_t n;unsigned generation;
        /* Native packet parser, actual first-chunk append and completion site. */
        parse_media(metadata,sizeof(metadata));parse_media(playback,sizeof(playback));
        check(media_updates==2 && media.uid==42 && media.art==0x84 && media.position==1000 && media.status==1,"actual 5001 parser capture and delta merge");
        header[8]=(unsigned char)(sizeof(image)>>8);header[9]=(unsigned char)sizeof(image);
        *(const char **)0x110a1c="/ramdisk";*(const char **)0x110a20="/ramdisk/cover.cur";
        ((int (*)(void *,unsigned,void *))0xee210)(header,sizeof(header),ack);
        packet[0]=0x84;packet[1]=0xc0;memcpy(packet+2,image,sizeof(image));
        ((int (*)(void *,unsigned,void *))0xee210)(packet,sizeof(packet),ack);
        check(media_cover_copied==1,"actual completed native FT image copied");
        pause_test();
        f=fopen("/ramdisk/wcp-rg/nowplaying.bin","r");check(f!=0,"media snapshot");n=fread(snap,1,sizeof(snap),f);fclose(f);
        check(n>140 && !memcmp(snap,"WNP1",4) && snap[32]==1 && snap[76]==0x84 && snap[80] && snap[84],"accepted media and cover published");
        f=fopen("/ramdisk/wcp-rg/cover.bin","r");check(f!=0,"owned cover snapshot");n=fread(snap,1,sizeof(snap),f);fclose(f);
        check(n==64+sizeof(image) && !memcmp(snap,"WCA1",4) && !memcmp(snap+64,image,sizeof(image)),"immutable exact cover bytes");
        generation=media.generation;header[8]=header[9]=0;
        ((int (*)(void *,unsigned,void *))0xee210)(header,sizeof(header),ack);
        ((int (*)(void *,unsigned,void *))0xee210)(packet,2,ack);
        check(media.generation!=generation,"native empty FT clears the current cover");pause_test();
        check(!media_published_cover,"cleared cover is not advertised");
        header[8]=(unsigned char)(sizeof(image)>>8);header[9]=(unsigned char)sizeof(image);
        parse_file(header,sizeof(header));check(media_ft_declared && media_ft_uid==42,"actual native FT declaration binds original UID before data");
        {unsigned char update[sizeof(metadata)];memcpy(update,metadata,sizeof(update));update[15]=43;parse_media(update,sizeof(update));}
        packet[1]=0xc0;memcpy(packet+2,image,sizeof(image));
        ((int (*)(void *,unsigned,void *))0xee210)(packet,sizeof(packet),ack);
        check(media_cover_copied==1,"track change between declaration and first byte rejects prior cover");
        generation=media.generation;
        ((int (*)(void *,unsigned,void *))0xee210)(header,sizeof(header),ack);
        packet[1]=0x80;((int (*)(void *,unsigned,void *))0xee210)(packet,20,ack);
        {unsigned char update[sizeof(metadata)];memcpy(update,metadata,sizeof(update));update[15]=44;parse_media(update,sizeof(update));}
        check(media.generation!=generation && media.uid==44,"next track identity");
        packet[1]=0x40;memcpy(packet+2,image+18,sizeof(image)-18);
        ((int (*)(void *,unsigned,void *))0xee210)(packet,sizeof(image)-18+2,ack);
        check(media_cover_copied==1,"late prior cover rejected even when transfer ID reused");
    }
    unlink("/dev/shmem/wcp_cp_session");pause_test();
    check(!guidance.accepted && guidance.sequence==0,"session loss clears retained route");
    check(!media.uid && !media.generation && access("/ramdisk/wcp-rg/cover.bin",F_OK)!=0,"media and cover session clear");
    printf("RECEIVER_TAP_PASS ids=3 actual_parser=1 sdk_clock=1 session_clear=1 timing_identity=1 main_fps=30 alternate_fps=20,25,30,40 unknown_displays_preserved=1 rhd_ram_merge=1 pregrant_burst=1 idr_cadence=8\n");fflush(stdout);_exit(0);
}
'''
source=source.replace('@IMAGE@',','.join(str(b) for b in (HERE.parents[1]/'build-v161-stable-repo/MU1367/integration/tests/artwork-png/fixtures/colors.jpg').read_bytes()))
source=source.replace('@NATIVE@',str(native)).replace('@CONFIG@',','.join(str(b) for b in plistlib.dumps({'rightHandDrive':True,'fixtureUnrelated':'preserved'},fmt=plistlib.FMT_BINARY)))
asm=(native/'wcp_tap.S').read_text();source=source.replace('@ASM@','__asm__('+json.dumps(asm)+');')
fixture.SOURCE=source
fixture.RUN_SCRIPT='''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
mkdir -p /ramdisk/gate-persist /ramdisk/icab/persistent/cpmap-ui /ramdisk/app/carplaymaps /ramdisk/.v75-native-0123456789abcdef0123456789abcdef
cp /test/payload/payload/wcp_receiver /dev/shmem/wcp_receiver
cp /test/payload/payload/libv75-transport.so /ramdisk/app/carplaymaps/libv75-transport.so
cp /test/payload/payload/libomonob-wireless-maps.so /ramdisk/app/carplaymaps/libomonob-wireless-maps.so
MU1367_GATE_ONLY=1 V75_WCP_NATIVE=1 V75_WCP_CARD=791 V75_WCP_TRANSPORT=1 V75_WCP_SCOPE=/ramdisk/.v75-native-0123456789abcdef0123456789abcdef CPMAP_WCP_TAP=162 CPMAP_WCP_TIMED_INPUT=1 LD_PRELOAD=/proc/boot/gate.so:/mnt/app/carplaymaps/libv75-transport.so:/mnt/app/carplaymaps/libomonob-wireless-maps.so /dev/shmem/wcp_receiver --version
'''
fixture.IFS_EXTRA='[type=link] /mnt/icab=/ramdisk/icab\n[type=link] /mnt/app=/ramdisk/app\n'
fixture.PASS_MARKER='RECEIVER_TAP_PASS ids=3'
fixture.EVIDENCE=dict(actual_receiver_parser='0xec5ec',actual_fprintf_site='0xecbc8',ids=['0x5201','0x5202','0x5204'],production_arm_shim=True,scoped_preload_chain=['owned tap source','libv75-transport.so','libomonob-wireless-maps.so'] )
fixture.EVIDENCE['production_sources_sha256']={str(f.relative_to(native)):__import__('hashlib').sha256(f.read_bytes()).hexdigest() for f in native.iterdir() if f.is_file() and f.suffix in ('.c','.h','.S')}
fixture.main()
# Check the real worker's priority readback and its native stats call site.
import re,sys
output=Path(sys.argv[sys.argv.index('--output')+1])
log=(output/'qemu.log').read_text(errors='replace')
checks={
    'native_audio_floor14':bool(re.search(r'WCP_PRIORITY role=receiver-audio-102 .*before=10 after=14 error=0',log)),
    'native_audio_higher_priority_preserved':bool(re.search(r'WCP_PRIORITY role=receiver-audio-102 .*before=20 after=20 error=0',log)),
    'native_audio_stats_timestamped':'[cpmap][audio] t_us=' in log,
}
result=json.loads((output/'result.json').read_text());result['audio_checks']=checks;result['passed']=result['passed'] and all(checks.values())
(output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(checks));assert result['passed']
