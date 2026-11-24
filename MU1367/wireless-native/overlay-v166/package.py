#!/usr/bin/env python3
"""Stage reversible input/profile experiments on the complete v1.6.3-e SD."""
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
for n in ('baseline','components','upstream','output'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--baseline-sha256',required=True)
p.add_argument('--tested-overlay',type=Path,required=True)
p.add_argument('--upstream-790-runtime',action='store_true',help='Test 2: pair the 790 receiver with its upstream core, bridge and supervisor.')
p.add_argument('--media790-components',type=Path,help='Test 3: audited metadata-only observer and 790 bootstrap.')
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);sd=out/'sd-card'
media790=None
if a.media790_components:
 assert a.upstream_790_runtime
 media790=json.loads((a.media790_components/'VERIFICATION.json').read_text());assert media790['passed']
 assert not media790['video_changes'] and not media790['audio_changes']
 for name,pin in media790['files'].items():assert sha((a.media790_components/name).read_bytes())==pin
generation=3 if media790 else 2 if a.upstream_790_runtime else 1
assert sha(a.baseline.read_bytes())==a.baseline_sha256
assert sha(a.tested_overlay.read_bytes())=='202ab34e7339324ca204e6ea64ef754d94a1174f76e9d139c41d59bfc28d3359'
assert sha(a.upstream.read_bytes())=='5b31522046f1abf397fc62723dc7a4a1c3a37e90559d3d48409c8e322b1a9cce'
proof=json.loads((a.components/'VERIFICATION.json').read_text());assert proof['passed']
with zipfile.ZipFile(a.baseline) as z:
 z.extractall(sd)
 for i in z.infolist():
  if not i.is_dir():(sd/i.filename).chmod((i.external_attr>>16&0o777) or 0o644)
custom=sd/'Custom';parent=custom/'carplay_mu1367_wireless_native';module=custom/'carplay_mu1367_input_profile';module.mkdir()
base=json.loads((parent/'manifest.json').read_text());assert base['version']=='1.6.6-e';by_target={r['target']:r for r in base['rows']}
template=(HERE.parent/'v161/control.sh').read_text()
factory_jxe='09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a'
roots={'790':'carplay-mu1367-profile-790-test','791':'carplay-mu1367-overlay-touch-test'}
legacy_roots=[]
if a.upstream_790_runtime:
 legacy_roots=[roots['790']]
 roots['790']='carplay-mu1367-profile-790-test2'
if media790:
 legacy_roots+=['carplay-mu1367-profile-790-test2','carplay-mu1367-profile-790-test3','carplay-mu1367-overlay-touch-test'];roots['790']='carplay-mu1367-profile-790-v166';roots['791']='carplay-mu1367-overlay-touch-v166'
controllers={};manifests={}
with zipfile.ZipFile(a.upstream) as up:
 prefix='SD_ROOT/carplay/payload/wireless/profiles/AID10.5-17PM/'
 native790={n:up.read(prefix+n) for n in ('wcp_receiver','wireless-entry','wireless-receiver-exec','libomonob-wireless-maps.so','v75-wireless-display.conf','cluster-profile','altscreen.conf','altscreen.geom')}
 runtime790={n:up.read('SD_ROOT/carplay/payload/'+sub+'/'+n) for n,sub in [('core.so','profiles/MU1367/790'),('altscreen-most-bridge','common'),('carplay-cluster-supervisor','common')]}
