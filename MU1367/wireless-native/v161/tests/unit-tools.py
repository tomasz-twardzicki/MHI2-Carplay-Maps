#!/usr/bin/env python3
"""Run owned tuning/launcher pre-exec contracts and scoped input on factory QNX."""
import importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
at=sys.argv.index('--components');components=Path(sys.argv[at+1]).resolve();del sys.argv[at:at+2]
native=HERE.parent/'src/native'
spec=importlib.util.spec_from_file_location('fixture',HERE.parents[1]/'tests/receiver-alt-gate.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
pins=json.loads((components/'COMPONENTS.json').read_text())
source=r'''
#define _POSIX_C_SOURCE 200809L
#pragma clang diagnostic ignored "-Wunused-function"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/stat.h>
static int stub_calls,expected_probe;
static void check(int ok,const char *why){if(!ok){printf("UNIT_TOOLS_FAILED=%s errno=%d\n",why,errno);fflush(stdout);_exit(81);}}
static int fixture_execl(const char *path,const char *arg,...){
 const char *scope=getenv("V75_WCP_SCOPE");struct stat st;
 check(!strcmp(path,"/dev/shmem/wcp_receiver") && !strcmp(path,arg),"receiver executable");
 check(scope && !lstat(scope,&st) && S_ISDIR(st.st_mode) && (st.st_mode&0777)==0700,"private native scope");
 check(!strcmp(getenv("V75_WCP_NATIVE"),"1") && !strcmp(getenv("V75_WCP_TRANSPORT"),"1") && !strcmp(getenv("V75_WCP_CARD"),"791"),"native contract");
 check(!strcmp(getenv("WCP_FPS"),"40") && !strcmp(getenv("WCP_VIDEO_FPS"),"40"),"configured FPS environment");
 check(!strcmp(getenv("CPMAP_WCP_TAP"),"161") && !strcmp(getenv("CPMAP_WCP_TIMED_INPUT"),"1"),"scoped extension enabled");
 check(strstr(getenv("LD_PRELOAD"),"libcpmap-wcp-tap.so:") && strstr(getenv("LD_PRELOAD"),"libv75-transport.so:") && strstr(getenv("LD_PRELOAD"),"libomonob-wireless-maps.so"),"scoped preload order");
 check((access("/dev/shmem/wcp_alt_probe",F_OK)==0)==expected_probe,"alternate probe/off policy");
 stub_calls++;errno=ENOENT;return -1;
}
#define main tuning_main
#include "@NATIVE@/wireless_tune.c"
#undef main
#define WCP_TAP_SHA256 "@TAP_SHA@"
#define execl fixture_execl
#define main launcher_main
@LAUNCHER@
#undef main
#undef execl
static void copy(const char *src,const char *dest){FILE *in=fopen(src,"rb"),*out=fopen(dest,"wb");unsigned char bytes[4096];size_t n;check(in && out,"copy open");while((n=fread(bytes,1,sizeof(bytes),in)))check(fwrite(bytes,1,n,out)==n,"copy write");check(!ferror(in) && !fclose(in) && !fclose(out),"copy close");}
static void put(const char *path,const char *value){FILE *f=fopen(path,"w");check(f!=0,"put");fputs(value,f);check(!fclose(f),"put close");}
__attribute__((constructor)) static void test(void){
 char *defaults[]={"wireless-tune","defaults",0},*fps[]={"wireless-tune","fps","25",0},*idr[]={"wireless-tune","idr","7",0},*smooth[]={"wireless-tune","smoothing","200",0},*bad[]={"wireless-tune","fps","41",0};
 char *normal[]={"wireless-receiver-exec",0},*verify_only[]={"wireless-receiver-exec","--verify-only",0},*transport[]={"wireless-receiver-exec","--transport-status",0};struct wcp_settings settings;
 check(getenv("MU1367_GATE_ONLY")!=0,"fixture only");
 check(!tuning_main(2,defaults) && !tuning_main(3,fps) && !tuning_main(3,idr) && !tuning_main(3,smooth),"tuning choices save");
 check(!wcp_settings_read(WCP_SETTINGS_PATH,&settings) && settings.fps==25 && settings.idr==7 && settings.smoothing==200,"tuning readback");
 check(tuning_main(3,bad)==2,"invalid tuning rejected");put(WCP_SETTINGS_PATH,"damaged\n");check(tuning_main(3,fps)==1 && !tuning_main(2,defaults),"damaged settings/default recovery");
 copy("/test/payload/payload/wcp_receiver","/dev/shmem/wcp_receiver");
 copy("/test/payload/payload/libv75-transport.so","/mnt/app/carplaymaps/libv75-transport.so");
 copy("/test/payload/payload/libomonob-wireless-maps.so","/mnt/app/carplaymaps/libomonob-wireless-maps.so");
 copy("/proc/boot/current-tap.so","/mnt/app/carplaymaps/libcpmap-wcp-tap.so");
 check(!launcher_main(2,verify_only) && !launcher_main(2,transport),"four exact hash pins pass");
 setenv("LD_PRELOAD","/unexpected.so",1);check(launcher_main(1,normal)==10,"inherited preload rejected");unsetenv("LD_PRELOAD");
 {
 struct timespec begin,end;long elapsed;
 unlink("/ramdisk/cpmap-driver-side.state");clock_gettime(CLOCK_MONOTONIC,&begin);
 expected_probe=1;check(launcher_main(1,normal)==127 && stub_calls==1,"positive pre-exec contract without coding");
 clock_gettime(CLOCK_MONOTONIC,&end);elapsed=(end.tv_sec-begin.tv_sec)*1000+(end.tv_nsec-begin.tv_nsec)/1000000;
 check(elapsed<2000,"no five-second coding wait before exec");
 }
 unsetenv("LD_PRELOAD");unlink("/dev/shmem/wcp_alt_probe");put("/mnt/persist/wcp_alt_off","1\n");expected_probe=0;check(launcher_main(1,normal)==127 && stub_calls==2,"explicit alternate off preserved");
 unsetenv("LD_PRELOAD");put("/dev/shmem/wcp_receiver","unknown receiver\n");check(launcher_main(2,verify_only)==10,"receiver hash drift rejected");
 puts("WCP_UNIT_TOOLS_NATIVE_PASS tuning=1 hash_pins=4 scoped_exec_stub=1 off_preserved=1 hardware_opened=0");fflush(stdout);_exit(0);
}
'''
launcher=(native/'wireless_receiver_exec.c').read_text().replace('#define _POSIX_C_SOURCE 200809L\n','')
launcher=launcher.replace('#include "wcp_sha.h"','#include "'+str(native/'wcp_sha.h')+'"').replace('#include "wcp_settings.h"','#include "'+str(native/'wcp_settings.h')+'"')
source=source.replace('@LAUNCHER@',launcher).replace('@NATIVE@',str(native)).replace('@TAP_SHA@',pins['libcpmap-wcp-tap.so'])
fixture.SOURCE=source
fixture.RAM_SECTORS=65536
fixture.EXTRA_FILES={'current-tap.so':components/'libcpmap-wcp-tap.so'}
fixture.IFS_EXTRA='[type=link] /mnt/icab=/ramdisk/icab\n[type=link] /mnt/app=/ramdisk/app\n[type=file]\ncurrent-tap.so\n'
fixture.RUN_SCRIPT='''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
mkdir -p /ramdisk/gate-persist /ramdisk/icab/persistent/cpmap-ui /ramdisk/app/carplaymaps
MU1367_GATE_ONLY=1 LD_PRELOAD=/proc/boot/gate.so:/test/payload/payload/libomonob-wireless-maps.so /test/payload/payload/wcp_receiver --version
rm -f /mnt/persist/wcp_alt_off /dev/shmem/wcp_alt_probe
/test/payload/payload/wireless-entry --selftest /ramdisk/input-plain /proc/boot/input.h264
rm -rf /ramdisk/input-plain
CPMAP_WCP_INPUT=161 LD_PRELOAD=/proc/boot/current-tap.so /test/payload/payload/wireless-entry --selftest /ramdisk/input-with-tap /proc/boot/input.h264
echo WCP_UNIT_TOOLS_PASS
'''
fixture.PASS_MARKER='WCP_UNIT_TOOLS_PASS'
fixture.EVIDENCE=dict(owned_components=pins,receiver_main_executed=False,launcher_exec_stubbed=True,input_preload_selftest=True)
fixture.main()
