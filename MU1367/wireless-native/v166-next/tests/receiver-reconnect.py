#!/usr/bin/env python3
"""Execute the pinned native sender through the ARM tap; stub socket I/O only.

The receiver main/radio/MFi/MOST are never started. Native queue allocation,
enqueue, sender loop and actual send callsite/register capture are exercised.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--native', type=Path, default=HERE.parent / 'src/native')
parser.add_argument('--expect-old-bug', action='store_true')
options, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0], *remaining]
native = options.native.resolve()
spec = importlib.util.spec_from_file_location('fixture', HERE.parents[1] / 'tests/receiver-alt-gate.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

source = r'''
#pragma clang diagnostic ignored "-Wunused-function"
#include "@NATIVE@/wcp_tap.c"
#include "@NATIVE@/wcp_rg.c"
#include <ucontext.h>
@ASM@
static uint32_t *sender;
static unsigned socket_active, injected, sends, send_bytes, frame_bytes=8, partial, send_calls;
static unsigned char *expected_frames[8];
static void check(int ok,const char *what) {
    if(!ok){printf("RECONNECT_FAILED=%s errno=%d\n",what,errno);fflush(stdout);_exit(81);}
}
static void fault(int sig,siginfo_t *info,void *context) {
    ucontext_t *u=context;printf("FAULT sig=%d pc=%x lr=%x address=%p\n",sig,
        (unsigned)u->uc_mcontext.cpu.gpr[15],(unsigned)u->uc_mcontext.cpu.gpr[14],info->si_addr);
    fflush(stdout);_exit(90);
}
static void put(const char *path,const char *text) {
    FILE *f=fopen(path,"w");check(f!=0,path);fputs(text,f);check(!fclose(f),"close");
}
int socket(int domain,int type,int protocol) {
    int (*real)(int,int,int)=dlsym(RTLD_NEXT,"socket");
    return socket_active?88:real(domain,type,protocol);
}
int connect(int fd,const struct sockaddr *addr,socklen_t size) {
    int (*real)(int,const struct sockaddr *,socklen_t)=dlsym(RTLD_NEXT,"connect");
    return socket_active && fd==88?0:real(fd,addr,size);
}
int setsockopt(int fd,int level,int name,const void *value,socklen_t size) {
    int (*real)(int,int,int,const void *,socklen_t)=dlsym(RTLD_NEXT,"setsockopt");
    return socket_active && fd==88?0:real(fd,level,name,value,size);
}
int close(int fd) {
    int (*real)(int)=dlsym(RTLD_NEXT,"close");
    return socket_active && fd==88?0:real(fd);
}
ssize_t recv(int fd,void *data,size_t size,int flags) {
    ssize_t (*real)(int,void *,size_t,int)=dlsym(RTLD_NEXT,"recv");
    if(!socket_active || fd!=88)return real(fd,data,size,flags);
    if(!injected) {
        unsigned i,j;uint64_t stamp=tap_now();
        injected=1;
        /* The sender owns its real queue lock here. Inject after its native
         * connection-start flush, using the actual enqueue function. */
        for(i=0;i<8;i++) {
            unsigned char *node=((void *(*)(unsigned,unsigned,uint64_t,unsigned))0xe6f00)(2,1,stamp,frame_bytes);
            check(node!=0,"native queue allocation");
            *(uint32_t *)(node+4)=16+frame_bytes;
            node[24]=node[25]=node[26]=0;node[27]=1;node[28]=i?0x41:0x65;
            for(j=5;j<frame_bytes;j++)node[24+j]=(unsigned char)(1+(i+j)%250);
            expected_frames[i]=malloc(frame_bytes);check(expected_frames[i]!=0,"expected frame allocation");
            memcpy(expected_frames[i],node+24,frame_bytes);
            ((void (*)(void *,void *))0xe6f98)(sender,node);
        }
    }
    errno=EAGAIN;return -1;
}
static ssize_t output(int fd,const void *data,size_t size,int flags) {
    unsigned count=(partial && !send_bytes && size>3)?3:size;
    check(fd==88 && flags==0 && size==frame_bytes-send_bytes,"original native send contract");
    check(!memcmp(data,expected_frames[sends]+send_bytes,count),"unchanged native payload");
    send_calls++;send_bytes+=count;
    if(send_bytes==frame_bytes) {
        free(expected_frames[sends]);expected_frames[sends++]=0;send_bytes=0;
        if(sends==8)sender[40/4]=1;
    }
    return count;
}
static void run_sender(const char *name,unsigned unrelated,unsigned port,unsigned accepted,unsigned bytes,unsigned split,unsigned expect_events) {
    uint64_t parent[64];uint32_t *p=(uint32_t *)parent;unsigned before=timing->sequence,expected;
    memset(parent,0,sizeof(parent));sender=(uint32_t *)((unsigned char *)parent+136);
    p[132/4]=1;sender[64/4]=port;sender[112/4]=1;sender[132/4]=unrelated;
    check(!pthread_mutex_init((pthread_mutex_t *)((char *)sender+8),0),"native sender lock");
    check(!pthread_cond_init((pthread_cond_t *)((char *)sender+16),0),"native sender condition");
    pthread_mutex_lock(&guard);wcp_rg_accept(&guidance,accepted);pthread_mutex_unlock(&guard);
    expected=timing->session==guidance.session?before+8:8;
    injected=sends=send_bytes=send_calls=0;frame_bytes=bytes;partial=split;
    unlink("/dev/shmem/alt_force_idr");unlink("/ramdisk/wcp-rg/idr.state");
    socket_active=1;next_send=output;
    ((void *(*)(void *))0xe6fcc)(sender);
    socket_active=0;
    check(sends==8,"all native queued frames sent");
    if(expect_events) {
        check(timing->magic==WCP_TIMING_MAGIC && timing->session==guidance.session,"accepted timing ownership");
        check(timing->sequence==expected,"one timing event per complete AU including partial sends");
        check(access("/ramdisk/wcp-rg/idr.state",F_OK)==0,"receiver cadence receipt restored");
    } else {
        check(timing->sequence==before,"excluded sender cannot publish timing");
        check(access("/ramdisk/wcp-rg/idr.state",F_OK)!=0,"excluded sender cannot claim cadence");
    }
    printf("NATIVE_SENDER name=%s port=%u unrelated=%u session=%u accepted=%u frames=%u calls=%u timing=%u cadence=%u\n",
        name,port,unrelated,guidance.session,accepted,sends,send_calls,timing->sequence,
        access("/ramdisk/wcp-rg/idr.state",F_OK)==0);fflush(stdout);
    pthread_cond_destroy((pthread_cond_t *)((char *)sender+16));
    pthread_mutex_destroy((pthread_mutex_t *)((char *)sender+8));
}
__attribute__((constructor)) static void exercise(void) {
    struct sigaction sa;unsigned original_session;
    memset(&sa,0,sizeof(sa));sa.sa_sigaction=fault;sa.sa_flags=SA_SIGINFO;
    sigaction(SIGBUS,&sa,0);sigaction(SIGSEGV,&sa,0);
    check(getenv("MU1367_GATE_ONLY")!=0,"fixture only");
    if(!enabled)init();check(enabled && timing!=MAP_FAILED,"production tap initialized");
    /* Disable only the file-poll publisher: acceptance is changed explicitly
     * under its production guard, so native sender restarts are deterministic. */
    pthread_mutex_lock(&guard);
    wcp_rg_accept(&guidance,1);original_session=guidance.session;
    pthread_mutex_unlock(&guard);
    run_sender("first-alt",1,9997,1,8,0,1);
    check(guidance.session==original_session,"same receiver and session");
    run_sender("restart-alt-zero-field",0,9997,1,8,0,@FIXED@);
    if(@FIXED@) {
        /* New accepted session in this same PID. Preserve the input fallback
         * until its new receiver cadence receipt has actually been written. */
        pthread_mutex_lock(&guard);wcp_rg_accept(&guidance,0);wcp_rg_accept(&guidance,1);pthread_mutex_unlock(&guard);
        run_sender("new-session-large-partial",0,9997,1,61000,1,1);
        check(guidance.session!=original_session,"accepted session advanced");
        run_sender("exclude-main-port",1,7101,1,8,0,0);
        run_sender("exclude-other-port",1,9998,1,8,0,0);
        run_sender("exclude-unaccepted",1,9997,0,8,0,0);
    }
    printf("RECEIVER_RECONNECT_PASS old_bug_reproduced=%u native_sender=0xe6fcc socket_io_stubbed=1 hardware_opened=0\n",!@FIXED@);
    fflush(stdout);_exit(0);
}
'''
# The tap resolves the actual libc pthread_create with dlsym. In init(), replace
# only creation of its publisher with a test no-op by wrapping that single call.
tap = (native / 'wcp_tap.c').read_text()
needle = 'if(!pthread_create(&thread,0,publisher,0)) {pthread_detach(thread);enabled=1;}'
if needle not in tap:
    raise RuntimeError('Publisher creation contract changed')
tap = tap.replace(needle, 'enabled=1; /* file-poll publisher disabled only in fixture */')
source = source.replace('#include "@NATIVE@/wcp_tap.c"', tap)
source = source.replace('@NATIVE@', str(native)).replace('@FIXED@', '0' if options.expect_old_bug else '1')
source = source.replace('@ASM@', '__asm__(' + json.dumps((native / 'wcp_tap.S').read_text()) + ');')
fixture.SOURCE = source
fixture.CFLAGS = ['-Wno-unused-variable', '-I' + str(native)]
fixture.RUN_SCRIPT = '''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
mkdir -p /ramdisk/gate-persist
MU1367_GATE_ONLY=1 CPMAP_WCP_TAP=162 CPMAP_WCP_TIMED_INPUT=1 LD_PRELOAD=/proc/boot/gate.so /test/payload/payload/wcp_receiver --version
'''
fixture.PASS_MARKER = 'RECEIVER_RECONNECT_PASS'
fixture.EVIDENCE = dict(actual_native_sender='0xe6fcc', actual_send_call='0xe72fc',
    old_bug_expected=options.expect_old_bug, socket_io_stubbed=True,
    real_radio_session_tested=False, publisher_polling_disabled=True,
    tap_sha256=hashlib.sha256((native / 'wcp_tap.c').read_bytes()).hexdigest())
fixture.main()
