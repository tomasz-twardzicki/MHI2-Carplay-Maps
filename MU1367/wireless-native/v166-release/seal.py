#!/usr/bin/env python3
"""Seal the complete 790/791 SD only after record-verification.py succeeds."""
import argparse, hashlib, json, re, shutil, subprocess, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
write=lambda p,v:p.write_text(json.dumps(v,indent=2)+'\n')
p=argparse.ArgumentParser()
p.add_argument('--build',type=Path,default=ROOT/'build-v166-stage-r2')
p.add_argument('--output',type=Path,default=ROOT/'dist/v1.6.6-e')
a=p.parse_args();sd=a.build.resolve()/'sd-card';custom=sd/'Custom'
layer=custom/'carplay_mu1367_wireless_native';profile=custom/'carplay_mu1367_input_profile'
checkpoint=read(HERE/'DEVELOPMENT-VERIFICATION.json')
assert checkpoint['passed'] and checkpoint['version']=='1.6.6-e'
assert not a.output.exists(),'Refuse to replace a sealed output'
for name,pin in checkpoint['source_sha256'].items():assert sha(ROOT/name)==pin,name
for name,row in checkpoint['reports'].items():assert sha(ROOT/row['path'])==row['sha256'],name
for name,row in checkpoint['retained_fixture_failures'].items():assert sha(ROOT/name)==row['sha256'],name
initial=checkpoint['initial_release_host_evidence']
for name in ('path','console_path','remaining_console_path'):
 pin={'path':'sha256','console_path':'console_sha256','remaining_console_path':'remaining_console_sha256'}[name]
 assert sha(ROOT/initial[name])==initial[pin]
for key,name in [('parent','carplay_mu1367_wireless_native'),('release','carplay_mu1367_release'),('oem','carplay_mu1367_oem_reset')]:
 assert sha(custom/name/'control.sh')==checkpoint['controller_sha256'][key]
manifest=read(layer/'manifest.json');profiles=read(profile/'manifest.json')
assert profiles==checkpoint['profiles']
for base,m in [(layer,manifest)]+[(profile/k,v) for k,v in profiles.items()]:
 for row in m['rows']:
  if row.get('kind','copy')=='copy':assert sha(base/'payload'/row['source'])==row['sha256']
# Information changes only: controllers and installed payloads remain those tested.
manifest.update(installation_tested=True,installation_test_scope='Host full-stack migrations; separate native parent/child/OEM transactions with explicit fixture boundaries.',
 package_seed_version='1.6.1',package_seed_archive_sha256='38279833ed495a057f4a513d568c5cf94a9f8d335a38773ebb580d09dcee47c1',
 vehicle_validation={'scope':'Combined v1.6.6-e requires vehicle acceptance; tested 790 video backend is preserved.'})
write(layer/'manifest.json',manifest)
top=read(sd/'MU1367_RELEASE_MANIFEST.json')
top.update(previous_stable_version='1.6.1',default_cluster='791',supported_clusters=['790','791'],
 vehicle_validation=manifest['vehicle_validation'],
 feature_matrix={'791':{'alternate_fps_demand':40,'idr_frames':8,'smoothing_ms':150,'native_guidance_tap':True},
                 '790':{'alternate_fps_demand':30,'video_backend':'User-tested overlay790 test3','native_guidance_tap':False,
                        'default_wireless_turn_card':'Off','safe_area':[202,16,606,344]}},
 bench_verification='VERIFICATION.json')
write(sd/'MU1367_RELEASE_MANIFEST.json',top)
write(a.build/'manifest.json',top)
verification=dict(checkpoint,ready_to_package=True,experimental=True,prerelease=True,
 installation_tested=True,profile_host_report_version_note='Inherited profile runner labels 1.6.1; complete child manifest and controller digests bind actual v1.6.6-e inputs.')
# Refresh current source, excluding recursive/generated proofs and Python caches.
source=layer/'source/v166'
if source.exists():shutil.rmtree(source)
shutil.copytree(HERE,source,ignore=shutil.ignore_patterns('__pycache__','VERIFICATION.json'))
profile_source=profile/'source'
if profile_source.exists():shutil.rmtree(profile_source)
shutil.copytree(ROOT/'overlay-v166',profile_source,ignore=shutil.ignore_patterns('__pycache__','VERIFICATION*.json'))
proofs=source/'verification-reports';proofs.mkdir()
for name,row in checkpoint['reports'].items():shutil.copy2(ROOT/row['path'],proofs/(name+'.json'))
for index,(name,row) in enumerate(checkpoint['retained_fixture_failures'].items()):
 shutil.copy2(ROOT/name,proofs/('retained-fixture-'+str(index)+Path(name).suffix))
for name in ('path','console_path','remaining_console_path'):
 shutil.copy2(ROOT/initial[name],proofs/('release-host-initial-'+name+Path(initial[name]).suffix))
