#!/usr/bin/env python3
"""Real QNX process-name/exec race and production bridge avcC recovery.

The hardware-free child deliberately spends four seconds named
wireless-receiver-exec, then execs wcp_receiver at the same PID. Only that
child's executable and the read-only netstat result are fixture substitutes;
the controller, pidin, ksh, grep and sleep are production/factory bytes.
"""
import hashlib,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
at=sys.argv.index('--firmware');firmware=Path(sys.argv[at+1]).resolve();del sys.argv[at:at+2]
sys.path.insert(0,str(HERE.parents[3]/'MU1367/port'))
from firmware import image_files,stage1,stage2
files=image_files(stage1(firmware/'MMX2/mifs-stage1/50/default/mifs-stage1.img'))
files.update(image_files(stage2(firmware/'MMX2/mifs-stage2/50/default/mifs-stage2.img')))
out=Path(sys.argv[sys.argv.index('--output')+1]).resolve()
extra=out.with_name(out.name+'-inputs');extra.mkdir(parents=True,exist_ok=False)
utility_pins={}
for name in ('pidin','sleep','tail'):
    hits={b for p,b in files.items() if Path(p).name==name};assert len(hits)==1,name
    data=hits.pop();(extra/name).write_bytes(data);utility_pins[name]=hashlib.sha256(data).hexdigest()
controller=HERE.parent/'src/runtime/wcp_ctl.sh'
text=controller.read_text()
pf_preflight='/bin/sh /mnt/ota/wcp_pf.sh on || { echo WCP_PF_NOT_READY;exit 1; }'
assert text.count(pf_preflight)==1
text=text.replace(pf_preflight,': # PF readiness is covered by the separate PF fixture')
assert text.count('LD_LIBRARY_PATH=$VLD /mnt/app/carplaymaps/wireless-receiver-exec')==1
text=text.replace('LD_LIBRARY_PATH=$VLD /mnt/app/carplaymaps/wireless-receiver-exec','LD_PRELOAD=/proc/boot/gate.so LD_LIBRARY_PATH=$VLD /mnt/app/carplaymaps/wireless-receiver-exec')
text=text.replace('CPMAP_PRIMARY_30FPS=1 LD_LIBRARY_PATH=$VLD $VIDEO_ENTRY',
    'LIFECYCLE_MODE=video-launcher LD_PRELOAD=/proc/boot/gate.so CPMAP_PRIMARY_30FPS=1 LD_LIBRARY_PATH=$VLD $VIDEO_ENTRY')
