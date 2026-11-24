#!/usr/bin/env python3
"""Seal stable only after runtime identity, migration and factory-shell proofs."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
p=argparse.ArgumentParser()
for n in ('build','test2-zip','host-result','qnx-result','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();build=a.build.resolve();sd=build/'sd-card';m=json.loads((build/'manifest.json').read_text())
host=json.loads(a.host_result.read_text());qnx=json.loads(a.qnx_result.read_text())
assert host['passed'] and host['tests']==7 and set(host['variants'])=={'6','7','6-road','7-road'}
assert qnx['passed']
control=sd/'Custom/carplay_mu1367_release/control.sh'
assert host['controller_sha256']==qnx['production_release_controller_sha256']==sha(control.read_bytes())==sha((HERE/'control.sh').read_bytes())
for name,h in qnx['production_diagnostics_sha256'].items():assert sha((sd/name).read_bytes())==h
assert sha(a.test2_zip.read_bytes())=='4c9688eb562c8c7006e6ffc12ca32d97e18a892394a7176baa5899143923a7cf'
with zipfile.ZipFile(a.test2_zip) as z:
 prefix='Custom/carplay_mu1367_wireless_native/'
 old=json.loads(z.read(prefix+'manifest.json'))
 # All native/JAR inputs, generated-config helpers and the 39-file transaction
 # controller remain the exact tested set. Only informational manifest differs.
 for name in z.namelist():
  if name.startswith(prefix) and '/source/' not in name and not name.endswith('/') and name!=prefix+'manifest.json':
   assert (sd/name).read_bytes()==z.read(name),name
 assert old['components']==m['wireless_runtime_components']
 for name in ('uninstall','recover'):
  path='Toolbox/scripts/cpmap_wireless_'+name+'.sh'
  assert (sd/path).read_bytes()==z.read(path), 'Wireless-only actions must retain their tested, base-preserving dispatch'
 runtime=json.loads(z.read('WIRELESS-VERIFICATION.json'))
 assert runtime['transactions']['rollback_cases']==runtime['transactions']['resume_cases']==39
 assert runtime['receiver']['passed'] and runtime['unit_tools']['passed'] and runtime['factory_j9']['passed']
# Check all shell entrypoints and static wrapper routing.
for f in sd.rglob('*.sh'):
 if 'source' not in f.relative_to(sd).parts:subprocess.run(['/bin/ksh','-n',str(f)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
for name in ('RUN_INSTALL.sh','RUN_RESTORE.sh','Toolbox/scripts/cpmap_suite_install.sh','Toolbox/scripts/cpmap_suite_recover.sh','Toolbox/scripts/cpmap_suite_restore-oem.sh','Toolbox/scripts/cpmap_restore.sh','Toolbox/scripts/cpmap_restore_core.sh'):
 text=(sd/name).read_text();assert 'carplay_mu1367_release' in text and 'REMOVE_OR_RECOVER_WIRELESS_LAYER_AND_REBOOT_FIRST' not in text,name
source=sd/'Custom/carplay_mu1367_release/source'
if source.exists():shutil.rmtree(source)
shutil.copytree(HERE,source,ignore=shutil.ignore_patterns('__pycache__','VERIFICATION.json'))
verification=dict(version='1.6.1',stable=True,prerelease=False,runtime_promoted_without_rebuild=True,runtime_build=m['wireless_runtime_build'],components=m['wireless_runtime_components'],vehicle_validation=m['vehicle_validation'],new_installation_flows={'host':host,'factory_qnx':qnx},tested_runtime=runtime,notes=['The native runtime was confirmed working on the vehicle by the maintainer on 2026-11-19.','Host tests execute actual base, legacy, Android Auto, wireless and OEM shell controllers. Host config generation replays native-QNX-generated, hash-verified outputs.','Factory-QNX flow checks use explicit stand-in child transactions; the actual combined collector and release control execute unchanged except the small fixture JXE hash/compatibility pins.','Historical test2 covers all 39 wireless commit rollback and power-loss recovery cases and native/J9 behavior.','No exhaustive tuning/endurance or new Android Auto validation is claimed.'])
(sd/'VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n')
(sd/'WIRELESS-VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n')
(HERE/'VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n')
# Root release docs, all manifests and both checksums describe this stable ZIP.
for name in ('WIRELESS-FILES.sha256','FILES_SHA256.json'):
 f=sd/name
 if f.exists():f.unlink()
files={str(f.relative_to(sd)):sha(f.read_bytes()) for f in sorted(sd.rglob('*')) if f.is_file()}
assert not any(f.is_symlink() for f in sd.rglob('*'))
(sd/'FILES_SHA256.json').write_text(json.dumps(files,indent=2)+'\n')
files['FILES_SHA256.json']=sha((sd/'FILES_SHA256.json').read_bytes())
(sd/'WIRELESS-FILES.sha256').write_text(''.join(h+'  '+n+'\n' for n,h in sorted(files.items())))
files['WIRELESS-FILES.sha256']=sha((sd/'WIRELESS-FILES.sha256').read_bytes())
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);archive=out/'CarPlay_Maps_VC_MU1367_791_v1.6.1.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name in sorted(files):
  f=sd/name;i=zipfile.ZipInfo(name,(2026,11,19,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED
  i.external_attr=(0o100000|(f.stat().st_mode&0o777))<<16;z.writestr(i,f.read_bytes())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==len(files)
 assert {n:sha(z.read(n)) for n in z.namelist()}==files
manifest=dict(m,archive=archive.name,archive_sha256=sha(archive.read_bytes()),files=len(files),zip_readback_verified=True,verification='VERIFICATION.json')
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(out/'SHA256SUMS.txt').write_text(manifest['archive_sha256']+'  '+archive.name+'\n')
for name in ('README.md','START_HERE.md','RELEASE-NOTES.md','VERIFICATION.json') :shutil.copy2(sd/name,out/name)
(out/'PACKAGE-VERIFICATION.json').write_text(json.dumps(dict(passed=True,version='1.6.1',archive_sha256=manifest['archive_sha256'],files=len(files),runtime_identical_to_vehicle_test=True,all_zip_entries_verified=True),indent=2)+'\n')
print(json.dumps(dict(passed=True,archive=str(archive),sha256=manifest['archive_sha256'],files=len(files))))
