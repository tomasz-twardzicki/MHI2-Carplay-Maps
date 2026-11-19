#!/usr/bin/env python3
"""Stage v161 over the exact released 1.5.4, retaining test1's pinned inputs."""
import argparse,hashlib,json,shlex,shutil,sys,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parent
sys.path.insert(0,str(OLD))
from archive_fix import apply as archive_fix
from diagnostics import add as diagnostics
sha=lambda b:hashlib.sha256(b).hexdigest()
quote=lambda s:shlex.quote(str(s))
p=argparse.ArgumentParser()
for name in ('baseline-zip','test1-zip','components','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);sd=out/'sd-card'
provenance=json.loads((HERE/'PROVENANCE.json').read_text())
assert sha(a.baseline_zip.read_bytes())==provenance['baseline_zip_sha256']
assert sha(a.test1_zip.read_bytes())=='498e2aee7d157405f2cda0566c9436e177931ce06fc55d2f8dbd219d63b3663b'
with zipfile.ZipFile(a.baseline_zip) as z:z.extractall(sd)
custom=sd/'Custom';layer=custom/'carplay_mu1367_wireless_native';payload=layer/'payload'
with zipfile.ZipFile(a.test1_zip) as z:
 prefix='Custom/carplay_mu1367_wireless_native/'
 for name in z.namelist():
  if name.startswith(prefix) and not name.startswith(prefix+'source/') and not name.endswith('/'):
   f=sd/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(name))
 m=json.loads(z.read(prefix+'manifest.json'))
rows=m['rows']
for row in rows:assert sha((payload/row['source']).read_bytes())==row['sha256']
components=json.loads((a.components/'COMPONENTS.json').read_text())
for name,h in components.items():assert sha((a.components/name).read_bytes())==h
for name in ('wireless-receiver-exec','carplay-cluster-supervisor'):(payload/name).write_bytes((a.components/name).read_bytes())
(payload/'wcp_ctl.sh').write_bytes((HERE/'src/runtime/wcp_ctl.sh').read_bytes())
s=(payload/'wcp_autostart.sh').read_text().replace('WCP_FPS=30','WCP_FPS=40').replace('WCP_VIDEO_FPS=30','WCP_VIDEO_FPS=40')
(payload/'wcp_autostart.sh').write_text(s)
# Suppress only the old adapter's fixed every-five-frames IDR request. All
# resume and decoder recovery requests continue through the original adapter.
s=(payload/'start-wireless-maps.sh').read_text()
s=s.replace(' "$ROOT/wireless-entry" --serve', ' CPMAP_WCP_INPUT=161 LD_PRELOAD="$ROOT/libcpmap-wcp-tap.so" "$ROOT/wireless-entry" --serve')
verify='''VERIFY=/mnt/app/carplay-mu1367-wireless-native-v161t2/verify
"$VERIFY" "$ROOT/wireless-entry" 54c765fc74b00ee06e9d740384817b8c39740a96c1b012a3057d990878a614e8 || exit 1
"$VERIFY" "$ROOT/libcpmap-wcp-tap.so" @TAP@ || exit 1
'''.replace('@TAP@',components['libcpmap-wcp-tap.so'])
s=s.replace('test -x "$ROOT/wireless-entry" || exit 1\n','test -x "$ROOT/wireless-entry" || exit 1\n'+verify)
(payload/'start-wireless-maps.sh').write_text(s)
for row in rows:
 if row['source']=='carplay-cluster-supervisor':row['before']=sha((custom/'carplay_mu1367_settings/carplay-cluster-supervisor').read_bytes())
 row['sha256']=sha((payload/row['source']).read_bytes())
def add(name,target,before='absent',mode='644'):
 (payload/name).write_bytes((a.components/name).read_bytes())
 rows.append(dict(key='k%02d'%len(rows),source=name,target=target,before=before,mode=mode,kind='copy',sha256=components[name]))
add('libcpmap-wcp-tap.so','/mnt/app/carplaymaps/libcpmap-wcp-tap.so')
add('wireless-tune','/mnt/app/carplaymaps/wireless-tune',mode='755')
add('altscreen-most-bridge','/mnt/app/carplaymaps/altscreen-most-bridge',sha((custom/'carplay_mu1367_guidance_v3/6/altscreen-most-bridge').read_bytes()),'755')
add('CarPlayMU1367Guidance.jar','/mnt/app/eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar',sha((custom/'carplay_mu1367_guidance_v3/6/CarPlayMU1367Guidance.jar').read_bytes()))
baseline_checks=m['baseline_checks']
for path,name in [('/mnt/app/carplaymaps/altscreen-most-bridge','carplay_mu1367_guidance_v3/6/altscreen-most-bridge'),('/mnt/app/carplaymaps/dio_manager.wrapper.sh','carplay_mu1367_settings/dio_manager.wrapper.sh'),('/mnt/app/eso/bin/apps/dio_manager','carplay_mu1367_settings/dio_manager.wrapper.sh'),('/mnt/app/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar','carplay_mu1367_artwork/CarPlayMU1367Audio.jar')]:baseline_checks[path]=sha((custom/name).read_bytes())
pairs=set();versions=set()
for folder in ('carplay_mu1367_guidance_v3','carplay_mu1367_v3_turn_cards'):
 for variant in ('6','6-road','7','7-road'):
  base=custom/folder/variant;pairs.add((sha((base/'core.so').read_bytes()),sha((base/'VCMenu.jar').read_bytes())))
  if folder=='carplay_mu1367_guidance_v3':versions.add((base/'VERSION').read_text().strip())
