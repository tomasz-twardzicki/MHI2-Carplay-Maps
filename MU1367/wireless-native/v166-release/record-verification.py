#!/usr/bin/env python3
"""Bind bench reports to the final staged payloads; retain failed fixtures."""
import argparse, hashlib, json, re, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
p=argparse.ArgumentParser()
p.add_argument('--build',type=Path,default=ROOT/'build-v166-stage-r2')
p.add_argument('--components',type=Path,default=ROOT/'build-v166-release-components-r4')
a=p.parse_args();sd=a.build.resolve()/'sd-card'
layer=sd/'Custom/carplay_mu1367_wireless_native';profile=sd/'Custom/carplay_mu1367_input_profile'
components=read(a.components/'COMPONENTS.json')
for name,pin in components.items():assert sha(a.components/name)==pin,name
m=read(layer/'manifest.json');top=read(sd/'MU1367_RELEASE_MANIFEST.json');profiles=read(profile/'manifest.json')
assert m['version']==top['version']=='1.6.6-e'
assert m['components']==top['wireless_runtime_components']==components
assert len(m['rows'])==45 and len(profiles['790']['rows'])==17
assert set(top['supported_clusters'])=={'790','791'}
assert 'carplay-mu1367-wireless-native-v165t2' in top['migration_roots']
for base,manifest in [(layer,m)]+[(profile/k,v) for k,v in profiles.items()]:
 for row in manifest['rows']:
  if row.get('kind','copy')=='copy':assert sha(base/'payload'/row['source'])==row['sha256'],row['target']
paths={
 'road_host':'build-v166-release-road-host-r1/result.json',
 'road_factory_j9':'build-v166-release-road-qnx-r1/result.json',
 'guidance_host':'build-v166-release-guidance-host-r1/result.json',
 'guidance_factory_j9':'build-v166-release-guidance-j9-r1/result.json',
 'media_host':'build-v166-release-media-host-r1/result.json',
 'media_policy_factory_j9':'build-v166-release-media-qnx-r1/result.json',
 'native_bt_rc':'build-v166-release-bt-r3/result.json',
 'receiver_791':'build-v166-release-receiver-r1/result.json',
 'clock_sanitizers':'build-v166-release-clock-r1/result.json',
 'bridge_diagnostics':'build-v166-release-bridge-diag-r1/result.json',
 'native_tools':'build-v166-release-tools-r1/result.json',
 'collector':'build-v166-release-collector-r1/result.json',
 'touch_host':'build-v166-input-r2/VERIFICATION.json',
 'touch_factory_j9':'build-v166-input-j9-r1/result.json',
 'receiver_790_build':'build-v166-media790-r3/VERIFICATION.json',
 'receiver_790_native':'build-v166-media790-qnx-r2/result.json',
 'imports_790':'build-v166-790-imports-r2.json',
 'card_defaults':'build-v166-defaults-r1/result.json',
 'release_host_remaining':'build-v166-release-host-r2/result.json',
 'release_host_private_export':'build-v166-release-host-r3/result.json',
 'release_qnx_orchestration':'build-v166-flow-qnx-r2/result.json',
 'parent_qnx_transactions':'build-v166-transactions-r2/result.json',
 'profiles_host':'build-v166-profiles-host-r3/result.json',
 'profiles_qnx':'build-v166-profiles-qnx-r2/result.json',
 'complete_oem_qnx':'build-v166-oem-qnx-r2/result.json',
 'stage_equivalence':str((a.build/'STAGE-EQUIVALENCE.json').resolve().relative_to(ROOT)),
}
for fw in ('K4525','P4521'):
 for hw in ('50','70'):paths['imports_791_'+fw+'_'+hw]=str((a.components/('imports-'+fw+'-'+hw+'.json')).resolve().relative_to(ROOT))
r={key:read(ROOT/path) for key,path in paths.items()}
assert all(v['passed'] for v in r.values())
for name,pin in r['stage_equivalence']['files_sha256'].items():assert sha(sd/name)==pin,name
for key,v in r.items():
 pin=v.get('log_sha256',v.get('qemu_log_sha256'))
 if pin:assert sha((ROOT/paths[key]).parent/'qemu.log')==pin,key
