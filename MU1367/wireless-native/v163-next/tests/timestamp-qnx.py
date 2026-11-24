#!/usr/bin/env python3
"""Reproduce capture/arrival PTS switching in the production bridge on QNX."""
import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(add_help=False)
p.add_argument('--bridge',type=Path,default=HERE.parent/'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c')
p.add_argument('--expect-old-bug',action='store_true')
a,rest=p.parse_known_args();sys.argv=[sys.argv[0],*rest]
spec=importlib.util.spec_from_file_location('fixture',HERE.parents[1]/'tests/receiver-alt-gate.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
source=r'''
#pragma clang diagnostic ignored "-Wunused-function"
#define main production_bridge_main
#include "@BRIDGE@"
#undef main
static void check(int ok,const char *why) {if(!ok){printf("TIMESTAMP_FAILED=%s\n",why);fflush(stdout);_exit(81);}}
static void put(const char *path,const char *text) {FILE *f=fopen(path,"w");check(f!=0,path);fputs(text,f);fclose(f);}
__attribute__((constructor)) static void exercise(void) {
    static const unsigned char config[]={1,100,0,31,255,225,0,2,103,1,1,0,2,104,1};
    unsigned char frame[]={0,0,0,4,101,1,2,3};AvcConfig avcc;char text[256];
    struct wcp_timing_ring *producer;unsigned i,seq=0;int fd;
    uint64_t base=monotonic_us(),prior=0,steps[3];
    memset(&avcc,0,sizeof(avcc));check(!queue_init(&g_queue),"queue");
    put(WCP_SETTINGS_PATH,"WCP161\nfps=40\nidr=8\nsmoothing_ms=0\n");
    snprintf(text,sizeof(text),"V75_NATIVE1\n%ld\n/ramdisk/.v75-native-0123456789abcdef0123456789abcdef\n",(long)getpid());put("/ramdisk/v75-wireless-native.owner",text);
    snprintf(text,sizeof(text),"%ld\n",(long)getpid());put("/dev/shmem/wcp_receiver.pid",text);put("/dev/shmem/wcp_cp_session","1\n");
    snprintf(text,sizeof(text),"V75_GRANT1\n%ld\n1\n",(long)getpid());put("/ramdisk/.v75-native-0123456789abcdef0123456789abcdef/cluster-session.accepted",text);
    snprintf(text,sizeof(text),"V75_FEED1\n%ld\n1\n1\n",(long)getpid());put("/ramdisk/.v75-native-0123456789abcdef0123456789abcdef/cluster-feed.state",text);
    fd=open(WCP_TIMING_PATH,O_RDWR|O_CREAT|O_TRUNC,0600);check(fd>=0 && !ftruncate(fd,sizeof(*producer)),"producer file");
    producer=mmap(0,sizeof(*producer),PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);close(fd);check(producer!=MAP_FAILED,"producer map");
    memset(producer,0,sizeof(*producer));producer->magic=WCP_TIMING_MAGIC;producer->version=1;producer->pid=getpid();producer->session=1;
    check(!parse_avcc_config(&avcc,config,sizeof(config)),"codec config");
    for(i=0;i<3;i++) {
        uint64_t capture=base+i*25000ULL,arrival=capture+2100000ULL;
        frame[5]=i+1;
        if(i!=1) {
            struct wcp_timing_event *event=&producer->events[seq++];
            check(wcp_fingerprint_avcc(&event->fingerprint,frame,sizeof(frame),4),"payload identity");
            event->timestamp_hi=capture>>32;event->timestamp_lo=capture;event->committed=seq;producer->sequence=seq;
        }
        check(!process_frame(&avcc,frame,sizeof(frame),ALT_FRAME_FLAG_KEYFRAME,i+1,
            (arrival/1000000ULL<<32)+((arrival%1000000ULL)<<32)/1000000ULL),"mux frame");
        steps[i]=g_last_pts-prior;prior=g_last_pts;
    }
    if(@OLD@) {
        check(steps[1]>180000 && steps[2]==1,"old two-second jump then one-tick clamp reproduced");
    } else {
        check(steps[1]>=2249 && steps[1]<=2251 && steps[2]>=2249 && steps[2]<=2251,"capture cadence survives correlation miss");
        check(g_smoothing_matches==2 && g_smoothing_misses==1,"matched/missing/matched path actually exercised");
    }
    if(!@OLD@) {
        pid_t child=fork();struct wcp_timing_ring *fresh;int status;
        check(child>=0,"replacement receiver process");
        if(!child) {for(;;)pause();}
        /* Publish a replacement timing inode exactly as the receiver now
         * does. The bridge still has its old mmap and must reopen it. */
        fd=open(WCP_TIMING_PATH ".next",O_RDWR|O_CREAT|O_EXCL,0600);
        check(fd>=0 && !ftruncate(fd,sizeof(*fresh)),"replacement timing file");
        fresh=mmap(0,sizeof(*fresh),PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);close(fd);
        check(fresh!=MAP_FAILED,"replacement timing map");memset(fresh,0,sizeof(*fresh));
        fresh->magic=WCP_TIMING_MAGIC;fresh->version=1;fresh->pid=child;fresh->session=1;
        frame[5]=10;check(wcp_fingerprint_avcc(&fresh->events[0].fingerprint,frame,sizeof(frame),4),"replacement identity");
        fresh->events[0].timestamp_hi=(base+75000)>>32;fresh->events[0].timestamp_lo=base+75000;
        fresh->events[0].committed=1;fresh->sequence=1;
        check(!rename(WCP_TIMING_PATH ".next",WCP_TIMING_PATH),"atomic producer publication");
        snprintf(text,sizeof(text),"V75_NATIVE1\n%ld\n/ramdisk/.v75-native-0123456789abcdef0123456789abcdef\n",(long)child);put("/ramdisk/v75-wireless-native.owner",text);
        snprintf(text,sizeof(text),"%ld\n",(long)child);put("/dev/shmem/wcp_receiver.pid",text);
        snprintf(text,sizeof(text),"V75_GRANT1\n%ld\n1\n",(long)child);put("/ramdisk/.v75-native-0123456789abcdef0123456789abcdef/cluster-session.accepted",text);
        snprintf(text,sizeof(text),"V75_FEED1\n%ld\n1\n1\n",(long)child);put("/ramdisk/.v75-native-0123456789abcdef0123456789abcdef/cluster-feed.state",text);
        check(!process_frame(&avcc,frame,sizeof(frame),ALT_FRAME_FLAG_KEYFRAME,4,
            ((base+2175000)/1000000ULL<<32)+(((base+2175000)%1000000ULL)<<32)/1000000ULL),"replacement receiver frame");
        check(g_smoothing_matches==3 && g_wireless_timing_pid==(uint32_t)child,"bridge remapped replacement receiver timing");
        check(producer->pid==(uint32_t)getpid(),"old inode remains readable without truncation");
        kill(child,SIGTERM);waitpid(child,&status,0);munmap(fresh,sizeof(*fresh));
        puts("TIMESTAMP_NEW_PID_PASS atomic_inode=1 old_mapping_readable=1 new_owner_matched=1");
    }
    printf("TIMESTAMP_QNX_PASS old_bug_reproduced=%u step_missing=%llu step_recovered=%llu hardware_opened=0\n",@OLD@,
        (unsigned long long)steps[1],(unsigned long long)steps[2]);fflush(stdout);_exit(0);
}
'''.replace('@BRIDGE@',str(a.bridge.resolve())).replace('@OLD@','1' if a.expect_old_bug else '0')
fixture.SOURCE=source
fixture.CFLAGS=['-I'+str(a.bridge.resolve().parent),'-I'+str(a.bridge.resolve().parents[3]/'native')]
fixture.IFS_EXTRA='[type=link] /mnt/icab=/ramdisk/icab\n'
fixture.RUN_SCRIPT='''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
mkdir -p /ramdisk/gate-persist /ramdisk/icab/persistent/cpmap-ui /ramdisk/.v75-native-0123456789abcdef0123456789abcdef
MU1367_GATE_ONLY=1 LD_PRELOAD=/proc/boot/gate.so /test/payload/payload/wcp_receiver --version
'''
fixture.PASS_MARKER='TIMESTAMP_QNX_PASS'
fixture.EVIDENCE=dict(bridge_sha256=hashlib.sha256(a.bridge.read_bytes()).hexdigest(),
    old_bug_expected=a.expect_old_bug,production_mux=True,most_writer_started=False,
    injected_arrival_offset_us=2100000)
fixture.main()
