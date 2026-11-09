#!/usr/bin/env python3
"""Audio-only install/idempotence/snapshot recovery with actual firmware ksh/utilities."""
import argparse,hashlib,json,shutil,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','setup','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--r1-package',type=Path)
 p.add_argument('--r2-package',type=Path)
 p.add_argument('--native-build',type=Path)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);setup=a.setup.resolve()
 custom=a.package/'sd-card/Custom';m=json.loads((a.package/'manifest.json').read_text());payload=custom/m.get('custom_layer','carplay_mu1367_audio_progress');art=custom/'carplay_mu1367_artwork';r2=m.get('revision')=='r2';r3=m.get('revision')=='artwork-r3'
 fixture=b'Audio progress QNX firmware fixture\n';fixture_sha=hashlib.sha256(fixture).hexdigest()
 audit=json.loads((custom/'carplay_mu1367_guidance_v3/COMMANDS.json').read_text())
 names=['startup-virt','libstartup.a','devc-serdebug','u-boot.bin','libc.so.3','libm.so.2','libsocket.so.3','pipe','c4-smoke']
 for n in names:shutil.copy2(setup/n,out/n)
 assert sha(out/'libc.so.3')=='485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc'
 for n,record in audit['commands'].items():
  assert sha(setup/('factory-'+n))==record['sha256'];shutil.copy2(setup/('factory-'+n),out/('factory-'+n))
 for src,name in [(payload/'verify','verify'),(payload/'CarPlayMU1367Audio.jar','new-audio'),(art/'CarPlayMU1367Audio.jar','old-audio'),(art/'ipod-drvr-iap2.so','driver'),(art/'artwork-fetch','fetch'),(payload/'VERSION','VERSION'),(payload/'guard','guard')]:shutil.copy2(src,out/name)
 if r2 or r3:
  assert a.r1_package is not None,'R1 package is required for upgrade tests'
  r1=a.r1_package/'sd-card/Custom/carplay_mu1367_audio_progress'
  assert sha(r1/'control.sh')=='50bb99d638223022d04fb9b8c133328be22d7f583ff108a9f37b5b43d75ca201'
  for src,name in [(r1/'control.sh','r1-control'),(r1/'CarPlayMU1367Audio.jar','r1-audio'),(r1/'VERSION','r1-version')]:shutil.copy2(src,out/name)
  r1_control=(out/'r1-control').read_text().replace('09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a',fixture_sha);(out/'r1-control').write_text(r1_control)
 if r3:
  assert a.r2_package is not None and a.native_build is not None
  r2root=a.r2_package/'sd-card/Custom/carplay_mu1367_audio_progress_r2'
  assert sha(r2root/'control.sh')=='615474000d3e92705f59e989bec9e11eef7a220354073cf4710267bf5af7efe6'
  for src,name in [(r2root/'control.sh','r2-control'),(r2root/'CarPlayMU1367Audio.jar','r2-audio'),(r2root/'VERSION','r2-version'),(payload/'artwork-fetch','new-fetch'),(a.native_build/'libz.so.2','factory-zlib')]:shutil.copy2(src,out/name)
  code=(out/'r2-control').read_text().replace('09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a',fixture_sha)
  (out/'r2-control').write_text(code)
 (out/'fixture-jxe').write_bytes(fixture)
 control=(payload/'control.sh').read_text().replace('09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a',fixture_sha)
 if r2:control=control.replace('50bb99d638223022d04fb9b8c133328be22d7f583ff108a9f37b5b43d75ca201',sha(out/'r1-control'))
 if r3:control=control.replace('615474000d3e92705f59e989bec9e11eef7a220354073cf4710267bf5af7efe6',sha(out/'r2-control'))
 (out/'control').write_text(control)
 script='''set -eu
export PATH=/proc/boot LD_LIBRARY_PATH=/proc/boot
export CPMAP_TEST_ROOT=/ramdisk/audio-suite
APP=$CPMAP_TEST_ROOT/mnt/app
P=/ramdisk/audio-payload
R=$APP/carplay-mu1367-audio-progress
J=$APP/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar
mkdir -p "$P" "$CPMAP_TEST_ROOT/ifs" "$CPMAP_TEST_ROOT/ramdisk" "$APP/carplaymaps" "$APP/eso/hmi/lsd/jars" "$APP/armle/lib/dll" "$APP/carplay-mu1367-artwork"
cp /proc/boot/fixture-jxe "$CPMAP_TEST_ROOT/ifs/lsd.jxe"
cp /proc/boot/control "$P/control.sh"
cp /proc/boot/new-audio "$P/CarPlayMU1367Audio.jar"
cp /proc/boot/VERSION "$P/VERSION"
cp /proc/boot/guard "$P/guard"
cp /proc/boot/verify "$P/verify"
chmod 755 "$P/verify"
cp /proc/boot/old-audio "$J"
cp /proc/boot/driver "$APP/armle/lib/dll/ipod-drvr-iap2.so"
cp /proc/boot/fetch "$APP/carplay-mu1367-artwork/artwork-fetch"
echo MU1367/791 > "$APP/carplaymaps/PROFILE"
'''
 for live,source in [('carplay-mu1367','carplay_mu1367'),('carplay-mu1367-settings','carplay_mu1367_settings'),('carplay-mu1367-artwork','carplay_mu1367_artwork')]:
  script+='mkdir -p "$APP/'+live+'"\necho installed > "$APP/'+live+'/STATE"\necho '+(custom/source/'VERSION').read_text().strip()+' > "$APP/'+live+'/VERSION"\n'
 script+='''
# Corrupt input fails before creating a snapshot or replacing audio.
echo broken > "$P/CarPlayMU1367Audio.jar"
if /bin/ksh "$P/control.sh" install "$P";then exit 20;fi
test ! -e "$R" || exit 21
cp /proc/boot/new-audio "$P/CarPlayMU1367Audio.jar"
# Unexpected installed audio is refused without a backup/write.
echo unknown > "$J"
if /bin/ksh "$P/control.sh" install "$P";then exit 22;fi
test ! -e "$R" || exit 23
cp /proc/boot/old-audio "$J"
# Shared lock and live feed gates hold before persistent writes.
mkdir "$CPMAP_TEST_ROOT/ramdisk/.carplay-guidance-install-lock"
if /bin/ksh "$P/control.sh" install "$P";then exit 24;fi
rm -rf "$CPMAP_TEST_ROOT/ramdisk/.carplay-guidance-install-lock"
: > "$CPMAP_TEST_ROOT/ramdisk/carplay-altstream.ready"
if /bin/ksh "$P/control.sh" install "$P";then exit 25;fi
rm "$CPMAP_TEST_ROOT/ramdisk/carplay-altstream.ready"
/bin/ksh "$P/control.sh" install "$P" || exit 26
/bin/ksh "$P/control.sh" install "$P" || exit 27
test "$(cat "$R/STATE")" = installed || exit 28
'''
 script+='"$P/verify" "$J" '+sha(payload/'CarPlayMU1367Audio.jar')+' || exit 29\n'
 script+='''
# A changed active runtime cannot be silently uninstalled.
echo changed > "$J"
if /bin/ksh "$R/control.sh" uninstall;then exit 30;fi
# Saved recovery works with a missing JAR only after restoring a regular target.
cp /proc/boot/new-audio "$J"
# A corrupted snapshot is refused before active audio is changed.
echo corrupt > "$R/backup/audio"
if /bin/ksh "$R/control.sh" recover;then exit 31;fi
'''
 script+='"$P/verify" "$J" '+sha(payload/'CarPlayMU1367Audio.jar')+' || exit 32\n'
 script+='''cp /proc/boot/old-audio "$R/backup/audio"
/bin/ksh "$R/control.sh" recover || exit 33
test "$(cat "$R/STATE")" = removed || exit 34
test -f "$R/backup/audio" || exit 35
test ! -e "$CPMAP_TEST_ROOT/ramdisk/.carplay-guidance-install-lock" || exit 36
'''
 script+='"$P/verify" "$J" '+sha(art/'CarPlayMU1367Audio.jar')+' || exit 37\n'
 script+='''# Retained snapshots cannot be overwritten by reinstallation.
if /bin/ksh "$P/control.sh" install "$P";then exit 38;fi
mv "$R" "$R.retained"
/bin/ksh "$P/control.sh" install "$P" || exit 39
/bin/ksh "$R/control.sh" uninstall || exit 40
'''
 script+='"$P/verify" "$J" '+sha(art/'CarPlayMU1367Audio.jar')+' || exit 41\n'
 for path,src in [('armle/lib/dll/ipod-drvr-iap2.so',art/'ipod-drvr-iap2.so'),('carplay-mu1367-artwork/artwork-fetch',art/'artwork-fetch')]:
  script+='"$P/verify" "$APP/'+path+'" '+sha(src)+' || exit 42\n'
 script+='echo AUDIO_TRANSACTION_QNX_PASS payload_gate=1 runtime_gate=1 lock=1 live_feed=1 install=1 repeat=1 changed_runtime=1 corrupt_snapshot=1 saved_recover=1 retained=1 uninstall=1\n'
 if r2:
  script=script.replace('R=$APP/carplay-mu1367-audio-progress\n','R=$APP/carplay-mu1367-audio-progress-r2\n')
  script+='''
mv "$R" "$R.baseline-retained"
R1=$APP/carplay-mu1367-audio-progress
mkdir -p "$R1/backup"
cp /proc/boot/r1-control "$R1/control.sh"
cp /proc/boot/r1-version "$R1/VERSION"
cp /proc/boot/verify "$R1/verify"
chmod 755 "$R1/verify"
echo installed > "$R1/STATE"
: > "$R1/BACKUPS_READY"
cp /proc/boot/old-audio "$R1/backup/audio"
"$P/verify" /proc/boot/old-audio > "$R1/backup/audio.sha256"
cp /proc/boot/r1-audio "$J"
echo corrupt > "$R1/backup/audio"
if /bin/ksh "$P/control.sh" install "$P";then exit 43;fi
test ! -e "$R" || exit 44
cp /proc/boot/old-audio "$R1/backup/audio"
/bin/ksh "$P/control.sh" install "$P" || exit 45
"$P/verify" "$R/backup/audio" 86d70b62d2561bd17882999a5c9748029189731da22a65d2b30b37a15179dd40 || exit 46
"$P/verify" "$R1/backup/audio" c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3 || exit 47
if /bin/ksh "$R1/control.sh" uninstall;then exit 48;fi
/bin/ksh "$R/control.sh" uninstall || exit 49
"$P/verify" "$J" 86d70b62d2561bd17882999a5c9748029189731da22a65d2b30b37a15179dd40 || exit 50
/bin/ksh "$R1/control.sh" uninstall || exit 51
"$P/verify" "$J" c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3 || exit 52
echo AUDIO_R1_UPGRADE_QNX_PASS snapshot_gate=1 upgrade=1 parent_guard=1 restore_r1=1 original_backup_preserved=1 restore_original=1
'''
 if r3:
  script=script.replace('R=$APP/carplay-mu1367-audio-progress\n','R=$APP/carplay-mu1367-artwork-r3\n')
  script=script.replace('cp /proc/boot/old-audio "$J"\n', 'cp /proc/boot/old-audio "$J"\n',1)
  r3_setup='mkdir -p "$CPMAP_TEST_ROOT/proc/boot"\ncp /proc/boot/factory-zlib "$CPMAP_TEST_ROOT/proc/boot/libz.so.2"\ncp /proc/boot/new-fetch "$P/artwork-fetch"\n'
  script=script.replace('# Corrupt input fails',r3_setup+'# Corrupt input fails')
  gate='# Both new payloads and the factory library are checked before snapshots.\necho broken > "$P/artwork-fetch"\nif /bin/ksh "$P/control.sh" install "$P";then exit 60;fi\ntest ! -e "$R" || exit 61\ncp /proc/boot/new-fetch "$P/artwork-fetch"\necho wrong > "$CPMAP_TEST_ROOT/proc/boot/libz.so.2"\nif /bin/ksh "$P/control.sh" install "$P";then exit 62;fi\ntest ! -e "$R" || exit 63\ncp /proc/boot/factory-zlib "$CPMAP_TEST_ROOT/proc/boot/libz.so.2"\n'
  script=script.replace('# Shared lock and live feed gates',gate+'# Shared lock and live feed gates')
  snap='# A corrupt second backup prevents restoration of either file.\necho broken > "$R/backup/fetch"\nif /bin/ksh "$R/control.sh" recover;then exit 64;fi\n"$P/verify" "$J" @AUDIO@ || exit 65\ncp /proc/boot/fetch "$R/backup/fetch"\n'.replace('@AUDIO@',m['audio_sha256'])
  script=script.replace('# A corrupted snapshot is refused',snap+'# A corrupted snapshot is refused')
  script+='\nmv "$R" "$R.base-retained"\nR1=$APP/carplay-mu1367-audio-progress\nR2=$APP/carplay-mu1367-audio-progress-r2\nmkdir -p "$R1/backup" "$R2/backup"\nfor Q in r1 r2;do\n if [ "$Q" = r1 ];then S=$R1; B=/proc/boot/old-audio;else S=$R2; B=/proc/boot/r1-audio;fi\n cp "/proc/boot/$Q-control" "$S/control.sh"\n cp "/proc/boot/$Q-version" "$S/VERSION"\n cp /proc/boot/verify "$S/verify"\n chmod 755 "$S/verify"\n echo installed > "$S/STATE"\n : > "$S/BACKUPS_READY"\n cp "$B" "$S/backup/audio"\n "$P/verify" "$B" > "$S/backup/audio.sha256"\ndone\ncp /proc/boot/r2-audio "$J"\necho corrupt > "$R2/backup/audio"\nif /bin/ksh "$P/control.sh" install "$P";then exit 66;fi\ntest ! -e "$R" || exit 67\ncp /proc/boot/r1-audio "$R2/backup/audio"\n/bin/ksh "$P/control.sh" install "$P" || exit 68\n"$P/verify" "$R/backup/audio" @R2AUDIO@ || exit 69\n"$P/verify" "$R/backup/fetch" @OLDFETCH@ || exit 70\n"$P/verify" "$R2/backup/audio" @R1AUDIO@ || exit 71\n"$P/verify" "$R1/backup/audio" @BASEAUDIO@ || exit 72\nif /bin/ksh "$R2/control.sh" uninstall;then exit 73;fi\n/bin/ksh "$R/control.sh" uninstall || exit 74\n"$P/verify" "$J" @R2AUDIO@ || exit 75\n"$P/verify" "$APP/carplay-mu1367-artwork/artwork-fetch" @OLDFETCH@ || exit 76\n/bin/ksh "$R2/control.sh" uninstall || exit 77\n"$P/verify" "$J" @R1AUDIO@ || exit 78\n/bin/ksh "$R1/control.sh" uninstall || exit 79\n"$P/verify" "$J" @BASEAUDIO@ || exit 80\necho ARTWORK_R3_UPGRADE_QNX_PASS second_payload=1 factory_library=1 whole_snapshot=1 r2_snapshot_gate=1 upgrade=1 parent_guard=1 restore_r2=1 restore_fetch=1 r1_r2_backups_preserved=1 unwind_original=1\n'
  for key,value in [('R2AUDIO',sha(out/'r2-audio')),('R1AUDIO',sha(out/'r1-audio')),('BASEAUDIO',sha(art/'CarPlayMU1367Audio.jar')),('OLDFETCH',sha(art/'artwork-fetch'))]:script=script.replace('@'+key+'@',value)
 if r3:
  # The A/B switch only ever touches its RAM-disk flag, and needs an installed test.
  ab="""
F="$CPMAP_TEST_ROOT/ramdisk/cpmap-artwork-png-stored"
/bin/ksh "$R/control.sh" png-stored || exit 70
test -e "$F" || exit 71
/bin/ksh "$R/control.sh" status | grep -q MU1367_ARTWORK_R3_PNG=UNCOMPRESSED_UNTIL_REBOOT || exit 72
/bin/ksh "$R/control.sh" png-compressed || exit 73
test ! -e "$F" || exit 74
/bin/ksh "$R/control.sh" status | grep -q MU1367_ARTWORK_R3_PNG=COMPRESSED || exit 75
"""
  ab+='"$P/verify" "$J" '+sha(payload/'CarPlayMU1367Audio.jar')+' || exit 76\n'
  marker='test "$(cat "$R/STATE")" = installed || exit 28\n';assert script.count(marker)==1
  script=script.replace(marker,marker+ab)
  marker='test "$(cat "$R/STATE")" = removed || exit 34\n';assert script.count(marker)==1
  script=script.replace(marker,marker+'if /bin/ksh "$R/control.sh" png-stored;then exit 77;fi\ntest ! -e "$CPMAP_TEST_ROOT/ramdisk/cpmap-artwork-png-stored" || exit 78\n')
 (out/'test.sh').write_text(script)
 template=(setup/'test.build').read_text();start=template.index(' display_msg "@@OEM-START@@"');end=template.index('\n}',start)
 template=template[:start]+' display_msg "@@AUDIO-TX-START@@"\n /proc/boot/ksh /proc/boot/test.sh\n display_msg "@@AUDIO-TX-END@@"'+template[end:]
 template=template[:template.index('\n[type=link] /bin/ksh=')]
 for n in ('rgi-observer','snapshot.bin'):template=template.replace('\n'+n+'\n','\n')
 template+='\n[type=link] /bin/ksh=/proc/boot/ksh\n[type=file]\n[data=copy]\n[perms=+r,+x]\n[+raw]\n'
 template+=''.join(n+'=factory-'+n+'\n' for n in audit['commands'])
 template+='\n'.join(['verify','old-audio','new-audio','driver','fetch','control','VERSION','guard','fixture-jxe','test.sh'])+'\n'
 if r2 or r3:template+='r1-control\nr1-audio\nr1-version\n'
 if r3:template+='r2-control\nr2-audio\nr2-version\nnew-fetch\nfactory-zlib\n'
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
   send(b'go 0x40200000\n');expect(b'@@AUDIO-TX-END@@',at)
  finally:
   proc.stdin.close();proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
 assert 'AUDIO_TRANSACTION_QNX_PASS' in logpath.read_text(errors='replace')
 if r2:
  assert 'AUDIO_R1_UPGRADE_QNX_PASS' in logpath.read_text(errors='replace')
  assert 'MU1367_AUDIO_PROGRESS_FAIL=FILE_CHANGED_audio' in logpath.read_text(errors='replace')
 if r3:
  assert 'ARTWORK_R3_UPGRADE_QNX_PASS' in logpath.read_text(errors='replace')
  assert 'MU1367_AUDIO_PROGRESS_R2_FAIL=FILE_CHANGED_audio' in logpath.read_text(errors='replace')
 r={'passed':True,'controller_sha256':sha(payload/'control.sh'),'audio_sha256':sha(payload/'CarPlayMU1367Audio.jar'),'actual_qnx_ksh':True,'sdk_utilities_injected':False,'mounts_mocked':True,'fixture_change':'Small-JXE fingerprint and dependent R1 controller hash only; verifier/driver/audio/worker use full real files.','tests':22 if r3 else 17 if r2 else 11,'r1_upgrade_verified':r2,'r2_upgrade_verified':r3,'two_file_restore_verified':r3,'qemu_log_sha256':sha(logpath),'on_unit_validated':False}
 (out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
