#!/usr/bin/env python3
"""Bind the final v165 component checks; final installer and ZIP gates are separate."""
from pathlib import Path
import hashlib,json,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
components=ROOT/'build-v165-components-r5';pins=json.loads((components/'COMPONENTS.json').read_text())
old=json.loads((ROOT/'build-gps-components-r3/COMPONENTS.json').read_text())
for name,pin in pins.items():assert sha(components/name)==pin,name
unchanged=[name for name in pins if old.get(name)==pins[name]]
for name in ('wireless-artwork-fetch','altscreen-most-bridge','carplay-cluster-supervisor'):assert name in unchanged,name
paths={
 'gps_road_host':'build-v165-guidance-host-r5/result.json',
 'gps_road_arm_j9':'build-v165-guidance-qnx-r2/result.json',
 'full_guidance_host':'build-v165-full-guidance-host-r1/result.json',
 'full_guidance_factory_j9':'build-v165-factory-guidance-r2/result.json',
 'wireless_policy_host':'build-v165-wireless-host-r1/result.json',
 'native_location_receiver':'build-v165-location-receiver-r1/result.json',
 'native_receiver_regression':'build-v165-receiver-r2/result.json',
 'collector':'build-v165-collector-r2/result.json',
 'unit_tools':'build-v165-tools-r6/result.json',
 'media_host':'build-v165-media-host-r1/result.json',
 'media_screen_factory_j9':'build-v165-media-qnx-r2/result.json',
 'screen_host':'build-v165-screen-host-r2/result.json',
 'native_bt':'build-v165-bt-r2/result.json',
 'launch_lifecycle':'build-v165-lifecycle-r1/result.json',
 'firmware_gps':str((HERE/'FIRMWARE-GPS-VERIFICATION.json').relative_to(ROOT)),
}
reports={key:json.loads((ROOT/path).read_text()) for key,path in paths.items()}
assert all(r['passed'] for r in reports.values())
for key,r in reports.items():
 loghash=r.get('log_sha256',r.get('qemu_log_sha256'))
 if loghash:assert sha(ROOT/Path(paths[key]).parent/'qemu.log')==loghash,key
assert reports['unit_tools']['owned_components']==pins
assert reports['unit_tools']['gps_gem_helper_sha256']==sha(HERE/'src/runtime/gps-preference.sh')
assert reports['unit_tools']['input_preload_functional_pass'] and not reports['unit_tools']['input_preload_comparison_only']
assert reports['collector']['collector_sha256']==sha(HERE/'src/runtime/collect-wireless.sh')
for name,pin in reports['native_receiver_regression']['production_sources_sha256'].items():assert sha(HERE/'src/native'/name)==pin,name
assert all(reports['native_receiver_regression']['audio_checks'].values())
assert reports['native_location_receiver']['actual_receiver_parser'] and reports['native_location_receiver']['actual_native_serial_queue']
assert reports['gps_road_arm_j9']['verified_and_noverify'] and reports['gps_road_arm_j9']['class49_negative_rejected']
assert reports['gps_road_host']['prototype_jar_sha256']==reports['gps_road_arm_j9']['prototype_jar_sha256']
with zipfile.ZipFile(components/'CarPlayMU1367Guidance.jar') as packaged,zipfile.ZipFile(ROOT/'build-v165-guidance-host-r5/gps-prototype.jar') as tested:
 assert set(packaged.namelist())==set(tested.namelist())
 for name in packaged.namelist():assert packaged.read(name)==tested.read(name),name
for key in ('full_guidance_host','wireless_policy_host'):assert reports[key]['guidance_sha256']==pins['CarPlayMU1367Guidance.jar']
assert len(reports['full_guidance_host']['results'])==19
assert reports['media_host']['components']==pins
assert reports['media_screen_factory_j9']['audio_sha256']==pins['CarPlayMU1367Audio.jar']
assert reports['media_screen_factory_j9']['cp_sha256']==reports['screen_host']['cp_sha256']==pins['CarPlayWireless-CP-55915411.jar']
assert reports['native_bt']['production_source_sha256']==sha(HERE/'src/native/bt_session_guard.c')
assert reports['launch_lifecycle']['controller_sha256']==sha(HERE/'src/runtime/wcp_ctl.sh')
for fw in ('K4525','P4521'):
 for hw in ('50','70'):
  path=components/('imports-'+fw+'-'+hw+'.json');r=json.loads(path.read_text());assert r['passed']
  for name,row in r['components'].items():assert row['sha256']==pins[name] and not row['missing']
  paths['imports_'+fw+'_'+hw]=str(path.relative_to(ROOT))
