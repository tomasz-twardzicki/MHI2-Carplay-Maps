#!/usr/bin/env python3
"""Reproduce PID archive collisions and check the patched factory-QNX helpers."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from archive_fix import TARGETS,apply


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('build','setup','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    shutil.copytree(a.setup,out,ignore=shutil.ignore_patterns('fat','qemu.log','result.json','ifs.bin'))
    sd=out/'patched-sd';shutil.copytree(a.build/'sd-card',sd)
    changes=apply(sd)
    (out/'PATCH.json').write_text(json.dumps(changes,indent=2)+'\n')
    script='''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
parents(){
 D=${1%/*}
 while [ -n "$D" ] && [ "$D" != / ];do
  [ -d "$D" ] && [ ! -L "$D" ] || return 1
  D=${D%/*}
 done
}
fail(){ echo "ARCHIVE_EXPECTED_OR_UNEXPECTED_FAIL=$1";exit 1; }
# Mounting the isolated fixture is already done by the boot harness.
mount(){ return 0; }
native(){ "$@"; }
cleanup(){ rm -rf "$LOCK"; }
P=/proc/boot
for SCRIPT in /proc/boot/patched-script-*;do /bin/ksh -n "$SCRIPT";done
'''
    extras=[]
    for i,(name,root) in enumerate(TARGETS.items()):
        before=(a.build/'sd-card'/name).read_text();after=(sd/name).read_text()
        (out/('patched-script-%d'%i)).write_text(after);extras.append('patched-script-%d'%i)
        if root=='R':
            def helper(text):
                at=text.index('retain_removed(){');end=text.index('\n}\n',at)+3
                return text[at:end]
            old=helper(before).replace('retain_removed(){','old_retain(){',1)
            new=helper(after)
            call='retain_removed "$R"'
            script+=old+new
        else:
            def helper(text):
                at=text.index('if [ -d "$ROOT" ];then\n # A removed session')
                end=text.index('\nfi\n',at)+4
                return text[at:end]
            script+='old_retain(){\n'+helper(before)+'\n}\nretain_removed(){\n'+helper(after)+'\n}\n'
            call='retain_removed'
        script+='''
BASE=/ramdisk/archive-%d
mkdir -p "$BASE"
R=$BASE/carplay-mu1367-layer
ROOT=$R
LOCK=$BASE/lock
OWN=no
VERIFY=/proc/boot/verify
mkdir -p "$R/backup"
echo removed > "$R/STATE"
echo old-test-version > "$R/VERSION"
: > "$R/BACKUPS_READY"
for K in core guidance menu parent reader bridge;do
 echo "original-$K" > "$R/backup/$K"
 /proc/boot/verify "$R/backup/$K" > "$R/backup/$K.sha256"
done
N0=$$
N1=$((N0+1))
N2=$((N0+2))
N3=$((N0+3))
mkdir "$R.removed-$N0"
echo retained-original > "$R.removed-$N0/sentinel"
# A dangling symlink also occupies an archive name; never follow/replace it.
ln -s /ramdisk/not-an-archive "$R.removed-$N1"
if ( old_retain "$R" );then echo OLD_GUARD_DID_NOT_REPRODUCE;exit 80;fi
test -d "$R"
test ! -e "$LOCK"
echo ARCHIVE_ORIGINAL_COLLISION_REPRODUCED=%d
%s
test "$BACK" = "$R.removed-$N2"
test ! -e "$R"
test -f "$BACK/backup/core"
grep '^retained-original$' "$R.removed-$N0/sentinel"
test -L "$R.removed-$N1"
test ! -e "$LOCK"
cp -R "$BACK" "$R"
%s
test "$BACK" = "$R.removed-$N3"
test -f "$R.removed-$N2/backup/core"
test -f "$R.removed-$N3/backup/core"
grep '^retained-original$' "$R.removed-$N0/sentinel"
test -L "$R.removed-$N1"
test ! -e "$LOCK"
echo ARCHIVE_COLLISION_FIXED=%d
'''%(i,i,call,call,i)
        if root=='R':
            script+='''cp -R "$BACK" "$R"
echo damaged >> "$R/backup/core"
if ( retain_removed "$R" );then echo DAMAGED_SNAPSHOT_ACCEPTED;exit 81;fi
test -f "$R/backup/core"
test ! -e "$LOCK"
echo ARCHIVE_DAMAGED_SNAPSHOT_REJECTED
'''
    script+='echo ARCHIVE_QNX_PASS scripts=3 collisions_per_script=2 damaged_snapshot_cases=2\n'
    (out/'archive-test.sh').write_text(script)
    template=(out/'test.build').read_text().replace('/bin/ksh /proc/boot/suite.sh','/bin/ksh /proc/boot/archive-test.sh')
    (out/'test.build').write_text(template+'archive-test.sh\n'+'\n'.join(extras)+'\n')
    docker=['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-i','-v',str(out)+':/w','-w','/w']
    with (out/'prepare.log').open('w') as f:subprocess.run(docker+['cpmap-qnx65-sdp','sh','/w/prepare.sh'],stdout=f,stderr=subprocess.STDOUT,check=True)
    with (out/'qemu.log').open('wb') as f:
        proc=subprocess.Popen(docker+['cpmap-qemu-arm','timeout','120','qemu-system-arm','-M','virt','-m','1024','-cpu','cortex-a15','-bios','/w/u-boot.bin','-drive','file=fat:rw:/w/fat,format=raw,media=disk','-nic','none','-display','none','-serial','stdio'],stdin=subprocess.PIPE,stdout=f,stderr=subprocess.STDOUT)
        def expect(token,offset=0):
            deadline=time.monotonic()+100
            while time.monotonic()<deadline and proc.poll() is None:
                at=(out/'qemu.log').read_bytes().find(token,offset)
                if at>=0:return at+len(token)
                time.sleep(.1)
            raise RuntimeError('Missing marker '+repr(token))
        def send(b):proc.stdin.write(b);proc.stdin.flush()
        try:
            at=expect(b'Hit any key to stop autoboot:');send(b'\n');at=expect(b'=> ',at)
            for cmd in (b'virtio scan\n',b'fatload virtio 0:1 0x40200000 ifs.bin\n'):
                send(cmd);at=expect(b'=> ',at)
            send(b'go 0x40200000\n');expect(b'@@HARNESS-FINISHED@@',at)
        finally:
            proc.stdin.close();proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    log=(out/'qemu.log').read_bytes()
    passed=b'ARCHIVE_QNX_PASS scripts=3' in log
    result=dict(passed=passed,changes=changes,firmware_utilities=True,scope='Actual retained-session helpers under factory QNX shell/utilities; isolated fixture remount stub; old collision reproduced, existing directories/symlinks preserved, repeat naming and snapshot validation checked. Full base migration not rerun.',log_sha256=hashlib.sha256(log).hexdigest())
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    assert passed,'Inspect qemu.log'


if __name__=='__main__':main()
