#!/usr/bin/env python3
"""Compressed-artwork layer: install/refusals/idempotence/snapshot recovery with actual firmware ksh/utilities."""
import argparse,hashlib,json,shutil,subprocess,time
from pathlib import Path
REAL='09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','setup','native-build','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);setup=a.setup.resolve()
 custom=a.package/'sd-card/Custom';payload=custom/'carplay_mu1367_artwork_png';art=custom/'carplay_mu1367_artwork'
 fixture=b'Compressed artwork QNX firmware fixture\n';fixture_sha=hashlib.sha256(fixture).hexdigest()
 audit=json.loads((custom/'carplay_mu1367_guidance_v3/COMMANDS.json').read_text())
 for n in ['startup-virt','libstartup.a','devc-serdebug','u-boot.bin','libc.so.3','libm.so.2','libsocket.so.3','pipe','c4-smoke']:shutil.copy2(setup/n,out/n)
 assert sha(out/'libc.so.3')=='485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc'
 for n,record in audit['commands'].items():
  assert sha(setup/('factory-'+n))==record['sha256'];shutil.copy2(setup/('factory-'+n),out/('factory-'+n))
 for src,name in [(payload/'verify','verify'),(payload/'artwork-fetch','new-fetch'),(art/'artwork-fetch','fetch'),(art/'CarPlayMU1367Audio.jar','audio'),(art/'ipod-drvr-iap2.so','driver'),(payload/'VERSION','VERSION'),(payload/'guard','guard'),(a.native_build/'libz.so.2','factory-zlib')]:shutil.copy2(src,out/name)
 (out/'fixture-jxe').write_bytes(fixture)
 control=(payload/'control.sh').read_text();assert control.count(REAL)==1
 (out/'control').write_text(control.replace(REAL,fixture_sha))
 new,old=sha(payload/'artwork-fetch'),sha(art/'artwork-fetch')
 script='''set -eu
export PATH=/proc/boot LD_LIBRARY_PATH=/proc/boot
export CPMAP_TEST_ROOT=/ramdisk/png-suite
APP=$CPMAP_TEST_ROOT/mnt/app
P=/ramdisk/png-payload
R=$APP/carplay-mu1367-artwork-png
T=$APP/carplay-mu1367-artwork/artwork-fetch
mkdir -p "$P" "$CPMAP_TEST_ROOT/ifs" "$CPMAP_TEST_ROOT/ramdisk" "$CPMAP_TEST_ROOT/proc/boot" "$APP/carplaymaps" "$APP/eso/hmi/lsd/jars" "$APP/armle/lib/dll" "$APP/carplay-mu1367-artwork"
cp /proc/boot/fixture-jxe "$CPMAP_TEST_ROOT/ifs/lsd.jxe"
cp /proc/boot/factory-zlib "$CPMAP_TEST_ROOT/proc/boot/libz.so.2"
cp /proc/boot/control "$P/control.sh"
cp /proc/boot/new-fetch "$P/artwork-fetch"
cp /proc/boot/VERSION "$P/VERSION"
cp /proc/boot/guard "$P/guard"
cp /proc/boot/verify "$P/verify"
chmod 755 "$P/verify"
cp /proc/boot/fetch "$T"
chmod 755 "$T"
cp /proc/boot/audio "$APP/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar"
cp /proc/boot/driver "$APP/armle/lib/dll/ipod-drvr-iap2.so"
echo MU1367/791 > "$APP/carplaymaps/PROFILE"
'''
 for live,source in [('carplay-mu1367','carplay_mu1367'),('carplay-mu1367-settings','carplay_mu1367_settings'),('carplay-mu1367-artwork','carplay_mu1367_artwork')]:
  script+='mkdir -p "$APP/'+live+'"\necho installed > "$APP/'+live+'/STATE"\necho '+(custom/source/'VERSION').read_text().strip()+' > "$APP/'+live+'/VERSION"\n'
 script+='''
# A corrupt payload fails before any snapshot or write.
echo broken > "$P/artwork-fetch"
if /bin/ksh "$P/control.sh" install "$P";then exit 20;fi
test ! -e "$R" || exit 21
cp /proc/boot/new-fetch "$P/artwork-fetch"
# Unknown installed helper is refused.
echo unknown > "$T"
if /bin/ksh "$P/control.sh" install "$P";then exit 22;fi
test ! -e "$R" || exit 23
cp /proc/boot/fetch "$T"
# A different factory zlib or artwork layer is refused.
echo wrong > "$CPMAP_TEST_ROOT/proc/boot/libz.so.2"
if /bin/ksh "$P/control.sh" install "$P";then exit 24;fi
test ! -e "$R" || exit 25
cp /proc/boot/factory-zlib "$CPMAP_TEST_ROOT/proc/boot/libz.so.2"
echo MU1367-artwork-other > "$APP/carplay-mu1367-artwork/VERSION"
if /bin/ksh "$P/control.sh" install "$P";then exit 26;fi
test ! -e "$R" || exit 27
echo @ARTWORK@ > "$APP/carplay-mu1367-artwork/VERSION"
# Shared lock and live CarPlay gates hold before persistent writes.
mkdir "$CPMAP_TEST_ROOT/ramdisk/.carplay-guidance-install-lock"
if /bin/ksh "$P/control.sh" install "$P";then exit 28;fi
rm -rf "$CPMAP_TEST_ROOT/ramdisk/.carplay-guidance-install-lock"
: > "$CPMAP_TEST_ROOT/ramdisk/carplay-altstream.ready"
if /bin/ksh "$P/control.sh" install "$P";then exit 29;fi
rm "$CPMAP_TEST_ROOT/ramdisk/carplay-altstream.ready"
/bin/ksh "$P/control.sh" install "$P" || exit 30
/bin/ksh "$P/control.sh" install "$P" > /ramdisk/png-repeat || exit 31
grep -q MU1367_ARTWORK_PNG_ALREADY_INSTALLED /ramdisk/png-repeat || exit 32
test "$(cat "$R/STATE")" = installed || exit 33
"$P/verify" "$T" @NEW@ || exit 34
test ! -e "$T.artwork-png-new" || exit 35
/bin/ksh "$R/control.sh" status | grep -q installed || exit 36
# A changed helper cannot be silently removed.
echo changed > "$T"
if /bin/ksh "$R/control.sh" uninstall;then exit 37;fi
cp /proc/boot/new-fetch "$T"
# A corrupted snapshot is refused before the helper changes.
echo corrupt > "$R/backup/fetch"
if /bin/ksh "$R/control.sh" recover;then exit 38;fi
"$P/verify" "$T" @NEW@ || exit 39
cp /proc/boot/fetch "$R/backup/fetch"
# Saved recovery without the SD payload.
rm -rf "$P"
/bin/ksh "$R/control.sh" recover || exit 40
test "$(cat "$R/STATE")" = removed || exit 41
"$P/verify" "$T" @OLD@ 2>/dev/null || "$R/verify" "$T" @OLD@ || exit 42
test -x "$T" || exit 43
test ! -e "$CPMAP_TEST_ROOT/ramdisk/.carplay-guidance-install-lock" || exit 44
'''
 script+='''# A retained snapshot cannot be overwritten; archived, a reinstall and normal removal work.
mkdir -p "$P"
cp /proc/boot/control "$P/control.sh"
cp /proc/boot/new-fetch "$P/artwork-fetch"
cp /proc/boot/VERSION "$P/VERSION"
cp /proc/boot/guard "$P/guard"
cp /proc/boot/verify "$P/verify"
chmod 755 "$P/verify"
if /bin/ksh "$P/control.sh" install "$P";then exit 45;fi
mv "$R" "$R.retained"
/bin/ksh "$P/control.sh" install "$P" || exit 46
"$P/verify" "$T" @NEW@ || exit 47
/bin/ksh "$R/control.sh" uninstall || exit 48
"$P/verify" "$T" @OLD@ || exit 49
test -x "$T" || exit 50
"$P/verify" "$APP/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar" @AUDIO@ || exit 51
"$P/verify" "$APP/armle/lib/dll/ipod-drvr-iap2.so" @DRIVER@ || exit 52
echo ARTWORK_PNG_TRANSACTION_QNX_PASS payload_gate=1 runtime_gate=1 zlib_gate=1 parent_gate=1 lock=1 live_feed=1 install=1 repeat=1 changed_runtime=1 corrupt_snapshot=1 saved_recover=1 retained=1 uninstall=1 other_files_untouched=1
'''
 for key,value in [('NEW',new),('OLD',old),('ARTWORK',(art/'VERSION').read_text().strip()),('AUDIO',sha(art/'CarPlayMU1367Audio.jar')),('DRIVER',sha(art/'ipod-drvr-iap2.so'))]:script=script.replace('@'+key+'@',value)
 (out/'test.sh').write_text(script)
 template=(setup/'test.build').read_text();start=template.index(' display_msg "@@OEM-START@@"');end=template.index('\n}',start)
 template=template[:start]+' display_msg "@@PNG-TX-START@@"\n /proc/boot/ksh /proc/boot/test.sh\n display_msg "@@PNG-TX-END@@"'+template[end:]
 template=template[:template.index('\n[type=link] /bin/ksh=')]
 for n in ('rgi-observer','snapshot.bin'):template=template.replace('\n'+n+'\n','\n')
 template+='\n[type=link] /bin/ksh=/proc/boot/ksh\n[type=file]\n[data=copy]\n[perms=+r,+x]\n[+raw]\n'
 template+=''.join(n+'=factory-'+n+'\n' for n in audit['commands'])
 template+='\n'.join(['verify','new-fetch','fetch','audio','driver','control','VERSION','guard','factory-zlib','fixture-jxe','test.sh'])+'\n'
 (out/'test.build').write_text(template)
 shutil.copy2(setup/'prepare.sh',out/'prepare.sh')
 docker=['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-i','-v',str(out)+':/w','-w','/w']
 with (out/'prepare.log').open('w') as log:subprocess.run(docker+['cpmap-qnx65-sdp','sh','/w/prepare.sh'],stdout=log,stderr=subprocess.STDOUT,check=True)
 logpath=out/'qemu.log'
 with logpath.open('wb') as log:
  proc=subprocess.Popen(docker+['cpmap-qemu-arm','timeout','60','qemu-system-arm','-M','virt','-m','256','-cpu','cortex-a15','-bios','/w/u-boot.bin','-drive','file=fat:rw:/w/fat,format=raw,media=disk','-nic','none','-display','none','-serial','stdio'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
  def expect(token,offset=0):
   deadline=time.monotonic()+40
   while time.monotonic()<deadline and proc.poll() is None:
    at=logpath.read_bytes().find(token,offset)
    if at>=0:return at+len(token)
    time.sleep(.1)
   raise RuntimeError('QNX transaction marker missing: '+token.decode())
  def send(b):proc.stdin.write(b);proc.stdin.flush()
  try:
   at=expect(b'Hit any key to stop autoboot:');send(b'\n');at=expect(b'=> ',at)
   for c in (b'virtio scan\n',b'fatload virtio 0:1 0x40200000 ifs.bin\n'):send(c);at=expect(b'=> ',at)
   send(b'go 0x40200000\n');expect(b'@@PNG-TX-END@@',at)
  finally:
   proc.stdin.close();proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
 text=logpath.read_text(errors='replace')
 assert 'ARTWORK_PNG_TRANSACTION_QNX_PASS' in text,text[-3000:]
 for token in ('PAYLOAD_HASH_fetch','UNEXPECTED_BASE_fetch','FACTORY_ZLIB_CHANGED','EXACT_ARTWORK_PARENT_REQUIRED','OPERATION_LOCKED','DISCONNECT_CARPLAY_AND_REBOOT_FIRST','FILE_CHANGED_fetch','RECOVERY_FAILED_KEEP_BACKUPS','RECOVERY_RETAINED_ARCHIVE_BEFORE_REINSTALL'):
  assert 'MU1367_ARTWORK_PNG_FAIL='+token in text,token
 r={'passed':True,'controller_sha256':sha(payload/'control.sh'),'fetch_sha256':new,'replaced_fetch_sha256':old,'actual_qnx_ksh':True,'sdk_utilities_injected':False,'mounts_mocked':True,'fixture_change':'Small-JXE fingerprint only; verifier, helpers, audio JAR, driver and factory zlib are full real files.','tests':14,'qemu_log_sha256':sha(logpath),'on_unit_validated':False}
 (out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
