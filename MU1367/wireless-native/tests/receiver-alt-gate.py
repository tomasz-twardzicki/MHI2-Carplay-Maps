#!/usr/bin/env python3
"""Execute the pinned receiver's actual display gate in an isolated QNX VM.

A test-only preload calls the audited ARM function before receiver main, then
exits. No socket, MFi or MOST success is simulated. The receiver is unmodified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

SOURCE=r'''
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
static void put(const char *path) {
    FILE *f=fopen(path,"w");
    if(!f) { perror(path); _exit(81); }
    fputs("fixture\n",f);
    if(fclose(f)) _exit(82);
}
static void check(const char *name,int expected) {
    int actual=((int (*)(void))0xe4330)();
    printf("RECEIVER_ALT_GATE name=%s expected=%d actual=%d\n",name,expected,actual);
    if(actual!=expected) { fflush(stdout); _exit(83); }
}
__attribute__((constructor)) static void test(void) {
    if(!getenv("MU1367_GATE_ONLY")) _exit(84);
    unlink("/dev/shmem/wcp_alt_probe");
    unlink("/mnt/persist/wcp_alt_probe");
    unlink("/mnt/persist/altscreen.conf");
    unlink("/mnt/persist/wcp_alt_off");
    check("no_config_or_probe",0);
    /* Dimensions alone are deliberately not one of the gate's file checks. */
    setenv("WCP_ALT_W","800",1); setenv("WCP_ALT_H","480",1);
    setenv("WCP_ALT_FEED_PORT","9997",1);
    check("dimensions_and_feed_only",0);
    put("/mnt/persist/altscreen.conf");
    check("config_exists",1);
    put("/mnt/persist/wcp_alt_off");
    check("config_with_off",0);
    put("/dev/shmem/wcp_alt_probe");
    check("ram_probe_overrides_off",1);
    unlink("/dev/shmem/wcp_alt_probe");
    put("/mnt/persist/wcp_alt_probe");
    check("persistent_probe_overrides_off",1);
    unlink("/mnt/persist/wcp_alt_probe");
    unlink("/mnt/persist/wcp_alt_off");
    unlink("/mnt/persist/altscreen.conf");
    put("/dev/shmem/wcp_alt_probe");
    check("ram_probe_without_config",1);
    unlink("/dev/shmem/wcp_alt_probe");
    check("probe_removed",0);
    puts("RECEIVER_ALT_GATE_PASS checks=8 hardware_opened=0");
    fflush(stdout); _exit(0);
}
'''
PASS_MARKER='RECEIVER_ALT_GATE_PASS checks=8'
EVIDENCE=dict(gate_virtual_address='0xe4330',checks=8,actual_receiver_code_executed=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('setup','toolchain','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    shutil.copytree(a.setup,out,ignore=shutil.ignore_patterns('fat','qemu.log','result.json','ifs.bin'))
    for name,path in globals().get("EXTRA_FILES",{}).items():shutil.copy2(path,out/name)
    if globals().get("RAM_SECTORS"):
        helper=out/'c4-smoke';data=helper.read_bytes();assert data.count(b'capacity=32768,nodinit')==1
        helper.write_bytes(data.replace(b'capacity=32768,nodinit',('capacity=%d,nodinit'%RAM_SECTORS).encode()))
    receiver=out/'payload/payload/wcp_receiver'
    expected='f195665b0e9fb8a592618e64b7201ddfc536a9b082c6dd35db214b99d5e01de1'
    assert hashlib.sha256(receiver.read_bytes()).hexdigest()==expected
    (out/'gate.c').write_text(SOURCE)
    qnx=a.toolchain.resolve()/'sdp/target/qnx6'
    subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/clang','--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','--sysroot='+str(qnx),'-isystem',str(qnx/'usr/include'),'-march=armv7-a','-mfloat-abi=softfp','-mfpu=vfpv3-d16','-mno-unaligned-access','-fno-short-enums','-fno-builtin','-fno-stack-protector','-fPIC','-O2','-Wall','-Wextra','-Werror',*globals().get('CFLAGS',[]),'-c',str(out/'gate.c'),'-o',str(out/'gate.o')],check=True)
    script='''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
mkdir -p /ramdisk/gate-persist
MU1367_GATE_ONLY=1 LD_PRELOAD=/test/payload/payload/libomonob-wireless-maps.so:/proc/boot/gate.so /test/payload/payload/wcp_receiver --version
'''
    script=globals().get('RUN_SCRIPT',script)
    (out/'gate.sh').write_text(script)
    template=(out/'test.build').read_text().replace('/bin/ksh /proc/boot/suite.sh','/bin/ksh /proc/boot/gate.sh')
    template+='gate.sh\ngate.so\n[type=link] /mnt/persist=/ramdisk/gate-persist\n'
    template+=globals().get('IFS_EXTRA','')
    (out/'test.build').write_text(template)
    lib='/opt/qnx650/target/qnx6/armle-v7/lib'
    (out/'prepare.sh').write_text('''#!/bin/sh
set -eu
arm-unknown-nto-qnx6.5.0eabi-ld -m armnto -shared -L{0} /w/gate.o -lc -o /w/gate.so
export MKIFS_PATH=/w:{0}/../boot/sys:{0}/../bin:{0}/../sbin:{0}:{0}/dll:{0}/../usr/lib
mkifs test.build ifs.bin
mkdir -p fat
mv ifs.bin fat/
'''.format(lib))
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
            for command in (b'virtio scan\n',b'fatload virtio 0:1 0x40200000 ifs.bin\n'):
                send(command);at=expect(b'=> ',at)
            send(b'go 0x40200000\n');expect(b'@@HARNESS-FINISHED@@',at)
        finally:
            proc.stdin.close();proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    log=(out/'qemu.log').read_bytes()
    result=dict(passed=PASS_MARKER.encode() in log,receiver_sha256=expected,hardware_opened=False,log_sha256=hashlib.sha256(log).hexdigest(),**EVIDENCE)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    assert result['passed'],'Inspect qemu.log'


if __name__=='__main__':main()