proof=json.loads((OLD/'FIRMWARE-VERIFICATION.json').read_text())
# Reuse the already exercised table generator, with only this release's exact
# preimages, row list and source-owned recovery template as its inputs.
original=(OLD/'build.py').read_text()
start=original.index('    table = "JXE_SHA="');end=original.index('    build = "MU1367-wireless-native-"',start)
code='\n'.join(line[4:] for line in original[start:end].splitlines())
exec(code)
controller=(OLD/'control.sh').read_text().replace('pinned v1.5.3 baseline','pinned v1.5.4 baseline').replace('ROOT=$APP/carplay-mu1367-wireless-native\n','ROOT=$APP/carplay-mu1367-wireless-native-v161t2\n').replace('EXACT_V153_BASELINE_REQUIRED','EXACT_V154_BASELINE_REQUIRED').replace('Wireless guidance/media text/artwork are not integrated in test1.','Wireless native guidance is enabled; media text/artwork are not integrated.')
controller=controller.replace('baseline_ok || fail EXACT_V154_BASELINE_REQUIRED','''if regular "$APP/carplay-mu1367-wireless-native/STATE";then
 [ "$(cat "$APP/carplay-mu1367-wireless-native/STATE")" = removed ] || fail REMOVE_TEST1_AND_REBOOT_FIRST
fi
if regular "$APP/carplay-mu1367-wireless-native-v161/STATE";then
 [ "$(cat "$APP/carplay-mu1367-wireless-native-v161/STATE")" = removed ] || fail REMOVE_V161_AND_REBOOT_FIRST
fi
baseline_ok || fail EXACT_V154_BASELINE_REQUIRED''')
(HERE/'control.sh').write_text(controller)
build='MU1367-wireless-native-v161t2-'+sha((json.dumps(rows,sort_keys=True)+table+controller).encode())[:12]
(layer/'control.sh').write_text(controller.replace('@BUILD@',quote(build)).replace('@TABLE@',table));(layer/'VERSION').write_text(build+'\n')
m.update(version='1.6.1-e-test2',build_id=build,baseline_version='1.5.4',baseline_zip_sha256=provenance['baseline_zip_sha256'],rows=rows,baseline_checks=baseline_checks,baseline_core_menu_pairs=sorted(pairs),wireless_information_features_integrated=True,native_menu_switch_integrated=False,installation_tested=False,on_unit_validated=False,components=components,recovery_root='/mnt/app/carplay-mu1367-wireless-native-v161t2')
for mapping in m.get('upstream_mapping',[]):
 match=next((row for row in rows if row['target']==mapping['target']),None)
 if match:mapping['packaged_sha256']=match['sha256']
