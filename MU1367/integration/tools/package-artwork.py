#!/usr/bin/env python3
"""Add the optional, recoverable artwork test to the published v1.4.5-e archive.

A post-processor: every release payload stays byte-identical, so RUNTIME.json and the
release proofs still describe the base. Only the Tuning menu and generated checks change.
"""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
from payload_checks import write_payload_checks
HERE=Path(__file__).resolve().parent.parent
BASE_ARCHIVE_SHA256='80e38ec252a8bf84af628e450af80e6a992319315aa8e4be4c66837fb61f4826'
ARCHIVE='CarPlay_Maps_VC_MU1367_791_v1.4.5-e.zip'
BASE_AUDIO='c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3'
R1_AUDIO='86d70b62d2561bd17882999a5c9748029189731da22a65d2b30b37a15179dd40'
R2_AUDIO='1b29ead7059890e07d27036eef46440cc4620c8da1d33d6d66774b84a89b9eba'
R2_CONTROL='615474000d3e92705f59e989bec9e11eef7a220354073cf4710267bf5af7efe6'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','native','host','qnx','native-host','base-archive','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();jar=a.build/'CarPlayMU1367Audio.jar';fetch=a.native/'artwork-fetch';h=sha(jar);f=sha(fetch)
 jm=json.loads((a.build/'manifest.json').read_text());nm=json.loads((a.native/'manifest.json').read_text())
 assert jm['revision']=='artwork-r3' and jm['jar_sha256']==h and nm['sha256']==f
 for manifest,key in [(jm,'source_sha256'),(nm,'sources')]:
  for name,digest in manifest[key].items():assert sha(HERE/name)==digest,name
 for proof in (a.host,a.qnx):
  r=json.loads(proof.read_text());assert r['passed'] and r['audio_sha256']==h
 qr=json.loads(a.qnx.read_text());assert qr['factory_j9_verified']
 assert qr['fetch_sha256']==f and qr['factory_zlib_sha256']==nm['factory_libraries']['libz.so.2']
 nh=json.loads(a.native_host.read_text());assert nh['passed']
 for name,digest in nh['source_sha256'].items():assert sha(HERE/name)==digest
 assert sha(a.base_archive)==BASE_ARCHIVE_SHA256
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);sd=out/'sd-card';sd.mkdir()
 with zipfile.ZipFile(a.base_archive) as z:
  for name in z.namelist():
   dest=sd/name;assert dest.resolve().is_relative_to(sd)
   if name.endswith('/'):dest.mkdir(parents=True,exist_ok=True);continue
   dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name));dest.chmod((z.getinfo(name).external_attr>>16)&0o777 or 0o644)
 custom='carplay_mu1367_artwork_r3';live='carplay-mu1367-artwork-r3';root=sd/'Custom'/custom;root.mkdir();old=sd/'Custom/carplay_mu1367_artwork'
 assert sha(old/'CarPlayMU1367Audio.jar')==BASE_AUDIO
 control=(HERE/'tools/transaction.sh').read_text().replace('carplay-mu1367-lanes',live).replace('MU1367_LANES','MU1367_ARTWORK_R3').replace('.lanes-new','.artwork-r3-new')
 control=control.replace('for K in parent settings;do','for K in $GUARDS;do')
 status='\n'.join('  if regular "$M/ramdisk/'+n+'";then cat "$M/ramdisk/'+n+'";fi' for n in ('carplay-now-playing-n1.status','cpmap-artwork.status','cpmap-artwork-timing.status'))
 control=control.replace('  echo "Cards: App-Connect > Virtual Cockpit settings > navigation card ON/OFF; reconnect after changing"',status)
 # Same-session A/B without a reboot or JAR change. The helper reads this RAM-disk flag per cover;
 # png_bytes in the timing rows shows which writer each cover used.
 flag='"$M/ramdisk/cpmap-artwork-png-stored"'
 status_png='  if [ -e '+flag+' ];then echo MU1367_ARTWORK_R3_PNG=UNCOMPRESSED_UNTIL_REBOOT;else echo MU1367_ARTWORK_R3_PNG=COMPRESSED;fi\n'
 ab=' png-stored|png-compressed)\n  [ "$(cat "$ROOT/STATE" 2>/dev/null)" = installed ] || fail ARTWORK_TEST_NOT_INSTALLED\n'
 ab+='  if [ "$ACTION" = png-stored ];then : > '+flag+' || fail PNG_FLAG;else rm -f '+flag+' || fail PNG_FLAG;fi\n'
 ab+=status_png+'  echo NEXT_COVER_USES_THIS_NO_REBOOT\n  exit 0;;\n'
 needle=' install|uninstall|recover) ;;\n';assert control.count(needle)==1;control=control.replace(needle,ab+needle)
 control=control.replace(status,status+'\n'+status_png.rstrip('\n'))
 marker=' [ "$(cat "$P/VERSION" 2>/dev/null)" = "$BUILD" ] || fail PAYLOAD_VERSION';assert control.count(marker)==1
 gates=' [ "$(cat "$APP/carplay-mu1367-artwork/STATE" 2>/dev/null)" = installed ] && [ "$(cat "$APP/carplay-mu1367-artwork/VERSION" 2>/dev/null)" = MU1367-artwork-f353117dbe5c ] || fail EXACT_ARTWORK_PARENT_REQUIRED\n'
 gates+=' check "$APP/armle/lib/dll/ipod-drvr-iap2.so" '+sha(old/'ipod-drvr-iap2.so')+' || fail ARTWORK_DRIVER_CHANGED\n'
 gates+=' check "$M/proc/boot/libz.so.2" '+nm['factory_libraries']['libz.so.2']+' || fail FACTORY_ZLIB_CHANGED\n'
 control=control.replace(marker,gates+marker)
 needle=' for K in $KEYS;do check "$(target "$K")" "$(before "$K")" || fail "UNEXPECTED_BASE_$K";done';assert control.count(needle)==1
 upgrade=''' CURRENT_AUDIO=$(digest "$(target audio)") || fail READ_CURRENT_AUDIO
 case "$CURRENT_AUDIO" in
 @BASE@) ;;
 @R2@)
  R2=$APP/carplay-mu1367-audio-progress-r2
  [ -d "$R2" ] && [ ! -L "$R2" ] && [ -d "$R2/backup" ] && [ ! -L "$R2/backup" ] || fail R2_SNAPSHOT_PATH
  regular "$R2/STATE" && [ "$(cat "$R2/STATE")" = installed ] || fail R2_NOT_INSTALLED
  regular "$R2/VERSION" && [ "$(cat "$R2/VERSION")" = MU1367-audio-native-r2-1b29ead70598 ] || fail R2_VERSION
  regular "$R2/BACKUPS_READY" || fail R2_BACKUP_NOT_READY
  check "$R2/control.sh" @CONTROL@ || fail R2_CONTROLLER_CHANGED
  regular "$R2/backup/audio.sha256" || fail R2_BACKUP_DIGEST
  R2_BEFORE=$(cat "$R2/backup/audio.sha256")
  case "$R2_BEFORE" in @BASE@|@R1@) ;; *) fail R2_BACKUP_DIGEST;; esac
  check "$R2/backup/audio" "$R2_BEFORE" || fail R2_BACKUP_CHANGED
  ;;
 *) fail UNEXPECTED_BASE_audio;;
 esac
 check "$(target fetch)" "$(before fetch)" || fail UNEXPECTED_BASE_fetch'''
 for key,value in [('BASE',BASE_AUDIO),('R1',R1_AUDIO),('R2',R2_AUDIO),('CONTROL',R2_CONTROL)]:upgrade=upgrade.replace('@'+key+'@',value)
 control=control.replace(needle,upgrade)
 guard='# Restore the R3 audio and fetch snapshot before changing lower layers.\n';build='MU1367-artwork-r3-'+hashlib.sha256((h+f).encode()).hexdigest()[:12]
 table="KEYS='audio fetch'\nFILES='audio fetch'\nGUARDS=''\nGUARD_SHA="+hashlib.sha256(guard.encode()).hexdigest()+'\n'
 table+='PARENT_BUILD='+(sd/'Custom/carplay_mu1367/VERSION').read_text().strip()+'\nSETTINGS_BUILD='+(sd/'Custom/carplay_mu1367_settings/VERSION').read_text().strip()+'\n'
 table+='target(){ case "$1" in audio) echo "$APP/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar";; fetch) echo "$APP/carplay-mu1367-artwork/artwork-fetch";; *) return 1;; esac; }\n'
 table+='payload(){ case "$1" in audio) echo CarPlayMU1367Audio.jar;; fetch) echo artwork-fetch;; *) return 1;; esac; }\n'
 table+='expected(){ case "$1" in audio) echo '+h+';; fetch) echo '+f+';; *) return 1;; esac; }\n'
 table+='before(){ case "$1" in audio) echo '+BASE_AUDIO+';; fetch) echo '+sha(old/'artwork-fetch')+';; *) return 1;; esac; }\n'
 (root/'control.sh').write_text(control.replace('@BUILD@',build).replace('@TABLE@',table));(root/'VERSION').write_text(build+'\n');(root/'guard').write_text(guard)
 for src in (jar,fetch,old/'verify'):shutil.copy2(src,root/src.name)
 labels={'install':'Install artwork test: fast + compressed (reboot)','png-stored':'Artwork test: uncompressed PNG (A/B)','png-compressed':'Artwork test: compressed PNG (A/B)','status':'Artwork test timings','uninstall':'Remove artwork test (reboot)','recover':'Recover interrupted artwork test (reboot)'}
 tuning=sd/'Toolbox/GEM/carplay-maps-vc-tuning.esd'
 with tuning.open('a') as menu:menu.write('\nkeyValue\n    value String sys 0x00000000 0\n    label "Optional artwork refresh test"\n    poll 0\n')
 for action,label in labels.items():
  code=(sd/'Toolbox/scripts/cpmap_suite_install.sh').read_text().replace('carplay_mu1367_guidance_v3/actions.sh',custom+'/control.sh').replace('carplay_mu1367_guidance_v3;',custom+';').replace('"$P/actions.sh" install','"$P/control.sh" '+action).replace('MU1367_OEM_RESET_','MU1367_ARTWORK_R3_')
  wrapper=sd/'Toolbox/scripts'/('cpmap_artwork_r3_'+action+'.sh');wrapper.write_text(code);wrapper.chmod(0o755)
  with tuning.open('a') as menu:menu.write('\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/'+wrapper.name+'"\n    label "'+label+'"\n')
 shutil.copy2(HERE/'ARTWORK-R3.md',sd/'ARTWORK-R3.md')
 note='\n## Optional artwork refresh test\n\nNot part of the normal install. **Tuning > Install artwork test** speeds up cover refresh and compresses the cover PNG. See [ARTWORK-R3.md](ARTWORK-R3.md).\n'
 for doc in ('README.md','RELEASE-NOTES.md'):
  with (sd/doc).open('a') as text:text.write(note)
 write_payload_checks(sd/'Custom')
 for script in [root/'control.sh',*(sd/'Toolbox/scripts').glob('cpmap_artwork_r3_*.sh')]:subprocess.run(['/bin/ksh','-n',str(script)],check=True);script.chmod(0o755)
 inv={str(p.relative_to(sd)):sha(p) for p in sorted(sd.rglob('*')) if p.is_file() and p.name!='FILES_SHA256.json'};(sd/'FILES_SHA256.json').write_text(json.dumps(inv,indent=2)+'\n')
 name=ARCHIVE;archive=out/name
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(sd.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(sd))
 result={'passed':True,'test_build':True,'revision':'artwork-r3','custom_layer':custom,'live_layer':live,'build_id':build,'audio_sha256':h,'fetch_sha256':f,'controller_sha256':sha(root/'control.sh'),'archive_name':name,'archive_sha256':sha(archive),'base_archive_sha256':sha(a.base_archive),'base_version':'1.4.5-e','runtime_changes':['audio JAR','artwork-fetch'],'on_unit_validated':False,'host':json.loads(a.host.read_text()),'qnx':json.loads(a.qnx.read_text()),'native_host':nh,'native':nm}
 # Release-asset manifest: the published one plus this archive's identity and the option.
 with zipfile.ZipFile(a.base_archive) as z:release=json.loads(z.read('MU1367_RELEASE_MANIFEST.json'))
 release.update(archive_name=name,archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,previous_archive_sha256=BASE_ARCHIVE_SHA256,optional_artwork_test={'build_id':build,'audio_sha256':h,'fetch_sha256':f,'installed_by_default':False,'on_unit_validated':False})
 (out/'release-manifest.json').write_text(json.dumps(release,indent=2)+'\n')
 (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');(out/'SHA256SUMS.txt').write_text(sha(archive)+'  '+name+'\n');print(json.dumps(result))
if __name__=='__main__':main()
