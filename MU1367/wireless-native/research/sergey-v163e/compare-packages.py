#!/usr/bin/env python3
"""Compare exact public v3.2 payloads with the sealed 790 test-1 candidate."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

p = argparse.ArgumentParser()
for n in ('upstream', 'candidate', 'output'):
    p.add_argument('--' + n, type=Path, required=True)
a = p.parse_args()
sha = lambda b: hashlib.sha256(b).hexdigest()
assert sha(a.upstream.read_bytes()) == '5b31522046f1abf397fc62723dc7a4a1c3a37e90559d3d48409c8e322b1a9cce'
assert sha(a.candidate.read_bytes()) == '72b8a568f84ad361bb54505e866987d8588599f2e18554737b597c40cfe11f71'
report = dict(upstream_release='https://github.com/omonob/VW-MHI2-Wireless-Carplay-Maps/releases/tag/v3.2',
              upstream_zip_sha256=sha(a.upstream.read_bytes()),
              candidate_zip_sha256=sha(a.candidate.read_bytes()), components=[])
with zipfile.ZipFile(a.upstream) as up, zipfile.ZipFile(a.candidate) as test:
    prefix = 'SD_ROOT/carplay/payload/'
    child = 'Custom/carplay_mu1367_input_profile/790/payload/'
    native = 'Custom/carplay_mu1367_wireless_native/payload/'
    pairs = [(n, prefix + 'wireless/profiles/AID10.5-17PM/' + n, child + n)
             for n in ('wcp_receiver', 'wireless-entry', 'wireless-receiver-exec',
                       'libomonob-wireless-maps.so', 'v75-wireless-display.conf',
                       'cluster-profile', 'altscreen.conf', 'altscreen.geom')]
    pairs += [('core.so', prefix + 'profiles/MU1367/790/core.so', child + 'core.so')]
    pairs += [(n, prefix + 'common/' + n, native + n)
              for n in ('altscreen-most-bridge', 'carplay-cluster-supervisor')]
    pairs += [(n, prefix + 'wireless/common/runtime/' + n, native + n)
              for n in ('libv75-transport.so', 'wireless-video-exec', 'wcp_video_tap',
                        'wcp_video_stock', 'libv75-wireless-video-tap.so')]
    for name, upstream, current in pairs:
        b, c = up.read(upstream), test.read(current)
        report['components'].append(dict(name=name, upstream_path=upstream,
                                        current_path=current, byte_identical=b == c,
                                        upstream_sha256=sha(b), current_sha256=sha(c)))
    bridge_source = 'Custom/carplay_mu1367_wireless_native/source/v163t2/src/runtime/vc-runtime/runtime/altscreen_most_bridge.c'
    report['shipped_bridge_source_sha256'] = sha(test.read(bridge_source))
    report['upstream_phone_profile'] = 'AID10.5-17PM'
    report['legacy_16e_entry_is_alias'] = 'exec /bin/ksh' in up.read('SD_ROOT/install/scripts/install-aid10-16e.sh').decode()
    report['changed_map_runtime_components'] = [r['name'] for r in report['components'] if not r['byte_identical']]
    assert report['changed_map_runtime_components'] == ['core.so', 'altscreen-most-bridge', 'carplay-cluster-supervisor']
a.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(identical=sum(r['byte_identical'] for r in report['components']),
                      different=report['changed_map_runtime_components'], output=str(a.output))))
