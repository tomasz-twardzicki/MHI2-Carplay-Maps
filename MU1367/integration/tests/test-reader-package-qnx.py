#!/usr/bin/env python3
"""Reader install/guard/rollback under actual MU1367 ksh and firmware utilities."""
import argparse,hashlib,json,shutil,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','setup','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);setup=a.setup.resolve()
 custom=a.package/'sd-card/Custom';payload=custom/'carplay_mu1367_reader_recovery';main=custom/'carplay_mu1367_guidance_v3'
 audit=json.loads((main/'COMMANDS.json').read_text())
 for n in ('startup-virt','libstartup.a','devc-serdebug','u-boot.bin','libc.so.3','libm.so.2','libsocket.so.3','pipe','c4-smoke'):shutil.copy2(setup/n,out/n)
 assert sha(out/'libc.so.3')=='485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc'
 # Both dependencies were checked against exact K4525 stage1 firmware, too.
 assert sha(out/'libsocket.so.3')=='36a062617f078d20d8cf53fb879667bd41d49b5d6b8ffb69375f4ca44eeff2d4'
 assert sha(out/'libm.so.2')=='715ba06e022f7f9f2d9e2cf6b94a03bf619e034f41f8d832601507cc5073cd83'
 for n,r in audit['commands'].items():
  assert sha(setup/('factory-'+n))==r['sha256'];shutil.copy2(setup/('factory-'+n),out/('factory-'+n))
 for src,name in [(payload/'verify','verify'),(payload/'rgi-observer','new-reader'),(custom/'carplay_mu1367/rgi-observer','old-reader'),(main/'6/CarPlayMU1367Guidance.jar','guidance'),(main/'6/control.sh','parent-control'),(main/'6/VERSION','parent-version'),(payload/'VERSION','VERSION'),(payload/'guard','guard')]:shutil.copy2(src,out/name)
 fixture=b'Reader recovery QNX firmware fixture\n';fixture_sha=hashlib.sha256(fixture).hexdigest();(out/'fixture-jxe').write_bytes(fixture)
 (out/'control').write_text((payload/'control.sh').read_text().replace('09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a',fixture_sha))
 script='''set -eu
export PATH=/proc/boot LD_LIBRARY_PATH=/proc/boot
export CPMAP_TEST_ROOT=/ramdisk/reader-suite
APP=$CPMAP_TEST_ROOT/mnt/app
P=/ramdisk/reader-payload
R=$APP/carplay-mu1367-reader-recovery
J=$APP/carplay-mu1367/rgi-observer
C=$APP/carplay-mu1367-guidance-v3/control.sh
mkdir -p "$P" "$CPMAP_TEST_ROOT/ifs" "$CPMAP_TEST_ROOT/ramdisk" "$APP/carplaymaps" "$APP/eso/hmi/lsd/jars" "$APP/carplay-mu1367" "$APP/carplay-mu1367-guidance-v3"
cp /proc/boot/fixture-jxe "$CPMAP_TEST_ROOT/ifs/lsd.jxe"
cp /proc/boot/control "$P/control.sh"
cp /proc/boot/new-reader "$P/rgi-observer"
cp /proc/boot/VERSION "$P/VERSION"
cp /proc/boot/guard "$P/guard"
cp /proc/boot/verify "$P/verify"
chmod 755 "$P/verify"
cp /proc/boot/old-reader "$J"
cp /proc/boot/parent-control "$C"
cp /proc/boot/parent-version "$APP/carplay-mu1367-guidance-v3/VERSION"
echo installed > "$APP/carplay-mu1367-guidance-v3/STATE"
cp /proc/boot/guidance "$APP/eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar"
echo MU1367/791 > "$APP/carplaymaps/PROFILE"
'''
 for live,source in [('carplay-mu1367','carplay_mu1367'),('carplay-mu1367-settings','carplay_mu1367_settings')]:script+='mkdir -p "$APP/'+live+'"\necho installed > "$APP/'+live+'/STATE"\necho '+(custom/source/'VERSION').read_text().strip()+' > "$APP/'+live+'/VERSION"\n'
 script+='''
echo broken > "$P/rgi-observer"
if /bin/ksh "$P/control.sh" install "$P";then exit 20;fi
test ! -e "$R" || exit 21
cp /proc/boot/new-reader "$P/rgi-observer"
echo unknown > "$J"
if /bin/ksh "$P/control.sh" install "$P";then exit 22;fi
test ! -e "$R" || exit 23
cp /proc/boot/old-reader "$J"
echo unknown > "$C"
if /bin/ksh "$P/control.sh" install "$P";then exit 24;fi
test ! -e "$R" || exit 25
cp /proc/boot/parent-control "$C"
mkdir "$CPMAP_TEST_ROOT/ramdisk/.carplay-guidance-install-lock"
if /bin/ksh "$P/control.sh" install "$P";then exit 26;fi
rm -rf "$CPMAP_TEST_ROOT/ramdisk/.carplay-guidance-install-lock"
: > "$CPMAP_TEST_ROOT/ramdisk/carplay-altstream.ready"
if /bin/ksh "$P/control.sh" install "$P";then exit 27;fi
rm "$CPMAP_TEST_ROOT/ramdisk/carplay-altstream.ready"
/bin/ksh "$P/control.sh" install "$P" || exit 28
/bin/ksh "$P/control.sh" install "$P" || exit 29
test "$(cat "$R/STATE")" = installed || exit 30
cp "$C" /ramdisk/guarded-parent
if /bin/ksh "$C" uninstall;then exit 31;fi
'''
 script+='"$P/verify" "$J" '+sha(payload/'rgi-observer')+' || exit 32\n'
 script+='''
echo changed > "$J"
if /bin/ksh "$R/control.sh" uninstall;then exit 33;fi
cp /proc/boot/new-reader "$J"
echo changed > "$C"
if /bin/ksh "$R/control.sh" uninstall;then exit 34;fi
cp /ramdisk/guarded-parent "$C"
echo corrupt > "$R/backup/parent"
if /bin/ksh "$R/control.sh" recover;then exit 35;fi
'''
 script+='"$P/verify" "$J" '+sha(payload/'rgi-observer')+' || exit 36\n'
 script+='''cp /proc/boot/parent-control "$R/backup/parent"
# Recovery accepts an interrupted/partially committed transaction.
echo prepared > "$R/STATE"
echo partial > "$J.reader-new"
/bin/ksh "$R/control.sh" recover || exit 37
test "$(cat "$R/STATE")" = removed || exit 38
test ! -e "$J.reader-new" || exit 39
'''
 for target,src in [('$J',custom/'carplay_mu1367/rgi-observer'),('$C',main/'6/control.sh')]:script+='"$P/verify" "'+target+'" '+sha(src)+' || exit 40\n'
 script+='''
if /bin/ksh "$P/control.sh" install "$P";then exit 41;fi
mv "$R" "$R.retained"
# Inject a single failure at the second commit; all copies and renames
# otherwise execute the actual firmware utilities.
mkdir -p /ramdisk/fault-tools
cp /proc/boot/fail-mv /ramdisk/fault-tools/mv
chmod 755 /ramdisk/fault-tools/mv
export READER_FAIL_TARGET=$C
: > /ramdisk/fail-once
export PATH=/ramdisk/fault-tools:/proc/boot
if /bin/ksh "$P/control.sh" install "$P";then exit 42;fi
export PATH=/proc/boot
test "$(cat "$R/STATE")" = removed || exit 43
'''
 for target,src in [('$J',custom/'carplay_mu1367/rgi-observer'),('$C',main/'6/control.sh')]:script+='"$P/verify" "'+target+'" '+sha(src)+' || exit 44\n'
 script+='''
test ! -e "$CPMAP_TEST_ROOT/ramdisk/.carplay-guidance-install-lock" || exit 45
mv "$R" "$R.rollback-retained"
/bin/ksh "$P/control.sh" install "$P" || exit 46
mv "$P" "$P.offline"
/bin/ksh "$R/control.sh" uninstall || exit 47
'''
 for target,src in [('$J',custom/'carplay_mu1367/rgi-observer'),('$C',main/'6/control.sh')]:script+='"$R/verify" "'+target+'" '+sha(src)+' || exit 48\n'
 script+='''test -f "$R.retained/backup/reader" || exit 49
test -f "$R.rollback-retained/backup/parent" || exit 50
echo READER_TRANSACTION_QNX_PASS payload_gate=1 runtime_gate=1 parent_gate=1 lock=1 live_feed=1 install=1 repeat=1 parent_guard=1 changed_runtime=1 changed_guard=1 corrupt_snapshot=1 interrupted_recover=1 retained=1 rollback=1 saved_uninstall=1
'''
 (out/'test.sh').write_text(script)
 (out/'fail-mv').write_text('''#!/bin/ksh
if [ "${2:-}" = "$READER_FAIL_TARGET" ] && [ -f /ramdisk/fail-once ];then /proc/boot/rm /ramdisk/fail-once;exit 1;fi
exec /proc/boot/mv "$@"
''')
 template=(setup/'test.build').read_text();start=template.index(' display_msg "@@');end=template.index('\n}',start)
 template=template[:start]+' display_msg "@@READER-TX-START@@"\n /proc/boot/ksh /proc/boot/test.sh\n display_msg "@@READER-TX-END@@"'+template[end:]
 template=template[:template.index('\n[type=link] /bin/ksh=')]
 for n in ('rgi-observer','snapshot.bin'):template=template.replace('\n'+n+'\n','\n')
 template+='\n[type=link] /bin/ksh=/proc/boot/ksh\n[type=file]\n[data=copy]\n[perms=+r,+x]\n[+raw]\n'
 template+=''.join(n+'=factory-'+n+'\n' for n in audit['commands'])
 template+='\n'.join(['libsocket.so.3','verify','old-reader','new-reader','guidance','parent-control','parent-version','control','VERSION','guard','fixture-jxe','test.sh','fail-mv'])+'\n'
 (out/'test.build').write_text(template);shutil.copy2(setup/'prepare.sh',out/'prepare.sh')
 docker=['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-i','-v',str(out)+':/w','-w','/w']
 with (out/'prepare.log').open('w') as log:subprocess.run(docker+['cpmap-qnx65-sdp','sh','/w/prepare.sh'],stdout=log,stderr=subprocess.STDOUT,check=True)
 logpath=out/'qemu.log'
 with logpath.open('wb') as log:
  proc=subprocess.Popen(docker+['cpmap-qemu-arm','timeout','60','qemu-system-arm','-M','virt','-m','256','-cpu','cortex-a15','-bios','/w/u-boot.bin','-drive','file=fat:rw:/w/fat,format=raw,media=disk','-nic','none','-display','none','-serial','stdio'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
  def expect(token,offset=0):
   end=time.monotonic()+40
   while time.monotonic()<end and proc.poll() is None:
    pos=logpath.read_bytes().find(token,offset)
    if pos>=0:return pos+len(token)
    time.sleep(.1)
   raise RuntimeError('QNX marker missing: '+token.decode())
  def send(b):proc.stdin.write(b);proc.stdin.flush()
  try:
   at=expect(b'Hit any key to stop autoboot:');send(b'\n');at=expect(b'=> ',at)
   for c in (b'virtio scan\n',b'fatload virtio 0:1 0x40200000 ifs.bin\n'):send(c);at=expect(b'=> ',at)
   send(b'go 0x40200000\n');expect(b'@@READER-TX-END@@',at)
  finally:
   proc.stdin.close();proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
 log=logpath.read_text(errors='replace');assert 'READER_TRANSACTION_QNX_PASS' in log,log[-7000:]
 assert 'MU1367_READER_REMOVE_TEST_FIRST' in log and 'MU1367_READER_FAIL=COMMIT_FILE' in log
 r={'passed':True,'controller_sha256':sha(payload/'control.sh'),'reader_sha256':sha(payload/'rgi-observer'),'actual_qnx_ksh':True,'sdk_utilities_injected':False,'mounts_mocked':True,'fixture_change':'Small-JXE fingerprint only; real reader/JAR/controllers/verifier and firmware utilities. One injected second-commit rename failure.','tests':15,'qemu_log_sha256':sha(logpath),'test_sha256':sha(Path(__file__)),'on_unit_validated':False}
 (out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
