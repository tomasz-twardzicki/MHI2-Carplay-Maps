#!/usr/bin/env python3
"""v1.5.0-e Android Auto layer: controller and gal wrapper on a disposable root (Debian container, ksh93, no network).
Runs with real absolute paths (CPMAP_TEST_ROOT=/), so the shipped wrapper executes unchanged. Never run on a workstation.
SPDX-License-Identifier: GPL-3.0-or-later
  test-android-auto-layer.py --package PACKAGE --inputs INPUTS --verifier HOST_VERIFY --output RESULT_JSON
"""
import argparse, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
p = argparse.ArgumentParser()
for n in ('package', 'inputs', 'verifier', 'output'): p.add_argument('--' + n, type=Path, required=True)
A = p.parse_args()
assert Path('/.dockerenv').exists() or os.environ.get('CPMAP_DISPOSABLE') == '1', 'disposable container only'
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
SRC = A.package / 'sd-card/Custom/carplay_mu1367_android_auto'
SD = Path('/aa-sd'); APP = Path('/mnt/app'); L = APP / 'carplay-mu1367-android-auto'; AA = APP / 'carplaymaps/aa'
GAL = APP / 'eso/bin/apps/gal'; FACTORY = sha(A.inputs / 'gal')
MAN = json.loads((SRC / 'manifest.json').read_text()); WRAP = MAN['wrapper_sha256']
checks = []; fails = []
def check(c, m):
    checks.append(m); print(('ok     ' if c else 'FAILED ') + m, flush=True)
    if not c: fails.append(m)

def fresh(main_version=None):
    for d in ('/mnt', '/ramdisk', '/ifs', str(SD)): shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(SRC, SD); shutil.copy2(A.verifier, SD / 'verify')
    os.makedirs('/ifs'); shutil.copy2(A.inputs / 'lsd.jxe', '/ifs/lsd.jxe')
    os.makedirs('/ramdisk'); (APP / 'eso/bin/apps').mkdir(parents=True); (APP / 'carplaymaps').mkdir()
    shutil.copy2(A.inputs / 'gal', GAL); GAL.chmod(0o755)
    (APP / 'carplaymaps/PROFILE').write_text('MU1367/791\n')
    (APP / 'carplaymaps/altscreen-most-bridge').write_text('#!/bin/sh\n'); (APP / 'carplaymaps/altscreen-most-bridge').chmod(0o755)
    main = APP / 'carplay-mu1367-guidance-v3'; main.mkdir()
    (main / 'STATE').write_text('installed\n'); (main / 'VERSION').write_text((main_version or MAN['main_versions'][2]) + '\n')

TOOLS = Path('/aa-tools'); shutil.rmtree(TOOLS, ignore_errors=True); TOOLS.mkdir()
(TOOLS / 'mount').write_text('#!/bin/sh\nexit 0\n'); (TOOLS / 'mount').chmod(0o755)
# Fault shims: the Nth external command call fails (fail) or kills the controller (kill, a power loss).
SHIMMED = ('cp', 'mv', 'rm', 'mkdir', 'chmod', 'sync', 'cat')
for c in SHIMMED:
    real = shutil.which(c)
    (TOOLS / c).write_text('''#!/bin/sh
if [ -n "${AA_FAULT_AT:-}" ]; then
 n=$(/bin/cat /aa-fault.count 2>/dev/null || echo 0); n=$((n+1)); echo $n > /aa-fault.count
 if [ "$n" = "$AA_FAULT_AT" ]; then
  if [ "$AA_FAULT_MODE" = kill ]; then kill -9 $PPID; exit 137; fi
  exit 1
 fi
fi
exec %s "$@"
''' % real); (TOOLS / c).chmod(0o755)

