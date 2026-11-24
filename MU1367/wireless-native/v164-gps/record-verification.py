#!/usr/bin/env python3
"""Bind GPS experiment evidence; installer/ZIP gates remain separate."""
from pathlib import Path
import hashlib,json,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
components=ROOT/'build-gps-components-r3';pins=json.loads((components/'COMPONENTS.json').read_text())
old=json.loads((ROOT/'build-v163t3-components-r5/COMPONENTS.json').read_text())
for name,pin in pins.items():assert sha(components/name)==pin,name
unchanged=[n for n in pins if old.get(n)==pins[n]]
for name in ('libcpmap-bt-session.so','wireless-artwork-fetch','altscreen-most-bridge','carplay-cluster-supervisor','CarPlayMU1367Audio.jar','CarPlayWireless-CP-55915411.jar'):assert name in unchanged,name
paths={'gps_host':'build-gps-host-r5/result.json','gps_arm_j9':'build-gps-qnx-r5/result.json','native_receiver':'build-gps-receiver-r7/result.json','receiver_regression':'build-gps-tap-regression-r2/result.json','collector':'build-gps-collector-r1/result.json','unit_tools':'build-gps-tools-r8/result.json','retained_media_host':'build-v163t3-media-host-r3/result.json','retained_factory_j9':'build-v163t3-media-qnx-r4/result.json','retained_bt_native':'build-v163t3-bt-qnx-r4/result.json','firmware_gps':str((HERE/'FIRMWARE-GPS-VERIFICATION.json').relative_to(ROOT))}
reports={k:json.loads((ROOT/v).read_text()) for k,v in paths.items()}
assert all(r['passed'] for r in reports.values())
for key,r in reports.items():
 loghash=r.get('log_sha256',r.get('qemu_log_sha256'))
 if loghash:assert sha(ROOT/Path(paths[key]).parent/'qemu.log')==loghash,key
assert reports['unit_tools']['owned_components']==pins
assert reports['unit_tools']['gps_gem_helper_sha256']==sha(HERE/'src/runtime/gps-preference.sh')
assert reports['unit_tools']['input_preload_comparison_only'] and not reports['unit_tools']['input_preload_functional_pass']
assert reports['collector']['collector_sha256']==sha(HERE/'src/runtime/collect-wireless.sh')
for name,pin in reports['receiver_regression']['production_sources_sha256'].items():assert sha(HERE/'src/native'/name)==pin,name
assert reports['native_receiver']['actual_receiver_parser'] and reports['native_receiver']['actual_native_serial_queue']
assert reports['gps_arm_j9']['verified_and_noverify'] and reports['gps_arm_j9']['class49_negative_rejected']
assert reports['gps_host']['prototype_jar_sha256']==reports['gps_arm_j9']['prototype_jar_sha256']
with zipfile.ZipFile(components/'CarPlayMU1367Guidance.jar') as packaged,zipfile.ZipFile(ROOT/'build-gps-host-r5/gps-prototype.jar') as tested:
 assert set(packaged.namelist())==set(tested.namelist())
 for n in packaged.namelist():assert packaged.read(n)==tested.read(n),n
assert reports['retained_factory_j9']['audio_sha256']==pins['CarPlayMU1367Audio.jar']
assert reports['retained_factory_j9']['cp_sha256']==pins['CarPlayWireless-CP-55915411.jar']
assert reports['retained_bt_native']['production_source_sha256']==sha(HERE/'src/native/bt_session_guard.c')
for fw in ('K4525','P4521'):
 for hw in ('50','70'):
  path=components/('imports-'+fw+'-'+hw+'.json');r=json.loads(path.read_text());assert r['passed']
  for name,row in r['components'].items():assert row['sha256']==pins[name] and not row['missing']
  paths['imports_'+fw+'_'+hw]=str(path.relative_to(ROOT))
limits=[
 'Experimental default-off vehicle GPS. Passive NMEA availability during wireless, native Unicode ABI on the car and live phone subscription/receipt/accuracy require vehicle acceptance.',
 'Fresh valid source fix is required at identification; late first fix or producer replacement requires reconnect. No exclusive iOS sensor selection is commanded.',
 'Source ARM fixture controls the Unicode conversion/lifetime boundary. Native receiver parser/serial queue/framer execute with QNX pipe wakeups and null remote transport; sent counts sender calls, not acknowledgements.',
 'Factory J9 dispatcher callbacks execute with and without verification, preserving listeners; event-loop and complete vehicle registry boundaries remain controlled.',
 'Published-control and candidate input-preload self-tests both fail the same bounded assertion (134). This is a retained diagnostic comparison, not a functional pass. Plain input and separate receiver timing/media/RHD/audio checks pass.',
 'Unchanged media/BT components reuse byte-identical test3 evidence. Radio, MFi, MOST, physical audio and BT guard vehicle acceptance remain open.',
 'Pre-acceptance Wi-Fi-first arbitration, track skip delay and SDK jitter/link tracing are not changed.'
]
r=dict(schema=3,checkpoint_date='2026-11-20',passed=True,bench_checks_passed=True,on_unit_validated=False,ready_to_package=False,status='GPS component checks passed; final managed installation gates separate',components=pins,component_directory=str(components.relative_to(ROOT)),unchanged_from_test3=unchanged,reports={k:dict(path=v,sha256=sha(ROOT/v)) for k,v in paths.items()},sources_sha256={str(p.relative_to(HERE)):sha(p) for directory in ('src','tools','tests') for p in sorted((HERE/directory).rglob('*')) if p.is_file() and '__pycache__' not in p.parts},known_failing_diagnostic=dict(path='build-gps-tools-r5/result.json',sha256=sha(ROOT/'build-gps-tools-r5/result.json'),control_exit=134,candidate_exit=134,scheduler_boundary_did_not_resolve=True),limits=limits)
(HERE/'DEVELOPMENT-VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print('GPS_COMPONENT_CHECKPOINT_PASS reports='+str(len(paths)))