assert r['native_tools']['owned_components']==components and r['native_tools']['input_preload_functional_pass']
assert r['native_tools']['gps_gem_helper_sha256']==sha(layer/'gps-preference.sh')==sha(HERE/'src/runtime/gps-preference.sh')
assert r['collector']['collector_sha256']==sha(HERE/'src/runtime/collect-wireless.sh')
for name,pin in r['receiver_791']['production_sources_sha256'].items():assert sha(HERE/'src/native'/name)==pin,name
assert all(r['receiver_791']['audio_checks'].values())
assert r['native_bt_rc']['production_source_sha256']==sha(HERE/'src/native/bt_session_guard.c')
assert r['native_bt_rc']['reconnect_header_sha256']==sha(HERE/'src/native/bt_reconnect.h')
assert r['clock_sanitizers']['header_sha256']==sha(HERE/'src/native/wcp_capture_clock.h')
assert r['bridge_diagnostics']['bridge_sha256']==sha(HERE/'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c')
assert r['road_host']['prototype_jar_sha256']==r['road_factory_j9']['prototype_jar_sha256']
assert r['guidance_host']['guidance_sha256']==r['guidance_factory_j9']['guidance_sha256']==components['CarPlayMU1367Guidance.jar']
assert len(r['guidance_host']['results'])==19 and r['media_host']['components']==components
for key in ('touch_host','touch_factory_j9'):
 for name,pin in r[key].get('components',r[key].get('files')).items():assert pin==components[name]
for field,name in [('audio_sha256','CarPlayMU1367Audio.jar'),('cp_sha256','CarPlayWireless-CP-55915411.jar')]:assert r['media_policy_factory_j9'][field]==components[name]
assert (ROOT/'build-v166-release-media-qnx-r1/qemu.log').read_text(errors='replace').count('BT_RELEASE_POLICY_PASS checks=30')==2
assert (ROOT/'build-v166-release-guidance-j9-r1/qemu.log').read_text(errors='replace').count('POSITION_SPLIT_FACTORY_PASS checks=13')==2
assert r['receiver_790_native']['bt_wrapper_with_790_launcher']
assert r['receiver_790_native']['bt_guard_sha256']==r['receiver_790_build']['bt_guard_sha256']==components['libcpmap-bt-session.so']
assert r['receiver_790_native']['components']==r['receiver_790_build']['files']
for name,pin in r['receiver_790_native']['components'].items():assert sha(profile/'790/payload'/name)==pin
for name,pin in r['receiver_790_build']['source_sha256'].items():
 f=ROOT/'overlay-v166/media'/name
 if not f.is_file():f=ROOT/'v162-next/src/native'/name
 assert sha(f)==pin,name
for key,v in r.items():
 if key.startswith('imports_791_'):
  for name,row in v['components'].items():assert row['sha256']==components[name] and not row['missing']
for fw in r['imports_790']['profiles'].values():
 for name,row in fw['modules'].items():
  f=profile/'790/payload'/name
  if not f.is_file():f=layer/'payload'/name
  assert sha(f)==row['sha256'] and not row['missing'],name
release_pin=sha(sd/'Custom/carplay_mu1367_release/control.sh');oem_pin=sha(sd/'Custom/carplay_mu1367_oem_reset/control.sh')
for key in ('release_host_remaining','release_host_private_export','profiles_host','complete_oem_qnx'):assert r[key]['controller_sha256']==release_pin,key
assert r['complete_oem_qnx']['oem_controller_sha256']==oem_pin
assert r['release_qnx_orchestration']['production_release_controller_sha256']==release_pin
for name,pin in r['release_qnx_orchestration']['production_diagnostics_sha256'].items():assert sha(sd/name)==pin
tx=r['parent_qnx_transactions']
assert tx['build_id']==m['build_id'] and tx['commit_sites']==45
assert tx['rollback_cases']==tx['resume_cases']==6 and tx['wireless_input_selftest']
assert set(tx['tested_keys'])=={'k00','k23','k39','k42','k43','k44'}
assert r['profiles_qnx']['controllers']==profiles and r['profiles_host']['tests']==7
# The inherited profile runner's version label is 1.6.1; actual controllers and
# the entire child manifest above identify the v1.6.6-e payload under test.
assert r['release_host_remaining']['tests']==6 and r['release_host_private_export']['tests']==1
for variant,v in r['card_defaults']['variants'].items():assert sha(sd/'Custom/carplay_mu1367_guidance_v3'/variant/'VCMenu.jar')==v['menu_sha256']
assert r['card_defaults']['default']=='Off'
initial=ROOT/'build-v166-release-host-r1/result.json';initial_log=ROOT/'build-v166-release-host-r1.console';remaining_log=ROOT/'build-v166-release-host-r2.console'
assert not read(initial)['passed'] and read(initial)['errors']==1
first=re.findall(r'^(test_\w+) .*\.\.\. ok$',initial_log.read_text(),re.M)
remaining=re.findall(r'^(test_\w+) .*\.\.\. ok$',remaining_log.read_text(),re.M)
assert len(first)==len(remaining)==6 and len(set(first+remaining))==12
assert 'FileNotFoundError' in initial_log.read_text() and 'test_old_wireless_candidates_retire_without_old_sd' in remaining
tested=ROOT/'dist/overlay790-test3-final/CarPlay_MU1367_Overlay_790_Experimental_Test3.zip'
assert sha(tested)=='202ab34e7339324ca204e6ea64ef754d94a1174f76e9d139c41d59bfc28d3359'
backend=('wcp_receiver','wireless-entry','core.so','libomonob-wireless-maps.so','altscreen-most-bridge','carplay-cluster-supervisor')
with zipfile.ZipFile(tested) as z:
 for name in backend:assert z.read('Custom/carplay_mu1367_input_profile/790/payload/'+name)==(profile/'790/payload'/name).read_bytes(),name
