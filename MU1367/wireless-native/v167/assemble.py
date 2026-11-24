#!/usr/bin/env python3
"""Stage 790-only support on exact vehicle-tested v1.6.5-e-test2."""
import argparse
import hashlib
import json
import shlex
import shutil
import zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
p=argparse.ArgumentParser()
for n in ('baseline','tested-790','launcher','output'):p.add_argument('--'+n,type=Path,required=True)


a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);sd=out/'sd-card'
assert sha(a.baseline.read_bytes())=='e9b815eb0be0e1b9cf45564278e15b12ddbe4d0436553a40177e54324882fcae'
assert sha(a.tested_790.read_bytes())=='202ab34e7339324ca204e6ea64ef754d94a1174f76e9d139c41d59bfc28d3359'
media790=json.loads((a.launcher/'VERIFICATION.json').read_text());assert media790['passed']
for name,pin in media790['files'].items():assert sha((a.launcher/name).read_bytes())==pin
with zipfile.ZipFile(a.baseline) as z:
 z.extractall(sd)
 for i in z.infolist():
  if not i.is_dir():(sd/i.filename).chmod((i.external_attr>>16&0o777) or 0o644)
custom=sd/'Custom';parent=custom/'carplay_mu1367_wireless_native';module=custom/'carplay_mu1367_input_profile';module.mkdir()
base=json.loads((parent/'manifest.json').read_text());by_target={r['target']:r for r in base['rows']}
template=(HERE.parent/'v161/control.sh').read_text()
assert base['version']=='1.6.5-e-test2'
assert base['build_id']=='MU1367-wireless-native-v165t2-8ebe482b1961'
factory_jxe='09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a'
roots={'790':'carplay-mu1367-profile-790-v167'}
controllers={};manifests={}
with zipfile.ZipFile(a.tested_790) as tested:
 prefix='Custom/carplay_mu1367_input_profile/790/payload/'
 native790={n:tested.read(prefix+n) for n in ('wcp_receiver','wireless-entry','wireless-receiver-exec','libomonob-wireless-maps.so','v75-wireless-display.conf','cluster-profile','altscreen.conf','altscreen.geom')}
 runtime790={n:tested.read(prefix+n) for n in ('core.so','altscreen-most-bridge','carplay-cluster-supervisor')}
