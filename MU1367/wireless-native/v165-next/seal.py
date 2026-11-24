#!/usr/bin/env python3
"""Seal this experimental candidate only after final installer/runtime evidence."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser()
for name in ('build','components','host-result','flow-result','transaction-result','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();sd=a.build.resolve()/'sd-card';layer=sd/'Custom/carplay_mu1367_wireless_native';release=sd/'Custom/carplay_mu1367_release'
checkpoint=json.loads((HERE/'DEVELOPMENT-VERIFICATION.json').read_text());assert checkpoint['bench_checks_passed']
components=json.loads((a.components/'COMPONENTS.json').read_text())
assert components==checkpoint['components']
for name,pin in components.items():assert sha(a.components/name)==pin,name
reports={name:json.loads(getattr(a,name+'_result').read_text()) for name in ('host','flow','transaction')}
assert all(r['passed'] for r in reports.values())
assert reports['host']['version']=='1.6.5-e-test1'
for name,report in reports.items():
 loghash=report.get('log_sha256',report.get('qemu_log_sha256'))
 if loghash:assert sha(getattr(a,name+'_result').parent/'qemu.log')==loghash,name
assert reports['transaction']['wireless_input_selftest']
assert reports['host']['tests']==7 and set(reports['host']['variants'])=={'6','7','6-road','7-road'}
assert sha(release/'control.sh')==reports['host']['controller_sha256']==reports['flow']['production_release_controller_sha256']
for name,pin in reports['flow']['production_diagnostics_sha256'].items():assert sha(sd/name)==pin,name
m=json.loads((layer/'manifest.json').read_text());top=json.loads((sd/'MU1367_RELEASE_MANIFEST.json').read_text())
assert components==m['components']==top['wireless_runtime_components'] and len(m['rows'])==45
assert m['build_id']==reports['transaction']['build_id'] and reports['transaction']['commit_sites']==45
assert set(reports['transaction']['tested_keys'])=={'k00','k23','k39','k42','k43','k44'}
assert reports['transaction']['rollback_cases']==reports['transaction']['resume_cases']==6
assert m['version']=='1.6.5-e-test1' and 'carplay-mu1367-wireless-native-v164t1' in top['migration_roots']
menu=(sd/'Toolbox/GEM/carplay-maps-vc-wireless.esd').read_text()
for kind in ('gps','gps-probe'):
 for action in ('on','off','status'):
  name='cpmap_wireless_'+kind.replace('-','_')+'_'+action+'.sh'
  assert menu.count('/'+name+'"')==1,name
  assert (sd/'Toolbox/scripts'/name).read_text().count('$P/gps-preference.sh\" '+kind+' '+action)==2,name
for action in ('next','current','off','status'):
 name='cpmap_wireless_road_label_'+action+'.sh'
 assert menu.count('/'+name+'\"')==1
 assert (sd/'Toolbox/scripts'/name).read_text().count('$P/gps-preference.sh\" road-label '+action)==2
assert not list(sd.rglob('road-label.mode'))
assert not list(sd.rglob('gps.enabled')) and not list(sd.rglob('gps-probe.enabled'))
assert {r['target'] for r in m['rows'] if r.get('source')=='dio_manager.wrapper.sh'}=={'/mnt/app/carplaymaps/dio_manager.wrapper.sh','/mnt/app/eso/bin/apps/dio_manager'}
for name,row in checkpoint['reports'].items():assert sha(HERE.parent/row['path'])==row['sha256'],name
for name,pin in checkpoint['sources_sha256'].items():assert sha(HERE/name)==pin,name
for row in m['rows']:
 if row['kind']=='copy':assert sha(layer/'payload'/row['source'])==row['sha256'],row['target']
assert (layer/'gps-preference.sh').read_bytes()==(HERE/'src/runtime/gps-preference.sh').read_bytes()
assert (layer/'payload/dio_manager.wrapper.sh').read_bytes()==(HERE/'src/runtime/dio_manager.wrapper.sh').read_bytes()
for name in ('btstack_wrap.sh','wcp_ctl.sh','wcp_pf.sh','wcp_pfwatch.sh','wcp_autostart.sh'):assert (layer/'payload'/name).read_bytes()==(HERE/'src/runtime'/name).read_bytes()
# Include the SD-only GPS helper in the layer's existing asset guard.
checks=[]
for f in sorted(layer.rglob('*')):
 if f.is_file() and f.name not in ('payload-check.sh','manifest.json') and 'source' not in f.relative_to(layer).parts:
  checks.append('check "$P/'+f.relative_to(layer).as_posix()+'" '+sha(f)+' || return 1')
(layer/'payload-check.sh').write_text('\n'.join(checks)+'\n')
for f in sd.rglob('*.sh'):
 if 'source' not in f.relative_to(sd).parts:subprocess.run(['/bin/ksh','-n',str(f)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
verification=dict(version=m['version'],passed=True,experimental=True,prerelease=True,on_unit_validated=False,build_id=m['build_id'],components=components,development_checkpoint=checkpoint,reports=reports,
 limits=checkpoint['limits']+[
 'QNX transactions install/remove all 45 targets and inject failures/interruptions at six named keys; no claim of 45 failure-injection cases.',
 'Factory-shell orchestration uses child stand-ins. Separate host tests run actual migration/OEM controllers across four layouts; QNX transaction tests run the real wireless controller.',
 'PF network/kernel operations use stand-ins. Actual PF parser/apply requires the vehicle AP and /dev/pf.'])

m.update(installation_tested=True,package_seed_version='1.6.1',package_seed_archive_sha256='38279833ed495a057f4a513d568c5cf94a9f8d335a38773ebb580d09dcee47c1')
m['baseline_vehicle_validation']=m.get('vehicle_validation',{})
m['vehicle_validation']={'scope':'v165 candidate vehicle validation pending; GPS raw-source/UTC qualification remains open.'}
m['installation_test_scope']='Actual host migration/OEM controllers across four base variants; final factory-QNX full transaction and six rollback/resume sites. Firmware JXE gate is substituted only inside the fixture.'
by_target={r['target']:r for r in m['rows']}
for item in m.get('upstream_mapping',[]):
 row=by_target.get(item['target'])
 if row and row['kind']=='copy':item['packaged_sha256']=row['sha256']
(layer/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
source=layer/'source/v165t1'
if source.exists():shutil.rmtree(source)
shutil.copytree(HERE,source,ignore=shutil.ignore_patterns('__pycache__','VERIFICATION.json'))
proofs=source/'verification-reports';proofs.mkdir()
for name,row in checkpoint['reports'].items():shutil.copy2(HERE.parent/row['path'],proofs/(name+'.json'))
for name in ('host','flow','transaction'):shutil.copy2(getattr(a,name+'_result'),proofs/('installer-'+name+'.json'))
equivalence=a.build/'STAGE-EQUIVALENCE.json'
assert json.loads(equivalence.read_text())['passed']
shutil.copy2(equivalence,proofs/'stage-equivalence.json')
resolved=checkpoint['resolved_fixture_diagnostic']['failure_report']
assert sha(HERE.parent/resolved['path'])==resolved['sha256']
shutil.copy2(HERE.parent/resolved['path'],proofs/'resolved-input-fixture-comparison.json')
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
  f=sd/name;i=zipfile.ZipInfo(name,(2026,11,23,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=(0o100000|(f.stat().st_mode&0o777))<<16;z.writestr(i,f.read_bytes())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==len(files)
 assert {n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}==files
result=dict(passed=True,version=m['version'],experimental=True,on_unit_validated=False,archive=archive.name,archive_sha256=sha(archive),files=len(files),all_zip_entries_verified=True,managed_targets=45)
(out/'PACKAGE-VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');(out/'SHA256SUMS.txt').write_text(result['archive_sha256']+'  '+archive.name+'\n')
for name in ('README.md','START_HERE.md','RELEASE-NOTES.md','VERIFICATION.json'):shutil.copy2(sd/name,out/name)
(HERE/'VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n');print(json.dumps(result))