stock790=HERE.parents[2]/'MU1102/790_AID10.5/payload/profiles/MU1102/790/core.so'
assert sha(stock790.read_bytes())=='a4bb6ce6e9e63a05cc1b6be20c5257983fb4dcbdf89f55528438acbd8edba8ee'
geometry=(HERE/'src/geometry.sh').read_text()
for variant in ('790','791'):
 dest=module/variant;payload=dest/'payload';payload.mkdir(parents=True);rows=[]
 def add(name,target,data,mode='644',before=None):
  key='k%02d'%len(rows);(payload/name).write_bytes(data)
  if before is None:
   row=by_target[target];before=row['sha256']
  rows.append(dict(key=key,source=name,target=target,mode=mode,before=before,sha256=sha(data)))
 for name in ('CarPlayWireless-CP-55915411.jar','CarPlayWireless-Touch-55915411.jar'):
  assert sha((a.components/name).read_bytes())==proof['files'][name]
  add(name,'/mnt/app/eso/hmi/lsd/jars/'+name,(a.components/name).read_bytes())
 cfg_key=None;call_key=None
 if variant=='790':
  native790['altscreen.conf']=native790['altscreen.conf'].replace(b'nsafex=42\n',b'nsafex=202\n')
  for name,data in native790.items():
   if media790 and name=='wireless-receiver-exec':data=(a.media790_components/name).read_bytes()
   target={'wcp_receiver':'/mnt/ota/wcp_receiver','wireless-entry':'/mnt/app/carplaymaps/wireless-entry','wireless-receiver-exec':'/mnt/app/carplaymaps/wireless-receiver-exec','libomonob-wireless-maps.so':'/mnt/app/carplaymaps/libomonob-wireless-maps.so','v75-wireless-display.conf':'/mnt/persist/v75-wireless-display.conf','cluster-profile':'/mnt/persist/omonob-phone/cluster-profile','altscreen.conf':'/mnt/persist/altscreen.conf','altscreen.geom':'/mnt/persist/altscreen.geom'}[name]
   add(name,target,data,'755' if name in ('wcp_receiver','wireless-entry','wireless-receiver-exec') else '644','optional' if name in ('altscreen.conf','altscreen.geom') else None)
   if name=='altscreen.conf':cfg_key=rows[-1]['key']
  add('core.so','/mnt/app/carplaymaps/core.so',runtime790['core.so'] if a.upstream_790_runtime else stock790.read_bytes(),before='core')
  if a.upstream_790_runtime:
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
   add('libcpmap-wcp-media790.so','/mnt/app/carplaymaps/libcpmap-wcp-media790.so',(a.media790_components/'libcpmap-wcp-media790.so').read_bytes(),before='absent')
   add('call-release-on','/mnt/persist/wcp_btaudio_release',b'1\n',before='callpref');call_key=rows[-1]['key']
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
 table+='baseline_ok(){\n [ "$(cat "$APP/carplay-mu1367-wireless-native-v166/STATE" 2>/dev/null)" = installed ] || return 1\n'
 table+=' check "$APP/carplay-mu1367-wireless-native-v166/control.sh" '+sha((parent/'control.sh').read_bytes())+' || return 1\n'
 table+=' [ "$(cat "$APP/carplaymaps/PROFILE")" = MU1367/791 ]\n}\n'
 s=template.replace('@TABLE@',table).replace('carplay-mu1367-wireless-native-v161t2',roots[variant])
 # The baseline table intentionally names the parent, not this child.
 s=s.replace('"$APP/'+roots[variant]+'/STATE" 2>/dev/null)" = installed', '"$APP/carplay-mu1367-wireless-native-v166/STATE" 2>/dev/null)" = installed',1)
 s=s.replace('"$APP/'+roots[variant]+'/control.sh" '+sha((parent/'control.sh').read_bytes()),'"$APP/carplay-mu1367-wireless-native-v166/control.sh" '+sha((parent/'control.sh').read_bytes()),1)
 start=s.index('if regular "$APP/carplay-mu1367-wireless-native/STATE";then');end=s.index('baseline_ok || fail',start);s=s[:start]+s[end:]
 s=s.replace('EXACT_V154_BASELINE_REQUIRED','FINISH_NATIVE_V163_INSTALL_AND_REBOOT_FIRST')
 s=s.replace('[ "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" = MU1367/791 ] || fail MU1367_791_ONLY','case "$(cat "$APP/carplaymaps/PROFILE" 2>/dev/null)" in MU1367/791|MU1367/790) :;;*) fail MU1367_PROFILE_REQUIRED;;esac')
 s=s.replace("echo 'Wireless native guidance is enabled; media text/artwork are not integrated.'",'echo "Experimental input/profile test; use its START_HERE.md."')
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
actions=(HERE/'src'/('actions-v2.sh' if a.upstream_790_runtime else 'actions.sh')).read_text().replace('@SHA790@',controllers['790']).replace('@SHA791@',controllers['791']);(module/'actions.sh').write_text(actions)
if media790:
 actions=actions.replace('carplay-mu1367-profile-790-test2','carplay-mu1367-profile-790-test3')
 actions=actions.replace(' legacy790) echo "$APP/carplay-mu1367-profile-790-test";;',' legacy790) echo "$APP/carplay-mu1367-profile-790-test";;\n legacy790test2) echo "$APP/carplay-mu1367-profile-790-test2";;')
 actions=actions.replace(' legacy790) echo 0e7678f4f633fe36c74785be6d8a498a68b3ad6b464ca9ef1d0a19a4a51f0307;;',' legacy790) echo 0e7678f4f633fe36c74785be6d8a498a68b3ad6b464ca9ef1d0a19a4a51f0307;;\n legacy790test2) echo ce77b1ab277361f40549b43543079569c2abd00251d73c308b9fa504fb8ee481;;')
 actions=actions.replace('for N in legacy790 790 791;do','for N in legacy790 legacy790test2 790 791;do')
 actions=actions.replace('case "$ACTION" in tune-*)','case "$ACTION" in calls-*) case "${ACTION#calls-}" in on) V=profiles;;off) V=keep;;status) V=status;;*) fail INVALID_ACTION;;esac;exec /bin/ksh "${P%/*}/carplay_mu1367_wireless_native/gps-preference.sh" bt-release "$V";;esac\ncase "$ACTION" in tune-*)')
 with zipfile.ZipFile(a.tested_overlay) as tested:
  legacy3=sha(tested.read('Custom/carplay_mu1367_input_profile/790/control.sh'))
  legacy791=sha(tested.read('Custom/carplay_mu1367_input_profile/791/control.sh'))
 actions=actions.replace('carplay-mu1367-profile-790-test3','carplay-mu1367-profile-790-v166').replace('carplay-mu1367-overlay-touch-test','carplay-mu1367-overlay-touch-v166')
 actions=actions.replace(' legacy790) echo "$APP/', ' legacy790test3) echo "$APP/carplay-mu1367-profile-790-test3";;\n legacy791) echo "$APP/carplay-mu1367-overlay-touch-test";;\n legacy790) echo "$APP/',1)
 actions=actions.replace(' legacy790) echo 0e7678', ' legacy790test3) echo '+legacy3+';;\n legacy791) echo '+legacy791+';;\n legacy790) echo 0e7678',1)
 actions=actions.replace('for N in legacy790 legacy790test2 790 791;do','for N in legacy790 legacy790test2 legacy790test3 legacy791 790 791;do')
 (module/'actions.sh').write_text(actions)
 calls=(HERE/'src/calls.sh').read_text().replace('@CONTROLLER_SHA@',controllers['790']).replace('@EMPTY_SHA@',sha(b'')).replace('@ON_SHA@',sha(b'1\n'))
 (module/'calls.sh').write_text(calls)