geometry=(HERE/'src/geometry.sh').read_text()
for variant in ('790',):
 dest=module/variant;payload=dest/'payload';payload.mkdir(parents=True);rows=[]
 def add(name,target,data,mode='644',before=None):
  key='k%02d'%len(rows);(payload/name).write_bytes(data)
  if before is None:
   row=by_target[target];before=row['sha256']
  rows.append(dict(key=key,source=name,target=target,mode=mode,before=before,sha256=sha(data)))
 cfg_key=None;call_key=None
 if variant=='790':
  native790['altscreen.conf']=native790['altscreen.conf'].replace(b'nsafex=42\n',b'nsafex=202\n')
  for name,data in native790.items():
   if media790 and name=='wireless-receiver-exec':data=(a.launcher/name).read_bytes()
   target={'wcp_receiver':'/mnt/ota/wcp_receiver','wireless-entry':'/mnt/app/carplaymaps/wireless-entry','wireless-receiver-exec':'/mnt/app/carplaymaps/wireless-receiver-exec','libomonob-wireless-maps.so':'/mnt/app/carplaymaps/libomonob-wireless-maps.so','v75-wireless-display.conf':'/mnt/persist/v75-wireless-display.conf','cluster-profile':'/mnt/persist/omonob-phone/cluster-profile','altscreen.conf':'/mnt/persist/altscreen.conf','altscreen.geom':'/mnt/persist/altscreen.geom'}[name]
   add(name,target,data,'755' if name in ('wcp_receiver','wireless-entry','wireless-receiver-exec') else '644','optional' if name in ('altscreen.conf','altscreen.geom') else None)
   if name=='altscreen.conf':cfg_key=rows[-1]['key']
  add('core.so','/mnt/app/carplaymaps/core.so',runtime790['core.so'],before='core')
  if True:
   for name in ('altscreen-most-bridge','carplay-cluster-supervisor'):
    add(name,'/mnt/app/carplaymaps/'+name,runtime790[name],'755')
  add('PROFILE','/mnt/app/carplaymaps/PROFILE',b'MU1367/790\n',before=sha(b'MU1367/791\n'))
  launch=(parent/'payload/start-wireless-maps.sh').read_text()
  start=launch.index('"$VERIFY" "$ROOT/libcpmap-wcp-tap.so"');end=launch.index('p=`cat',start)
  launch=launch[:start]+launch[end:]
  launch=launch.replace('54c765fc74b00ee06e9d740384817b8c39740a96c1b012a3057d990878a614e8',sha(native790['wireless-entry']))
  launch=launch.replace('omonob-791-input','omonob-790-input').replace('CPMAP_WCP_INPUT=162 LD_PRELOAD="$ROOT/libcpmap-wcp-tap.so" ','')
  add('start-wireless-maps.sh','/mnt/app/carplaymaps/start-wireless-maps.sh',launch.encode(),'755')
  if media790:
   add('libcpmap-wcp-media790.so','/mnt/app/carplaymaps/libcpmap-wcp-media790.so',(a.launcher/'libcpmap-wcp-media790.so').read_bytes(),before='absent')

 table='JXE_SHA='+factory_jxe+'\nKEYS='+shlex.quote(' '.join(r['key'] for r in rows))+'\nREVERSE_KEYS='+shlex.quote(' '.join(r['key'] for r in reversed(rows)))+'\n'
 if call_key:table+='callpref_ok(){ absent "$1" || check "$1" '+sha(b'')+' || check "$1" '+sha(b'1\n')+'; }\n'
 for fn,field in [('target','target'),('mode','mode')]:
  table+=fn+'(){ case "$1" in\n'
  for r in rows:table+=' '+r['key']+') echo "'+('$M' if fn=='target' else '')+r[field]+'";;\n'
  table+=' *) return 1;;esac; }\n'
 table+='before_ok(){ case "$1" in\n'
 for r in rows:
  if r['before']=='optional':cmd='regular "$2" || absent "$2"'
  elif r['before']=='absent':cmd='absent "$2"'
  elif r['before']=='callpref':cmd='callpref_ok "$2"'
  elif r['before']=='core':
   hashes={json.loads((custom/('carplay_mu1367_guidance_v3/'+v+'/manifest.json')).read_text())['files']['core'] for v in ('6','7','6-road','7-road')}
   cmd='H=$(digest "$2") || return 1;case "$H" in '+'|'.join(sorted(hashes))+') return 0;;*) return 1;;esac'
  else:cmd='check "$2" '+r['before']
  table+=' '+r['key']+') '+cmd+';;\n'
 table+=' *) return 1;;esac; }\nstage_payload(){ case "$1" in\n'
 for r in rows:
  if r['before']=='callpref':table+=' '+r['key']+') T=$(target "$1");if absent "$T";then return 0;fi;callpref_ok "$T" && cp -p "$T" "$2" && callpref_ok "$2";;\n'
  else:table+=' '+r['key']+') cp "$P/payload/'+r['source']+'" "$2" && check "$2" '+r['sha256']+';;\n'
 table+=' *) return 1;;esac; }\n'
 table+='baseline_ok(){\n [ "$(cat "$APP/carplay-mu1367-wireless-native-v165t2/STATE" 2>/dev/null)" = installed ] || return 1\n'
 table+=' check "$APP/carplay-mu1367-wireless-native-v165t2/control.sh" '+sha((parent/'control.sh').read_bytes())+' || return 1\n'
 table+=' [ "$(cat "$APP/carplaymaps/PROFILE")" = MU1367/791 ]\n}\n'
 s=template.replace('@TABLE@',table).replace('carplay-mu1367-wireless-native-v161t2',roots[variant])
 # The baseline table intentionally names the parent, not this child.
 s=s.replace('"$APP/'+roots[variant]+'/STATE" 2>/dev/null)" = installed', '"$APP/carplay-mu1367-wireless-native-v165t2/STATE" 2>/dev/null)" = installed',1)
 s=s.replace('"$APP/'+roots[variant]+'/control.sh" '+sha((parent/'control.sh').read_bytes()),'"$APP/carplay-mu1367-wireless-native-v165t2/control.sh" '+sha((parent/'control.sh').read_bytes()),1)
 start=s.index('if regular "$APP/carplay-mu1367-wireless-native/STATE";then');end=s.index('baseline_ok || fail',start);s=s[:start]+s[end:]
 s=s.replace('EXACT_V154_BASELINE_REQUIRED','FINISH_TEST2_BASELINE_INSTALL_AND_REBOOT_FIRST')
 s=s.replace('[ "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" = MU1367/791 ] || fail MU1367_791_ONLY','case "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" in MU1367/791|MU1367/790) :;;*) fail MU1367_PROFILE_REQUIRED;;esac')
 s=s.replace("echo 'Wireless native guidance is enabled; media text/artwork are not integrated.'",'echo "790-only runtime on unchanged test2 parent; see START_HERE.md."')
 s=s.replace('restore(){','''retain_collecting(){
 [ "$(cat "$ROOT/VERSION" 2>/dev/null)" = "$BUILD" ] && baseline_ok || return 1
 for K in $KEYS;do T=$(target "$K");parents "$T" && before_ok "$K" "$T" || return 1;done
 native_mount /mnt/app || return 1
 N=$$;COUNT=0;ARCHIVE=$ROOT.incomplete-$N
 while ! absent "$ARCHIVE";do COUNT=$((COUNT+1));[ "$COUNT" -lt 10000 ] || return 1;N=$((N+1));ARCHIVE=$ROOT.incomplete-$N;done
 mv "$ROOT" "$ARCHIVE" && sync || return 1
 VERIFY=$P/verify
 echo "EXPERIMENTAL_INCOMPLETE_SNAPSHOT_RETAINED=$ARCHIVE"
}
restore(){''',1)
 s=s.replace(' snapshot_ok || fail SNAPSHOT_CORRUPT_NO_FILES_CHANGED', ''' if [ "$(cat "$ROOT/STATE" 2>/dev/null)" = collecting ] && ! regular "$ROOT/BACKUPS_READY";then
  retain_collecting || fail INCOMPLETE_SNAPSHOT_OR_PREIMAGE_CHANGED
  exit 0
 fi
 snapshot_ok || fail SNAPSHOT_CORRUPT_NO_FILES_CHANGED''',1)
 s=s.replace('if regular "$ROOT/STATE";then\n [ "$(cat "$ROOT/VERSION")" = "$BUILD" ]', '''if [ "$(cat "$ROOT/STATE" 2>/dev/null)" = collecting ] && ! regular "$ROOT/BACKUPS_READY";then
 retain_collecting || fail INCOMPLETE_SNAPSHOT_OR_PREIMAGE_CHANGED
fi
if regular "$ROOT/STATE";then
 [ "$(cat "$ROOT/VERSION")" = "$BUILD" ]''',1)
 s=s.replace(' echo "$BUILD" > "$ROOT/VERSION" || fail SAVE_VERSION', ' echo "$BUILD" > "$ROOT/VERSION" || fail SAVE_VERSION\n state collecting || fail COLLECTING_MARKER',1)
 # A prepared transaction which never changed a target needs no install receipt.
 needle=' snapshot_ok || fail SNAPSHOT_CORRUPT_NO_FILES_CHANGED\n'
 s=s.replace(needle,needle+''' if [ "$(cat "$ROOT/STATE" 2>/dev/null)" = prepared ] && targets_match original;then
  mounts && state removed || fail PREPARED_RECOVERY_FAILED
  echo EXPERIMENTAL_PREPARED_SNAPSHOT_RETAINED_REBOOT_REQUIRED
  exit 0
 fi
''')
 if cfg_key:
  s=s.replace('regular(){',geometry+'\nregular(){',1)
  s=s.replace('  if [ "$INDEX" = original ];then H=', '  if [ "$INDEX" = installed ] && [ "$K" = '+cfg_key+' ];then cfg_ok "$T" || return 1;continue;fi\n  if [ "$INDEX" = original ];then H=',1)
  s=s.replace('  else fail UNKNOWN_CHANGED_TARGET_PRESERVED;fi','  elif [ "$K" = '+cfg_key+' ] && cfg_ok "$T";then :\n  else fail UNKNOWN_CHANGED_TARGET_PRESERVED;fi',1)
 if call_key:
  s=s.replace('  if [ "$INDEX" = original ];then H=', '  if [ "$INDEX" = installed ] && [ "$K" = '+call_key+' ];then callpref_ok "$T" || return 1;continue;fi\n  if [ "$INDEX" = original ];then H=',1)
  s=s.replace('  else fail UNKNOWN_CHANGED_TARGET_PRESERVED;fi','  elif [ "$K" = '+call_key+' ] && callpref_ok "$T";then :\n  else fail UNKNOWN_CHANGED_TARGET_PRESERVED;fi',1)
 s=s.replace('MU1367_WIRELESS','MU1367_EXPERIMENTAL_PROFILE')
 build='MU1367-input-profile-'+variant+'-'+sha(s.encode())[:12];s=s.replace('@BUILD@',shlex.quote(build))
 (dest/'control.sh').write_text(s);(dest/'VERSION').write_text(build+'\n');(dest/'geometry.sh').write_text(geometry)
 shutil.copy2(parent/'verify',dest/'verify')
 lines=[]
 for f in sorted(dest.rglob('*')):
  if f.is_file():lines.append('check "$P/'+f.relative_to(dest).as_posix()+'" '+sha(f.read_bytes())+' || return 1')
 (dest/'payload-check.sh').write_text('\n'.join(lines)+'\n')
 controllers[variant]=sha(s.encode());manifests[variant]=dict(build_id=build,recovery_root=roots[variant],controller_sha256=sha(s.encode()),rows=rows,mutable_geometry_key=cfg_key)
