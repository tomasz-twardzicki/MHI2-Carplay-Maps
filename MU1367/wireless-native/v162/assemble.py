#!/usr/bin/env python3
"""Create an isolated v1.6.2-e test SD from exact stable 1.6.1 and owned builds."""
import argparse,hashlib,json,shlex,shutil,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
p=argparse.ArgumentParser()
for n in ('baseline','components','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);sd=out/'sd-card'
assert sha(a.baseline.read_bytes())=='38279833ed495a057f4a513d568c5cf94a9f8d335a38773ebb580d09dcee47c1'
with zipfile.ZipFile(a.baseline) as z:
 z.extractall(sd)
 for i in z.infolist():
  if not i.is_dir() and i.external_attr>>16&0o777:(sd/i.filename).chmod(i.external_attr>>16&0o777)
custom=sd/'Custom';layer=custom/'carplay_mu1367_wireless_native';payload=layer/'payload';release=custom/'carplay_mu1367_release'
manifest=json.loads((layer/'manifest.json').read_text());stable=json.loads((sd/'MU1367_RELEASE_MANIFEST.json').read_text());legacy=stable['migration_roots']
oldroot=Path(manifest['recovery_root']).name;newroot='carplay-mu1367-wireless-native-v162';version='1.6.2-e-test1'
oldcontrol=(layer/'control.sh').read_text();oldtable=oldcontrol[oldcontrol.index('JXE_SHA='):oldcontrol.index('regular(){')]
components=json.loads((a.components/'COMPONENTS.json').read_text())
for name,h in components.items():assert sha((a.components/name).read_bytes())==h
rows=manifest['rows']
for row in rows:
 if row['kind']=='copy' and row['source'] in components:(payload/row['source']).write_bytes((a.components/row['source']).read_bytes())
script=payload/'start-wireless-maps.sh'
s=script.read_text().replace(oldroot,newroot).replace('CPMAP_WCP_INPUT=161','CPMAP_WCP_INPUT=162').replace(manifest['components']['libcpmap-wcp-tap.so'],components['libcpmap-wcp-tap.so']);script.write_text(s)
for name,target,before,mode in [('CarPlayMU1367Audio.jar','/mnt/app/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar','c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3','644'),('wireless-artwork-fetch','/mnt/app/carplay-mu1367-wireless-media/wireless-artwork-fetch','absent','755')]:
 (payload/name).write_bytes((a.components/name).read_bytes());rows.append(dict(key='k%02d'%len(rows),source=name,target=target,before=before,mode=mode,kind='copy'))
for r in rows:
 if r['kind']=='copy':r['sha256']=sha((payload/r['source']).read_bytes())
quote=shlex.quote
table='JXE_SHA=09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a\nKEYS='+quote(' '.join(r['key'] for r in rows))+'\nREVERSE_KEYS='+quote(' '.join(r['key'] for r in reversed(rows)))+'\n'
for fn,field in [('target','target'),('mode','mode')]:
 table+=fn+'(){ case "$1" in\n'
 for r in rows:table+=' '+r['key']+') echo "'+('$M' if fn=='target' else '')+r[field]+'";;\n'
 table+=' *) return 1;;esac; }\n'
table+='before_ok(){ case "$1" in\n'
for r in rows:
 before=r['before'];command='absent "$2"' if before=='absent' else 'regular "$2" || absent "$2"' if before=='optional' else 'regular "$2" && /bin/ksh -n "$2"' if before=='boot' else 'check "$2" '+quote(before)
 table+=' '+r['key']+') '+command+';;\n'
table+=' *) return 1;;esac; }\nstage_payload(){ case "$1" in\n'
for r in rows:
 kind=r['kind']
 if kind=='copy':command='cp "$P/payload/'+r['source']+'" "$2" && check "$2" '+r['sha256']
 elif kind=='missing':command='return 0'
 elif kind in ('si','connectivity'):command='"$P/config-patch" '+kind+' "$(target "$1")" "$2"'
 else:command='/bin/sh "$P/merge-wireless.sh" '+kind+' "$(target "$1")" "$2" && '+('/bin/ksh -n "$2"' if kind=='lsd' else 'regular "$2"')
 table+=' '+r['key']+') '+command+';;\n'
table+=' *) return 1;;esac; }\n'+oldtable[oldtable.index('baseline_ok(){'):]
controller=(HERE.parent/'v161/control.sh').read_text().replace(oldroot,newroot)
controller=controller.replace('baseline_ok || fail EXACT_V154_BASELINE_REQUIRED','if regular "$APP/'+oldroot+'/STATE";then\n [ "$(cat "$APP/'+oldroot+'/STATE")" = removed ] || fail REMOVE_V161_STABLE_AND_REBOOT_FIRST\nfi\nbaseline_ok || fail EXACT_V154_BASELINE_REQUIRED')
controller=controller.replace('Wireless native guidance is enabled; media text/artwork are not integrated.','Wireless maps, guidance, text and artwork are integrated; vehicle validation pending.')
build='MU1367-wireless-native-v162-'+sha((json.dumps(rows,sort_keys=True)+table+controller).encode())[:12]
(layer/'control.sh').write_text(controller.replace('@TABLE@',table).replace('@BUILD@',quote(build)));(layer/'VERSION').write_text(build+'\n')
manifest.update(version=version,build_id=build,recovery_root='/mnt/app/'+newroot,components=components,experimental=True,prerelease=True,on_unit_validated=False,installation_tested=False,component_build_ids_retained=False)
manifest['wireless_features'].update(media_text=True,artwork=True,playback_state=True,play_position=True,oem_icon_label='Volkswagen',alt_sender_priority_floor=14,input_adapter_priority_floor=14)
(layer/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
legacy[newroot]=dict(version=version,build_id=build,controller_sha256=sha((layer/'control.sh').read_bytes()),targets={r['key']:r['target'] for r in rows})
compat=table+'\nWIRELESS_ROOTS='+quote(' '.join(legacy))+'\nCURRENT_WIRELESS_ROOT='+quote(newroot)+'\nwireless_controller(){ case "$1" in\n'
for root,m in legacy.items():compat+=' '+root+') echo '+m['controller_sha256']+';;\n'
compat+=' *) return 1;;esac; }\nlegacy_keys(){ case "$1" in\n'
for root,m in legacy.items():compat+=' '+root+') echo '+quote(' '.join(m['targets']))+';;\n'
compat+=' *) return 1;;esac; }\nlegacy_target(){ case "$1:$2" in\n'
for root,m in legacy.items():
 for key,target in m['targets'].items():compat+=' '+root+':'+key+') echo "$M'+target+'";;\n'
compat+=' *) return 1;;esac; }\n';(release/'compatibility.sh').write_text(compat)
s=(release/'control.sh').read_text().replace('1.6.1',version).replace('1_6_1','1_6_2_E_TEST1').replace('release-v161','release-v162');(release/'control.sh').write_text(s)
# Preserve the old generation as a recognized recovery root; protect direct base
# actions while the new generation exists, and include it in OEM archival.
for f in sd.rglob('*.sh'):
 if f.is_relative_to(layer) or f.is_relative_to(release):continue
 s=f.read_text()
 if 'for L in carplay-mu1367-wireless-native ' in s:s=s.replace(oldroot+';',oldroot+' '+newroot+';')
 if f.name=='control.sh' and f.parent.name=='carplay_mu1367_oem_reset':s=s.replace(oldroot+"'",oldroot+' '+newroot+"'")
 f.write_text(s)
oem=custom/'carplay_mu1367_oem_reset';m=json.loads((oem/'manifest.json').read_text());m['controller_sha256']=sha((oem/'control.sh').read_bytes());m['layers_archived']=list(dict.fromkeys(m['layers_archived']+[newroot]));(oem/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
for name in ('collect-wireless.sh','Toolbox/scripts/cpmap_wireless_collect_data.sh'):
 f=sd/name;s=f.read_text().replace(' '+oldroot+' carplay-mu1367-guidance-v3;',' '+oldroot+' '+newroot+' carplay-mu1367-guidance-v3;').replace('"$APP/'+oldroot+'/verify"','"$APP/'+newroot+'/verify"')
 s=s.replace('for F in latest.bin session.state','for F in nowplaying.bin cover.bin latest.bin session.state')
 s=s.replace('sync\necho "WIRELESS_DIAG_OK=', '''copy_file "$M/ramdisk/wcp-now-playing.status" "$OUT/state/wcp-now-playing.status"
if regular "$APP/carplay-mu1367-wireless-native-v162/verify";then
 {
  echo '=== wireless media fingerprints'
  for F in /mnt/app/carplay-mu1367-wireless-media/wireless-artwork-fetch /mnt/app/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar;do
   echo "$F";"$APP/carplay-mu1367-wireless-native-v162/verify" "$M$F"
  done
 } >> "$OUT/summary.txt" 2>&1
fi
sync
echo "WIRELESS_DIAG_OK=''')
 f.write_text(s)
for f in (sd/'Toolbox/GEM').glob('carplay-maps-vc*.esd'):
 s=f.read_text().replace('v1.6.1','v'+version);f.write_text(s)
for name in ('README.md','START_HERE.md','RELEASE-NOTES.md'):(sd/name).write_text((HERE/name).read_text())
(sd/'WIRELESS_VERSION').write_text(version+'\n')
source=layer/'source/v162';shutil.copytree(HERE,source,ignore=shutil.ignore_patterns('__pycache__','VERIFICATION.json'))
stable.update(version=version,experimental=True,prerelease=True,wireless_runtime_build=build,wireless_runtime_components=components,migration_roots=legacy,runtime_promoted_without_rebuild=False,vehicle_validation={'scope':'Pending vehicle test; successful v1.6.1 is the exact baseline.'})
(sd/'MU1367_RELEASE_MANIFEST.json').write_text(json.dumps(stable,indent=2)+'\n');(out/'manifest.json').write_text(json.dumps(stable,indent=2)+'\n')
# Every writable Custom payload is checked by the same comprehensive SD guard.
lines=[]
for f in sorted(custom.rglob('*')):
 if f.is_file() and f.name!='payload-check.sh' and 'source' not in f.relative_to(custom).parts:
  lines.append('"$P/verify" "$CUSTOM_CHECK/'+f.relative_to(custom).as_posix()+'" '+sha(f.read_bytes())+' || return 1')
body='CUSTOM_CHECK=${P%/*}\n'+'\n'.join(lines)+'\n'
for f in custom.glob('*/payload-check.sh'):
 if f.parent!=layer:f.write_text(body)
checks=[]
for f in sorted(layer.rglob('*')):
 if f.is_file() and f.name not in ('payload-check.sh','manifest.json') and 'source' not in f.relative_to(layer).parts:
  checks.append('check "$P/'+f.relative_to(layer).as_posix()+'" '+sha(f.read_bytes())+' || return 1')
(layer/'payload-check.sh').write_text('\n'.join(checks)+'\n')
for f in sd.rglob('*.sh'):f.chmod(0o755)
print(json.dumps(dict(staged=str(out),version=version,build_id=build,rows=len(rows))))