tune=(HERE/'src/tune.sh').read_text().replace('@GEOMETRY_SHA@',sha(geometry.encode())).replace('@CONTROLLER_SHA@',controllers['790'])
if a.upstream_790_runtime:tune=tune.replace('carplay-mu1367-profile-790-test',roots['790'])
(module/'tune.sh').write_text(tune)
(module/'manifest.json').write_text(json.dumps(manifests,indent=2)+'\n')
wrapper=(sd/'RUN_INSTALL.sh').read_text().replace('carplay_mu1367_release','carplay_mu1367_input_profile').replace('control.sh','actions.sh')
def wrap(action):return wrapper.replace('"$P/actions.sh" install "$P"','"$P/actions.sh" '+action+' "$P"')
for label,action in [('790','select-790'),('791','select-791'),('remove','remove'),('status','status')]:
 (sd/('Toolbox/scripts/cpmap_profile_'+label+'.sh')).write_text(wrap(action))
 (sd/('RUN_PROFILE_'+label.upper()+'.sh')).write_text(wrap(action))
for action in ('install','uninstall','recover','restore-oem'):
 code=wrap('base-'+action);(sd/('Toolbox/scripts/cpmap_suite_'+action+'.sh')).write_text(code)
for name,action in [('RUN_INSTALL.sh','install'),('RUN_RESTORE.sh','restore-oem'),('Toolbox/scripts/cpmap_restore.sh','restore-oem'),('Toolbox/scripts/cpmap_restore_core.sh','restore-oem')]:
 (sd/name).write_text(wrap('base-'+action))
