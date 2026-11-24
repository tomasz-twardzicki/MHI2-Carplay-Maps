#!/usr/bin/env python3
"""Seal the verified v161 SD candidate and verify every ZIP entry on readback."""
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;OLD=HERE.parent
sha=lambda b:hashlib.sha256(b).hexdigest()
p=argparse.ArgumentParser()
for n in ('build','components','repro','baseline-zip','receiver-result','tools-result','j9-result','guidance-result','archive-result','host-result','lifecycle-result','output'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--transaction-results',type=Path,nargs='+',required=True)
a=p.parse_args();m=json.loads((a.build/'manifest.json').read_text())
components=json.loads((a.components/'COMPONENTS.json').read_text())
assert components==json.loads((a.repro/'COMPONENTS.json').read_text())==m['components']
assert sha(a.baseline_zip.read_bytes())==m['baseline_zip_sha256']
for n,h in components.items():assert sha((a.components/n).read_bytes())==h
reports={name:json.loads(getattr(a,name+'_result').read_text()) for name in ('receiver','tools','j9','guidance','archive','host','lifecycle')}
assert all(r['passed'] for r in reports.values())
assert reports['lifecycle']['controller_sha256']==sha((HERE/'src/runtime/wcp_ctl.sh').read_bytes())
assert reports['lifecycle']['bridge_source_sha256']==sha((HERE/'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c').read_bytes())
command_proof=json.loads((HERE/'PIDIN-COMPATIBILITY.json').read_text())
assert command_proof['passed'] and set(command_proof['utilities'])=={'K4525-50','K4525-70','P4521-50','P4521-70'}
assert all(v==reports['lifecycle']['factory_utilities'] for v in command_proof['utilities'].values())
for name in ('guidance','j9','host'):assert reports[name]['guidance_sha256']==components['CarPlayMU1367Guidance.jar']
assert reports['tools']['owned_components']==components
native={}
for train in ('K4525','P4521'):
 for variant in ('50','70'):
  name=train+'-'+variant;native[name]=json.loads((a.components/('NATIVE-'+name+'.json')).read_text());assert native[name]['passed']
  for n,r in native[name]['components'].items():assert r['sha256']==components[n] and not r['missing']
transactions=[json.loads(p.read_text()) for p in a.transaction_results]
keys=[]
for r in transactions:
 assert r['passed'] and r['build_id']==m['build_id'] and r['commit_sites']==len(m['rows'])
 assert r['rollback_cases']==r['resume_cases']==len(r['tested_keys']) and r['wireless_input_selftest'] and r['session_checks']==17
 keys+=r['tested_keys']
assert len(keys)==len(set(keys))==len(m['rows']) and set(keys)=={r['key'] for r in m['rows']}
assert reports['archive']['changes']==json.loads((a.build/'base-archive-fix.json').read_text())
for p in a.transaction_results:
 log=(p.parent/'qemu.log').read_text(errors='replace');assert 'REMOVE_TEST1_AND_REBOOT_FIRST' in log and 'REMOVE_V161_AND_REBOOT_FIRST' in log
for n,h in reports['receiver']['production_sources_sha256'].items():assert sha((HERE/'src/native'/n).read_bytes())==h
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);sd=out/'sd-card';shutil.copytree(a.build/'sd-card',sd)
layer=sd/'Custom/carplay_mu1367_wireless_native'
# Sources/evidence are informational; the checked installer/payload table stays identical.
source=layer/'source';source.mkdir()
shutil.copytree(HERE,source/'v161',ignore=shutil.ignore_patterns('__pycache__','VERIFICATION.json'))
shutil.copytree(OLD/'src',source/'src');shutil.copytree(OLD/'tests',source/'tests',ignore=shutil.ignore_patterns('__pycache__'))
for n in ('build.py','control.sh','archive_fix.py','diagnostics.py','collect-wireless.sh','gem-collect-wireless.sh','enable-alt-probe.sh','UPSTREAM.json','FIRMWARE-VERIFICATION.json','P4521-COMPATIBILITY.json','FEASIBILITY.md'):shutil.copy2(OLD/n,source/n)
for n in ('README.md','START_HERE.md','RELEASE-NOTES.md','FILES_SHA256.json','MU1367_RELEASE_MANIFEST.json'):(sd/n).rename(sd/('BASELINE_'+n))
for n in ('BASELINE_README.md','BASELINE_START_HERE.md'):
 f=sd/n;f.write_text(f.read_text().replace('](START_HERE.md)','](BASELINE_START_HERE.md)').replace('](RELEASE-NOTES.md)','](BASELINE_RELEASE-NOTES.md)'))
