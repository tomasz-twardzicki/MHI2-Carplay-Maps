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
 # Return immediately after the real private GOT calls under test.
 patch(0x253e8,0xe59f8be4,0xe12fff18)
 patch(0x25ce0,0xe59f036c,0xe12fff18)
 patch(0x20760,0xe59f526c,0xe12fff18)
open(o,'wb').write(b)
'''
subprocess.run([str(a.python_elf),'-c',script,str(original),str(inputs/'btwcp-noinit.so')],check=True)
spec=importlib.util.spec_from_file_location('fixture',HERE.parents[1]/'tests/receiver-alt-gate.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
fixture.SOURCE=r'''
#pragma clang diagnostic ignored "-Wunused-function"
#define CPMAP_BT_NO_CONSTRUCTOR
#define BT_HASH_PATH "/ramdisk/bt-library.so"
#include <stdint.h>
static const char *bt_fixture_load_path="/proc/boot/absent-library.so";
#define BT_LOAD_PATH bt_fixture_load_path
static int bt_fixture_race;
static void bt_fixture_cas(volatile uintptr_t *,volatile uintptr_t *);
#define CPMAP_BT_BEFORE_CAS bt_fixture_cas
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <dlfcn.h>
static unsigned bt_fixture_global_calls;
static ssize_t bt_fixture_global_write(int fd,const void *p,size_t n){(void)fd;(void)p;(void)n;bt_fixture_global_calls++;return -1;}
static void *bt_fixture_dlsym(void *handle,const char *name){
 if(handle==RTLD_DEFAULT&&!strcmp(name,"write"))return (void *)bt_fixture_global_write;
 return dlsym(handle,name);
}
#define dlsym bt_fixture_dlsym
static int bt_wired;
static int bt_fixture_access(const char *path,int mode){if(!strcmp(path,"/dev/ipod0")){if(bt_wired)return 0;errno=ENOENT;return -1;}return access(path,mode);}
#define access bt_fixture_access
#include "@NATIVE@/bt_session_guard.c"
#undef dlsym
#undef access
#include <sys/mman.h>
static void bt_fixture_cas(volatile uintptr_t *o,volatile uintptr_t *w){
 (void)o;if(bt_fixture_race){bt_fixture_race=0;*w=(uintptr_t)bt_real_write;}
}
static int byes,checks;
static void check(int ok,const char *why){checks++;if(!ok){printf("BT_SESSION_FAILED=%s checks=%d base=%lx errno=%d\n",why,checks,(unsigned long)bt_base,errno);fflush(stdout);_exit(81);}}
static void copy(const char *from,const char *to){FILE *in=fopen(from,"rb"),*out=fopen(to,"wb");char b[4096];size_t n;check(in&&out,"copy files");while((n=fread(b,1,sizeof(b),in)))check(fwrite(b,1,n,out)==n,"copy write");check(!ferror(in)&&!fclose(in)&&!fclose(out),"copy close");}
static void put(const char *path,const char *s){FILE *f=fopen(path,"w");check(f!=0,path);fputs(s,f);check(!fclose(f),"put close");}
int bt_command_boundary(const char *text){check(!strcmp(text,"WC bye\n"),"native bye command");byes++;return 0;}
int bt_fd_boundary(int fd){if(fd<0)return 0;close(fd);return 1;}
__asm__(".text\n.arm\n.align 2\n.global bt_probe_close\nbt_probe_close:\n push {r4-r11,lr}\n add r11,sp,#28\n sub sp,sp,#4\n mov r8,r1\n bx r0\n.global bt_probe_resend\nbt_probe_resend:\n push {r4-r11,lr}\n sub sp,sp,#4\n adr r8,1f\n bx r0\n1:\n bl bt_fd_boundary\n add sp,sp,#4\n pop {r4-r11,pc}\n");
extern void bt_probe_close(uintptr_t,int (*)(const char *));extern int bt_probe_resend(uintptr_t);
static void snapshot(unsigned session,unsigned counter,unsigned active){char s[160];snprintf(s,sizeof(s),"WCPRG1\n%ld\n1234\n%u\n%u\n%u\n",(long)getpid(),counter,session,active);put("/ramdisk/wcp-rg/session.state",s);bt_poll();}
static int paused(void){return ((int (*)(const char *))(bt_base+0x22eb4U))((const char *)(bt_base+0x121eU));}
static int released(void){return ((int (*)(void))(bt_base+0x22e54U))();}
__asm__(".text\n.arm\n.align 2\n.global rc_open_site\nrc_open_site:\n push {r4-r11,lr}\n sub sp,sp,#4\n mov r12,r0\n mov r0,r1\n mov r1,#0\n mov r2,#0\n adr r8,1f\n bx r12\n1:\n add sp,sp,#4\n pop {r4-r11,pc}\n.global rc_write_site\nrc_write_site:\n push {r4-r11,lr}\n sub sp,sp,#4\n mov r12,r0\n mov r0,r1\n mov r1,r2\n mov r2,r3\n adr r8,2f\n bx r12\n2:\n add sp,sp,#4\n pop {r4-r11,pc}\n");
extern int rc_open_site(uintptr_t,const char *);extern ssize_t rc_write_site(uintptr_t,int,const void *,size_t);
static void rc_policy(unsigned counter,int allow,int wired,int second){char b[256];snprintf(b,sizeof(b),"BTRC1\n42\n%u\n%d\n%d\n123456789ABC\n%d\n123456789ABC\n%s",counter,allow,wired,second?2:1,second?"111111111111\n":"");put("/ramdisk/cpmap-bt-policy.state",b);bt_rc_poll();}
static void rc_tests(void){
 unsigned char original_bank[24];unsigned char *bank=(unsigned char *)(bt_base+0x5bf5aU);int i;volatile int *count=(volatile int *)(bt_base+0x49124U),*cursor=(volatile int *)(bt_base+0x49128U);
 bt_reset();memset(&bt_rc,0,sizeof(bt_rc));bt_rc_started=bt_clock();check(paused(),"bounded startup wait for OEM trusted list");bt_rc_started=0;check(!paused(),"no-policy native fallback after bounded startup gate");
 *count=4;*cursor=0;for(i=0;i<24;i++)bank[i]=(unsigned char)(i+1);memset(bank,0x11,6);check(bt_rc_address("123456789ABC",bank+18),"native little-endian address conversion");memcpy(original_bank,bank,24);
 rc_policy(1,1,0,0);rc_policy(2,1,0,0);check(!paused(),"trusted policy ready");
 check(rc_open_site(bt_base+0x253e4U,(const char *)(bt_base+0x104cU))<0&&*cursor==3,"actual native selector GOT probe prefers fourth last-success phone");
 check(*count==4&&!memcmp(bank,original_bank,24),"OEM scan bank and pairing candidates remain unchanged");
 rc_write_site(bt_base+0x25cdcU,1,(const void *)(bt_base+0x1ff0U),0);check(bt_rc_attempt_valid,"actual native page-log call captures candidate");
 rc_write_site(bt_base+0x2075cU,1,(const void *)(bt_base+0x1b96U),0);check(bt_rc_failures==1&&!bt_rc_attempt_valid&&paused(),"actual native failure call cools failed address");
 rc_policy(3,1,0,1);check(!paused(),"other trusted phone remains eligible while last phone cools");
 rc_open_site(bt_base+0x253e4U,(const char *)(bt_base+0x104cU));check(*cursor==0,"fallback skips failed and stale addresses");
 memset(bt_rc_failed_until,0,sizeof(bt_rc_failed_until));rc_open_site(bt_base+0x253e4U,(const char *)(bt_base+0x104cU));check(*cursor==3,"last success eligible after cooldown");
 rc_policy(4,0,0,0);check(paused(),"manual stop ignition standby policy pauses RC");rc_policy(5,1,1,0);check(paused(),"wired takeover pauses RC");
 rc_policy(6,1,0,0);bt_rc_session(1);bt_rc_session(0);check(paused()&&bt_rc_wifi_windows==1,"accepted loss opens bounded Wi-Fi-first window");bt_rc_wifi_until=0;check(!paused(),"BT fallback resumes after Wi-Fi window");
 bt_rc.changed=1;check(paused(),"stale HMI policy fails closed");rc_policy(7,1,0,0);check(!paused(),"fresh HMI policy resumes RC");
 *count=0;check(paused(),"invalid native bank refuses override");*count=4;
 printf("BT_RECONNECT_NATIVE_PASS OEM_scan_bank_preserved=1 last_success_fourth=1 trusted_only=1 failure_cooldown=1 wifi_first=1 stop_policy=1\n");
}
__attribute__((constructor))static void test(void){
 char text[256];int before;struct timespec delay={1,600000000};uintptr_t *slot,*write_slot,base;unsigned attempts;
 check(getenv("MU1367_GATE_ONLY")!=0,"fixture only");
 unlink(BT_HASH_PATH);bt_service_step(1000,1000);check(!bt_installed&&!strcmp(bt_reason,"library-hash")&&bt_attempts==1,"missing library reason and first retry");
 bt_service_step(1999,1000);check(bt_attempts==1,"retry rate bounded");
 bt_service_step(61000,1000);check(bt_timed_out&&!bt_installed&&bt_attempts==1&&!strcmp(bt_reason,"attach-timeout"),"sixty second deadline without sleep");
 copy("/proc/boot/btwcp-original.so",BT_HASH_PATH);bt_timed_out=0;bt_next_attach=0;
 bt_service_step(62000,62000);check(!bt_installed&&!strcmp(bt_reason,"library-load"),"delayed library load reason");
 bt_fixture_load_path="/proc/boot/btwcp-noinit.so";bt_handle=dlopen(bt_fixture_load_path,RTLD_LAZY|RTLD_LOCAL);check(bt_handle!=0,"actual pinned DSO fixture load");
 base=(uintptr_t)dlsym(bt_handle,"pthread_setname_np")-0x13770U;
 slot=(uintptr_t *)(base+0x47878U);write_slot=(uintptr_t *)(base+0x47860U);
 *slot=*write_slot=base+0x272f0U;
 bt_service_step(63000,62000);check(bt_installed&&*slot==(uintptr_t)bt_private_open&&*write_slot==(uintptr_t)bt_private_write,"both unresolved slots installed after delayed availability");
 check(!strcmp(bt_open_kind,"lazy")&&!strcmp(bt_write_kind,"lazy"),"exact native resolver categorized");
 check(bt_default_write==(uintptr_t)bt_fixture_global_write&&bt_libc_write!=(uintptr_t)bt_fixture_global_write,"global write lookup is independently interposed");
 check((uintptr_t)bt_real_write==bt_libc_write&&bt_libc_write-bt_libc_open==0x238cU,"canonical factory libc pair selected");
 {int fd=open("/dev/null",O_WRONLY);check(fd>=0&&bt_private_write(fd,"x",1)==1&&!bt_fixture_global_calls,"write calls canonical native target, never global wrapper");close(fd);}
 *slot=(uintptr_t)bt_real_open;*write_slot=base+0x272f0U;bt_fixture_race=1;
 bt_service_step(64000,62000);check(!bt_installed&&!strcmp(bt_reason,"write-slot-race")&&*slot==(uintptr_t)bt_real_open&&*write_slot==(uintptr_t)bt_real_write,"in-flight native resolution preserves both original slots on CAS failure");
 bt_service_step(65000,62000);check(bt_installed&&bt_repairs==1,"resolved libc slots reattached");
 *slot=base+0x272f0U;bt_service_step(65100,62000);check(bt_installed&&bt_repairs==2,"post-install lazy overwrite repaired");
 attempts=bt_attempts;bt_service_step(65200,62000);check(bt_attempts==attempts,"healthy monitor does not rehash or reattach");
 *slot=(uintptr_t)bt_real_open;*write_slot=0x12345678U;bt_service_step(66000,62000);
 check(!bt_installed&&!strcmp(bt_reason,"write-slot-conflict")&&*slot==(uintptr_t)bt_real_open&&*write_slot==0x12345678U,"unknown write hook refused before touching open slot");
 *write_slot=(uintptr_t)bt_real_write;*slot=0x12345678U;bt_service_step(67000,62000);
 check(!bt_installed&&!strcmp(bt_reason,"open-slot-conflict")&&*write_slot==(uintptr_t)bt_real_write,"unknown open hook refused");
 *slot=(uintptr_t)bt_real_open;bt_service_step(68000,62000);check(bt_installed,"native restored slots can reattach");
 *write_slot=(uintptr_t)bt_fixture_global_write;bt_service_step(69000,62000);check(!bt_installed&&*write_slot==(uintptr_t)bt_fixture_global_write&&!strcmp(bt_reason,"write-slot-conflict"),"a real competing write hook is still preserved");
 *write_slot=bt_libc_write;bt_service_step(70000,62000);check(bt_installed,"native libc slot accepted despite different global write");
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
 rc_tests();bt_status();
 {FILE *f=fopen("/ramdisk/cpmap-bt-session.log","r");char log[16384];size_t n;check(f!=0,"native symbol diagnostic file");n=fread(log,1,sizeof(log)-1,f);check(!ferror(f)&&!fclose(f),"native diagnostic read");log[n]=0;
  check(strstr(log,"tag=default-write address=")&&strstr(log,"tag=libc-write address=")&&strstr(log,"name=write"),"global and explicit libc addresses and native symbol name are logged");}
 printf("BT_SESSION_NATIVE_PASS checks=%d byes=%d preserved=%lu paused=%lu resends=%lu hardware_boundaries_stubbed=1\n",checks,byes,bt_preserved,bt_paused,bt_resends);fflush(stdout);_exit(0);
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
fixture.PASS_MARKER='BT_SESSION_NATIVE_PASS';fixture.EVIDENCE=dict(production_source_sha256=hashlib.sha256((HERE.parent/'src/native/bt_session_guard.c').read_bytes()).hexdigest(),bt_library_sha256=hashlib.sha256(b).hexdigest(),native_bluetooth_paths_executed=['0x1c494 BT-close','0x22e54 RC released-check','0x22eb4 reconnect-preference probe','0x23c20 resend probe'],reconnect_header_sha256=hashlib.sha256((HERE.parent/'src/native/bt_reconnect.h').read_bytes()).hexdigest(),fixture_boundaries=['DSO constructor disabled','RC close notification skipped','WC command captured','resend decision returned after real probe','physical USB presence controlled'],radio_hardware_tested=False,lazy_resolved_mixed_slots=True,delayed_availability_and_deadline=True,cas_resolution_boundary_controlled=True,unknown_hooks_preserved=True)
fixture.main()