(module/'manifest.json').write_text(json.dumps(manifests,indent=2)+'\n')
for name in ('actions.sh','tune.sh'):
 text=(HERE/'src'/name).read_text().replace('@SHA790@',controllers['790']).replace('@GEOMETRY_SHA@',sha(geometry.encode())).replace('@CONTROLLER_SHA@',controllers['790']).replace('@PARENT_SHA@',sha((parent/'control.sh').read_bytes()))
 if name=='actions.sh':
  historical={}
  for tag,archive in [('test3',a.tested_790),('v166',HERE.parent/'dist/v1.6.6-e/CarPlay_Maps_VC_MU1367_790_791_v1.6.6-e.zip')]:
   if tag=='v166':assert sha(archive.read_bytes())=='1c16da70848c6b81ae7020e514c209e3ce25228f965dbccb3c15e14ea77d8343'
   with zipfile.ZipFile(archive) as z:
    for kind,info in json.loads(z.read('Custom/carplay_mu1367_input_profile/manifest.json')).items():
     historical[info['recovery_root']]=sha(z.read('Custom/carplay_mu1367_input_profile/'+kind+'/control.sh'))
    if tag=='v166':
     prior=json.loads(z.read('Custom/carplay_mu1367_wireless_native/manifest.json'))
     historical[Path(prior['recovery_root']).name]=sha(z.read('Custom/carplay_mu1367_wireless_native/control.sh'))
  historical.update({'carplay-mu1367-profile-790-test':'0e7678f4f633fe36c74785be6d8a498a68b3ad6b464ca9ef1d0a19a4a51f0307','carplay-mu1367-profile-790-test2':'ce77b1ab277361f40549b43543079569c2abd00251d73c308b9fa504fb8ee481'})
  roots="known(){ case \"$1\" in\n"+''.join(' '+root+') echo '+pin+';;\n' for root,pin in historical.items())+" *) return 1;;esac; }\n"
  text=text.replace('@HISTORICAL@',roots).replace('@OLD_CHILDREN@',' '.join(k for k in historical if 'wireless-native' not in k))
 (module/name).write_text(text)