for name in ('README.md','START_HERE.md','RELEASE-NOTES.md'):(sd/name).write_bytes((HERE/name).read_bytes())
if not (sd/'BASELINE_KNOWN-ISSUES.md').exists():shutil.copy2(sd/'KNOWN-ISSUES.md',sd/'BASELINE_KNOWN-ISSUES.md')
(sd/'KNOWN-ISSUES.md').write_text('# v1.6.6-e experimental limits\n\n'+'\n\n'.join('- '+v for v in checkpoint['limits'])+'\n')
(sd/'DEVELOPMENT.md').write_bytes((HERE/'BUILD-AND-TEST.md').read_bytes())
(sd/'WIRELESS_VERSION').write_text('1.6.6-e\n')
for name in ('VERIFICATION.json','WIRELESS-VERIFICATION.json'):write(sd/name,verification)
# Seed-package runtime reports remain in source history, not as a second current seal.
(sd/'TEST2-RUNTIME-VERIFICATION.json').unlink(missing_ok=True)
checks=[]
for f in sorted(layer.rglob('*')):
 if f.is_file() and f.name not in ('payload-check.sh','manifest.json') and 'source' not in f.relative_to(layer).parts:
  checks.append('check "$P/'+f.relative_to(layer).as_posix()+'" '+sha(f)+' || return 1')
(layer/'payload-check.sh').write_text('\n'.join(checks)+'\n')
shared=[]
for f in sorted(custom.rglob('*')):
 if f.is_file() and f.name!='payload-check.sh' and 'source' not in f.relative_to(custom).parts:
  shared.append('"$P/verify" "$CUSTOM_CHECK/'+f.relative_to(custom).as_posix()+'" '+sha(f)+' || return 1')
for f in custom.glob('*/payload-check.sh'):
 if f.parent!=layer:f.write_text('CUSTOM_CHECK=${P%/*}\n'+'\n'.join(shared)+'\n')
guards=0
for f in custom.rglob('payload-check.sh'):
 if 'source' in f.relative_to(custom).parts:continue
 refs=re.findall(r'(?:check "\$P/([^\"]+)"|"\$P/verify" "\$CUSTOM_CHECK/([^\"]+)") ([0-9a-f]{64})',f.read_text())
 assert refs,f
 for local,global_name,pin in refs:
  assert sha(f.parent/local if local else custom/global_name)==pin,(f,local,global_name)
  guards+=1
scripts=0
for f in sd.rglob('*.sh'):
 if 'source' not in f.relative_to(sd).parts:
  subprocess.run(['/bin/ksh','-n',str(f)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE);scripts+=1
for base,m in [(layer,manifest)]+[(profile/k,v) for k,v in profiles.items()]:
 for row in m['rows']:
  if row.get('kind','copy')=='copy':assert sha(base/'payload'/row['source'])==row['sha256']
for name in ('FILES_SHA256.json','WIRELESS-FILES.sha256'):(sd/name).unlink(missing_ok=True)
assert not any(f.is_symlink() for f in sd.rglob('*'))
files={f.relative_to(sd).as_posix():sha(f) for f in sorted(sd.rglob('*')) if f.is_file()}
assert not any('__pycache__' in n or n.endswith(('.pyc','.DS_Store')) for n in files)
write(sd/'FILES_SHA256.json',files);files['FILES_SHA256.json']=sha(sd/'FILES_SHA256.json')
(sd/'WIRELESS-FILES.sha256').write_text(''.join(h+'  '+n+'\n' for n,h in sorted(files.items())))
files['WIRELESS-FILES.sha256']=sha(sd/'WIRELESS-FILES.sha256')
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
archive=out/'CarPlay_Maps_VC_MU1367_790_791_v1.6.6-e.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name in sorted(files):
  f=sd/name;i=zipfile.ZipInfo(name,(2026,11,24,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=(0o100000|(f.stat().st_mode&0o777))<<16;z.writestr(i,f.read_bytes())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==len(files)
 assert all(not n.startswith('/') and '..' not in Path(n).parts for n in z.namelist())
 assert {n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}==files
result=dict(passed=True,version='1.6.6-e',experimental=True,prerelease=True,on_unit_validated=False,
 archive=archive.name,archive_sha256=sha(archive),zip_entries=len(files),all_zip_entries_verified=True,
 guard_references_verified=guards,shell_scripts_parsed=scripts,parent_targets=45,profile_790_targets=17,
 verification_sha256=sha(sd/'VERIFICATION.json'),manifest_sha256=sha(sd/'MU1367_RELEASE_MANIFEST.json'))
write(out/'PACKAGE-VERIFICATION.json',result)
for name in ('README.md','START_HERE.md','RELEASE-NOTES.md','VERIFICATION.json','MU1367_RELEASE_MANIFEST.json'):shutil.copy2(sd/name,out/name)
(out/'SHA256SUMS.txt').write_text(''.join(sha(f)+'  '+f.name+'\n' for f in sorted(out.iterdir()) if f.is_file()))
write(HERE/'VERIFICATION.json',verification)
print(json.dumps(result))
