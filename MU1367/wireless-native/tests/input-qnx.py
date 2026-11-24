#!/usr/bin/env python3
"""Run the independent input self-test on a fresh transaction-fixture boot."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--transactions',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    source=a.transactions.resolve();out=a.output.resolve()
    prior=json.loads((source/'result.json').read_text())
    log=(source/'qemu.log').read_bytes()
    assert prior['rollback_cases']==prior['resume_cases']==prior['commit_sites']==35
    assert b'WIRELESS_TRANSACTIONS_PASS' in log and b'WIRELESS_SESSION_PASS checks=17' in log
    shutil.copytree(source,out,ignore=shutil.ignore_patterns('fat','qemu.log','result.json','ifs.bin'))
    # SDK boot helper only: its 16 MiB disk cannot hold the 16 MiB + 1808 ring.
    helper=out/'c4-smoke';data=helper.read_bytes()
    assert data.count(b'capacity=32768,nodinit')==1
    helper.write_bytes(data.replace(b'capacity=32768,nodinit',b'capacity=65536,nodinit'))
    script='''#!/bin/ksh
set -u
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
/proc/boot/wireless-entry --selftest /ramdisk/input-test /proc/boot/input.h264
RC=$?
echo INPUT_SELFTEST_RC=$RC
ls -l /ramdisk/input-test
exit "$RC"
'''
    (out/'input-only.sh').write_text(script)
    template=(out/'test.build').read_text().replace('/bin/ksh /proc/boot/suite.sh','/bin/ksh /proc/boot/input-only.sh')
    (out/'test.build').write_text(template+'input-only.sh\n')
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
    text=(out/'qemu.log').read_bytes()
    passed=b'OMONOB_791_ENTRY_SELFTEST_PASS' in text and b'INPUT_SELFTEST_RC=0' in text
    result=dict(passed=passed,build_id=prior['build_id'],fresh_boot=True,transaction_log_sha256=hashlib.sha256(log).hexdigest(),input_log_sha256=hashlib.sha256(text).hexdigest(),h264_fixture_sha256=prior['h264_fixture_sha256'],fixture_correction='Initially absent owned directory; SDK boot-helper RAM disk enlarged from 16 to 32 MiB to hold the unchanged 16 MiB + 1808 byte ring. Production binaries and factory utilities unchanged.')
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    assert passed,'Input self-test failed; inspect isolated qemu.log'
    combined=dict(prior,passed=True,wireless_input_selftest=True,input_test_separate_boot=True,input_test=result,first_combined_run_input_selftest=False)
    (out/'combined-result.json').write_text(json.dumps(combined,indent=2)+'\n')


if __name__=='__main__':main()