# Wrap SD entry points only. Installed 791 payloads remain byte-identical.
wrapper=(sd/'RUN_INSTALL.sh').read_text().replace('carplay_mu1367_release','carplay_mu1367_input_profile').replace('control.sh','actions.sh')
def wrap(action):return wrapper.replace('\"$P/actions.sh\" install \"$P\"','\"$P/actions.sh\" '+action+' \"$P\"')
for label,action in [('790','select-790'),('791','select-791'),('remove','remove'),('status','status')]:
 for name in ['RUN_PROFILE_'+label.upper()+'.sh','Toolbox/scripts/cpmap_profile_'+label+'.sh']:(sd/name).write_text(wrap(action))
for action in ('install','uninstall','recover','restore-oem'):(sd/('Toolbox/scripts/cpmap_suite_'+action+'.sh')).write_text(wrap('base-'+action))
for name,action in [('RUN_INSTALL.sh','install'),('RUN_RESTORE.sh','restore-oem'),('Toolbox/scripts/cpmap_restore.sh','restore-oem'),('Toolbox/scripts/cpmap_restore_core.sh','restore-oem'),('Toolbox/scripts/cpmap_wireless_install.sh','install')]:
 (sd/name).write_text(wrap('base-'+action))
for action in ('uninstall','recover'):(sd/('Toolbox/scripts/cpmap_wireless_'+action+'.sh')).write_text(wrap('base-wireless-'+action))
menu='screen Experimental-Profiles carplay-maps-vc\n\n'
for label,action in [('791: original test2 runtime and input','791'),('790: tested map backend; test2 input','790'),('Remove 790 and restore saved test2 parent','remove'),('Profile and migration status','status')]:
 menu+='script\n    value sys 1 0x0100 \"/eso/hmi/engdefs/scripts/mqb/cpmap_profile_'+action+'.sh\"\n    label \"'+label+'\"\n\n'
