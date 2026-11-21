#!/usr/bin/env python3
"""Bind this development checkpoint to successful, relevant bench reports.

This is deliberately not an SD seal or release approval. Pending work remains
explicit and no installation/vehicle success is inferred from these checks.
"""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
components=ROOT/'build-v163t2-components-r5'
pins=json.loads((components/'COMPONENTS.json').read_text())
for name,pin in pins.items():assert sha(components/name)==pin,name
paths={
    'reconnect_old':'build-v162next-reconnect-old-r1/result.json',
    'reconnect_fixed':'build-v162next-reconnect-fixed-r2/result.json',
    'native_receiver':'build-v162next-receiver-r4/result.json',
    'timestamp_old':'build-v162next-clock-old-r1/result.json',
    'timestamp_fixed':'build-v162next-clock-fixed-r3/result.json',
    'capture_clock':'build-v162next-clock-host-r2/result.json',
    'long_diagnostics':'build-v162next-bridge-diag-r4/result.json',
    'collector':'build-v162next-collector-r3/result.json',
    'lifecycle':'build-v162next-lifecycle-r3/result.json',
    'pf_k4525':'build-v162next-pf-r4/result.json',
    'pf_p4521':'build-v162next-pf-r3/result.json',
    'input_and_launcher':'build-v162next-tools-r3/result.json',
    'wired_recovery':'build-v162next-recovery-host-r1/result.json',
    'pf_firmware':'v162-next/PF-FIRMWARE.json',
    'media_host':'build-v163t2-media-host-r7/result.json',
    'media_factory_j9':'build-v163t2-media-qnx-r5/result.json',
    'screen_host':'build-v163t2-screen-host-r2/result.json',
    'captured_cover':'build-v163t2-car-cover/result.json',
    'candidate_flow':'build-v163t2-flow-qnx-r1/result.json',
}
reports={}
for name,path in paths.items():
    f=ROOT/path;r=json.loads(f.read_text());assert r['passed'],name
    if 'log_sha256' in r:assert sha(f.parent/'qemu.log')==r['log_sha256'],name
    reports[name]=r
tap=sha(HERE/'src/native/wcp_tap.c')
bridge=sha(HERE/'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c')
assert reports['reconnect_fixed']['tap_sha256']==tap
for name in ['timestamp_fixed','long_diagnostics']:
    assert reports[name]['bridge_sha256']==bridge,name
assert reports['wired_recovery']['results']['fixed']['bridge_sha256']==bridge
assert reports['lifecycle']['bridge_source_sha256']==bridge
assert reports['lifecycle']['controller_sha256']==sha(HERE/'src/runtime/wcp_ctl.sh')
assert reports['collector']['collector_sha256']==sha(HERE/'src/runtime/collect-wireless.sh')
for name in ['pf_k4525','pf_p4521']:
    assert reports[name]['components']['wireless-tune']==pins['wireless-tune']
    assert reports[name]['pf_script_sha256']==sha(HERE/'src/runtime/wcp_pf.sh')
for name,pin in reports['input_and_launcher']['owned_components'].items():
    # Reuse native bench evidence only for byte-identical native components.
    # The two changed HMI JARs have their own current reports below.
    if not name.endswith('.jar'):assert pins[name]==pin,name
assert reports['media_host']['components']==pins
assert reports['media_factory_j9']['audio_sha256']==pins['CarPlayMU1367Audio.jar']
assert reports['media_factory_j9']['cp_sha256']==pins['CarPlayWireless-CP-55915411.jar']
assert reports['media_factory_j9']['wireless_screen_factory_j9']
assert reports['screen_host']['cp_sha256']==pins['CarPlayWireless-CP-55915411.jar']
assert reports['capture_clock']['header_sha256']==sha(HERE/'src/native/wcp_capture_clock.h')
assert reports['capture_clock']['test_sha256']==sha(HERE/'tests/capture-clock.c')
for name in ['wcp_tap.c','wcp_tap.S','wcp_rg.c','wcp_rg.h','wcp_timing.h','wcp_settings.h',
             'wcp_priority.h','wcp_media.c','wcp_media_tap.h','wcp_driver_side.h','wireless_session.h']:
    assert reports['native_receiver']['production_sources_sha256'][name]==sha(HERE/'src/native'/name),name
assert all(reports['native_receiver']['audio_checks'].values())
for fw in ['K4525','P4521']:
    for variant in ['50','70']:
        f=ROOT/'build-v162next-components-r5'/('imports-'+fw+'-'+variant+'.json');r=json.loads(f.read_text())
        assert r['passed']
        for name,row in r['components'].items():assert row['sha256']==pins[name]
        paths['imports_'+fw+'_'+variant]=str(f.relative_to(ROOT))
frozen=json.loads((ROOT/'research/v162-drive-review/EVIDENCE.json').read_text())
for name,pin in frozen['reviewed_source_sha256'].items():assert sha(ROOT/name)==pin,name
for release,row in frozen['packages'].items():assert sha(ROOT/row['path'])==row['sha256'],release
result=dict(schema=1,status='development bench checkpoint',checkpoint_date='2026-11-20',bench_checks_passed=True,
    ready_to_package=False,on_unit_validated=False,new_sd_package_created=False,
    components=pins,component_directory=str(components.relative_to(ROOT)),
    reports={name:dict(path=path,sha256=sha(ROOT/path)) for name,path in paths.items()},
    sources_sha256={str(f.relative_to(HERE)):sha(f) for directory in ['src','tools','tests']
        for f in sorted((HERE/directory).rglob('*')) if f.is_file() and '__pycache__' not in f.parts},
    preserved_packages=frozen['packages'],
    limits=['No radio/MFi/MOST/physical-audio success claimed.',
            'PF kernel/network queries are explicit stand-ins; real parser cannot complete without network interfaces.',
            'Candidate is staged; migration/interruption tests and sealing are separate required package gates.'],
    pending=['BT/Wi-Fi ownership, coexistence and call routing',
             'SDK audio jitter counters and skip/flush timeline',
             'Navigation-card packaged defaults and ordinary menu access',
             'Vehicle GPS forwarding',
             'Complete candidate recovery/regression validation and sealing'])
(HERE/'VERIFICATION-DEVELOPMENT.json').write_text(json.dumps(result,indent=2)+'\n')
print('DEVELOPMENT_CHECKPOINT_PASS reports='+str(len(paths))+' ready_to_package=0')
