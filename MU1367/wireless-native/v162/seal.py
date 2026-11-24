#!/usr/bin/env python3
"""Seal a local experimental candidate after binding all test evidence."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
p=argparse.ArgumentParser()
for n in ('build','components','host-result','host-build','flow-result','receiver-result','tools-result','media-host-result','media-qnx-result','transaction-result','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();sd=a.build.resolve()/'sd-card';layer=sd/'Custom/carplay_mu1367_wireless_native';m=json.loads((layer/'manifest.json').read_text());release=json.loads((a.build/'manifest.json').read_text())
components=json.loads((a.components/'COMPONENTS.json').read_text());assert m['components']==components==release['wireless_runtime_components']
reports={k:json.loads(getattr(a,k+'_result').read_text()) for k in ('host','flow','receiver','tools','media_host','media_qnx','transaction')}
assert all(r['passed'] for r in reports.values())
assert reports['host']['tests']==7 and set(reports['host']['variants'])=={'6','7','6-road','7-road'}
release_control=sd/'Custom/carplay_mu1367_release/control.sh'
assert sha(release_control.read_bytes())==reports['host']['controller_sha256']==reports['flow']['production_release_controller_sha256']
for name,h in reports['flow']['production_diagnostics_sha256'].items():assert sha((sd/name).read_bytes())==h
assert reports['tools']['owned_components']==reports['media_host']['components']==components
assert reports['media_qnx']['audio_sha256']==components['CarPlayMU1367Audio.jar'] and reports['media_qnx']['wireless_native_decoder_sha256']==components['wireless-artwork-fetch']
assert reports['transaction']['build_id']==m['build_id'] and reports['transaction']['commit_sites']==41
assert set(reports['transaction']['tested_keys'])=={'k39','k40'} and reports['transaction']['rollback_cases']==reports['transaction']['resume_cases']==2
for name,h in reports['receiver']['production_sources_sha256'].items():assert sha((HERE/'src/native'/name).read_bytes())==h
linkage={}
for fw in ('K4525','P4521'):
 for hw in ('50','70'):
  r=json.loads((a.components/('audit-'+fw+'-'+hw+'.json')).read_text());assert r['passed']
  for name,data in r['components'].items():assert data['sha256']==components[name] and not data['missing']
  linkage[fw+'/'+hw]=r
# The host matrix ran before the final edge-case fixes in the native media tap.
# Its shell controller is identical except exact opaque payload hash/build pins.
old_layer=a.host_build/'sd-card/Custom/carplay_mu1367_wireless_native';old=json.loads((old_layer/'manifest.json').read_text());mapping={old['build_id']:m['build_id']}
assert len(old['rows'])==len(m['rows'])==41
for before,after in zip(old['rows'],m['rows']):
 assert {k:v for k,v in before.items() if k!='sha256'}=={k:v for k,v in after.items() if k!='sha256'}
 if before.get('sha256')!=after.get('sha256'):mapping[before['sha256']]=after['sha256']
text=(old_layer/'control.sh').read_text()
for before,after in mapping.items():text=text.replace(before,after)
assert text==(layer/'control.sh').read_text()
for row in m['rows']:
 if row['kind']=='copy':assert sha((layer/'payload'/row['source']).read_bytes())==row['sha256']
for f in sd.rglob('*.sh'):
 if 'source' not in f.relative_to(sd).parts:subprocess.run(['/bin/ksh','-n',str(f)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
contract=json.loads((HERE/'FIRMWARE-MEDIA-VERIFICATION.json').read_text());assert contract['passed'] and len(contract['firmware_tables'])==4
verification=dict(version=m['version'],passed=True,experimental=True,prerelease=True,on_unit_validated=False,components=components,build_id=m['build_id'],native_firmware_linkage=linkage,media_firmware_contract=contract,vehicle_v4=json.loads((HERE/'VEHICLE-V4.json').read_text()),reports=reports,host_installer_hash_only_update=dict(passed=True,substitutions=mapping,explanation='Same 41 targets and exact release/child shell logic. Only payload hash pins/build ID differ from the complete host migration/OEM matrix. Final QNX transaction test executes the final controller/payload pins.'),limits=['Vehicle reverse-load timing and actual MU/AID rendering remain to be tested.','Final QNX rollback and interrupted-recovery checks target both added media files; full install/removal checks all 41 targets. This is not a claim of 41 new failure-injection cases.','Factory-flow child transactions are explicit stand-ins; real migration/OEM controllers run in the host matrix.','Native receiver tests exercise actual parser/copy/completion code before hardware main. They do not emulate Bluetooth, MFi, MOST or a phone.'])
m['installation_tested']=True
m['package_seed_version']='1.6.1'
m['package_seed_archive_sha256']='38279833ed495a057f4a513d568c5cf94a9f8d335a38773ebb580d09dcee47c1'
m['baseline_vehicle_validation']=m.get('vehicle_validation',{})
m['vehicle_validation']={'scope':'Candidate vehicle validation pending; previous successful test2 feedback applies to the stable baseline.'}
by_target={r['target']:r for r in m['rows']}
for item in m.get('upstream_mapping',[]):
 row=by_target.get(item['target'])
 if row and row['kind']=='copy':item['packaged_sha256']=row['sha256']
(layer/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
# Refresh source/doc copies without changing the tested executable controllers.
source=layer/'source/v162'
if source.exists():shutil.rmtree(source)
shutil.copytree(HERE,source,ignore=shutil.ignore_patterns('__pycache__','VERIFICATION.json'))
for name in ('README.md','START_HERE.md','RELEASE-NOTES.md'):(sd/name).write_text((HERE/name).read_text())
for name in ('VERIFICATION.json','WIRELESS-VERIFICATION.json'):(sd/name).write_text(json.dumps(verification,indent=2)+'\n')
(HERE/'VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n')
# Informational manifests change after the test result is sealed. Recalculate
# the comprehensive SD checker; native byte pins and shell code stay identical.
custom=sd/'Custom';lines=[]
for f in sorted(custom.rglob('*')):
 if f.is_file() and f.name!='payload-check.sh' and 'source' not in f.relative_to(custom).parts:lines.append('"$P/verify" "$CUSTOM_CHECK/'+f.relative_to(custom).as_posix()+'" '+sha(f.read_bytes())+' || return 1')
body='CUSTOM_CHECK=${P%/*}\n'+'\n'.join(lines)+'\n'
for f in custom.glob('*/payload-check.sh'):
 if f.parent!=layer:f.write_text(body)
for name in ('FILES_SHA256.json','WIRELESS-FILES.sha256'):
 f=sd/name
 if f.exists():f.unlink()
files={str(f.relative_to(sd)):sha(f.read_bytes()) for f in sorted(sd.rglob('*')) if f.is_file()};assert not any(f.is_symlink() for f in sd.rglob('*'))
(sd/'FILES_SHA256.json').write_text(json.dumps(files,indent=2)+'\n');files['FILES_SHA256.json']=sha((sd/'FILES_SHA256.json').read_bytes())
(sd/'WIRELESS-FILES.sha256').write_text(''.join(h+'  '+n+'\n' for n,h in sorted(files.items())));files['WIRELESS-FILES.sha256']=sha((sd/'WIRELESS-FILES.sha256').read_bytes())
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);archive=out/('CarPlay_Maps_VC_MU1367_791_v'+m['version']+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name in sorted(files):
  f=sd/name;i=zipfile.ZipInfo(name,(2026,11,19,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=(0o100000|(f.stat().st_mode&0o777))<<16;z.writestr(i,f.read_bytes())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==len(files)
 assert {n:sha(z.read(n)) for n in z.namelist()}==files
result=dict(passed=True,version=m['version'],experimental=True,on_unit_validated=False,archive=archive.name,archive_sha256=sha(archive.read_bytes()),files=len(files),all_zip_entries_verified=True,managed_targets=41)
(out/'PACKAGE-VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');(out/'SHA256SUMS.txt').write_text(result['archive_sha256']+'  '+archive.name+'\n')
for name in ('README.md','START_HERE.md','RELEASE-NOTES.md','VERIFICATION.json'):shutil.copy2(sd/name,out/name)
print(json.dumps(result))