(sd/'START_HERE.md').write_text((HERE/'TEST-PACKAGE.md').read_text())
(sd/'README.md').write_text('# MU1367 / AID 791 v1.6.1-e-test2 experimental\n\nFull v1.5.4 base plus the optional wireless maps/guidance layer. Read [START_HERE.md](START_HERE.md) for upgrade order, GEM tuning, vehicle checks and rollback. On-vehicle validation of this candidate is pending.\n\n[BASELINE_README.md](BASELINE_README.md) describes the stable base. WIRELESS-FILES.sha256 covers this complete candidate; BASELINE_FILES_SHA256.json describes the original stable archive.\n')
(sd/'RELEASE-NOTES.md').write_text('# v1.6.1-e-test2 experimental candidate\n\n- Includes stable v1.5.4 ETA/arrival-time behavior and wired IDR/FPS controls.\n- Automatic wireless AID activation and OEM RHD/LHD forwarding through a RAM-only config merge, late /info refresh and last-known coding cache.\n- Native wireless route/lane messages feed the existing guidance adapter, using wireless component 1 and accepted-session leases.\n- Wireless 40 FPS / IDR request every 8 frames / 150 ms smoothing defaults; GEM FPS, IDR and Off/100/150/200 ms choices.\n- Fixes the v3 launcher/PID race and keeps fallback IDR requests until receiver cadence is active.\n- Missing decoder configuration triggers bounded IDR recovery.\n- Full snapshot restoration to v1.5.4; old test1 and v1.6.1-e snapshots are retained.\n\nSee START_HERE.md. Wireless media text/artwork remain pending. This package makes no v1.6.1-e-test2 on-vehicle success claim. Original stable notes: BASELINE_RELEASE-NOTES.md.\n')
(sd/'WIRELESS_VERSION').write_text('1.6.1-e-test2\n')
(sd/'WIRELESS-NOTICE.txt').write_text("Uses omonob's pinned V3.1 receiver dependencies with recorded reuse/modification permission; see Custom/carplay_mu1367_wireless_native/source/FEASIBILITY.md and UPSTREAM-CREDITS.md / UPSTREAM-LICENSE in that layer. Owned changes are supplied under GPL-3.0-or-later.\n")
# Read-only guard checks on every affected base action and each recovery generation.
guarded=[]
with tempfile.TemporaryDirectory(prefix='mu1367-v161-guards-') as fixture:
 for generation in ('carplay-mu1367-wireless-native','carplay-mu1367-wireless-native-v161','carplay-mu1367-wireless-native-v161t2'):
  state=Path(fixture)/'mnt/app'/generation/'STATE';state.parent.mkdir(parents=True);state.write_text('installed\n')
  for script in [sd/n for n in ('RUN_INSTALL.sh','RUN_RESTORE.sh','RUN_RESET_SETTINGS.sh')]+list((sd/'Toolbox/scripts').glob('cpmap_suite_*.sh')):
   if 'for L in carplay-mu1367-wireless-native carplay-mu1367-wireless-native-v161 carplay-mu1367-wireless-native-v161t2;' not in script.read_text():continue
   r=subprocess.run(['/bin/ksh',str(script)],env=dict(os.environ,CPMAP_TEST_ROOT=fixture),capture_output=True,text=True)
   assert r.returncode==1 and r.stdout.strip()=='REMOVE_OR_RECOVER_WIRELESS_LAYER_AND_REBOOT_FIRST',(script,r.stdout,r.stderr)
   assert state.read_text()=='installed\n';guarded.append(str(script.relative_to(sd))+':'+generation)
  state.unlink()
for f in (sd/'Toolbox/scripts').glob('cpmap_wireless_*.sh'):subprocess.run(['/bin/ksh','-n',str(f)],check=True)
menu=(sd/'Toolbox/GEM/carplay-maps-vc-wireless.esd').read_text()
commands=re.findall(r'"/eso/hmi/engdefs/scripts/mqb/([^\"]+)"',menu)
assert len(commands)==len(set(commands)) and len(commands)==20
assert all((sd/'Toolbox/scripts'/name).is_file() for name in commands)
for f in (sd/'Toolbox/scripts').glob('cpmap_wireless_tune_*.sh'):
 s=f.read_text();assert 'exec on -f mmx /mnt/app/carplaymaps/wireless-tune' in s and 'exec /mnt/app/carplaymaps/wireless-tune' in s and '/bin/ksh /mnt/app/carplaymaps/wireless-tune' not in s
