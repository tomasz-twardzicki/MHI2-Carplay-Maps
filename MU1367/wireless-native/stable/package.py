#!/usr/bin/env python3
"""Assemble stable v1.6.1 around the exact vehicle-confirmed test2 runtime."""
import argparse,hashlib,importlib.util,json,shutil,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
p=argparse.ArgumentParser(description=__doc__)
for n in ('test2-zip','test1-zip','v161-zip','seed-zip'):p.add_argument('--'+n,type=Path)
for n in ('integration','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);sd=out/'sd-card'
archives=[] if a.seed_zip else [(a.test1_zip,'498e2aee7d157405f2cda0566c9436e177931ce06fc55d2f8dbd219d63b3663b'),(a.v161_zip,'5a3d41a18fb1c71ef311d468fac368d013217e57f3e3103aa85a7ed49ac04e73'),(a.test2_zip,'4c9688eb562c8c7006e6ffc12ca32d97e18a892394a7176baa5899143923a7cf')]
legacy={};prefix='Custom/carplay_mu1367_wireless_native/'
for path,pin in archives:
 assert path and sha(path.read_bytes())==pin
 with zipfile.ZipFile(path) as z:
  m=json.loads(z.read(prefix+'manifest.json'));root=Path(m.get('recovery_root','/mnt/app/carplay-mu1367-wireless-native')).name
  legacy[root]={'version':m['version'],'build_id':m['build_id'],'controller_sha256':sha(z.read(prefix+'control.sh')),'archive_sha256':pin,'targets':{r['key']:r['target'] for r in m['rows']}}
with zipfile.ZipFile(a.seed_zip or a.test2_zip) as z:
 if a.seed_zip:
  seed=json.loads(z.read('MU1367_RELEASE_MANIFEST.json'))
  assert seed['version']=='1.6.1' and not seed['prerelease']
  legacy=seed['migration_roots']
 z.extractall(sd)
 for item in z.infolist():
  if not item.is_dir():
   mode=(item.external_attr>>16)&0o777
   if mode:(sd/item.filename).chmod(mode)
custom=sd/'Custom';layer=custom/'carplay_mu1367_wireless_native'
tested=json.loads((layer/'manifest.json').read_text());evidence=json.loads((sd/('TEST2-RUNTIME-VERIFICATION.json' if a.seed_zip else 'WIRELESS-VERIFICATION.json')).read_text())
assert tested['build_id']=='MU1367-wireless-native-v161t2-f6dfb5e724b1' and tested['components']==evidence['components']
for row in tested['rows']:
 if row['kind']=='copy':assert sha((layer/'payload'/row['source']).read_bytes())==row['sha256']
release=custom/'carplay_mu1367_release';release.mkdir(exist_ok=True);shutil.copy2(layer/'verify',release/'verify');shutil.copy2(HERE/'control.sh',release/'control.sh')
control=(layer/'control.sh').read_text();table=control[control.index('\n',control.index('BUILD='))+1:control.index('regular(){')]
assert 'baseline_ok(){' in table and 'before_ok(){' in table
compat=table+'\nWIRELESS_ROOTS='+repr(' '.join(legacy))+'\nCURRENT_WIRELESS_ROOT='+repr(Path(tested['recovery_root']).name)+'\nwireless_controller(){ case "$1" in\n'
for root,m in legacy.items():compat+=' '+root+') echo '+m['controller_sha256']+';;\n'
compat+=' *) return 1;;\nesac; }\n';(release/'compatibility.sh').write_text(compat)
compat+='legacy_keys(){ case "$1" in\n'
for root,m in legacy.items():compat+=' '+root+') echo '+repr(' '.join(m['targets']))+';;\n'
compat+=' *) return 1;;\nesac; }\nlegacy_target(){ case "$1:$2" in\n'
for root,m in legacy.items():
 for key,target in m['targets'].items():compat+=' '+root+':'+key+') echo "$M'+target+'";;\n'
compat+=' *) return 1;;\nesac; }\n';(release/'compatibility.sh').write_text(compat)
tested.update(version='1.6.1',experimental=False,prerelease=False,on_unit_validated=True,vehicle_validation={'date':'2026-11-19','source':'Maintainer feedback: test2 works; stable retains its exact runtime bytes.','scope':'Successful wireless candidate reported; exhaustive tuning/endurance/Android Auto testing is not claimed.'},component_build_ids_retained=True)
(layer/'manifest.json').write_text(json.dumps(tested,indent=2)+'\n')
oem=custom/'carplay_mu1367_oem_reset';f=oem/'control.sh';s=f.read_text();at=s.index("LAYERS='")+8;end=s.index("'",at);names=list(dict.fromkeys(s[at:end].split()+list(legacy)));s=s[:at]+' '.join(names)+s[end:];f.write_text(s)
om=json.loads((oem/'manifest.json').read_text());om['controller_sha256']=sha(f.read_bytes());om['layers_archived']=list(dict.fromkeys(om['layers_archived']+list(legacy)));(oem/'manifest.json').write_text(json.dumps(om,indent=2)+'\n')
wrapper=(sd/'Toolbox/scripts/cpmap_suite_status.sh').read_text()
guard_start=wrapper.index('W=${CPMAP_TEST_ROOT:-}') if 'W=${CPMAP_TEST_ROOT:-}' in wrapper else -1
if guard_start>=0:wrapper=wrapper[:guard_start]+wrapper[wrapper.index('M=${CPMAP_TEST_ROOT:-}',guard_start):]
for action in ('install','uninstall','recover','restore-oem'):
 code=wrapper.replace('carplay_mu1367_guidance_v3','carplay_mu1367_release').replace('actions.sh','control.sh').replace('"$P/control.sh" status "$P"','"$P/control.sh" '+action+' "$P"')
 (sd/('Toolbox/scripts/cpmap_suite_'+action+'.sh')).write_text(code)
for name,action in [('RUN_INSTALL.sh','install'),('RUN_RESTORE.sh','restore-oem'),('Toolbox/scripts/cpmap_restore.sh','restore-oem'),('Toolbox/scripts/cpmap_restore_core.sh','restore-oem')]:
 (sd/name).write_bytes((sd/('Toolbox/scripts/cpmap_suite_'+action+'.sh')).read_bytes())
# Enable uses the complete upgrade flow. Wireless-only remove/recover retain
# the tested current-layer controller and can never fall through to uninstall
# the base when wireless has already been removed. Main Recovery handles all
# legacy generations and complete OEM restoration.
(sd/'Toolbox/scripts/cpmap_wireless_install.sh').write_bytes((sd/'Toolbox/scripts/cpmap_suite_install.sh').read_bytes())
for menu in (sd/'Toolbox/GEM').glob('carplay-maps-vc*.esd'):
 s=menu.read_text().replace('v1.6.1-e-test2','v1.6.1').replace('v1.5.4','v1.6.1').replace('Wireless-CarPlay-Test','Wireless-CarPlay')
 s=s.replace('MU1367 / 791 v1.6.1 (CarPlay + Android Auto)','MU1367 / 791 v1.6.1 (wired + wireless CarPlay + Android Auto)')
 s=s.replace('Remove wireless and restore v1.6.1','Remove wireless and restore v1.5.4').replace('wireless maps and guidance','wireless maps, guidance and tuning')
 menu.write_text(s)
spec=importlib.util.spec_from_file_location('collector',HERE/'diagnostics.py');diag=importlib.util.module_from_spec(spec);spec.loader.exec_module(diag);diag.apply(sd)
for name in ('README.md','START_HERE.md','RELEASE-NOTES.md'):(sd/name).write_text((HERE/name).read_text())
(sd/'WIRELESS_VERSION').write_text('1.6.1\n')
manifest=dict(version='1.6.1',experimental=False,prerelease=False,base_version='1.5.4',previous_stable_version='1.5.4',supported_firmware=['K4525','P4521'],cluster='791',wireless_runtime_build=tested['build_id'],wireless_runtime_components=tested['components'],vehicle_validation=tested['vehicle_validation'],migration_roots=legacy,install_flow='checked saved-layer restore; full reboot; v1.5.4 base migration/install; full reboot; tested wireless transaction; full reboot',oem_restore='wireless snapshot restoration and reboot first; forward factory OEM restoration and archive of all wireless roots next',diagnostics='standard cpmap-diag includes wireless subfolder',runtime_promoted_without_rebuild=True)
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(sd/'MU1367_RELEASE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
(sd/'TEST2-RUNTIME-VERIFICATION.json').write_text(json.dumps(evidence,indent=2)+'\n')
spec=importlib.util.spec_from_file_location('checks',a.integration/'tools/payload_checks.py');checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
roots=sorted(r for r in custom.iterdir() if r.is_dir() and (r.name in ('carplay_maps_vc','carplay_mu1367') or r.name.startswith('carplay_mu1367_')))
lines=[]
for root in roots:
 for f in sorted(root.rglob('*')):
  if f.is_file() and f.name!='payload-check.sh' and 'source' not in f.relative_to(root).parts:
   lines.append('"$P/verify" "$CUSTOM_CHECK/'+f.relative_to(custom).as_posix()+'" '+sha(f.read_bytes())+' || return 1')
body='CUSTOM_CHECK=${P%/*}\n'+'\n'.join(lines)+'\n'
for name in checks.CHECKER_ROOTS:(custom/name/'payload-check.sh').write_text(body)
shutil.copy2(custom/'carplay_mu1367_guidance_v3/payload-check.sh',release/'payload-check.sh')
for f in sd.rglob('*.sh'):f.chmod(0o755)
(release/'verify').chmod(0o755)
print(json.dumps(dict(staged=str(out),version='1.6.1',runtime_build=tested['build_id'],runtime_components_unchanged=True)))
