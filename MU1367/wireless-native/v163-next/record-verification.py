#!/usr/bin/env python3
"""Bind BT/artwork component checks; final installer/ZIP gates are separate."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
components=ROOT/'build-v163t3-components-r5';pins=json.loads((components/'COMPONENTS.json').read_text())
old=json.loads((ROOT/'build-v163t2-components-r5/COMPONENTS.json').read_text())
for name,pin in pins.items():
 assert sha(components/name)==pin,name
 if name in old and name not in ['CarPlayMU1367Audio.jar','wireless-receiver-exec']:assert old[name]==pin,name
paths={'media_host':'build-v163t3-media-host-r3/result.json','factory_j9':'build-v163t3-media-qnx-r4/result.json','collector':'build-v163t3-collector-qnx-r2/result.json','bt_native':'build-v163t3-bt-qnx-r4/result.json','unit_tools':'build-v163t3-tools-qnx-r3/result.json'}
reports={k:json.loads((ROOT/v).read_text()) for k,v in paths.items()}
assert all(r['passed'] for r in reports.values())
for name in ['CarPlayMU1367Audio.jar','wireless-artwork-fetch']:assert reports['media_host']['components'][name]==pins[name]
assert 'ARTWORK_TRACE_PASS' in reports['media_host']['trace']
assert reports['factory_j9']['audio_sha256']==pins['CarPlayMU1367Audio.jar']
assert reports['factory_j9']['cp_sha256']==pins['CarPlayWireless-CP-55915411.jar']
assert reports['factory_j9']['factory_j9_verified'] and reports['factory_j9']['verified_and_noverify']
qnx=ROOT/Path(paths['factory_j9']).parent/'qemu.log';assert sha(qnx)==reports['factory_j9']['qemu_log_sha256']
log=qnx.read_text(errors='replace');assert log.count('ARTWORK_TRACE_PASS')==2
assert log.count('skip_decode=1 reconnect_decode=1 injected_worker_error_logged=1')==2
for name in ['collector','bt_native','unit_tools']:
 assert sha(ROOT/Path(paths[name]).parent/'qemu.log')==reports[name]['log_sha256']
assert reports['bt_native']['production_source_sha256']==sha(HERE/'src/native/bt_session_guard.c')
assert reports['collector']['collector_sha256']==sha(HERE/'src/runtime/collect-wireless.sh')
assert reports['unit_tools']['owned_components']==pins
assert reports['unit_tools']['bt_wrapper_sha256']==sha(HERE/'src/runtime/btstack_wrap.sh')
assert reports['unit_tools']['bt_wrapper_final_exec_only_stubbed']
for fw in ['K4525','P4521']:
 for hw in ['50','70']:
  path=components/('imports-'+fw+'-'+hw+'.json');r=json.loads(path.read_text());assert r['passed']
  for name,row in r['components'].items():assert row['sha256']==pins[name] and not row['missing']
  paths['imports_'+fw+'_'+hw]=str(path.relative_to(ROOT))
package=ROOT/'dist/v1.6.3-e-test2/CarPlay_Maps_VC_MU1367_791_v1.6.3-e-test2.zip'
assert sha(package)=='16d7b9f268bb4629a9836df1af9a09056be42aeab98bb3f0b74db25de7da4dba'
result=dict(schema=2,checkpoint_date='2026-11-20',status='BT accepted-owner guard and artwork diagnostics; final package gates separate',passed=True,bench_checks_passed=True,on_unit_validated=False,ready_to_package=False,
 components=pins,component_directory=str(components.relative_to(ROOT)),unchanged_from_test2=[n for n in pins if n in old and old[n]==pins[n]],
 reports={k:dict(path=v,sha256=sha(ROOT/v)) for k,v in paths.items()},
 sources_sha256={str(p.relative_to(HERE)):sha(p) for directory in ['src','tools','tests'] for p in sorted((HERE/directory).rglob('*')) if p.is_file() and '__pycache__' not in p.parts},
 review_evidence_sha256=sha(ROOT/'research/v163-test2-review/EVIDENCE.json'),baseline_archive_sha256=sha(package),
 retained_failed_fixture={'path':'build-v163t3-tools-qnx-r2/result.json','sha256':sha(ROOT/'build-v163t3-tools-qnx-r2/result.json'),'note':'Unchanged input self-test failed before wrapper checks; identical gate/tap/input bytes pass r1 and r3. Cause of that isolated failure is not established.'},
 limits=['BT native decision paths execute with constructor/radio/control boundaries explicitly stubbed; actual BT/AirPlay timeout and in-flight/multi-phone/call behavior require the car.',
 'The guard extends private addon probes without creating release/preference/crash flags. Pre-acceptance Wi-Fi-first arbitration is not changed.',
 'Factory J9 event-loop boundary is controlled, not a complete vehicle ASL registry.',
 'Actual old artwork exception causes and missing current UID/cover remain open; logging does not repair absent transfers.',
 'Installer/recovery and final ZIP checks must pass separately.'])
(HERE/'DEVELOPMENT-VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n')
print('BT_ARTWORK_CHECKPOINT_PASS reports='+str(len(paths)))
