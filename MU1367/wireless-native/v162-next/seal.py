#!/usr/bin/env python3
"""Seal this experimental candidate only after final installer/runtime evidence."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser()
for name in ('build','components','host-result','flow-result','transaction-result','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();sd=a.build.resolve()/'sd-card';layer=sd/'Custom/carplay_mu1367_wireless_native';release=sd/'Custom/carplay_mu1367_release'
checkpoint=json.loads((HERE/'VERIFICATION-DEVELOPMENT.json').read_text());assert checkpoint['bench_checks_passed']
components=json.loads((a.components/'COMPONENTS.json').read_text())
assert components==checkpoint['components']
for name,pin in components.items():assert sha(a.components/name)==pin,name
reports={name:json.loads(getattr(a,name+'_result').read_text()) for name in ('host','flow','transaction')}
assert all(r['passed'] for r in reports.values())
assert reports['host']['tests']==7 and set(reports['host']['variants'])=={'6','7','6-road','7-road'}
assert sha(release/'control.sh')==reports['host']['controller_sha256']==reports['flow']['production_release_controller_sha256']
for name,pin in reports['flow']['production_diagnostics_sha256'].items():assert sha(sd/name)==pin,name
m=json.loads((layer/'manifest.json').read_text());top=json.loads((sd/'MU1367_RELEASE_MANIFEST.json').read_text())
assert components==m['components']==top['wireless_runtime_components'] and len(m['rows'])==41
assert m['build_id']==reports['transaction']['build_id'] and reports['transaction']['commit_sites']==41
assert set(reports['transaction']['tested_keys'])=={'k04','k05','k08','k39','k40'}
assert reports['transaction']['rollback_cases']==reports['transaction']['resume_cases']==5
assert m['version']=='1.6.3-e-test2' and 'carplay-mu1367-wireless-native-v162' in top['migration_roots']
for name,row in checkpoint['reports'].items():assert sha(HERE.parent/row['path'])==row['sha256'],name
for name,pin in checkpoint['sources_sha256'].items():assert sha(HERE/name)==pin,name
for row in m['rows']:
 if row['kind']=='copy':assert sha(layer/'payload'/row['source'])==row['sha256'],row['target']
for name in ('wcp_ctl.sh','wcp_pf.sh','wcp_pfwatch.sh','wcp_autostart.sh'):assert (layer/'payload'/name).read_bytes()==(HERE/'src/runtime'/name).read_bytes()
for f in sd.rglob('*.sh'):
 if 'source' not in f.relative_to(sd).parts:subprocess.run(['/bin/ksh','-n',str(f)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
verification=dict(version=m['version'],passed=True,experimental=True,prerelease=True,on_unit_validated=False,build_id=m['build_id'],components=components,development_checkpoint=checkpoint,reports=reports,
 limits=['Factory ARM J9 tests execute real notification event creation and listener invocation; the event-loop boundary is controlled by the fixture, not the complete vehicle ASL registry.',
 'QNX transactions install/remove all 41 targets and inject failures/interruptions at the five named keys; no claim of 41 failure-injection cases.',
 'PF network/kernel operations use explicit stand-ins. Actual PF parser/apply requires the vehicle AP and /dev/pf.',
 'No radio, MFi, MOST or physical audio hardware result is established by bench tests.',
 'BT release remains opt-in; Wi-Fi-first arbitration, SDK jitter/skip tracing, navigation-card defaults and vehicle GNSS forwarding remain open.'])
m.update(installation_tested=True,package_seed_version='1.6.1',package_seed_archive_sha256='38279833ed495a057f4a513d568c5cf94a9f8d335a38773ebb580d09dcee47c1')
m['baseline_vehicle_validation']=m.get('vehicle_validation',{})
m['vehicle_validation']={'scope':'Candidate vehicle validation pending; v162 single-session feedback is in the drive review.'}
m['installation_test_scope']='Actual host migration/OEM controllers across four base variants; final factory-QNX full transaction and five rollback/resume sites. Firmware JXE gate is substituted only inside the fixture.'
by_target={r['target']:r for r in m['rows']}
for item in m.get('upstream_mapping',[]):
 row=by_target.get(item['target'])
 if row and row['kind']=='copy':item['packaged_sha256']=row['sha256']
(layer/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
source=layer/'source/v163t2'
if source.exists():shutil.rmtree(source)
shutil.copytree(HERE,source,ignore=shutil.ignore_patterns('__pycache__','VERIFICATION.json'))
for name in ('README.md','START_HERE.md','RELEASE-NOTES.md'):(sd/name).write_text((HERE/name).read_text())
for name in ('VERIFICATION.json','WIRELESS-VERIFICATION.json'):(sd/name).write_text(json.dumps(verification,indent=2)+'\n')
custom=sd/'Custom';lines=[]
for f in sorted(custom.rglob('*')):
 if f.is_file() and f.name!='payload-check.sh' and 'source' not in f.relative_to(custom).parts:lines.append('"$P/verify" "$CUSTOM_CHECK/'+f.relative_to(custom).as_posix()+'" '+sha(f)+' || return 1')
body='CUSTOM_CHECK=${P%/*}\n'+'\n'.join(lines)+'\n'
for f in custom.glob('*/payload-check.sh'):
 if f.parent!=layer:f.write_text(body)
# Original layer checker intentionally excludes its informational manifest.
for name in ('FILES_SHA256.json','WIRELESS-FILES.sha256'):
 f=sd/name
 if f.exists():f.unlink()
assert not any(f.is_symlink() for f in sd.rglob('*'))
files={str(f.relative_to(sd)):sha(f) for f in sorted(sd.rglob('*')) if f.is_file()}
(sd/'FILES_SHA256.json').write_text(json.dumps(files,indent=2)+'\n');files['FILES_SHA256.json']=sha(sd/'FILES_SHA256.json')
(sd/'WIRELESS-FILES.sha256').write_text(''.join(h+'  '+n+'\n' for n,h in sorted(files.items())));files['WIRELESS-FILES.sha256']=sha(sd/'WIRELESS-FILES.sha256')
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);archive=out/('CarPlay_Maps_VC_MU1367_791_v'+m['version']+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name in sorted(files):
  f=sd/name;i=zipfile.ZipInfo(name,(2026,11,20,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=(0o100000|(f.stat().st_mode&0o777))<<16;z.writestr(i,f.read_bytes())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==len(files)
 assert {n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}==files
result=dict(passed=True,version=m['version'],experimental=True,on_unit_validated=False,archive=archive.name,archive_sha256=sha(archive),files=len(files),all_zip_entries_verified=True,managed_targets=41)
(out/'PACKAGE-VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');(out/'SHA256SUMS.txt').write_text(result['archive_sha256']+'  '+archive.name+'\n')
for name in ('README.md','START_HERE.md','RELEASE-NOTES.md','VERIFICATION.json'):shutil.copy2(sd/name,out/name)
(HERE/'VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n');print(json.dumps(result))