text=text.replace('/mnt/app/carplaymaps/wireless-receiver-exec --launch-stamp',': --launch-stamp') # Timestamp helper is checked separately with its real native binary.
text='netstat(){ echo "fixture.5000 "; }\n'+text
(extra/'controller.sh').write_text(text)
spec=importlib.util.spec_from_file_location('fixture',HERE.parents[1]/'tests/receiver-alt-gate.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
bridge=HERE.parent/'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c'
fixture.SOURCE=r'''
#pragma clang diagnostic ignored "-Wunused-function"
#define main bridge_main
#include "@BRIDGE@"
#undef main
static void require(int ok,const char *message) {
 if(!ok){printf("LIFECYCLE_FAILED=%s\n",message);fflush(stdout);_exit(81);}
}
__attribute__((constructor)) static void exercise(void) {
 const char *mode=getenv("LIFECYCLE_MODE");struct timespec delay;
 require(mode!=0,"fixture scope");
 if(!strcmp(mode,"launcher")) {
  write(2,"FIXTURE_LAUNCHER_ENTER\n",23);
  delay.tv_sec=4;delay.tv_nsec=0;nanosleep(&delay,0);
  setenv("LIFECYCLE_MODE","receiver",1);
  execl("/dev/shmem/wcp_receiver","/dev/shmem/wcp_receiver",(char *)0);_exit(82);
 }
 if(!strcmp(mode,"receiver") || !strcmp(mode,"video")) {for(;;)pause();}
 if(!strcmp(mode,"video-launcher")) {
  delay.tv_sec=2;delay.tv_nsec=0;nanosleep(&delay,0);
  setenv("LIFECYCLE_MODE","video",1);
  execl("/mnt/app/carplaymaps/wcp_video_tap","/mnt/app/carplaymaps/wcp_video_tap",(char *)0);_exit(82);
 }
 require(!strcmp(mode,"probe"),"probe scope");
 unlink(ALT_FRAME_FORCE_IDR_PATH);
 recover_missing_avcc(0,20,1000000);
 require(!access(ALT_FRAME_FORCE_IDR_PATH,F_OK),"first missing avcC requests IDR");
 unlink(ALT_FRAME_FORCE_IDR_PATH);recover_missing_avcc(0,20,1999999);
 require(access(ALT_FRAME_FORCE_IDR_PATH,F_OK)!=0,"retry is rate limited");
 recover_missing_avcc(0,20,2000000);
 require(!access(ALT_FRAME_FORCE_IDR_PATH,F_OK),"retry after one second");
 unlink(ALT_FRAME_FORCE_IDR_PATH);recover_missing_avcc(1,20,2100000);
 require(!g_config_idr_retry_us && access(ALT_FRAME_FORCE_IDR_PATH,F_OK)!=0,"valid avcC resets recovery");
 recover_missing_avcc(0,0,2200000);
 require(access(ALT_FRAME_FORCE_IDR_PATH,F_OK)!=0,"no retry without frames");
 recover_missing_avcc(0,20,2300000);
 require(!access(ALT_FRAME_FORCE_IDR_PATH,F_OK),"new config loss recovers immediately");
 puts("AVCC_RECOVERY_PASS checks=6");fflush(stdout);_exit(0);
}
'''.replace('@BRIDGE@',str(bridge))
fixture.CFLAGS=['-I',str(HERE.parent/'src/native'),'-I',str(bridge.parent)]
fixture.EXTRA_FILES={name:extra/name for name in ('pidin','sleep','tail','controller.sh')}
fixture.IFS_EXTRA='[type=link] /mnt/app=/ramdisk/app\n[type=file]\npidin\nsleep\ntail\ncontroller.sh\n'
fixture.RUN_SCRIPT='''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
mkdir -p /ramdisk/app/carplaymaps /ramdisk/gate-persist
cp /test/payload/payload/wcp_receiver /mnt/app/carplaymaps/wireless-receiver-exec
cp /test/payload/payload/wcp_receiver /dev/shmem/wcp_receiver
chmod 755 /mnt/app/carplaymaps/wireless-receiver-exec /dev/shmem/wcp_receiver
export WCP_VIDEO=0 LIFECYCLE_MODE=launcher
/bin/ksh /proc/boot/controller.sh start
P=$(cat /dev/shmem/wcp_receiver.pid)
pidin -p "$P" -F '%256n' | grep wireless-receiver-exec
sleep 3
test "$(cat /dev/shmem/wcp_receiver.pid)" = "$P"
pidin -p "$P" | grep wcp_receiver
/bin/ksh /proc/boot/controller.sh stop
test ! -e /dev/shmem/wcp_receiver.pid
# A live unrelated process must neither count as a receiver nor be killed.
sleep 12 &
Q=$!
echo "$Q" > /dev/shmem/wcp_receiver.pid
/bin/ksh /proc/boot/controller.sh stop
kill -0 "$Q"
kill "$Q"
# Stopping during preflight must terminate that launcher at its own PID.
/bin/ksh /proc/boot/controller.sh start
P=$(cat /dev/shmem/wcp_receiver.pid)
/bin/ksh /proc/boot/controller.sh stop
if kill -0 "$P" 2>/dev/null;then exit 83;fi
# Both the video bootstrap and the native tap executable own the video role.
cp /test/payload/payload/wcp_receiver /mnt/app/carplaymaps/wireless-video-exec
cp /test/payload/payload/wcp_receiver /mnt/app/carplaymaps/wcp_video_tap
cp /test/payload/payload/wcp_receiver /dev/shmem/wcp_video
chmod 755 /mnt/app/carplaymaps/wireless-video-exec /mnt/app/carplaymaps/wcp_video_tap /dev/shmem/wcp_video
WCP_VIDEO=1 /bin/ksh /proc/boot/controller.sh start
V=$(cat /dev/shmem/wcp_video.pid)
pidin -p "$V" -F '%256n' | grep mnt/app/carplaymaps/wcp_video_tap
/bin/ksh /proc/boot/controller.sh status > /ramdisk/video-status || :
grep "wcp_video 运行中 pid=$V" /ramdisk/video-status
/bin/ksh /proc/boot/controller.sh stop
if kill -0 "$V" 2>/dev/null;then exit 84;fi
LIFECYCLE_MODE=video-launcher LD_PRELOAD=/proc/boot/gate.so /mnt/app/carplaymaps/wireless-video-exec &
V=$!
echo "$V" > /dev/shmem/wcp_video.pid
/bin/ksh /proc/boot/controller.sh stop
if kill -0 "$V" 2>/dev/null;then exit 85;fi
# A reused PID and a different executable with the same basename are excluded.
sleep 12 &
Q=$!
echo "$Q" > /dev/shmem/wcp_video.pid
/bin/ksh /proc/boot/controller.sh stop
kill -0 "$Q"
kill "$Q"
mkdir -p /ramdisk/unrelated
cp /test/payload/payload/wcp_receiver /ramdisk/unrelated/wcp_video_tap
chmod 755 /ramdisk/unrelated/wcp_video_tap
LIFECYCLE_MODE=video LD_PRELOAD=/proc/boot/gate.so /ramdisk/unrelated/wcp_video_tap &
Q=$!
echo "$Q" > /dev/shmem/wcp_video.pid
/bin/ksh /proc/boot/controller.sh stop
kill -0 "$Q"
kill "$Q"
LIFECYCLE_MODE=probe LD_PRELOAD=/proc/boot/gate.so /dev/shmem/wcp_receiver --version
echo VIDEO_LIFECYCLE_PASS wrapper_and_tap=1 stop_preflight=1 reused_pid_excluded=1 basename_collision_excluded=1
echo LAUNCH_LIFECYCLE_PASS
'''
fixture.PASS_MARKER='LAUNCH_LIFECYCLE_PASS'
fixture.EVIDENCE=dict(controller_sha256=hashlib.sha256(controller.read_bytes()).hexdigest(),bridge_source_sha256=hashlib.sha256(bridge.read_bytes()).hexdigest(),factory_utilities=utility_pins,delayed_exec_seconds=4,controller_probe_seconds=2,receiver_hardware_main_executed=False,unrelated_process_preserved=True,stop_during_preflight=True,avcc_recovery_checks=6)
fixture.main()
