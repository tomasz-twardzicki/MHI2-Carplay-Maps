#!/usr/bin/env python3
"""Run owned tuning/launcher pre-exec contracts and scoped input on factory QNX."""
import importlib.util,json,sys,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
at=sys.argv.index('--components');components=Path(sys.argv[at+1]).resolve();del sys.argv[at:at+2]
at=sys.argv.index('--gps-dio');gps_dio=Path(sys.argv[at+1]).resolve();del sys.argv[at:at+2]
assert __import__('hashlib').sha256(gps_dio.read_bytes()).hexdigest()=='ead570d45071bb4dafe4a4667003bb9f82a72f58178f30dc86a08f11ce62a3ae'
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
static int stub_calls,expected_probe,expected_gps;
static void check(int ok,const char *why){if(!ok){printf("UNIT_TOOLS_FAILED=%s errno=%d\n",why,errno);fflush(stdout);_exit(81);}}
static int fixture_execl(const char *path,const char *arg,...){
 const char *scope=getenv("V75_WCP_SCOPE");struct stat st;
 check(!strcmp(path,"/dev/shmem/wcp_receiver") && !strcmp(path,arg),"receiver executable");
 check(scope && !lstat(scope,&st) && S_ISDIR(st.st_mode) && (st.st_mode&0777)==0700,"private native scope");
 check(!strcmp(getenv("V75_WCP_NATIVE"),"1") && !strcmp(getenv("V75_WCP_TRANSPORT"),"1") && !strcmp(getenv("V75_WCP_CARD"),"791"),"native contract");
 check(!strcmp(getenv("WCP_FPS"),"40") && !strcmp(getenv("WCP_VIDEO_FPS"),"40"),"configured FPS environment");
 check(!strcmp(getenv("CPMAP_WCP_TAP"),"162") && !strcmp(getenv("CPMAP_WCP_TIMED_INPUT"),"1"),"scoped extension enabled");
 check(!strcmp(getenv("CPMAP_WCP_LOCATION"),expected_gps?"164":"0"),"GPS mode is explicit and hash gated");
 check(strstr(getenv("LD_PRELOAD"),"libcpmap-wcp-tap.so:") && strstr(getenv("LD_PRELOAD"),"libv75-transport.so:") && strstr(getenv("LD_PRELOAD"),"libomonob-wireless-maps.so"),"scoped preload order");
 check((access("/dev/shmem/wcp_alt_probe",F_OK)==0)==expected_probe,"alternate probe/off policy");
 stub_calls++;errno=ENOENT;return -1;
}
#define main tuning_main
#define GPS_SOURCE_SHA256 "@GPS_SHA@"
#include "@NATIVE@/wireless_tune.c"
#undef main
#define WCP_TAP_SHA256 "@TAP_SHA@"
#define BT_GUARD_SHA256 "@BT_SHA@"
#define execl fixture_execl
#define main launcher_main
@LAUNCHER@
#undef main
#undef execl
static void copy(const char *src,const char *dest){FILE *in=fopen(src,"rb"),*out=fopen(dest,"wb");unsigned char bytes[4096];size_t n;check(in && out,"copy open");while((n=fread(bytes,1,sizeof(bytes),in)))check(fwrite(bytes,1,n,out)==n,"copy write");check(!ferror(in) && !fclose(in) && !fclose(out),"copy close");}
static void put(const char *path,const char *value){FILE *f=fopen(path,"w");check(f!=0,"put");fputs(value,f);check(!fclose(f),"put close");}
__attribute__((constructor)) static void test(void){
 char *defaults[]={"wireless-tune","defaults",0},*fps[]={"wireless-tune","fps","25",0},*idr[]={"wireless-tune","idr","7",0},*smooth[]={"wireless-tune","smoothing","200",0},*bad[]={"wireless-tune","fps","41",0};
 char *normal[]={"wireless-receiver-exec",0},*verify_only[]={"wireless-receiver-exec","--verify-only",0},*transport[]={"wireless-receiver-exec","--transport-status",0},*bt_status[]={"wireless-receiver-exec","--bt-guard-status",0};struct wcp_settings settings;
 check(getenv("MU1367_GATE_ONLY")!=0,"fixture only");
 check(!tuning_main(2,defaults) && !tuning_main(3,fps) && !tuning_main(3,idr) && !tuning_main(3,smooth),"tuning choices save");
 check(!wcp_settings_read(WCP_SETTINGS_PATH,&settings) && settings.fps==25 && settings.idr==7 && settings.smoothing==200,"tuning readback");
 check(tuning_main(3,bad)==2,"invalid tuning rejected");put(WCP_SETTINGS_PATH,"damaged\n");check(tuning_main(3,fps)==1 && !tuning_main(2,defaults),"damaged settings/default recovery");
 copy("/test/payload/payload/wcp_receiver","/dev/shmem/wcp_receiver");
 copy("/test/payload/payload/libv75-transport.so","/mnt/app/carplaymaps/libv75-transport.so");
 copy("/test/payload/payload/libomonob-wireless-maps.so","/mnt/app/carplaymaps/libomonob-wireless-maps.so");
 copy("/proc/boot/current-tap.so","/mnt/app/carplaymaps/libcpmap-wcp-tap.so");
 copy("/proc/boot/current-bt-guard.so","/mnt/app/carplaymaps/libcpmap-bt-session.so");
 copy("/test/payload/payload/libbtwcp.so","/mnt/ota/libbtwcp.so");
 {
 char *gps_status[]={"wireless-receiver-exec","--gps-source-status",0};
 check(launcher_main(2,gps_status)==10,"missing GPS assets rejected");
 check(!mkdir("/mnt/app/carplaymaps/stock_first",0700)||errno==EEXIST,"stock DIO directory");
 copy("/proc/boot/gps-stock-dio","/mnt/app/carplaymaps/stock_first/dio_manager.real");
 check(!chmod("/mnt/app/carplaymaps/stock_first/dio_manager.real",0700),"stock DIO executable mode");
 copy("/proc/boot/current-gps-source.so","/mnt/app/carplaymaps/libcpmap-gps-source.so");
 check(!launcher_main(2,gps_status),"exact GPS source and DIO hashes pass");
 put("/mnt/app/carplaymaps/libcpmap-gps-source.so","drift");check(launcher_main(2,gps_status)==10,"GPS source drift rejected");
 copy("/proc/boot/current-gps-source.so","/mnt/app/carplaymaps/libcpmap-gps-source.so");
 put("/mnt/app/carplaymaps/stock_first/dio_manager.real","drift");check(launcher_main(2,gps_status)==10,"DIO firmware drift rejected");
 copy("/proc/boot/gps-stock-dio","/mnt/app/carplaymaps/stock_first/dio_manager.real");
 check(!chmod("/mnt/app/carplaymaps/stock_first/dio_manager.real",0700),"stock DIO executable mode restored");
 check(!mkdir(WCP_LOCATION_LAYER,0700)||errno==EEXIST,"GPS-owned preference root");put(WCP_LOCATION_LAYER "/STATE","installed\n");
 {char *on[]={"wireless-tune","gps","on",0},*off[]={"wireless-tune","gps","off",0},*probe[]={"wireless-tune","gps-probe","on",0};
 check(!tuning_main(3,on)&&gps_option_enabled(WCP_LOCATION_ENABLE_FILE),"GEM GPS opt-in preference");
 check(!tuning_main(3,off)&&!gps_option_enabled(WCP_LOCATION_ENABLE_FILE),"GEM GPS opt-out preference");
 check(!tuning_main(3,probe)&&gps_option_enabled(WCP_LOCATION_PROBE_FILE),"GEM diagnostic probe preference");unlink(WCP_LOCATION_PROBE_FILE);}
 }
 check(!launcher_main(2,bt_status),"BT add-on and guard hashes pass");
 put("/mnt/app/carplaymaps/libcpmap-bt-session.so","corrupted guard\n");check(launcher_main(2,bt_status)==10,"BT guard drift rejected");
 copy("/proc/boot/current-bt-guard.so","/mnt/app/carplaymaps/libcpmap-bt-session.so");
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
 copy("/test/payload/payload/wcp_receiver","/dev/shmem/wcp_receiver");
 put(WCP_LOCATION_ENABLE_FILE,"1\n");expected_gps=1;
 check(launcher_main(1,normal)==127&&stub_calls==3,"GPS explicit opt-in after validated assets");
 unsetenv("LD_PRELOAD");put("/mnt/app/carplaymaps/libcpmap-gps-source.so","drift\n");expected_gps=0;
 check(launcher_main(1,normal)==127&&stub_calls==4,"GPS asset drift falls back without breaking CarPlay launch");
 copy("/proc/boot/current-gps-source.so","/mnt/app/carplaymaps/libcpmap-gps-source.so");unlink(WCP_LOCATION_ENABLE_FILE);
 puts("WCP_UNIT_TOOLS_NATIVE_PASS tuning=1 hash_pins=4 scoped_exec_stub=1 off_preserved=1 hardware_opened=0");fflush(stdout);_exit(0);
}
'''
launcher=(native/'wireless_receiver_exec.c').read_text().replace('#define _POSIX_C_SOURCE 200809L\n','')
launcher=launcher.replace('#include "wcp_sha.h"','#include "'+str(native/'wcp_sha.h')+'"').replace('#include "wcp_settings.h"','#include "'+str(native/'wcp_settings.h')+'"')
source=source.replace('@LAUNCHER@',launcher).replace('@NATIVE@',str(native)).replace('@TAP_SHA@',pins['libcpmap-wcp-tap.so']).replace('@BT_SHA@',pins['libcpmap-bt-session.so']).replace('@GPS_SHA@',pins['libcpmap-gps-source.so'])
fixture.CFLAGS=["-I"+str(native)]
fixture.SOURCE=source
fixture.RAM_SECTORS=65536
wrapper=(HERE.parent/'src/runtime/btstack_wrap.sh').read_text()
assert wrapper.count('exec "$REAL" "$@"')==2
wrapper=wrapper.replace('exec "$REAL" "$@"','echo "BT_WRAPPER_FINAL guard=${CPMAP_BT_GUARD:-0} preload=${LD_PRELOAD:-none}";exit 0')
wrapper_fixture=components/'btstack-wrapper-fixture.sh';wrapper_fixture.write_text(wrapper)
dio_wrapper=(HERE.parent/'src/runtime/dio_manager.wrapper.sh').read_text().replace('exec "$REAL" "$@"','echo "DIO_WRAPPER_FINAL gps=${CPMAP_GPS_DIO:-0} preload=${LD_PRELOAD:-none}";exit 0')
dio_fixture=components/'dio-wrapper-fixture.sh';dio_fixture.write_text(dio_wrapper)
control_tap=HERE.parents[1]/'build-v163t3-components-r5/libcpmap-wcp-tap.so'
assert __import__('hashlib').sha256(control_tap.read_bytes()).hexdigest()=='83521b9b5fdb29a5f22008353976441e4363d5bef50881e9008ca4b675184648'
fixture.EXTRA_FILES={'current-tap.so':components/'libcpmap-wcp-tap.so','control-tap.so':control_tap,'current-bt-guard.so':components/'libcpmap-bt-session.so','current-launcher':components/'wireless-receiver-exec','wrapper.sh':wrapper_fixture,'current-gps-source.so':components/'libcpmap-gps-source.so','gps-stock-dio':gps_dio,'dio-wrapper.sh':dio_fixture}
fixture.IFS_EXTRA='[type=link] /mnt/icab=/ramdisk/icab\n[type=link] /mnt/app=/ramdisk/app\n[type=link] /mnt/ota=/ramdisk/ota\n[type=file]\ncurrent-tap.so\ncontrol-tap.so\ncurrent-bt-guard.so\ncurrent-launcher\nwrapper.sh\ncurrent-gps-source.so\ngps-stock-dio\ndio-wrapper.sh\n'
fixture.EXTRA_FILES['gps-preference.sh']=HERE.parent/'src/runtime/gps-preference.sh'
fixture.EXTRA_FILES['current-tune']=components/'wireless-tune'
fixture.IFS_EXTRA+='gps-preference.sh\ncurrent-tune\n'
fixture.RUN_SCRIPT='''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
mkdir -p /ramdisk/gate-persist /ramdisk/ota /ramdisk/icab/persistent/cpmap-ui /ramdisk/app/carplaymaps
MU1367_GATE_ONLY=1 LD_PRELOAD=/proc/boot/gate.so:/test/payload/payload/libomonob-wireless-maps.so /test/payload/payload/wcp_receiver --version
rm -f /mnt/persist/wcp_alt_off /dev/shmem/wcp_alt_probe
/test/payload/payload/wireless-entry --selftest /ramdisk/input-plain /proc/boot/input.h264
rm -rf /ramdisk/input-plain
CONTROL_STATUS=0
MU1367_INPUT_SELFTEST=1 CPMAP_WCP_INPUT=162 LD_PRELOAD=/proc/boot/control-tap.so /test/payload/payload/wireless-entry --selftest /ramdisk/input-control-tap /proc/boot/input.h264 || CONTROL_STATUS=$?
CANDIDATE_STATUS=0
MU1367_INPUT_SELFTEST=1 CPMAP_WCP_INPUT=162 LD_PRELOAD=/proc/boot/current-tap.so /test/payload/payload/wireless-entry --selftest /ramdisk/input-with-tap /proc/boot/input.h264 || CANDIDATE_STATUS=$?
echo "INPUT_COMPARISON control=$CONTROL_STATUS candidate=$CANDIDATE_STATUS"
# Native helper performs real hash checks; only final OEM exec is captured.
cp /proc/boot/current-launcher /mnt/app/carplaymaps/wireless-receiver-exec
cp /proc/boot/current-bt-guard.so /mnt/app/carplaymaps/libcpmap-bt-session.so
cp /test/payload/payload/libbtwcp.so /mnt/ota/libbtwcp.so
cp /test/payload/payload/libv75-transport.so /mnt/app/carplaymaps/libv75-transport.so
echo 1 > /mnt/persist/btwcp_enable
/bin/ksh /proc/boot/wrapper.sh > /ramdisk/bt-wrapper-on
 grep 'guard=1 preload=/mnt/app/carplaymaps/libcpmap-bt-session.so:/mnt/app/carplaymaps/libv75-transport.so:/mnt/ota/libbtwcp.so' /ramdisk/bt-wrapper-on