for action,label in [('status','790 safe area'),('x-up','790 right 10 px'),('x-down','790 left 10 px'),('y-up','790 down 10 px'),('y-down','790 up 10 px'),('width-up','790 wider 10 px'),('width-down','790 narrower 10 px'),('height-up','790 taller 10 px'),('height-down','790 shorter 10 px'),('reset','790 reset centred safe area'),('card-on','790 wireless turn card On'),('card-off','790 wireless turn card Off')]:
 name='cpmap_profile_tune-'+action+'.sh';(sd/'Toolbox/scripts'/name).write_text(wrap('tune-'+action))
 menu+='script\n    value sys 1 0x0100 \"/eso/hmi/engdefs/scripts/mqb/'+name+'\"\n    label \"'+label+'\"\n\n'
(sd/'Toolbox/GEM/carplay-maps-vc-experimental.esd').write_text(menu)
f=sd/'Toolbox/GEM/carplay-maps-vc.esd'
f.write_text(f.read_text().replace('MU1367 / 791 v1.6.5-e-test2 (wired + wireless CarPlay + Android Auto)','MU1367 / 790 + 791 v1.6.7-e (test2 runtime)'))
f=sd/'Toolbox/GEM/carplay-maps-vc-wireless.esd'
f.write_text(f.read_text().replace('v1.6.5-e-test2 - wireless maps, guidance and tuning','v1.6.7-e SD - original test2 wireless runtime').replace('Enable v1.6.5-e-test2 wireless (reboot)','Install test2 baseline (reboot stages)'))
# Recovery metadata only: the baseline forward-reset algorithm/payloads stay
# intact, while it also archives the child/withdrawn-generation receipts.
oem=custom/'carplay_mu1367_oem_reset/control.sh'
text=oem.read_text();old=next(line for line in text.splitlines() if line.startswith('LAYERS='))
extra=list(historical)+['carplay-mu1367-profile-790-v167']
new=old[:-1]+' '+' '.join(extra)+"'"
oem.write_text(text.replace(old,new,1))
oem_manifest=oem.parent/'manifest.json'
info=json.loads(oem_manifest.read_text())
info.update(controller_sha256=sha(oem.read_bytes()),layers_archived=shlex.split(new.split('=',1)[1])[0].split())
oem_manifest.write_text(json.dumps(info,indent=2)+'\n')
# SD-only allowlisted evidence for the optional 790 child. No receiver or HMI
# payload changes and no recursive copying of pairing/hotspot configuration.
for relative in ('collect-wireless.sh','Toolbox/scripts/cpmap_wireless_collect_data.sh'):
 f=sd/relative;s=f.read_text()
 s=s.replace('for F in omonob-791-input.log','for F in omonob-790-input.log omonob-791-input.log')
 s=s.replace('omonob-791-input.pid carplay-dio-manager.pid','omonob-790-input.pid omonob-791-input.pid carplay-dio-manager.pid')
 extension='''for L in carplay-mu1367-profile-790-v167 carplay-mu1367-profile-790-v166 carplay-mu1367-profile-791-v166 carplay-mu1367-wireless-native-v166;do
 mkdir -p "$OUT/state/$L" || exit 1
 for F in STATE VERSION installed.index installed.index.sha256 backup.index backup.index.sha256;do
  copy_file "$APP/$L/$F" "$OUT/state/$L/$F"
 done
done
copy_file "$APP/carplaymaps/PROFILE" "$OUT/state/PROFILE"
copy_file "$M/mnt/persist/altscreen.geom" "$OUT/state/altscreen.geom"
'''
 assert s.count('sync\necho "WIRELESS_DIAG_OK=')==1
 f.write_text(s.replace('sync\necho "WIRELESS_DIAG_OK=',extension+'sync\necho "WIRELESS_DIAG_OK='))