m['wireless_features']=dict(aid_activation=True,oem_driving_side=True,native_guidance=True,lane_guidance=True,media_text=False,artwork=False,default_fps=40,default_idr_request_frames=8,default_smoothing_ms=150)
(layer/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');(out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
# Snapshot payload check intentionally excludes informational manifest/source.
checks=[]
for f in sorted(layer.rglob('*')):
 if f.is_file() and f.name not in ('payload-check.sh','manifest.json'):checks.append('check "$P/'+str(f.relative_to(layer))+'" '+sha(f.read_bytes())+' || return 1')
(layer/'payload-check.sh').write_text('# SPDX-License-Identifier: GPL-3.0-or-later\n'+'\n'.join(checks)+'\n')
# GEM controller wrappers retain the stock RCC -> MMX forwarding path.
gem=sd/'Toolbox/GEM/carplay-maps-vc-wireless.esd'
text='screen Wireless-CarPlay-Test carplay-maps-vc\n\nkeyValue\n    value String sys 0x00000000 0\n    label "v1.6.1-e-test2 - wireless maps and guidance"\n    poll 0\n'
for action,label in [('install','Enable v1.6.1-e-test2 wireless (reboot)'),('uninstall','Remove wireless and restore v1.5.4 (reboot)'),('recover','Recover interrupted wireless install (reboot)'),('status','Wireless layer status')]:
 wrapper=(sd/'Toolbox/scripts/cpmap_suite_status.sh').read_text().replace('carplay_mu1367_guidance_v3','carplay_mu1367_wireless_native').replace('actions.sh','control.sh').replace('"$P/control.sh" status "$P"','"$P/control.sh" '+action+' "$P"')
 (sd/('Toolbox/scripts/cpmap_wireless_'+action+'.sh')).write_text(wrapper)
 text+='\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_wireless_'+action+'.sh"\n    label "'+label+'"\n'
gem.write_text(text);diagnostics(sd)
# The RAM probe is now automatic at each verified receiver launch.
text=gem.read_text();start=text.index('\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_wireless_alt_probe.sh"');text=text[:start]+text[text.index('\n',text.index('    label ',start))+1:]
for key,values in [('fps',(20,25,30,40)),('idr',(5,7,8,10,15)),('smoothing',(0,100,150,200))]:
 for value in values:
  name='cpmap_wireless_tune_'+key+'_'+str(value)+'.sh'
  wrapper=(sd/'Toolbox/scripts/cpmap_wireless_status.sh').read_text()
  wrapper=wrapper.replace('/bin/ksh "$P/control.sh" status "$P"','/mnt/app/carplaymaps/wireless-tune '+key+' '+str(value))
  (sd/'Toolbox/scripts'/name).write_text(wrapper)
  label=('Wireless FPS '+str(value)) if key=='fps' else ('Wireless IDR request every '+str(value)+' frames') if key=='idr' else ('Wireless smoothing '+('Off' if value==0 else str(value)+' ms (adaptive)'))
  text+='\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/'+name+'"\n    label "'+label+'"\n'
for action,label in [('','Show wireless tuning'),('defaults','Restore wireless tuning defaults')]:
 name='cpmap_wireless_tune_'+('defaults' if action else 'show')+'.sh'
 wrapper=(sd/'Toolbox/scripts/cpmap_wireless_status.sh').read_text().replace('/bin/ksh "$P/control.sh" status "$P"','/mnt/app/carplaymaps/wireless-tune'+(' '+action if action else ''))
 (sd/'Toolbox/scripts'/name).write_text(wrapper)
 text+='\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/'+name+'"\n    label "'+label+'"\n'
gem.write_text(text)
# All baseline-changing actions check both retained recovery generations.
guard='''
W=${CPMAP_TEST_ROOT:-}
if [ -z "$W" ] && [ ! -s /ifs/lsd.jxe ];then W=/net/mmx;fi
for L in carplay-mu1367-wireless-native carplay-mu1367-wireless-native-v161 carplay-mu1367-wireless-native-v161t2;do
 if [ -s "$W/mnt/app/$L/STATE" ] && [ "$(cat "$W/mnt/app/$L/STATE")" != removed ];then
  echo REMOVE_OR_RECOVER_WIRELESS_LAYER_AND_REBOOT_FIRST
  exit 1
 fi
done
'''
for script in list((sd/'Toolbox/scripts').glob('cpmap_suite_*.sh'))+[sd/n for n in ('RUN_INSTALL.sh','RUN_RESTORE.sh','RUN_RESET_SETTINGS.sh')]:
 s=script.read_text()
 if script.parent==sd or any(('"$P/actions.sh" '+action+' "$P"') in s for action in ('install','uninstall','recover','restore-oem','enable-cards','disable-cards','recover-cards')):
  assert s.count('set -u\n')==1;script.write_text(s.replace('set -u\n','set -u\n'+guard))
# Extend diagnostics without copying payloads or pairing stores.
for name in ('collect-wireless.sh','Toolbox/scripts/cpmap_wireless_collect_data.sh'):
 f=sd/name;s=f.read_text().replace('carplay-mu1367-wireless-native','carplay-mu1367-wireless-native-v161t2').replace('wireless-receiver-exec libomonob','wireless-receiver-exec libcpmap-wcp-tap.so altscreen-most-bridge wireless-tune libomonob').replace('wireless-carplay.previous;do','wireless-carplay.previous wireless-stream.conf;do')
 s=s.replace('for L in carplay-mu1367-wireless-native-v161t2 carplay-mu1367-guidance-v3;', 'for L in carplay-mu1367-wireless-native carplay-mu1367-wireless-native-v161 carplay-mu1367-wireless-native-v161t2 carplay-mu1367-guidance-v3;')
 s=s.replace('for F in v75-wireless-native.owner','for F in cpmap-driver-side.state v75-wireless-native.owner')
 s=s.replace('sync\necho "WIRELESS_DIAG_OK=', '''copy_file "$M/mnt/persist/cpmap-driver-side.state" "$OUT/state/cpmap-driver-side.cached.state"
for F in session.state idr.state source-status.txt adapter-status.txt guidance-evidence.txt lane-evidence.txt failure-first.txt;do
 copy_file "$M/ramdisk/wcp-rg/$F" "$OUT/state/wcp-rg-$F"
done
sync
echo "WIRELESS_DIAG_OK=''');f.write_text(s)
# The stable v154 scripts already contain the retained-session fix if released
# with it; only patch the exact old form where it remains.
base_fixes={}
f=sd/'Custom/carplay_mu1367_guidance_v3/actions.sh'
if 'fail RETAINED_SESSION_EXISTS' in f.read_text():base_fixes=archive_fix(sd)
(out/'base-archive-fix.json').write_text(json.dumps(base_fixes,indent=2)+'\n')
for f in layer.rglob('*'):
 if f.is_file():f.chmod(0o755 if f.name in ('verify','config-patch','control.sh') else 0o644)
print(json.dumps(dict(build_id=build,rows=len(rows),baseline='1.5.4',staged=str(out))))
