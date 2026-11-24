#!/usr/bin/env python3
"""Seal an exact-test2 parent with an isolated 790 child and SD-only recovery."""
import argparse, hashlib, json, re, shlex, shutil, subprocess, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
W=HERE.parent
sha=lambda b:hashlib.sha256(b).hexdigest()
file_sha=lambda f:sha(f.read_bytes())
p=argparse.ArgumentParser()
for n in ('build','baseline','tested-790','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();sd=a.build.resolve()/'sd-card';custom=sd/'Custom';parent=custom/'carplay_mu1367_wireless_native';child=custom/'carplay_mu1367_input_profile'
assert file_sha(a.baseline)=='e9b815eb0be0e1b9cf45564278e15b12ddbe4d0436553a40177e54324882fcae'
assert file_sha(a.tested_790)=='202ab34e7339324ca204e6ea64ef754d94a1174f76e9d139c41d59bfc28d3359'
reports_paths={
 'host':'build-v167-profiles-host-r2/result.json',
 'profiles_qnx':'build-v167-profiles-qnx-r1/result.json',
 'launcher_qnx':'build-v167-launcher-qnx-r1/result.json',
 'oem_qnx':'build-v167-oem-qnx-r1/result.json',
 'firmware_imports':'build-v167-imports-r1.json',
 'defaults':'build-v167-defaults-r1/result.json',
 'sd_evidence':'build-v167-sd-evidence-r2.json',
 'launcher_build':'build-v167-launcher-r1/VERIFICATION.json'}
reports={k:json.loads((W/v).read_text()) for k,v in reports_paths.items()}
assert all(r['passed'] for r in reports.values())
assert reports['host']['tests']==8 and reports['host']['failures']==reports['host']['errors']==0
assert len(reports['firmware_imports']['profiles'])==4
for name,r in reports.items():
 log=r.get('qemu_log_sha256',r.get('log_sha256'))
 if log:assert file_sha((W/reports_paths[name]).parent/'qemu.log')==log,name
profile=json.loads((child/'manifest.json').read_text());assert profile==reports['profiles_qnx']['controllers']
assert list(profile)==['790'] and len(profile['790']['rows'])==14
assert file_sha(child/'790/control.sh')==profile['790']['controller_sha256']
assert file_sha(custom/'carplay_mu1367_release/control.sh')==reports['host']['controller_sha256']
assert file_sha(custom/'carplay_mu1367_oem_reset/control.sh')==reports['oem_qnx']['controller_sha256']
assert profile['790']['recovery_root'] in reports['oem_qnx']['archived_recovery_roots']
# Rebind evidence to the exact selector/tuner/controller bytes mapped into QNX.
qnx=(W/reports_paths['profiles_qnx']).parent;mapping=(qnx/'test.build').read_text()
for name in ('actions.sh','tune.sh','790/geometry.sh','790/control.sh'):
 m=re.search(r'^/test/profile/'+re.escape(name)+r'=([^\n]+)$',mapping,re.M);assert m,name
 assert file_sha(qnx/m[1])==file_sha(child/name),name
for row in profile['790']['rows']:
 assert file_sha(child/'790/payload'/row['source'])==row['sha256']
 assert not row['target'].endswith('.jar') and 'btaudio' not in row['target']
assert reports['launcher_qnx']['components']==reports['launcher_build']['files']
assert file_sha(HERE/'src/receiver_exec790.c')==reports['launcher_build']['source_sha256']
for name,pin in reports['launcher_build']['files'].items():assert file_sha(child/'790/payload'/name)==pin
for fw in reports['firmware_imports']['profiles'].values():
 for name,proof in fw['modules'].items():
  f=child/'790/payload'/name
  if not f.is_file():f=parent/'payload'/name
  assert file_sha(f)==proof['sha256'],name
for row in reports['sd_evidence']['collectors']:assert file_sha(sd/row['path'])==row['sha256']
for variant,r in reports['defaults']['variants'].items():assert file_sha(custom/'carplay_mu1367_guidance_v3'/variant/'VCMenu.jar')==r['menu_sha256']
assert reports['defaults']['default']=='Off' and reports['defaults']['saved_choices_preserved']
with zipfile.ZipFile(a.baseline) as baseline,zipfile.ZipFile(a.tested_790) as tested:
 # Every parent asset, including controller, manifest, guard, native/JAR payloads
 # and installed helper, remains byte-identical to the known-good archive.
 prefix='Custom/carplay_mu1367_wireless_native/'
 parent_equal=[];other_equal=[];allowed=[]
 for n in baseline.namelist():
  if not n.startswith('Custom/') or n.endswith('/') or '/source/' in n:continue
  f=sd/n
  if n.startswith(prefix):
   assert f.read_bytes()==baseline.read(n),n;parent_equal.append(n)
  elif n.endswith('/payload-check.sh') or n in ('Custom/carplay_mu1367_oem_reset/control.sh','Custom/carplay_mu1367_oem_reset/manifest.json'):
   allowed.append(n)
  else:assert f.read_bytes()==baseline.read(n),n;other_equal.append(n)
 assert len(parent_equal)==54
 old=baseline.read('Custom/carplay_mu1367_oem_reset/control.sh').decode()
 new=(custom/'carplay_mu1367_oem_reset/control.sh').read_text()
 drop=lambda text:'\n'.join(l for l in text.splitlines() if not l.startswith('LAYERS='))
 assert drop(old)==drop(new)
 old_roots=shlex.split(next(l for l in old.splitlines() if l.startswith('LAYERS=')).split('=',1)[1])[0].split()
 new_roots=shlex.split(next(l for l in new.splitlines() if l.startswith('LAYERS=')).split('=',1)[1])[0].split()
 assert set(old_roots)<=set(new_roots)
 info=json.loads((custom/'carplay_mu1367_oem_reset/manifest.json').read_text())
 assert info['controller_sha256']==sha(new.encode()) and info['layers_archived']==new_roots
 baseline_proof=json.loads(baseline.read('VERIFICATION.json'))
 tested_proof=json.loads(tested.read('VERIFICATION.json'))
 assert baseline_proof['passed'] and tested_proof['passed']
 unchanged790=[]
 for name in ('wcp_receiver','wireless-entry','libomonob-wireless-maps.so','v75-wireless-display.conf','cluster-profile','altscreen.geom','core.so','altscreen-most-bridge','carplay-cluster-supervisor','libcpmap-wcp-media790.so'):
  assert (child/'790/payload'/name).read_bytes()==tested.read('Custom/carplay_mu1367_input_profile/790/payload/'+name),name
  unchanged790.append(name)
 original=tested.read('Custom/carplay_mu1367_input_profile/790/payload/altscreen.conf')
 assert (child/'790/payload/altscreen.conf').read_bytes()==original.replace(b'nsafex=42\n',b'nsafex=202\n')
 assert b'alturl=maps:/car/instrumentcluster/map\n' in (child/'790/payload/altscreen.conf').read_bytes()
 assert not list(sd.rglob('gps.enabled')) and not list(sd.rglob('gps-probe.enabled'))
 # Store original evidence as reused, not newly executed runtime tests.
 reused={'baseline':baseline_proof,'tested_790':tested_proof}
base=json.loads((parent/'manifest.json').read_text())
assert base['version']=='1.6.5-e-test2' and len(base['rows'])==45
for row in base['rows']:
 if row['kind']=='copy':assert file_sha(parent/'payload'/row['source'])==row['sha256']
for name,pin in base['components'].items():assert file_sha(parent/'payload'/name)==pin
assert reports['launcher_qnx']['bt_guard_sha256']==base['components']['libcpmap-bt-session.so']
assert reports['launcher_qnx']['bt_wrapper_sha256']==file_sha(parent/'payload/btstack_wrap.sh')
# Firmware compatibility was executed with factory commands. No new unit-side
# commands are introduced by this release's wrappers or collector additions.
assert reports['oem_qnx']['actual_qnx_ksh'] and not reports['oem_qnx']['sdk_utilities_injected']
top=json.loads((sd/'MU1367_RELEASE_MANIFEST.json').read_text())
top.update(version='1.6.7-e',cluster='790/791',previous_stable_version='1.6.1',runtime_baseline='1.6.5-e-test2',
 vehicle_validation={'baseline':'User reported v1.6.5-e-test2 working, including BT preservation and artwork.',
 '790_backend':'Video/metadata backend from the user-tested overlay790 test3 ZIP; combined test2 input requires car acceptance.',
 'release':'v1.6.7-e assembly has not yet been tested in a vehicle.'},
 input_handling='Unchanged test2 on both profiles',gps={'default':'disabled','standalone_asi_client_included':False},
 profile_scope={'791':'exact test2 runtime; no child','790':'isolated 14-target child, tested backend, centred safe area, test2 input'},
 retirement_wrapper={'sha256':file_sha(child/'actions.sh'),'known_controller_hashes':True,'reboots_required':True},
 oem_restore_scope='Baseline test2 managed restoration; OEM payloads and algorithm unchanged, recovery archive names extended. Not a universal third-party uninstaller.')
(sd/'MU1367_RELEASE_MANIFEST.json').write_text(json.dumps(top,indent=2)+'\n')
# Preserve original sealed evidence by explicit name before replacing current SD docs.
(sd/'BASELINE_TEST2_VERIFICATION.json').write_text(json.dumps(baseline_proof,indent=2)+'\n')
for name in ('README.md','START_HERE.md','RELEASE-NOTES.md'):(sd/name).write_bytes((HERE/name).read_bytes())
# Reproducible source and precise evidence; no firmware dumps, host drive logs or
# private pairing stores are copied into this release.
source=child/'source/v167'
assert not source.exists()
shutil.copytree(HERE,source,ignore=shutil.ignore_patterns('__pycache__','VERIFICATION.json'))
proofs=source/'verification-reports';proofs.mkdir()
for name,path in reports_paths.items():shutil.copy2(W/path,proofs/(name+'.json'))
for name,r in reused.items():(proofs/('reused-'+name+'.json')).write_text(json.dumps(r,indent=2)+'\n')
for name,path in [('host-fixture-failure','build-v167-profiles-host-r1/result.json')]:
 f=W/path
 if f.is_file():shutil.copy2(f,proofs/(name+'.json'))
# Do not refresh the test2 parent's own guard. Shared SD guards already include
# the new child; sources and informational top-level manifests are excluded.
guards=0
for f in custom.rglob('payload-check.sh'):
 if 'source' in f.relative_to(custom).parts:continue
 refs=re.findall(r'(?:check "\$P/([^\"]+)"|"\$P/verify" "\$CUSTOM_CHECK/([^\"]+)") ([0-9a-f]{64})',f.read_text());assert refs,f
 for local,shared,pin in refs:
  assert file_sha(f.parent/local if local else custom/shared)==pin,(f,local,shared);guards+=1
shells=0
for f in sd.rglob('*.sh'):
 if 'source' not in f.relative_to(sd).parts:
  subprocess.run(['/bin/ksh','-n',str(f)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE);shells+=1
menu=(sd/'Toolbox/GEM/carplay-maps-vc-experimental.esd').read_text()
assert menu.startswith('screen Experimental-Profiles carplay-maps-vc\n')
for script in re.findall(r'/eso/hmi/engdefs/scripts/mqb/([^"\n]+)',menu):assert (sd/'Toolbox/scripts'/script).is_file(),script
sourcepins={f.relative_to(HERE).as_posix():file_sha(f) for f in sorted(HERE.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.name!='VERIFICATION.json'}
dependencies={}
for path in ('v161/control.sh','v162-next/src/native/wcp_sha.h','stable/test-host.py','tests/receiver-alt-gate.py','v163-release/test-defaults.py','v163-release/TestCardDefault.java'):
 dependencies[path]=file_sha(W/path)
verification=dict(version='1.6.7-e',passed=True,experimental=True,prerelease=True,on_unit_validated=False,
 runtime_baseline=base['version'],runtime_build_id=base['build_id'],runtime_recovery_root=base['recovery_root'],
 baseline_zip_sha256=file_sha(a.baseline),tested_790_zip_sha256=file_sha(a.tested_790),
 parent_assets_byte_identical=parent_equal,other_custom_assets_byte_identical_count=len(other_equal),
 allowed_custom_exceptions=allowed,unchanged_tested_790_components=unchanged790,
 profiles=profile,reports=reports,report_files={k:{'path':v,'sha256':file_sha(W/v)} for k,v in reports_paths.items()},
 sources_sha256=sourcepins,dependencies_sha256=dependencies,reused_evidence={k:{'passed':r['passed'],'scope':'Reused only for byte-identical runtime components; original tests were not rerun.'} for k,r in reused.items()},
 input_jars_unchanged_both_profiles=True,gps_enabled=False,guard_references_verified=guards,shell_syntax_checked=shells,
 limits=['Physical MU/AID/touch/call/reconnect acceptance remains pending for this assembly; the 790/test2-input combination is new.',
 'Host migration uses a host SHA verifier, native-output config replay, inert mounts/sync and simulated reboots.',
 'QNX profile and OEM fixtures use small firmware-gate substitutes and inert mounts; launcher CLI tests do not start radio hardware.',
 'The 790 backend retains its own 30 fps map path and older observer; it does not acquire the custom 791 accepted-session/guidance/timing/IDR/GPS hooks.',
 'Test2 runtime is preserved including its open startup-freeze and pre-acceptance stale-address paging issues; no v166 fixes are imported.',
 'GPS remains off by default; the standalone raw GNSS/UTC ASI listener is unimplemented.',
 'OEM restoration is scoped to managed baseline layers; arbitrary third-party installations require their own removal procedure.'],
 retained_failed_fixture={'path':'build-v167-profiles-host-r1/result.json','reason':'Fixture assumed an mmipod payload absent from the unchanged test2 OEM reset. Removed that fixture-only assumption; all eight groups pass in r2.'})
for name in ('VERIFICATION.json','WIRELESS-VERIFICATION.json'):(sd/name).write_text(json.dumps(verification,indent=2)+'\n')
(HERE/'VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n')
for name in ('FILES_SHA256.json','WIRELESS-FILES.sha256'):(sd/name).unlink(missing_ok=True)
assert not any(f.is_symlink() for f in sd.rglob('*'))
files={f.relative_to(sd).as_posix():file_sha(f) for f in sorted(sd.rglob('*')) if f.is_file()}
(sd/'FILES_SHA256.json').write_text(json.dumps(files,indent=2)+'\n');files['FILES_SHA256.json']=file_sha(sd/'FILES_SHA256.json')
(sd/'WIRELESS-FILES.sha256').write_text(''.join(h+'  '+n+'\n' for n,h in sorted(files.items())));files['WIRELESS-FILES.sha256']=file_sha(sd/'WIRELESS-FILES.sha256')
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);archive=out/'CarPlay_Maps_VC_MU1367_790_791_v1.6.7-e.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name in sorted(files):
  f=sd/name;i=zipfile.ZipInfo(name,(2026,11,24,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=(0o100000|(f.stat().st_mode&0o777))<<16;z.writestr(i,f.read_bytes())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==len(files)
 assert {n:sha(z.read(n)) for n in z.namelist()}==files
result=dict(passed=True,version='1.6.7-e',experimental=True,on_unit_validated=False,archive=archive.name,archive_sha256=file_sha(archive),files=len(files),all_zip_entries_verified=True,parent_assets_byte_identical=54,profile_targets=14)
(out/'PACKAGE-VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');(out/'SHA256SUMS.txt').write_text(result['archive_sha256']+'  '+archive.name+'\n')
for name in ('README.md','START_HERE.md','RELEASE-NOTES.md','VERIFICATION.json','MU1367_RELEASE_MANIFEST.json'):shutil.copy2(sd/name,out/name)
print(json.dumps(result))
