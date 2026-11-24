#!/usr/bin/env python3
"""Execute native add-on guard/BT-close/resend paths; stub hardware boundaries."""
import argparse,hashlib,importlib.util,json,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(add_help=False);p.add_argument('--python-elf',type=Path,required=True)
a,remaining=p.parse_known_args();sys.argv=[sys.argv[0],*remaining]
out=Path(remaining[remaining.index('--output')+1]).resolve();inputs=out.with_name(out.name+'-inputs');inputs.mkdir(parents=True,exist_ok=False)
original=HERE.parents[1]/'build-v163t3-audit/libbtwcp.so';b=original.read_bytes();assert hashlib.sha256(b).hexdigest()=='95a75391792c7266eb8c759c20f3b35745d2cd890b74fad45e2c36a5406e9d4e'
# ELF parsing is done with the existing host-only audit environment.
import subprocess
script=r'''import sys,struct,json
from elftools.elf.elffile import ELFFile
p=sys.argv[1];o=sys.argv[2];b=bytearray(open(p,'rb').read())
with open(p,'rb') as f:
 e=ELFFile(f);s=e.get_section_by_name('.dynamic')
 for i,t in enumerate(s.iter_tags()):
  if t.entry.d_tag=='DT_INIT_ARRAYSZ':assert t.entry.d_val==4;struct.pack_into('<I',b,s['sh_offset']+i*8+4,0)
 def patch(va,expected,new):
  for seg in e.iter_segments():
   if seg['p_type']=='PT_LOAD' and seg['p_vaddr']<=va<seg['p_vaddr']+seg['p_filesz']:
    off=seg['p_offset']+va-seg['p_vaddr'];assert struct.unpack_from('<I',b,off)[0]==expected;struct.pack_into('<I',b,off,new);return
  raise AssertionError(va)
 # Only VM boundaries: no OEM constructor, no RC event callback, no actual
 # control socket; capture the resend decision after its real open/compare.
 patch(0x1bf94,0xeb000eff,0xe1a00000)
 patch(0x22ee4,0xe92d48f0,0xe12fff18)
 patch(0x23c38,0x4a00002c,0xe12fff18)
open(o,'wb').write(b)
'''
subprocess.run([str(a.python_elf),'-c',script,str(original),str(inputs/'btwcp-noinit.so')],check=True)
spec=importlib.util.spec_from_file_location('fixture',HERE.parents[1]/'tests/receiver-alt-gate.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
fixture.SOURCE=r'''
#pragma clang diagnostic ignored "-Wunused-function"
#define CPMAP_BT_NO_CONSTRUCTOR
#define BT_HASH_PATH "/proc/boot/btwcp-original.so"
#define BT_LOAD_PATH "/proc/boot/btwcp-noinit.so"
#include <unistd.h>
#include <string.h>
#include <errno.h>
static int bt_wired;
static int bt_fixture_access(const char *path,int mode){if(!strcmp(path,"/dev/ipod0")){if(bt_wired)return 0;errno=ENOENT;return -1;}return access(path,mode);}
#define access bt_fixture_access
#include "@NATIVE@/bt_session_guard.c"
#undef access
#include <sys/mman.h>
static int byes,checks;
static void check(int ok,const char *why){checks++;if(!ok){printf("BT_SESSION_FAILED=%s checks=%d base=%lx errno=%d\n",why,checks,(unsigned long)bt_base,errno);fflush(stdout);_exit(81);}}
static void put(const char *path,const char *s){FILE *f=fopen(path,"w");check(f!=0,path);fputs(s,f);check(!fclose(f),"put close");}
int bt_command_boundary(const char *text){check(!strcmp(text,"WC bye\n"),"native bye command");byes++;return 0;}
int bt_fd_boundary(int fd){if(fd<0)return 0;close(fd);return 1;}
__asm__(".text\n.arm\n.align 2\n.global bt_probe_close\nbt_probe_close:\n push {r4-r11,lr}\n add r11,sp,#28\n sub sp,sp,#4\n mov r8,r1\n bx r0\n.global bt_probe_resend\nbt_probe_resend:\n push {r4-r11,lr}\n sub sp,sp,#4\n adr r8,1f\n bx r0\n1:\n bl bt_fd_boundary\n add sp,sp,#4\n pop {r4-r11,pc}\n");
extern void bt_probe_close(uintptr_t,int (*)(const char *));extern int bt_probe_resend(uintptr_t);
static void snapshot(unsigned session,unsigned counter,unsigned active){char s[160];snprintf(s,sizeof(s),"WCPRG1\n%ld\n1234\n%u\n%u\n%u\n",(long)getpid(),counter,session,active);put("/ramdisk/wcp-rg/session.state",s);bt_poll();}
static int paused(void){return ((int (*)(const char *))(bt_base+0x22eb4U))((const char *)(bt_base+0x121eU));}
static int released(void){return ((int (*)(void))(bt_base+0x22e54U))();}
__attribute__((constructor))static void test(void){
 char text[256];int before;struct timespec delay={1,600000000};uintptr_t *slot;
 check(getenv("MU1367_GATE_ONLY")!=0,"fixture only");
 check(bt_attach(),"exact private GOT installed");slot=(uintptr_t *)(bt_base+0x47878U);check(*slot==(uintptr_t)bt_private_open,"open slot scoped");
 check(!paused()&&!released(),"cold start unchanged");
 put("/dev/shmem/wcp_cp_session","1\n");
 bt_probe_close(bt_base+0x1c494U,bt_command_boundary);check(byes==1,"old behavior reproduced before lease");
 mkdir("/ramdisk/wcp-rg",0700);mkdir("/ramdisk/.v75-native-0123456789abcdef0123456789abcdef",0700);
 snprintf(text,sizeof(text),"V75_NATIVE1\n%ld\n/ramdisk/.v75-native-0123456789abcdef0123456789abcdef\n",(long)getpid());put("/ramdisk/v75-wireless-native.owner",text);
 snprintf(text,sizeof(text),"%ld\n",(long)getpid());put("/dev/shmem/wcp_receiver.pid",text);
 snprintf(text,sizeof(text),"V75_GRANT1\n%ld\n1\n",(long)getpid());put("/ramdisk/.v75-native-0123456789abcdef0123456789abcdef/cluster-session.accepted",text);
 snapshot(2,1,1);check(!bt_live(),"one stale sample not accepted");snapshot(2,2,1);check(bt_live(),"advancing accepted owner");
 check(released()&&paused(),"native RC boolean guards use accepted owner");
 check(access("/dev/shmem/wcp_bt_released",F_OK)&&access("/mnt/persist/btwcp_reconnect_off",F_OK),"no profile or preference marker fabricated");
 before=byes;bt_probe_close(bt_base+0x1c494U,bt_command_boundary);check(byes==before&&bt_preserved==1,"BT-only close preserves native control session");
 check(bt_probe_resend(bt_base+0x23c20U)&&bt_resends==1,"native resend probe guarded");
 snapshot(2,3,0);check(!bt_live()&&!paused(),"AirPlay inactive ends pause immediately");
 unlink("/dev/shmem/wcp_cp_session");bt_probe_close(bt_base+0x1c494U,bt_command_boundary);check(byes==before,"no phantom bye after AirPlay teardown");
 put("/dev/shmem/wcp_cp_session","1\n");snapshot(4,1,1);check(!bt_live(),"new session requires fresh advancement");snapshot(4,2,1);check(bt_live()&&paused(),"reconnect reacquires ownership");
 nanosleep(&delay,0);check(!bt_live()&&!paused(),"stale heartbeat expires without poll/cleanup");
 snapshot(4,3,1);check(bt_live(),"heartbeat recovery");bt_wired=1;bt_poll();check(!bt_live()&&!paused(),"wired takeover restores native reconnect behavior");bt_wired=0;
 snapshot(6,1,1);snapshot(6,2,1);put("/mnt/persist/btwcp_off","1\n");bt_poll();check(!bt_live(),"wireless disable revokes lease");unlink("/mnt/persist/btwcp_off");
 put("/mnt/persist/btwcp_reconnect_off","user\n");check(paused(),"real user reconnect preference retained while unaccepted");unlink("/mnt/persist/btwcp_reconnect_off");
 put("/dev/shmem/wcp_bt_released","real\n");check(released(),"original actual profile-release behavior retained");unlink("/dev/shmem/wcp_bt_released");
 snapshot(8,1,1);snapshot(8,2,1);unlink("/dev/shmem/wcp_receiver.pid");bt_poll();check(!bt_live()&&!paused(),"owner receipt loss restores RC");
 bt_status();printf("BT_SESSION_NATIVE_PASS checks=%d byes=%d preserved=%lu paused=%lu resends=%lu hardware_boundaries_stubbed=1\n",checks,byes,bt_preserved,bt_paused,bt_resends);fflush(stdout);_exit(0);
}
'''.replace('@NATIVE@',str((HERE.parent/'src/native').resolve()))
fixture.EXTRA_FILES={'btwcp-original.so':original,'btwcp-noinit.so':inputs/'btwcp-noinit.so'}
fixture.IFS_EXTRA='[type=file]\nbtwcp-original.so\nbtwcp-noinit.so\n'
fixture.RUN_SCRIPT='''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
mkdir -p /ramdisk/gate-persist
MU1367_GATE_ONLY=1 LD_PRELOAD=/proc/boot/gate.so /test/payload/payload/wcp_receiver --version
'''
fixture.PASS_MARKER='BT_SESSION_NATIVE_PASS';fixture.EVIDENCE=dict(production_source_sha256=hashlib.sha256((HERE.parent/'src/native/bt_session_guard.c').read_bytes()).hexdigest(),bt_library_sha256=hashlib.sha256(b).hexdigest(),native_bluetooth_paths_executed=['0x1c494 BT-close','0x22e54 RC released-check','0x22eb4 reconnect-preference probe','0x23c20 resend probe'],fixture_boundaries=['DSO constructor disabled','RC close notification skipped','WC command captured','resend decision returned after real probe','physical USB presence controlled'],radio_hardware_tested=False)
fixture.main()