# Rebind existing SD-only shared asset guards after the recovery metadata and
# new child have been added. The parent runtime/manifest/guard are untouched.
checks=[]
for f in sorted(custom.rglob('*')):
 if f.is_file() and f.name!='payload-check.sh' and 'source' not in f.relative_to(custom).parts:
  checks.append('"$P/verify" "$CUSTOM_CHECK/'+f.relative_to(custom).as_posix()+'" '+sha(f.read_bytes())+' || return 1')
for f in custom.glob('*/payload-check.sh'):
 if f.parent!=parent:f.write_text('CUSTOM_CHECK=${P%/*}\n'+'\n'.join(checks)+'\n')
top=json.loads((sd/'MU1367_RELEASE_MANIFEST.json').read_text());top.update(version='1.6.7-e',experimental=True,prerelease=True,supported_clusters=['790','791'],default_cluster='791',runtime_baseline='1.6.5-e-test2',baseline_zip_sha256=sha(a.baseline.read_bytes()),profiles=manifests)
(sd/'MU1367_RELEASE_MANIFEST.json').write_text(json.dumps(top,indent=2)+'\n');(sd/'WIRELESS_VERSION').write_text('1.6.7-e\n')
(out/'manifest.json').write_text(json.dumps(top,indent=2)+'\n')
print(json.dumps(dict(passed=True,staged=True,version='1.6.7-e',runtime_baseline=base['version'],profile_targets=len(manifests['790']['rows']))))
