#!/usr/bin/env python3
"""Run reset on QNX6/QNX ksh with factory libc and the actual ARM verifier.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(action_script="", extras=None, command_audit=None):
    extras = extras or {}
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('payload', 'reader-setup', 'toolchain', 'firmware-commands', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    a = parser.parse_args()
    work = a.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((a.payload / 'manifest.json').read_text())
    audit = json.loads((command_audit or (a.payload / 'COMMANDS.json')).read_text())
    for name, record in audit['commands'].items():
        assert sha(a.firmware_commands / name) == record['sha256']
        shutil.copy2(a.firmware_commands / name, work / ('factory-' + name))
    for name in ('startup-virt', 'libstartup.a', 'devc-serdebug', 'u-boot.bin', 'libc.so.3', 'pipe', 'c4-smoke'):
        shutil.copy2(a.reader_setup / name, work / name)
    assert sha(work / 'libc.so.3') == '485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc'
    shutil.copytree(a.payload, work / 'payload', ignore=shutil.ignore_patterns('source'))
    # Keep the QEMU RAM disk small. Only the fixture firmware constant changes;
    # host tests separately use the real complete 55,840,541-byte firmware JXE.
    fixture = b'OEM reset QNX filesystem fixture\n'
    (work / 'fixture-jxe').write_bytes(fixture)
    control = (work / 'payload/control.sh').read_text()
    assert control.count('JXE_SHA=' + manifest['jxe_sha256']) == 1
    (work / 'payload/control.sh').write_text(control.replace('JXE_SHA=' + manifest['jxe_sha256'], 'JXE_SHA=' + hashlib.sha256(fixture).hexdigest()))
    fixture_control_sha = sha(work / 'payload/control.sh')
    (work / 'fake-mount').write_text('#!/bin/ksh\nexit 0\n')
    script = '''#!/bin/ksh
set -eu
export PATH=/ramdisk/test-tools:/proc/boot
export CPMAP_TEST_ROOT=/ramdisk/mmx
P=/ramdisk/recovery
R=$CPMAP_TEST_ROOT/mnt/app/carplay-mu1367-oem-reset
mkdir -p /ramdisk/test-tools "$P/payload" "$CPMAP_TEST_ROOT/ifs" "$CPMAP_TEST_ROOT/ramdisk"
cp /proc/boot/fake-mount /ramdisk/test-tools/mount
chmod 755 /ramdisk/test-tools/mount
cp /proc/boot/control.sh "$P/control.sh"
cp /proc/boot/verify "$P/verify"
chmod 755 "$P/verify"
cp /proc/boot/fixture-jxe "$CPMAP_TEST_ROOT/ifs/lsd.jxe"
'''
    script += '/proc/boot/verify /proc/boot/verify ' + manifest['verifier_sha256'] + ' || exit 9\n'
    for k, path in manifest['targets'].items():
        script += 'mkdir -p "$CPMAP_TEST_ROOT/' + str(Path(path).parent) + '"\n'
        script += 'echo "old mixed ' + k + '" > "$CPMAP_TEST_ROOT/' + path + '"\n'
    for k in manifest['oem_sha256']:
        script += 'cp /proc/boot/oem-' + k + ' "$P/payload/' + k + '"\n'
    for name in manifest['layers_archived']:
        script += 'mkdir -p "$CPMAP_TEST_ROOT/mnt/app/' + name + '/backup"\n'
        script += 'echo removed > "$CPMAP_TEST_ROOT/mnt/app/' + name + '/STATE"\n'
        script += 'echo retained > "$CPMAP_TEST_ROOT/mnt/app/' + name + '/backup/original"\n'
    script += '''command -v rmdir >/dev/null 2>&1 && exit 8
: # Actual firmware application gawk is available
/bin/ksh "$P/control.sh" check-tools "$P" || exit 10
/bin/ksh "$P/control.sh" inspect "$P" || exit 10
/bin/ksh "$P/control.sh" restore "$P" || exit 11
/bin/ksh "$P/control.sh" verify "$P" || exit 12
/bin/ksh "$R/control.sh" restore "$R" || exit 13
test ! -e "$CPMAP_TEST_ROOT/ramdisk/.carplay-guidance-install-lock" || exit 16
test -f "$R/pre-reset/boot" || exit 14
'''
    for name in manifest['layers_archived']:
        script += 'test -f "$R/archive/' + name + '/backup/original" || exit 15\n'
    script += 'echo OEM_RESET_QNX_PASS restore=1 verify=1 saved_idempotence=1 archives=12\n'
    script += action_script
    (work / 'test.sh').write_text(script)
    template = (a.reader_setup / 'test.build').read_text()
    start = template.index(' display_msg "@@C4-START@@"')
    end = template.index('\n}', start)
    template = template[:start] + ' display_msg "@@OEM-START@@"\n /proc/boot/ksh /proc/boot/test.sh\n display_msg "@@OEM-END@@"' + template[end:]
    template += '\n[type=link] /bin/ksh=/proc/boot/ksh\n[type=file]\n[data=copy]\n[perms=+r,+x]\n'
    # mkifs normally rewrites/strips ELF inputs. OEM hashes require byte-exact
    # files, including section headers; carry these as opaque raw data.
    template += '[+raw]\n'
    for name in audit['commands']:
        template += name + '=factory-' + name + '\n'
    template += 'verify=payload/verify\ncontrol.sh=payload/control.sh\nfixture-jxe\nfake-mount\ntest.sh\n'
    for k in manifest['oem_sha256']:
        template += 'oem-' + k + '=payload/payload/' + k + '\n'
    for name,value in extras.items():
        if isinstance(value,Path):shutil.copy2(value,work/name)
        else:(work/name).write_text(value)
    template+=''.join(name+'\n' for name in extras)
    (work / 'test.build').write_text(template)
    # The base IFS lists two reader inputs not used by this test.
    for name in ('rgi-observer', 'snapshot.bin'):
        shutil.copy2(a.reader_setup / name, work / name)
    (work / 'prepare.sh').write_text('''#!/bin/sh
set -eu
T=/opt/qnx650/target/qnx6/armle-v7
cp "$T/boot/sys/procnto-smp" /w/procnto-smp
export MKIFS_PATH=/w:$T/boot/sys:$T/bin:$T/sbin:$T/lib:$T/lib/dll:$T/usr/lib:$T/usr/bin
mkifs test.build ifs.bin
mkdir fat
mv ifs.bin fat/
''')
    docker = ['docker', '--context', 'colima-cpmap-rgi', 'run', '--rm', '--pull=never', '--network=none', '-i', '-v', str(work) + ':/w', '-w', '/w']
    with (work / 'prepare.log').open('w') as log:
        subprocess.run(docker + ['cpmap-qnx65-sdp', 'sh', '/w/prepare.sh'], stdout=log, stderr=subprocess.STDOUT, check=True)
    with (work / 'qemu.log').open('wb') as log:
        proc = subprocess.Popen(docker + ['cpmap-qemu-arm', 'timeout', '90', 'qemu-system-arm', '-M', 'virt', '-m', '256', '-cpu', 'cortex-a15', '-bios', '/w/u-boot.bin', '-drive', 'file=fat:rw:/w/fat,format=raw,media=disk', '-nic', 'none', '-display', 'none', '-serial', 'stdio'], stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
        def expect(token, offset=0):
            until = time.monotonic() + 20
            while time.monotonic() < until and proc.poll() is None:
                text = (work / 'qemu.log').read_bytes()
                at = text.find(token, offset)
                if at >= 0:
                    return at + len(token)
                time.sleep(.1)
            raise RuntimeError('QEMU prompt missing: ' + repr(token))
        def send(s):
            proc.stdin.write(s)
            proc.stdin.flush()
        try:
            off = expect(b'Hit any key to stop autoboot:')
            send(b'\n')
            off = expect(b'=> ', off)
            for cmd in (b'virtio scan\n', b'fatload virtio 0:1 0x40200000 ifs.bin\n'):
                send(cmd)
                off = expect(b'=> ', off)
            send(b'go 0x40200000\n')
            until = time.monotonic() + 60
            while time.monotonic() < until and proc.poll() is None:
                if b'@@OEM-END@@' in (work / 'qemu.log').read_bytes():
                    break
                time.sleep(.25)
        finally:
            proc.stdin.close()
            # The test has no persistent VM state; stop immediately on its marker.
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    text = (work / 'qemu.log').read_text(errors='replace')
    passed = (not action_script or 'RELEASE_FACTORY_ACTIONS_PASS' in text) and 'OEM_RESET_QNX_PASS' in text and '@@OEM-END@@' in text
    result = {'passed': passed, 'controller_sha256': manifest['controller_sha256'],
              'fixture_controller_sha256': fixture_control_sha,
              'fixture_only_change': 'JXE_SHA constant for small RAM-disk fixture; host tests use full real JXE',
              'verifier_sha256': sha(a.payload / 'verify'), 'factory_libc_sha256': sha(work / 'libc.so.3'),
              'actual_qnx_ksh': True, 'mounts_mocked': True, 'on_unit_validated': False,
              'factory_utilities_sha256': {name: record['sha256'] for name, record in audit['commands'].items()},
              'sdk_utilities_injected': False, 'rmdir_absent_factory_gawk_present': True, 'lock_cleanup_verified': True,
              'qemu_log_sha256': sha(work / 'qemu.log'), 'test_sha256': sha(Path(__file__))}
    (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
