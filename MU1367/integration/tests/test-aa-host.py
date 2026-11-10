#!/usr/bin/env python3
"""v1.5.0-e: Android Auto host suites in the disposable Debian test image (no network).
Builds the release feeder source, the MU1367 bridge (file output) and supervisor for the host, then runs the feeder
harness (upstream cases + MU1367 cases) and the end-to-end test. Writes feeder-host.json and e2e.json to OUTPUT.
SPDX-License-Identifier: GPL-3.0-or-later
  test-aa-host.py --output OUT [--docker-context colima-cpmap-rgi] [--image cpmap143e-host-tests]
"""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent; I = HERE.parent
p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True)
p.add_argument('--docker-context', default='colima-cpmap-rgi'); p.add_argument('--image', default='cpmap143e-host-tests')
a = p.parse_args(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
R = '/i/src/runtime/vc-runtime'
script = f'''set -e
cc -O2 -Wall -Wextra -Werror -Wno-format-truncation -std=gnu99 -I{R}/runtime /i/src/android-auto/feeder/aa_most_feeder.c -o /o/aa-most-feeder
cc -O2 -std=gnu99 -pthread -D_GNU_SOURCE -DALTSCREEN_BRIDGE_FILE_OUTPUT -I/i/tests/android-auto/e2e/stub -I{R}/runtime {R}/runtime/altscreen_most_bridge.c -o /o/altscreen-most-bridge-carplay
cc -O2 -std=gnu99 -pthread -D_GNU_SOURCE -DALTSCREEN_BRIDGE_FILE_OUTPUT -DALTSCREEN_AA_SINGLE_IDR -I/i/tests/android-auto/e2e/stub -I{R}/runtime {R}/runtime/altscreen_most_bridge.c -o /o/altscreen-most-bridge
cc -O2 -std=gnu99 -pthread -D_GNU_SOURCE -I/i/tests/android-auto/e2e/stub -I{R}/runtime -I{R}/mirror {R}/runtime/carplay_cluster_supervisor.c -o /o/carplay-cluster-supervisor
cc -O2 -Wall -Wextra -Werror -std=gnu99 /i/tests/android-auto/test_aeabi_conv.c -o /o/aeabi && /o/aeabi > /o/aeabi.log
cd /tmp && python3 -I /i/tests/android-auto/feeder/run_host_test.py /o/aa-most-feeder > /o/feeder-host.log 2>&1
python3 -I /i/tests/android-auto/e2e/run_e2e.py /o /i/src/android-auto/unit/feeder.conf /i/tests/android-auto/feeder /o/e2e.json > /o/e2e.log 2>&1
python3 -I /i/tests/android-auto/e2e/bridge_recovery.py /o/altscreen-most-bridge-carplay /o/altscreen-most-bridge /i/tests/android-auto/feeder /o/bridge-recovery.json > /o/bridge-recovery.log 2>&1
'''
r = subprocess.run(['docker', '--context', a.docker_context, 'run', '--rm', '--network=none', '-v', str(I) + ':/i:ro', '-v', str(out) + ':/o',
                    a.image, 'sh', '-c', script], capture_output=True, text=True)
(out / 'docker.log').write_text(r.stdout + r.stderr)
assert r.returncode == 0, r.stdout + r.stderr + ((out / 'feeder-host.log').read_text()[-3000:] if (out / 'feeder-host.log').exists() else '')
log = (out / 'feeder-host.log').read_text(); conv = (out / 'aeabi.log').read_text()
assert 'FAILED CHECKS: 0' in log and ' bad=0' in conv
e2e = json.loads((out / 'e2e.json').read_text()); assert e2e['passed']
src = {f.relative_to(I).as_posix(): sha(f) for f in sorted((I / 'src/android-auto/feeder').glob('*.c')) + sorted((HERE / 'android-auto').rglob('*.py')) + [I / 'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c', I / 'src/runtime/vc-runtime/runtime/carplay_cluster_supervisor.c']}
host = {'passed': True, 'checks': log.count('\nok') + log.startswith('ok'), 'mu1367_cases': len(re.findall(r'^ok +MU\d', log, re.M)),
        'aeabi_conv': conv.strip(), 'source_sha256': src, 'test_sha256': sha(Path(__file__)), 'on_unit_validated': False}
(out / 'feeder-host.json').write_text(json.dumps(host, indent=2) + '\n')
rec = json.loads((out / 'bridge-recovery.json').read_text()); assert rec['passed']
e2e.update(source_sha256=src, real_mu1367_bridge=True, real_mu1367_supervisor=True, aa_bridge_build='ALTSCREEN_AA_SINGLE_IDR', bridge_recovery=rec)
(out / 'e2e.json').write_text(json.dumps(e2e, indent=2) + '\n')
print(json.dumps({'feeder_host_checks': host['checks'], 'mu1367_cases': host['mu1367_cases'], 'e2e_checks': e2e['checks'], 'nal_types': e2e['nal_types']}))