# Baseline runtime bytes remain untouched in their own install payloads.
differences=[];baseline_attrs={}
with zipfile.ZipFile(a.baseline_zip) as z:
 for item in z.infolist():
  if item.is_dir():continue
  baseline_attrs[item.filename]=item.external_attr
  f=sd/item.filename
  if not f.exists() or f.read_bytes()!=z.read(item):differences.append(item.filename)
allowed=lambda n:n in reports['archive']['changes'] or n in ('README.md','START_HERE.md','RELEASE-NOTES.md','FILES_SHA256.json','MU1367_RELEASE_MANIFEST.json','RUN_INSTALL.sh','RUN_RESTORE.sh','RUN_RESET_SETTINGS.sh') or n.startswith('Toolbox/scripts/cpmap_suite_')
assert all(allowed(n) for n in differences),differences
assert {n for n in differences if n.startswith('Custom/')}==set(reports['archive']['changes'])
m.update(installation_tested=True,on_unit_validated=False)
(layer/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
owned_source={str(f.relative_to(HERE)):sha(f.read_bytes()) for f in sorted(HERE.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.name!='VERIFICATION.json'}
verification=dict(version='1.6.1-e-test2',experimental=True,build_id=m['build_id'],base_version='1.5.4',baseline_zip_sha256=m['baseline_zip_sha256'],on_unit_validated=False,components=components,reproducible=True,owned_source_sha256=owned_source,native_factory_linkage=native,factory_command_compatibility=command_proof,receiver=reports['receiver'],unit_tools=reports['tools'],launch_lifecycle=reports['lifecycle'],factory_j9=reports['j9'],guidance_regressions=reports['guidance'],host=reports['host'],transactions=dict(passed=True,commit_sites=len(keys),rollback_cases=len(keys),resume_cases=len(keys),fresh_boot_batches=transactions,scope='Factory-QNX utilities; isolated disk trees; fixture JXE hash substitution only, no vehicle installation.'),archive_fix=reports['archive'],guarded_base_actions=guarded,gem_actions=commands,baseline_differences=differences,vehicle_v2_findings=json.loads((HERE/'VEHICLE-V2.json').read_text()),vehicle_v3_findings=json.loads((HERE/'VEHICLE-V3.json').read_text()),wireless_features=m['wireless_features'])
(sd/'WIRELESS-VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n')
(sd/'MU1367_RELEASE_MANIFEST.json').write_text(json.dumps(dict(version='1.6.1-e-test2',experimental=True,prerelease=True,base_version='1.5.4',build_id=m['build_id'],on_unit_validated=False,verification='WIRELESS-VERIFICATION.json',baseline_manifest='BASELINE_MU1367_RELEASE_MANIFEST.json',wireless_features=m['wireless_features']),indent=2)+'\n')
files={str(f.relative_to(sd)):sha(f.read_bytes()) for f in sorted(sd.rglob('*')) if f.is_file()}
assert not any(f.is_symlink() for f in sd.rglob('*'))
(sd/'WIRELESS-FILES.sha256').write_text(''.join(h+'  '+n+'\n' for n,h in sorted(files.items())))
files['WIRELESS-FILES.sha256']=sha((sd/'WIRELESS-FILES.sha256').read_bytes())
archive=out/'CarPlay_Maps_VC_MU1367_791_v1.6.1-e-test2.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name in sorted(files):
  f=sd/name;i=zipfile.ZipInfo(name,(2026,11,18,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED
  i.external_attr=baseline_attrs.get(name,(0o100755 if f.suffix=='.sh' or f.name in ('verify','config-patch') else 0o100644)<<16)
  z.writestr(i,f.read_bytes())
with zipfile.ZipFile(archive) as z:
 assert len(z.namelist())==len(set(z.namelist()))==len(files) and z.testzip() is None
 assert {n:sha(z.read(n)) for n in z.namelist()}==files
report=dict(passed=True,version='1.6.1-e-test2',build_id=m['build_id'],archive=archive.name,archive_sha256=sha(archive.read_bytes()),files=len(files),rollback_cases=len(keys),resume_cases=len(keys),zip_readback_verified=True,on_unit_validated=False)
(out/'SHA256SUMS.txt').write_text(report['archive_sha256']+'  '+archive.name+'\n')
(out/'PACKAGE-VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
shutil.copy2(sd/'START_HERE.md',out/'START_HERE.md');shutil.copy2(sd/'WIRELESS-VERIFICATION.json',out/'WIRELESS-VERIFICATION.json')
(HERE/'VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n')
print(json.dumps(report,indent=2))