conf=(profile/'790/payload/altscreen.conf').read_text()
assert 'safex=202\n' in conf and 'nsafex=202\n' in conf and 'alturl=maps:/car/instrumentcluster/map\n' in conf
retained={}
for name,description in {
 'build-v166-release-host-r1/result.json':'Six groups passed; missing CLI ZIP fixture corrected in r2.',
 'build-v166-profiles-host-r1/result.json':'Five groups passed; legacy fixture corrected, then all seven rerun on final profile.',
 'build-v166-transactions-r1/result.json':'SDK virtual board RAM exhaustion; 512 MiB fixture rerun passed.',
 'build-v166-full-flow-qnx-r3/result.json':'Full fresh native stack exhausted SDK RAM; full host and per-layer native coverage used.',
 'build-v166-full-flow-qnx-r5/qemu.log':'Larger full-stack SDK image could not boot; no full fresh native-stack pass claimed.',
}.items():
 f=ROOT/name
 if f.exists():
  if f.suffix=='.json':assert not read(f)['passed']
  retained[name]=dict(sha256=sha(f),description=description)
limits=[
 'Combined release vehicle acceptance is pending; physical radio, MOST, decoder presentation, microphone and call routes are not bench-validated.',
 '790 retains the tested 30 fps video backend. Custom 791 guidance, timestamp smoothing, IDR and GPS hooks are absent.',
 'BT RC tests execute actual pinned native cursor/open/write decisions with radio and command boundaries controlled. Paging latency, profile release and cold ignition need car acceptance.',
 'BT profile release is guarded and opt-in. Full ACL release and global BT stack shutdown are not implemented.',
 'Raw GNSS plus UTC remains unqualified; GPS/probe default off. The main-screen startup freeze is not established fixed.',
 'Native transactions cover 45 parent targets and six failure/interruption keys. Host profile tests cover all 17 child failure/interruption sites; native child tests use k04/k11.',
 'Full fresh stack uses actual host controllers and explicit mount/config/reboot fixtures. Native parent, child and OEM reset execute separately with firmware utilities. The full fresh native SDK image remains a harness limitation after RAM exhaustion/boot shutdown.',
 'QNX orchestration uses child stand-ins; separate native per-layer tests execute actual controllers. JXE hash/size boundaries and mounts are fixture substitutes.',
 'PF kernel/AP behavior, NavSD consumer field selection, startup presentation, track skip latency and deeper SDK jitter/link metrics require vehicle evidence.',
 'Recovery preserves unknown changes and requires requested reboots. Forward OEM reset covers exact recognized firmware/plaintext upstream scope, not arbitrary third-party changes.',
]
source_pins={str(f.relative_to(ROOT)):sha(f) for root in (HERE,ROOT/'overlay-v166') for f in sorted(root.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.name not in ('VERIFICATION.json','DEVELOPMENT-VERIFICATION.json')}
result=dict(schema=5,version='1.6.6-e',date='2026-11-24',passed=True,bench_checks_passed=True,on_unit_validated=False,build_id=m['build_id'],components=components,profiles=profiles,
 controller_sha256=dict(parent=sha(layer/'control.sh'),release=release_pin,oem=oem_pin),
 reports={key:dict(path=path,sha256=sha(ROOT/path)) for key,path in paths.items()},
 initial_release_host_evidence=dict(path=str(initial.relative_to(ROOT)),sha256=sha(initial),console_path=str(initial_log.relative_to(ROOT)),console_sha256=sha(initial_log),passing_groups=first,remaining_console_path=str(remaining_log.relative_to(ROOT)),remaining_console_sha256=sha(remaining_log),remaining_groups=remaining,unique_passing_groups=12),
 tested_790_backend_unchanged=list(backend),source_sha256=source_pins,retained_fixture_failures=retained,limits=limits)
(HERE/'DEVELOPMENT-VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(passed=True,reports=len(r),host_release_groups=12,host_profile_groups=7)))