echo drift > /mnt/app/carplaymaps/libcpmap-bt-session.so
/bin/ksh /proc/boot/wrapper.sh > /ramdisk/bt-wrapper-drift
 grep 'guard=0 preload=none' /ramdisk/bt-wrapper-drift
rm -f /mnt/persist/btwcp_enable
echo MU1367/791 > /mnt/app/carplaymaps/PROFILE
echo fixture > /mnt/app/carplaymaps/core.so
/bin/ksh /proc/boot/dio-wrapper.sh > /ramdisk/gps-wrapper-off
 grep 'gps=0 preload=/mnt/app/carplaymaps/core.so:' /ramdisk/gps-wrapper-off
echo 1 > /mnt/app/carplay-mu1367-wireless-native-v164t1/gps.enabled
/bin/ksh /proc/boot/dio-wrapper.sh > /ramdisk/gps-wrapper-on
 grep 'gps=164 preload=/mnt/app/carplaymaps/libcpmap-gps-source.so:' /ramdisk/gps-wrapper-on
/bin/ksh /proc/boot/dio-wrapper.sh > /ramdisk/gps-wrapper-restart
 grep 'gps=0 preload=/mnt/app/carplaymaps/core.so:' /ramdisk/gps-wrapper-restart
echo drift > /mnt/app/carplaymaps/libcpmap-gps-source.so
/bin/ksh /proc/boot/dio-wrapper.sh > /ramdisk/gps-wrapper-drift
 grep 'gps=0 preload=/mnt/app/carplaymaps/core.so:' /ramdisk/gps-wrapper-drift