def ctl(action, env=None, ctl=None):
    e = dict(os.environ, CPMAP_TEST_ROOT='/', PATH=str(TOOLS) + ':' + os.environ['PATH'])
    if env: e.update(env)
    script = ctl or (SD / 'control.sh'); base = SD if ctl is None else ctl.parent
    r = subprocess.run(['/bin/ksh', str(script), action, str(base)], env=e, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr

def runtime_absent(): return not AA.exists() and not (L / 'gal.real').exists() and not Path(str(GAL) + '.aa-new').exists()
def stub_real(target):
    target.write_text('#!/bin/sh\necho "ARGS=$*"\necho "PRELOAD=${LD_PRELOAD:-}"\necho "CONF=${GAL_HOOK_CONF:-}"\necho "PLAYER=${GAL_PLAYER_PATH:-}"\n')
    target.chmod(0o755)
def wrapper(env=None):
    e = {'PATH': '/usr/bin:/bin', 'LD_PRELOAD': 'factory.so'}
    if env: e.update(env)
    r = subprocess.run([str(GAL), 'a', 'b c'], env=e, capture_output=True, text=True, timeout=20)
    last = open('/ramdisk/carplay-aa-last').read() if os.path.exists('/ramdisk/carplay-aa-last') else ''
    return r.returncode, r.stdout, last

# 1. install, idempotent reinstall, exact files
fresh()
rc, out = ctl('install'); check(rc == 0 and 'MU1367_ANDROID_AUTO_INSTALLED_REBOOT_REQUIRED' in out, 'install: ' + out.strip().split('\n')[-1])
check(sha(GAL) == WRAP and GAL.stat().st_mode & 0o777 == 0o755, 'gal is the wrapper, factory mode kept')
check(sha(L / 'gal.real') == FACTORY == sha(L / 'backup/gal') and (L / 'backup/gal.sha256').read_text().strip() == FACTORY, 'factory gal snapshot and run copy')
check(all(sha(AA / n) == h for n, h in MAN['files'].items()), 'runtime files exact')
check((AA / 'aa-most-feeder').stat().st_mode & 0o777 == 0o755 and (AA / 'gal-hook.conf').stat().st_mode & 0o777 == 0o644, 'runtime modes')
check((L / 'STATE').read_text().strip() == 'installed' and (L / 'VERSION').read_text().strip() == MAN['build_id'], 'state and identity')
check(sha(L / 'control.sh') == sha(SD / 'control.sh'), 'controller saved on the unit')
rc, out = ctl('install'); check(rc == 0 and 'MU1367_ANDROID_AUTO_ALREADY_INSTALLED' in out, 'second install is a no-op')

# 2. wrapper decisions (a stub stands in for the factory gal; it prints what it was started with)
stub_real(L / 'gal.real')
rc, out, last = wrapper()
check(rc == 0 and 'ARGS=a b c' in out and 'PRELOAD=/mnt/app/carplaymaps/aa/libgal_hook.so:factory.so' in out
      and 'CONF=/mnt/app/carplaymaps/aa/gal-hook.conf' in out and 'PLAYER=/mnt/app/carplaymaps/aa/aa-most-feeder' in out
      and last.startswith('hook=yes'), 'wrapper: hook preloaded, arguments and existing preload kept')
rc, out = ctl('disable'); check(rc == 0 and (L / 'DISABLED').exists(), 'menu off: DISABLED marker')
rc, out, last = wrapper(); check('PRELOAD=factory.so' in out and 'CONF=\n' in out and last.startswith('hook=no'), 'wrapper: menu off runs factory gal untouched')
rc, out = ctl('enable'); check(rc == 0 and not (L / 'DISABLED').exists(), 'menu on: marker removed')
(APP / 'carplaymaps/stock_first').mkdir(); (APP / 'carplaymaps/stock_first/DISABLED').write_text('')
rc, out, last = wrapper(); check(last.startswith('hook=no'), 'wrapper: CarPlay Maps stock-first switch disables the hook too')
shutil.rmtree(APP / 'carplaymaps/stock_first')
os.rename(AA / 'aa-most-feeder', AA / 'x'); rc, out, last = wrapper(); check(last.startswith('hook=no') and 'PRELOAD=factory.so' in out, 'wrapper: missing feeder -> factory gal')
os.rename(AA / 'x', AA / 'aa-most-feeder')
os.rename(AA / 'altscreen-most-bridge-aa', AA / 'b'); rc, out, last = wrapper(); check(last.startswith('hook=no'), 'wrapper: missing Android Auto bridge -> factory gal')
os.rename(AA / 'b', AA / 'altscreen-most-bridge-aa')
os.rename(L / 'gal.real', L / 'g'); bk = (L / 'backup/gal').read_bytes(); stub_real(L / 'backup/gal')
rc, out, last = wrapper(); check(rc == 0 and 'ARGS=a b c' in out, 'wrapper: run copy missing -> snapshot copy runs')
(L / 'backup/gal').write_bytes(bk); os.rename(L / 'g', L / 'gal.real')
shutil.copy2(L / 'backup/gal', L / 'gal.real')
rc, out = ctl('status'); check(rc == 0 and 'ANDROID_AUTO_STATE=installed' in out and 'hook=' in out, 'status')

# 3. uninstall restores the factory gal; reinstall keeps the removed session
rc, out = ctl('uninstall'); check(rc == 0 and 'FACTORY_GAL_RESTORED' in out, 'uninstall')
check(sha(GAL) == FACTORY and GAL.stat().st_mode & 0o777 == 0o755 and runtime_absent() and (L / 'STATE').read_text().strip() == 'removed'
      and sha(L / 'backup/gal') == FACTORY, 'factory gal back, runtime gone, snapshot kept')
rc, out = ctl('install'); check(rc == 0 and 'RETAINED_SESSION' in out and 'INSTALLED_REBOOT_REQUIRED' in out
                                and any(p.name.startswith('carplay-mu1367-android-auto.removed-') for p in APP.iterdir()), 'reinstall keeps the removed snapshot')
rc, out = ctl('uninstall', ctl=L / 'control.sh'); check(rc == 0 and sha(GAL) == FACTORY, 'uninstall from the saved controller without the SD')

# 4. after an OEM reset (carplaymaps archived): factory gal still runs; the saved controller restores it,
#    or a later install repairs the runtime
def oem_reset():
    shutil.rmtree('/archived-carplaymaps', ignore_errors=True)
    shutil.move(str(APP / 'carplaymaps'), '/archived-carplaymaps')
def oem_reinstall_base():
    (APP / 'carplaymaps').mkdir(); shutil.copy2('/archived-carplaymaps/PROFILE', APP / 'carplaymaps/PROFILE')
    shutil.copy2('/archived-carplaymaps/altscreen-most-bridge', APP / 'carplaymaps/altscreen-most-bridge')
fresh(); ctl('install'); oem_reset()
stub_real(L / 'gal.real'); rc, out, last = wrapper(); check(rc == 0 and last.startswith('hook=no') and 'PRELOAD=factory.so' in out, 'OEM reset: wrapper runs the factory gal')
shutil.copy2(L / 'backup/gal', L / 'gal.real')
rc, out = ctl('uninstall', ctl=L / 'control.sh')
check(rc == 0 and sha(GAL) == FACTORY and not (APP / 'carplaymaps').exists(), 'OEM reset: saved controller restores the factory gal without carplaymaps')
fresh(); ctl('install'); oem_reset(); oem_reinstall_base()
rc, out = ctl('install'); check(rc == 0 and 'INCOMPLETE_RUNTIME_RESTORED_REINSTALLING' in out and 'INSTALLED_REBOOT_REQUIRED' in out
                                and all(sha(AA / n) == h for n, h in MAN['files'].items()), 'reinstall after OEM reset repairs the runtime')

# 4b. in-place upgrade of layers installed by the published v1.5.0-e and both v1.5.1-e controllers (car units already have one)
for OLD_REV in ('release-v1.5.0-e', 'release-v1.5.1-e-first', 'release-v1.5.1-e'):
    OLD = Path(__file__).resolve().parent / 'revisions' / OLD_REV / 'carplay_mu1367_android_auto'
    # The old controller installs only on its own main layer; v1.5.1-e changed the main layer, so the old Android Auto
    # layer is then left on top of this release's main layer (the AA_PREVIOUS in-place path).
    fresh(json.loads((OLD / 'manifest.json').read_text())['main_versions'][2])
    OSD = Path('/aa-old-sd'); shutil.rmtree(OSD, ignore_errors=True); shutil.copytree(OLD, OSD); shutil.copy2(A.verifier, OSD / 'verify')
    rc, out = ctl('install', ctl=OSD / 'control.sh')
    old_build = (OSD / 'VERSION').read_text().strip()
    (APP / 'carplay-mu1367-guidance-v3/VERSION').write_text(MAN['main_versions'][2] + '\n')
    check(rc == 0 and (L / 'VERSION').read_text().strip() == old_build and sha(GAL) == json.loads((OLD / 'manifest.json').read_text())['wrapper_sha256'] != FACTORY, 'published %s layer installed (its own wrapper)' % OLD_REV)
    rc, out = ctl('install')
    check(rc == 0 and 'PREVIOUS_BUILD_REMOVED_UPGRADING' in out and 'RETAINED_SESSION' in out and 'INSTALLED_REBOOT_REQUIRED' in out
          and sha(GAL) == WRAP and (L / 'VERSION').read_text().strip() == MAN['build_id'] and all(sha(AA / n) == h for n, h in MAN['files'].items()),
          '%s layer upgraded in place: factory gal restored first, old snapshot retained' % OLD_REV)
    check(any(sha(q / 'backup/gal') == FACTORY for q in APP.glob('carplay-mu1367-android-auto.removed-*')), 'old factory snapshot kept')
    rc, out = ctl('uninstall', ctl=L / 'control.sh'); check(rc == 0 and sha(GAL) == FACTORY and runtime_absent(), 'upgraded layer removes cleanly')

# 5. gates change nothing
fresh(); GAL.write_bytes(b'other'); rc, out = ctl('install')
check(rc != 0 and 'UNEXPECTED_FACTORY_GAL' in out and not L.exists() and not AA.exists() and GAL.read_bytes() == b'other', 'unknown gal refused, nothing written')
fresh('mu1367-guidance-v3-000000000000'); rc, out = ctl('install')
check(rc != 0 and 'EXACT_RELEASE_MAIN_LAYER_REQUIRED' in out and not L.exists() and sha(GAL) == FACTORY, 'other main layer refused')
fresh(); (APP / 'carplaymaps/aa').mkdir(); rc, out = ctl('install')
check(rc != 0 and 'ANDROID_AUTO_RUNTIME_DIRECTORY_EXISTS' in out and sha(GAL) == FACTORY, 'foreign runtime directory refused')
fresh(); (SD / 'aa-most-feeder').write_bytes(b'x'); rc, out = ctl('install')
check(rc != 0 and 'PAYLOAD_HASH_aa-most-feeder' in out and not L.exists(), 'damaged SD payload refused before writes')
fresh(); rc, out = ctl('uninstall'); check(rc != 0 and sha(GAL) == FACTORY, 'uninstall without layer refused')

# 6. fault injection at every external command: rollback (fail) and power loss (kill) + recover
def fault_run(mode):
    n = 1; cases = 0; ok = True
    while True:
        fresh()
        if os.path.exists('/aa-fault.count'): os.unlink('/aa-fault.count')
        e = dict(os.environ, CPMAP_TEST_ROOT='/', PATH=str(TOOLS) + ':' + os.environ['PATH'], AA_FAULT_AT=str(n), AA_FAULT_MODE=mode)
        proc = subprocess.Popen(['/bin/ksh', str(SD / 'control.sh'), 'install', str(SD)], env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out = proc.communicate(timeout=120)[0]
        calls = int(open('/aa-fault.count').read()) if os.path.exists('/aa-fault.count') else 0
        if proc.returncode == 0 and calls < n: break           # no fault reached: install completed
        cases += 1
        g = sha(GAL)
        if mode == 'fail' and proc.returncode != 0 and g != FACTORY: ok = False; print('rollback left gal changed at', n, out)
        shutil.rmtree('/ramdisk/.carplay-guidance-install-lock', ignore_errors=True)   # a power cycle clears the RAM disk
        if L.exists():
            rc, o2 = ctl('recover')
            if rc != 0: ok = False; print('recover failed at', n, o2)
        if sha(GAL) != FACTORY or not runtime_absent(): ok = False; print('not factory after recover at', n, out)
        rc, o3 = ctl('install')
        if rc != 0 or sha(GAL) != WRAP: ok = False; print('install after recover failed at', n, o3)
        n += 1
    return cases, ok
for mode in ('fail', 'kill'):
    cases, ok = fault_run(mode)
    check(ok and cases >= 20, '%s at each of %d command calls: factory gal or clean install after recover' % (mode, cases))

json.dump({'passed': not fails, 'checks': len(checks), 'failed': fails, 'layer_build': MAN['build_id'], 'wrapper_sha256': WRAP,
           'factory_gal_sha256': FACTORY, 'controller_sha256': sha(SRC / 'control.sh'), 'on_unit_validated': False}, open(A.output, 'w'), indent=2)
print('FAILED CHECKS: %d' % len(fails)); sys.exit(1 if fails else 0)
