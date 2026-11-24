#!/usr/bin/env python3
"""Record a development checkpoint; this is deliberately not a release seal."""
import hashlib, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
components = ROOT/'build-v166-components-r4'
pins = json.loads((components/'COMPONENTS.json').read_text())
for name, digest in pins.items(): assert sha(components/name) == digest, name
paths = {
    'road_host': 'build-v166-road-host-r3/result.json',
    'road_factory_j9': 'build-v166-road-qnx-r2/result.json',
    'guidance_factory_j9': 'build-v166-factory-guidance-r3/result.json',
    'receiver_native': 'build-v166-receiver-r2/result.json',
    'media_reverse_policy_factory_j9': 'build-v166-media-qnx-r4/result.json',
    'screen_policy_host': 'build-v166-cp-host-r2/result.json',
    'preference_gem_qnx': 'build-v166-tools-r1/result.json',
    'collector_qnx': 'build-v166-collector-r1/result.json',
    'capture_clock_sanitizers': 'build-v166-clock-r1/result.json',
}
reports = {key: json.loads((ROOT/path).read_text()) for key, path in paths.items()}
assert all(report['passed'] for report in reports.values())
assert reports['preference_gem_qnx']['owned_components'] == pins
assert reports['guidance_factory_j9']['guidance_sha256'] == pins['CarPlayMU1367Guidance.jar']
assert reports['media_reverse_policy_factory_j9']['cp_sha256'] == reports['screen_policy_host']['cp_sha256'] == pins['CarPlayWireless-CP-55915411.jar']
assert reports['media_reverse_policy_factory_j9']['audio_sha256'] == pins['CarPlayMU1367Audio.jar']
assert reports['collector_qnx']['collector_sha256'] == sha(HERE/'src/runtime/collect-wireless.sh')
assert reports['preference_gem_qnx']['gps_gem_helper_sha256'] == sha(HERE/'src/runtime/gps-preference.sh')
assert reports['road_host']['prototype_jar_sha256'] == reports['road_factory_j9']['prototype_jar_sha256']
for name, digest in reports['receiver_native']['production_sources_sha256'].items():
    assert sha(HERE/'src/native'/name) == digest, name
assert reports['capture_clock_sanitizers']['header_sha256'] == sha(HERE/'src/native/wcp_capture_clock.h')
media_log = (ROOT/'build-v166-media-qnx-r4/qemu.log').read_text(errors='replace')
assert media_log.count('BT_RELEASE_POLICY_PASS checks=22') == 2
guidance_log = (ROOT/'build-v166-factory-guidance-r3/qemu.log').read_text(errors='replace')
assert guidance_log.count('POSITION_SPLIT_FACTORY_PASS checks=13') == 2
assert 'BT_REQUEST_NATIVE_PASS' in (ROOT/'build-v166-receiver-r2/qemu.log').read_text(errors='replace')
old = ROOT/'dist/v1.6.5-e-test2/CarPlay_Maps_VC_MU1367_791_v1.6.5-e-test2.zip'
stable = ROOT/'dist/v1.6.1/CarPlay_Maps_VC_MU1367_791_v1.6.1.zip'
assert sha(old) == 'e9b815eb0be0e1b9cf45564278e15b12ddbe4d0436553a40177e54324882fcae'
assert sha(stable) == '38279833ed495a057f4a513d568c5cf94a9f8d335a38773ebb580d09dcee47c1'
sources = {str(f.relative_to(HERE)): sha(f) for f in sorted(HERE.rglob('*'))
           if f.is_file() and '__pycache__' not in f.parts and f.name != 'CHECKPOINT.json'}
result = dict(date='2026-11-24', development_checkpoint=True, installable=False,
    release_seal=False, vehicle_validated=False, components=pins,
    component_directory=components.name, source_sha256=sources,
    reports={key: dict(path=path, sha256=sha(ROOT/path), passed=True) for key, path in paths.items()},
    evidence_sha256=sha(ROOT/'research/v165t2-review/EVIDENCE.json'),
    incomplete=['Reason-aware Wi-Fi-first reconnect and stale-address/last-phone fallback.',
        'Device-specific full ACL release and vehicle call/radio acceptance.',
        'Raw GNSS/UTC producer and main-screen startup freeze.',
        'Distinct recovery root/version, exact test2 migration, complete assembled install/rollback/OEM-restore and firmware-import gates.'],
    scope='The copied test2 version/recovery/build placeholders must not be installed or packaged.')
(HERE/'CHECKPOINT.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(dict(development_checkpoint=True, installable=False, passed_report_groups=len(reports), source_files=len(sources))))
