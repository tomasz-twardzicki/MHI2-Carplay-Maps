#!/usr/bin/env python3
"""Add a reversible audio test to the unchanged v1.4.1 runtime baseline."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
from payload_checks import write_payload_checks
HERE=Path(__file__).resolve().parent.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','host','qnx','base-archive','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--revision',choices=('r1','r2'),default='r2')
 a=p.parse_args();jar=a.build/'CarPlayMU1367Audio.jar';h=sha(jar)
 build_manifest=json.loads((a.build/'manifest.json').read_text())
 assert build_manifest['jar_sha256']==h
 for name,digest in build_manifest['source_sha256'].items():assert sha(HERE/name)==digest,name
 for f in (a.host,a.qnx):
  r=json.loads(f.read_text());assert r['passed'] and r['audio_sha256']==h
 assert json.loads(a.qnx.read_text())['factory_j9_verified']
 # A test must never silently change the baseline or promote itself to a release.
 base=HERE.parents[1]/'releases/MU1367/v1.4.1/manifest.json'
 assert sha(a.base_archive)==json.loads(base.read_text())['archive_sha256']
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);sd=out/'sd-card';sd.mkdir()
 with zipfile.ZipFile(a.base_archive) as z:
  for n in z.namelist():
   dest=sd/n;assert dest.resolve().is_relative_to(sd)
   if n.endswith('/'):dest.mkdir(parents=True,exist_ok=True);continue
   dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(n))
   dest.chmod((z.getinfo(n).external_attr>>16)&0o777 or 0o644)
 custom_layer='carplay_mu1367_audio_progress'+('_r2' if a.revision=='r2' else '')
 live_layer='carplay-mu1367-audio-progress'+('-r2' if a.revision=='r2' else '')
 root=sd/'Custom'/custom_layer;root.mkdir()
 old=sd/'Custom/carplay_mu1367_artwork';baseline=sha(old/'CarPlayMU1367Audio.jar')
 assert baseline=='c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3'
 control=(HERE/'tools/transaction.sh').read_text().replace('carplay-mu1367-lanes',live_layer).replace('MU1367_LANES','MU1367_AUDIO_PROGRESS'+('_R2' if a.revision=='r2' else '')).replace('.lanes-new','.audio-progress-new')
 # This transaction replaces only the audio JAR. Existing controllers already
 # reject changed runtime hashes; it never rewrites their saved identities.
 control=control.replace('for K in parent settings;do','for K in $GUARDS;do')
 control=control.replace('  echo "Cards: App-Connect > Virtual Cockpit settings > navigation card ON/OFF; reconnect after changing"','  if regular "$M/ramdisk/carplay-now-playing-n1.status";then cat "$M/ramdisk/carplay-now-playing-n1.status";fi\n  if regular "$M/ramdisk/cpmap-artwork.status";then cat "$M/ramdisk/cpmap-artwork.status";fi')
 marker=' [ "$(cat "$P/VERSION" 2>/dev/null)" = "$BUILD" ] || fail PAYLOAD_VERSION'
 gates=' [ "$(cat "$APP/carplay-mu1367-artwork/STATE" 2>/dev/null)" = installed ] && [ "$(cat "$APP/carplay-mu1367-artwork/VERSION" 2>/dev/null)" = MU1367-artwork-f353117dbe5c ] || fail EXACT_ARTWORK_PARENT_REQUIRED\n'
 gates+=' check "$APP/armle/lib/dll/ipod-drvr-iap2.so" '+sha(old/'ipod-drvr-iap2.so')+' || fail ARTWORK_DRIVER_CHANGED\n'
 gates+=' check "$APP/carplay-mu1367-artwork/artwork-fetch" '+sha(old/'artwork-fetch')+' || fail ARTWORK_FETCH_CHANGED\n'
 assert control.count(marker)==1;control=control.replace(marker,gates+marker)
 if a.revision=='r2':
  # Upgrade exactly the field-tested R1 without overwriting its original backup.
  needle=' for K in $KEYS;do check "$(target "$K")" "$(before "$K")" || fail "UNEXPECTED_BASE_$K";done'
  assert control.count(needle)==1
  upgrade=''' CURRENT_AUDIO=$(digest "$(target audio)") || fail READ_CURRENT_AUDIO
 case "$CURRENT_AUDIO" in
 c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3) ;;
 86d70b62d2561bd17882999a5c9748029189731da22a65d2b30b37a15179dd40)
  R1=$APP/carplay-mu1367-audio-progress
  [ -d "$R1" ] && [ ! -L "$R1" ] && [ -d "$R1/backup" ] && [ ! -L "$R1/backup" ] || fail R1_SNAPSHOT_PATH
  regular "$R1/STATE" && [ "$(cat "$R1/STATE")" = installed ] || fail R1_NOT_INSTALLED
  regular "$R1/VERSION" && [ "$(cat "$R1/VERSION")" = MU1367-audio-progress-86d70b62d256 ] || fail R1_VERSION
  regular "$R1/BACKUPS_READY" || fail R1_BACKUP_NOT_READY
  check "$R1/control.sh" 50bb99d638223022d04fb9b8c133328be22d7f583ff108a9f37b5b43d75ca201 || fail R1_CONTROLLER_CHANGED
  check "$R1/backup/audio" c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3 || fail R1_BACKUP_CHANGED
  regular "$R1/backup/audio.sha256" && [ "$(cat "$R1/backup/audio.sha256")" = c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3 ] || fail R1_BACKUP_DIGEST
  ;;
 *) fail UNEXPECTED_BASE_audio;;
 esac'''
  control=control.replace(needle,upgrade)
 guard='# Audio test replaces only its JAR; restore it before base changes.\n'
 build=('MU1367-audio-native-r2-' if a.revision=='r2' else 'MU1367-audio-progress-')+h[:12]
 table="KEYS='audio'\nFILES='audio'\nGUARDS=''\nGUARD_SHA="+hashlib.sha256(guard.encode()).hexdigest()+'\n'
 table+='PARENT_BUILD='+ (sd/'Custom/carplay_mu1367/VERSION').read_text().strip()+'\n'
 table+='SETTINGS_BUILD='+ (sd/'Custom/carplay_mu1367_settings/VERSION').read_text().strip()+'\n'
 table+='target(){ case "$1" in audio) echo "$APP/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar";; *) return 1;; esac; }\n'
 table+='payload(){ case "$1" in audio) echo CarPlayMU1367Audio.jar;; *) return 1;; esac; }\n'
 table+='expected(){ case "$1" in audio) echo '+h+';; *) return 1;; esac; }\n'
 table+='before(){ case "$1" in audio) echo '+baseline+';; *) return 1;; esac; }\n'
 (root/'control.sh').write_text(control.replace('@BUILD@',build).replace('@TABLE@',table))
 (root/'VERSION').write_text(build+'\n');(root/'guard').write_text(guard)
 shutil.copy2(jar,root/jar.name);shutil.copy2(old/'verify',root/'verify')
 for action in ('install','uninstall','recover','status'):
  wrapper=(sd/'Toolbox/scripts/cpmap_suite_install.sh').read_text().replace('carplay_mu1367_guidance_v3/actions.sh',custom_layer+'/control.sh').replace('carplay_mu1367_guidance_v3;',custom_layer+';').replace('"$P/actions.sh" install','"$P/control.sh" '+action).replace('MU1367_OEM_RESET_','MU1367_AUDIO_PROGRESS_')
  (sd/'Toolbox/scripts'/('cpmap_audio_progress_'+action+'.sh')).write_text(wrapper)
 menu=sd/'Toolbox/GEM/carplay-maps-vc.esd'
 with menu.open('a') as f:
  labels=[('install','Install native audio R2 probe (reboot)'),('uninstall','Restore audio before R2 (reboot)'),('recover','Recover interrupted audio R2 (reboot)'),('status','Native audio R2 / artwork timings')] if a.revision=='r2' else [('install','Install audio progress test (reboot)'),('uninstall','Restore previous audio (reboot)'),('recover','Recover interrupted audio update (reboot)'),('status','Audio progress / artwork status')]
  for action,label in labels:
   f.write('\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_audio_progress_'+action+'.sh"\n    label "'+label+'"\n')
 shutil.copy2(HERE/'AUDIO-PROGRESS.md',sd/'AUDIO-PROGRESS.md')
 if a.revision=='r2':shutil.copy2(HERE/'AUDIO-NATIVE-R2.md',sd/'AUDIO-NATIVE-R2.md')
 # Baseline ZIPs predate the CarPlay-only preflight scope. Regenerate all three
 # checkers, including this test's payload, without changing baseline runtimes.
 write_payload_checks(sd/'Custom')
 (sd/'README.md').write_text('# MU1367 / 791 audio test\n\nRead ['+('AUDIO-NATIVE-R2.md](AUDIO-NATIVE-R2.md)' if a.revision=='r2' else 'AUDIO-PROGRESS.md](AUDIO-PROGRESS.md)')+' for installation and rollback.\n')
 for f in [root/'control.sh',*(sd/'Toolbox/scripts').glob('cpmap_audio_progress_*.sh')]:
  subprocess.run(['/bin/ksh','-n',str(f)],check=True);f.chmod(0o755)
 inv={str(f.relative_to(sd)):sha(f) for f in sorted(sd.rglob('*')) if f.is_file() and f.name!='FILES_SHA256.json'}
 (sd/'FILES_SHA256.json').write_text(json.dumps(inv,indent=2)+'\n')
 name='CarPlay_Maps_VC_MU1367_791_Audio_Native_R2_Probe.zip' if a.revision=='r2' else 'CarPlay_Maps_VC_MU1367_791_Audio_Progress_Test.zip';archive=out/name
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for f in sorted(sd.rglob('*')):
   if f.is_file():z.write(f,f.relative_to(sd))
 result={'passed':True,'test_build':True,'revision':a.revision,'custom_layer':custom_layer,'live_layer':live_layer,'build_id':build,'audio_sha256':h,'base_audio_sha256':baseline,'archive_name':name,'archive_sha256':sha(archive),'base_archive_sha256':sha(a.base_archive),'on_unit_validated':False,'runtime_changes':['audio JAR only'],'host':json.loads(a.host.read_text()),'qnx':json.loads(a.qnx.read_text())}
 (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');(out/'SHA256SUMS.txt').write_text(sha(archive)+'  '+name+'\n');print(json.dumps(result))
if __name__=='__main__':main()
