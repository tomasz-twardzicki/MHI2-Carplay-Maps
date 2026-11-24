#!/usr/bin/env python3
"""Seal a checked experimental SD; preserve every test2 wireless-layer byte."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
p = argparse.ArgumentParser()
for name in ('build', 'baseline', 'regression-result', 'host-result', 'qnx-result', 'defaults-result', 'output'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
sd = a.build.resolve() / 'sd-card'
custom = sd / 'Custom'
release = custom / 'carplay_mu1367_release'
oem = custom / 'carplay_mu1367_oem_reset'
layer = custom / 'carplay_mu1367_wireless_native'
reports = {name: json.loads(getattr(a, name + '_result').read_text()) for name in ('regression', 'host', 'qnx', 'defaults')}
assert all(r['passed'] for r in reports.values())
assert reports['regression']['tests'] == 11
assert set(reports['regression']['variants']) == {'6', '7', '6-road', '7-road'}
assert reports['host']['tests'] == 4
assert reports['host']['controller_sha256'] == reports['qnx']['controller_sha256'] == sha(release / 'control.sh')
assert reports['host']['oem_controller_sha256'] == reports['qnx']['oem_controller_sha256'] == sha(oem / 'control.sh')
assert not reports['qnx']['child_transactions_stubbed']
assert set(reports['defaults']['variants']) == {'6', '7', '6-road', '7-road'}
assert sha(a.baseline) == '16d7b9f268bb4629a9836df1af9a09056be42aeab98bb3f0b74db25de7da4dba'
with zipfile.ZipFile(a.baseline) as z:
    runtime_files = []
    for f in layer.rglob('*'):
        if f.is_file() and 'source' not in f.relative_to(layer).parts:
            name = f.relative_to(sd).as_posix()
            assert f.read_bytes() == z.read(name), name
            runtime_files.append(name)
    baseline_verification = json.loads(z.read('VERIFICATION.json'))
top = json.loads((sd / 'MU1367_RELEASE_MANIFEST.json').read_text())
assert top['version'] == '1.6.3-e' and top['experimental'] and top['prerelease']
assert top['wireless_runtime_components'] == baseline_verification['components']
for variant, proof in reports['defaults']['variants'].items():
    assert proof['menu_sha256'] == sha(custom / ('carplay_mu1367_guidance_v3/' + variant + '/VCMenu.jar'))
for f in sd.rglob('*.sh'):
    if 'source' not in f.relative_to(sd).parts:
        r = subprocess.run(['/bin/ksh', '-n', str(f)], capture_output=True)
        assert r.returncode == 0, (str(f), r.stderr.decode())

# Independently validate every SD guard reference, including the native layer's
# unchanged local guard. No host verifier is substituted in the deliverable.
guard_checks = 0
for f in custom.glob('*/payload-check.sh'):
    matches = re.findall(r'(?:check "\$P/([^\"]+)"|"\$P/verify" "\$CUSTOM_CHECK/([^\"]+)") ([0-9a-f]{64})', f.read_text())
    assert matches, f
    for local, shared, expected in matches:
        target = f.parent / local if local else custom / shared
        assert sha(target) == expected, target
        guard_checks += 1

source = release / 'source/v163-release'
shutil.rmtree(source)
shutil.copytree(HERE, source, ignore=shutil.ignore_patterns('__pycache__', 'VERIFICATION.json'))
for name in ('README.md', 'START_HERE.md', 'RELEASE-NOTES.md'):
    (sd / name).write_bytes((HERE / name).read_bytes())
verification = dict(
    version='1.6.3-e', passed=True, experimental=True, prerelease=True,
    on_unit_validated=False, baseline_version='1.6.3-e-test2',
    baseline_archive_sha256=sha(a.baseline), wireless_runtime_unchanged=True,
    wireless_runtime_build=top['wireless_runtime_build'],
    wireless_runtime_components=top['wireless_runtime_components'],
    unchanged_wireless_layer_files=len(runtime_files),
    controller_sha256=sha(release / 'control.sh'), oem_controller_sha256=sha(oem / 'control.sh'),
    reports=reports,
    factory_extra=json.loads((HERE / 'FACTORY-EXTRA.json').read_text()),
    upstream_restore_audit=json.loads((HERE / 'UPSTREAM-RESTORE-AUDIT.json').read_text()),
    historical_test2_verification=baseline_verification,
    limits=[
        'Bench tests do not establish radio, MFi, MOST, calls, vehicle display or endurance acceptance.',
        'Factory-QNX tests keep production controllers unchanged; a small JXE marker is accepted only by fixture verifier/stat wrappers, and mounts are inert.',
        'Upstream reset tests seed the exact public transaction target layouts; upstream services/hardware are not executed.',
        'The reported need to install v1.5.4 first was not reproduced with a complete clean SD. Clean base/wireless installation and reboot enforcement are explicitly verified.',
        'Runtime limitations recorded in historical test2 evidence still apply; its open turn-card-default question is superseded by the current packaged-JAR tests.',
    ],
)
for name in ('VERIFICATION.json', 'WIRELESS-VERIFICATION.json'):
    (sd / name).write_text(json.dumps(verification, indent=2) + '\n')
for name in ('FILES_SHA256.json', 'WIRELESS-FILES.sha256'):
    (sd / name).unlink(missing_ok=True)
assert not any(f.is_symlink() for f in sd.rglob('*'))
files = {f.relative_to(sd).as_posix(): sha(f) for f in sorted(sd.rglob('*')) if f.is_file()}
(sd / 'FILES_SHA256.json').write_text(json.dumps(files, indent=2) + '\n')
files['FILES_SHA256.json'] = sha(sd / 'FILES_SHA256.json')
(sd / 'WIRELESS-FILES.sha256').write_text(''.join(h + '  ' + name + '\n' for name, h in sorted(files.items())))
files['WIRELESS-FILES.sha256'] = sha(sd / 'WIRELESS-FILES.sha256')
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
archive = out / 'CarPlay_Maps_VC_MU1367_791_v1.6.3-e.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for name in sorted(files):
        f = sd / name
        i = zipfile.ZipInfo(name, (2026, 11, 21, 0, 0, 0))
        i.compress_type = zipfile.ZIP_DEFLATED
        i.external_attr = (0o100000 | (f.stat().st_mode & 0o777)) << 16
        z.writestr(i, f.read_bytes())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and len(z.namelist()) == len(set(z.namelist())) == len(files)
    assert {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()} == files
package = dict(passed=True, version='1.6.3-e', experimental=True, prerelease=True,
               archive=archive.name, archive_sha256=sha(archive), files=len(files),
               all_zip_entries_verified=True, guard_references_verified=guard_checks,
               wireless_runtime_unchanged=True, on_unit_validated=False)
(out / 'PACKAGE-VERIFICATION.json').write_text(json.dumps(package, indent=2) + '\n')
(out / 'SHA256SUMS.txt').write_text(package['archive_sha256'] + '  ' + archive.name + '\n')
for name in ('README.md', 'START_HERE.md', 'RELEASE-NOTES.md', 'VERIFICATION.json'):
    shutil.copy2(sd / name, out / name)
(HERE / 'VERIFICATION.json').write_text(json.dumps(verification, indent=2) + '\n')
print(json.dumps(package))