for action in ('uninstall','recover'):(sd/('Toolbox/scripts/cpmap_wireless_'+action+'.sh')).write_text(wrap('base-wireless-'+action))
(sd/'Toolbox/scripts/cpmap_wireless_install.sh').write_text(wrap('base-install'))
menu='screen carplay-maps-vc-experimental Customization\n\n'
for label,action in [('791: OEM overlay touch test','791'),('790: maps + playback information + OEM touch' if media790 else '790: upstream runtime comparison + OEM touch' if a.upstream_790_runtime else '790: experimental map profile + OEM touch','790'),('Remove experiment and restore saved 791 runtime','remove'),('Experimental profile status','status')]:
 menu+='script\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_profile_'+action+'.sh"\n    label "'+label+'"\n\n'
for action,label in [('status','Show 790 safe area'),('x-up','790: safe area right 10 px'),('x-down','790: safe area left 10 px'),('y-up','790: safe area down 10 px'),('y-down','790: safe area up 10 px'),('width-up','790: safe area wider 10 px'),('width-down','790: safe area narrower 10 px'),('height-up','790: safe area taller 10 px'),('height-down','790: safe area shorter 10 px'),('reset','790: reset centred safe area'),('card-on','790: wireless turn card On'),('card-off','790: wireless turn card Off')]:
 name='cpmap_profile_tune-'+action+'.sh';(sd/'Toolbox/scripts'/name).write_text(wrap('tune-'+action))
 menu+='script\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/'+name+'"\n    label "'+label+'"\n\n'
if media790:
 for action,label in [('status','790: show call handoff preference'),('on','790: prefer CarPlay calls and media (test)'),('off','790: keep OEM Bluetooth calls and media')]:
  name='cpmap_profile_calls-'+action+'.sh';(sd/'Toolbox/scripts'/name).write_text(wrap('calls-'+action))
  menu+='script\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/'+name+'"\n    label "'+label+'"\n\n'
(sd/'Toolbox/GEM/carplay-maps-vc-experimental.esd').write_text(menu)
oem=custom/'carplay_mu1367_oem_reset';s=(oem/'control.sh').read_text();start=s.index("LAYERS='")+8;end=s.index("'",start)
s=s[:end]+' '+' '.join(list(roots.values())+legacy_roots)+s[end:]
old_build=s.split('BUILD=')[1].split('\n')[0];new_build='MU1367-oem-reset-overlay790-'+sha(s.encode())[:12];s=s.replace('BUILD='+old_build,'BUILD='+new_build)
(oem/'control.sh').write_text(s)
om=json.loads((oem/'manifest.json').read_text());om['build_id']=new_build;om['controller_sha256']=sha(s.encode());om['layers_archived']+=list(roots.values())+legacy_roots;(oem/'manifest.json').write_text(json.dumps(om,indent=2)+'\n')
for f in sd.rglob('*.sh'):f.chmod(0o755)
# Parent SD guards cover new modules as well; the original wireless controller
# and its local guard remain unchanged so its snapshot identity stays usable.
lines=[]
for f in sorted(custom.rglob('*')):
 if f.is_file() and f.name!='payload-check.sh' and 'source' not in f.relative_to(custom).parts and f.relative_to(custom).parts[0].startswith('carplay_'):
  lines.append('"$P/verify" "$CUSTOM_CHECK/'+f.relative_to(custom).as_posix()+'" '+sha(f.read_bytes())+' || return 1')
for f in custom.glob('*/payload-check.sh'):
 if f.parent!=parent:f.write_text('CUSTOM_CHECK=${P%/*}\n'+'\n'.join(lines)+'\n')
(out/'PROFILE-MANIFEST.json').write_text(json.dumps(dict(experimental=True,published=False,baseline='1.6.6-e',profiles=manifests,input=proof,generation=generation,media790=media790,upstream_790_runtime=a.upstream_790_runtime,upstream_archive_sha256=sha(a.upstream.read_bytes())),indent=2)+'\n')
top=json.loads((sd/'MU1367_RELEASE_MANIFEST.json').read_text());top.update(supported_clusters=['790','791'],profile_support=manifests);(sd/'MU1367_RELEASE_MANIFEST.json').write_text(json.dumps(top,indent=2)+'\n');(out/'manifest.json').write_text(json.dumps(top,indent=2)+'\n')
print(json.dumps(dict(staged=str(out),profiles={k:len(v['rows']) for k,v in manifests.items()})))