rm -f /mnt/app/carplay-mu1367-wireless-native-v164t1/gps.enabled
# Exercise SD-side remount preflight with real native preference writes;
# mount itself is an explicit stub because /mnt/app is a RAM alias here.
cp /proc/boot/current-tune /mnt/app/carplaymaps/wireless-tune
cp /proc/boot/current-gps-source.so /mnt/app/carplaymaps/libcpmap-gps-source.so
mkdir -p /ramdisk/gps-helper-tools
export TMPDIR=/ramdisk
cat > /ramdisk/gps-helper-tools/mount <<'MOUNT'
#!/bin/ksh
[ "$1" = -uw ] && [ "$2" = /mnt/app ] || exit 82
echo remount >> /ramdisk/gps-mount-check
[ "${GPS_FIXTURE_MOUNT_FAIL:-0}" = 0 ]
MOUNT
chmod 755 /ramdisk/gps-helper-tools/mount
export PATH=/ramdisk/gps-helper-tools:$PATH
if GPS_FIXTURE_MOUNT_FAIL=1 /bin/ksh /proc/boot/gps-preference.sh gps on;then exit 86;fi
test ! -e /mnt/app/carplay-mu1367-wireless-native-v164t1/gps.enabled
/bin/ksh /proc/boot/gps-preference.sh gps on
test -s /mnt/app/carplay-mu1367-wireless-native-v164t1/gps.enabled
BEFORE=$(cat /ramdisk/gps-mount-check)
/bin/ksh /proc/boot/gps-preference.sh gps status
[ "$BEFORE" = "$(cat /ramdisk/gps-mount-check)" ]
/bin/ksh /proc/boot/gps-preference.sh gps off
test ! -e /mnt/app/carplay-mu1367-wireless-native-v164t1/gps.enabled
echo GPS_GEM_REMOUNT_GUARD_PASS status_read_only=1 failed_mount_blocks_write=1 real_native_preferences=1
echo WCP_UNIT_TOOLS_WRAPPERS_PASS
[ "$CONTROL_STATUS" = "$CANDIDATE_STATUS" ] || exit 1
# Comparison is diagnostic: the retained published control also fails this bounded self-test.
echo INPUT_PRELOAD_COMPARISON_ONLY_NOT_A_FUNCTIONAL_PASS
echo WCP_UNIT_TOOLS_PASS
'''
fixture.PASS_MARKER='WCP_UNIT_TOOLS_PASS'
fixture.EVIDENCE=dict(owned_components=pins,receiver_main_executed=False,launcher_exec_stubbed=True,input_preload_comparison_only=True, input_preload_functional_pass=False,bt_wrapper_final_exec_only_stubbed=True,bt_wrapper_sha256=__import__('hashlib').sha256((HERE.parent/'src/runtime/btstack_wrap.sh').read_bytes()).hexdigest())
fixture.EVIDENCE['gps_gem_helper_sha256']=__import__('hashlib').sha256((HERE.parent/'src/runtime/gps-preference.sh').read_bytes()).hexdigest()
fixture.main()