prior=ROOT/'build-v165-tools-r5/result.json';prior_log=prior.parent/'qemu.log';prior_report=json.loads(prior.read_text())
assert prior_report['input_preload_comparison_only'] and not prior_report['input_preload_functional_pass']
assert sha(prior_log)==prior_report['log_sha256']
assert 'INPUT_RING_TRUNCATE fd=5 bytes=16779024 result=-1 errno=28' in prior_log.read_text(errors='replace')
assert 'INPUT_COMPARISON control=0 candidate=0' in (ROOT/'build-v165-tools-r6/qemu.log').read_text(errors='replace')
with zipfile.ZipFile(ROOT/'dist/v1.6.1/CarPlay_Maps_VC_MU1367_791_v1.6.1.zip') as z:
 assert z.read('Custom/carplay_mu1367_wireless_native/payload/wireless-entry')==(ROOT/'build-v165-stage-r1/sd-card/Custom/carplay_mu1367_wireless_native/payload/wireless-entry').read_bytes()
limits=[
 'Vehicle GPS remains unavailable in the supplied wireless-only sessions because DIO is absent. Raw GNSS and UTC qualification are unresolved. GPS and probe default off; enabling/rebooting alone is not a fix.',
 'The source ARM fixture controls Unicode conversion/lifetime. Native receiver parser/serial queue/framing execute with QNX pipe wakeups and null remote transport; sender counts are not phone acknowledgements.',
 'Factory J9 callbacks execute with and without verification, preserving listeners; complete HMI registry/event-loop and picture presentation boundaries remain controlled.',
 'BT tests execute pinned native decisions with constructor/radio/command boundaries controlled. BT-only loss survival, physical RC paging, Wi-Fi teardown and later ignition require vehicle acceptance.',
 'Artwork replacement retry and diagnostics do not establish complete physical MU/AID cover presentation or solve all metadata/skip timing cases.',
 'The MU-only startup freeze is instrumented, not established fixed. Ownership wall/ASL clocks and native monotonic timestamps must be correlated with primary receive/decode/presentation.',
 'Pre-acceptance Wi-Fi-first/last-phone arbitration, bootstrap resend policy, track skip delay and deeper SDK jitter/link metrics remain open.',
 '40/8/150 and native main-screen demand 30 are retained; no new phone sensor-selection or main-screen FPS claim.',
 'Managed recovery supports recognized snapshots and preserves unknown changes; it is not a universal uninstaller for arbitrary third-party installations.'
]
r=dict(schema=4,checkpoint_date='2026-11-23',passed=True,bench_checks_passed=True,on_unit_validated=False,ready_to_package=False,status='Component gates passed; final managed installation and ZIP gates remain separate',components=pins,component_directory=str(components.relative_to(ROOT)),unchanged_from_v164=unchanged,reports={key:dict(path=path,sha256=sha(ROOT/path)) for key,path in paths.items()},sources_sha256={str(p.relative_to(HERE)):sha(p) for directory in ('src','tools','tests') for p in sorted((HERE/directory).rglob('*')) if p.is_file() and '__pycache__' not in p.parts},resolved_fixture_diagnostic=dict(failure_report=dict(path=str(prior.relative_to(ROOT)),sha256=sha(prior)),failure_log_sha256=sha(prior_log),failure_errno=28,cause='Sequential 16,779,024-byte ring allocations exhausted the emulator RAM disk before frame publication',resolution='Remove each isolated ring directory and run the firmware sync utility between tests; production input unchanged',functional_control_exit=0,functional_candidate_exit=0,resolution_report='unit_tools'),limits=limits)
(HERE/'DEVELOPMENT-VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print('V165_COMPONENT_CHECKPOINT_PASS reports='+str(len(paths)))
