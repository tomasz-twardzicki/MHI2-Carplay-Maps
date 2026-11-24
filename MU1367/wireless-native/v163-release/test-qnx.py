#!/usr/bin/env python3
"""Full fresh install/OEM reset with actual controllers and firmware utilities.

No child-controller stand-ins. The native verifier is real; its fixture wrapper
recognizes a small JXE gate, and the stat wrapper reports the matching size.
Mount changes are inert (fixture directories live on one RAM filesystem).
Radio/MOST/HMI services are not started.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
for name in ('build', 'inputs', 'firmware', 'setup', 'toolchain', 'output'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(HERE.parents[1] / 'port'))
from firmware import QNX6, image_files, stage1, stage2
sd = a.build.resolve() / 'sd-card'
inputs = a.output.resolve().with_name(a.output.name + '-inputs')
inputs.mkdir(parents=True, exist_ok=False)
# Keep every production controller byte-identical. Only the fixture verifier
# and stat boundary recognize a small JXE marker instead of the 55 MB image.
fake = b'isolated full-install firmware gate\n'
fake_sha = hashlib.sha256(fake).hexdigest()
fixture_sd = inputs / 'sd'
shutil.copytree(sd / 'Custom', fixture_sd / 'Custom', ignore=shutil.ignore_patterns('source'))
verifier = ("#!/bin/ksh\ncase \"$1\" in */ifs/lsd.jxe)\n"
            + ' /proc/boot/verify \"$1\" ' + fake_sha + ' || exit 1\n'
            + ' if [ \"${2:-}\" = 09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a ];then exit 0;fi\n'
            + ';;esac\nexec /proc/boot/verify \"$@\"\n').encode()
original_verifier = hashlib.sha256((sd / 'Custom/carplay_mu1367_release/verify').read_bytes()).hexdigest()
fixture_verifier = hashlib.sha256(verifier).hexdigest()
for f in fixture_sd.rglob('verify'):
    f.write_bytes(verifier)
for f in fixture_sd.rglob('payload-check.sh'):
    f.write_text(f.read_text().replace(original_verifier, fixture_verifier))
(inputs / 'small-jxe').write_bytes(fake)

files = image_files(stage1(a.firmware / 'MMX2/mifs-stage1/50/default/mifs-stage1.img'))
files.update(image_files(stage2(a.firmware / 'MMX2/mifs-stage2/50/default/mifs-stage2.img')))
app = QNX6(a.firmware / 'MMX2/app/50/default/app.img')
extra = {}
for name, data in {
    'factory-basename': app.get('armle/usr/bin/basename'),
    'factory-touch': files['bin/touch'],
    'factory-zlib': (a.inputs / 'libz.so.2').read_bytes(),
}.items():
    (inputs / name).write_bytes(data)
    extra[name] = inputs / name
for name in ('lsd.jxe', 'boot', 'dio', 'driver', 'iap2.cfg', 'gal', 'btstack',
             'connectionmanager', 'bundles.properties', 'connectivity.json', 'smartphone_integrator.json'):
    extra['stock-' + name] = inputs / 'small-jxe' if name == 'lsd.jxe' else a.inputs / name
extra['stock-mmipod'] = sd / 'Custom/carplay_mu1367_oem_reset/payload/mmipod'

code = (HERE.parent / 'tests/receiver-alt-gate.py').read_text()
code = code.replace("b'capacity=32768,nodinit'", "b'capacity=65536,nodinit'")
# Full multi-layer fresh installation hashes the entire SD repeatedly.
code = code.replace("'120','qemu-system-arm'", "'900','qemu-system-arm'").replace('time.monotonic()+100', 'time.monotonic()+850')
ns = {'__file__': str(HERE.parent / 'tests/receiver-alt-gate.py'), '__name__': 'full_fresh_fixture'}
exec(compile(code, ns['__file__'], 'exec'), ns)
ns['SOURCE'] = 'int full_install_no_hardware;\n'
ns['RAM_SECTORS'] = 99999
ifs = '[type=file]\n' + '\n'.join(extra) + '\n'
ifs += 'basename=factory-basename\ntouch=factory-touch\nlibz.so.2=factory-zlib\n'
for f in sorted((fixture_sd / 'Custom').rglob('*')):
    if f.is_file() and f.relative_to(fixture_sd / 'Custom').parts[0].startswith('carplay_'):
        name = 'sd-file-%04d' % len(extra)
        extra[name] = f
        ifs += '/test/sd/' + f.relative_to(fixture_sd).as_posix() + '=' + name + '\n'
ns['EXTRA_FILES'] = extra
ns['IFS_EXTRA'] = ifs
ns['PASS_MARKER'] = 'V163E_FULL_FRESH_OEM_QNX_PASS'
script = r'''#!/bin/ksh
set -eu
export PATH=/ramdisk/tools:/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
export CPMAP_TEST_ROOT=/ramdisk/unit
M=$CPMAP_TEST_ROOT
mkdir -p /ramdisk/tools
echo '#!/bin/ksh' > /ramdisk/tools/mount
echo 'case "$1" in -uw) exit 0;;esac;exec /proc/boot/mount "$@"' >> /ramdisk/tools/mount
chmod 755 /ramdisk/tools/mount
echo '#!/bin/ksh' > /ramdisk/tools/ls
echo 'case "$*" in *-ln*ifs/lsd.jxe) echo "-rwxr-xr-x 1 0 0 55840541 Nov 21 00:00 lsd.jxe";exit 0;;esac;exec /proc/boot/ls "$@"' >> /ramdisk/tools/ls
chmod 755 /ramdisk/tools/ls
mkdir -p /ramdisk/sd "$M/ifs" "$M/ramdisk" "$M/dev/shmem" "$M/mnt/ota" "$M/mnt/persist" "$M/proc/boot" "$M/mnt/icab/persistent"
cp /proc/boot/libz.so.2 "$M/proc/boot/libz.so.2"
'''
for dest, name in {
    'ifs/lsd.jxe': 'lsd.jxe', 'mnt/app/eso/hmi/lsd/lsd.sh': 'boot',
    'mnt/app/eso/bin/apps/dio_manager': 'dio',
    'mnt/app/armle/lib/dll/ipod-drvr-iap2.so': 'driver',
    'mnt/system/etc/mm/iap2.cfg': 'iap2.cfg',
    'mnt/app/eso/bin/apps/gal': 'gal',
    'mnt/app/armle/usr/sbin/mm-ipod': 'mmipod',
    'mnt/app/eso/bin/apps/btstack': 'btstack',
    'mnt/app/eso/bin/apps/connectionmanager': 'connectionmanager',
    'mnt/app/eso/hmi/lsd/config/bundles.properties': 'bundles.properties',
    'mnt/system/etc/eso/production/connectivity.json': 'connectivity.json',
    'mnt/system/etc/eso/production/smartphone_integrator.json': 'smartphone_integrator.json',
}.items():
    script += 'mkdir -p "$M/' + str(Path(dest).parent) + '"\ncp /proc/boot/stock-' + name + ' "$M/' + dest + '"\n'
script += r'''
mkdir -p "$M/mnt/app/eso/hmi/lsd/jars" "$M/mnt/app/eso/hmi/engdefs/scripts"
chmod 755 "$M/mnt/app/eso/bin/apps/dio_manager" "$M/mnt/app/eso/hmi/lsd/lsd.sh" "$M/mnt/app/eso/bin/apps/gal"
P=/test/sd/Custom/carplay_mu1367_release
V=$P/verify
run(){ /bin/ksh "$P/control.sh" "$1" "$P"; }
boot(){ rm -f "$M/ramdisk/.cpmap-release-v163e-reboot" "$M/ramdisk/.cpmap-release-migration-reboot"; }
echo V163E_FRESH_BEGIN
run install
test -f "$M/mnt/app/carplay-mu1367-guidance-v3/STATE"
if run install;then exit 81;fi
boot
run install
test "$(cat "$M/mnt/app/carplay-mu1367-wireless-native-v163t2/STATE")" = installed
boot
run install
echo V163E_FRESH_INSTALL_PASS
run restore-oem
boot
run restore-oem
boot
O=/test/sd/Custom/carplay_mu1367_oem_reset
/bin/ksh "$O/control.sh" verify "$O"
run restore-oem
echo V163E_LOCAL_OEM_PASS
'''
# Seed actual v3.2 target paths with foreign bytes and incomplete journals:
# forward factory recovery must not depend on old executable scripts/receipts.
om = json.loads((sd / 'Custom/carplay_mu1367_oem_reset/manifest.json').read_text())
script += 'rm -rf "$M/mnt/app/carplay-mu1367-oem-reset"\n'
for path in om['additional_removed_files']:
    script += 'mkdir -p "$M' + str(Path(path).parent) + '"\necho upstream > "$M' + path + '"\n'
for row in om['additional_factory_files'].values():
    script += 'echo upstream > "$M' + row['target'] + '"\n'
script += r'''
mkdir -p "$M/mnt/app/eso/hmi/engdefs/scripts/wireless-carplay-maps/feature-backup" "$M/mnt/app/carplaymaps" "$M/mnt/persist/wcp"
echo retained > "$M/mnt/app/eso/hmi/engdefs/scripts/wireless-carplay-maps/feature-backup/journal"
echo paired > "$M/mnt/persist/wcp/pairing.key"
echo active > "$M/dev/shmem/wcp_cp_session"
if run restore-oem;then exit 82;fi
test ! -e "$M/mnt/app/carplay-mu1367-oem-reset"
rm "$M/dev/shmem/wcp_cp_session"
boot
run restore-oem
boot
/bin/ksh "$O/control.sh" verify "$O"
grep retained "$M/mnt/app/carplay-mu1367-oem-reset/archive/upstream-wireless-manager/feature-backup/journal"
grep paired "$M/mnt/persist/wcp/pairing.key"
echo V163E_FULL_FRESH_OEM_QNX_PASS
'''
ns['RUN_SCRIPT'] = script
ns['EVIDENCE'] = dict(scope='Actual full fresh base/wireless controllers, idempotent adoption, local OEM rollback, upstream file-layout forward reset; native verifier/factory tools; only JXE hash/size substituted at verifier/stat boundaries in fixture; mounts inert.',
                      controller_sha256=hashlib.sha256((sd / 'Custom/carplay_mu1367_release/control.sh').read_bytes()).hexdigest(),
                      oem_controller_sha256=hashlib.sha256((sd / 'Custom/carplay_mu1367_oem_reset/control.sh').read_bytes()).hexdigest(),
                      child_transactions_stubbed=False)
sys.argv = [sys.argv[0], '--setup', str(a.setup), '--toolchain', str(a.toolchain), '--output', str(a.output)]
ns['main']()
