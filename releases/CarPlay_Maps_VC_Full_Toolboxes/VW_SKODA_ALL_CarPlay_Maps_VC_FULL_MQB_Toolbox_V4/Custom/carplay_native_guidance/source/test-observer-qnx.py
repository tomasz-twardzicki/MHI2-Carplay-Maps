#!/usr/bin/env python3
"""Execute C4's production reader on QNX/QEMU with factory MMX libc and pipe.

The QEMU BSP/startup artifacts come from the pinned toolchain, not the car.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('toolchain', type=Path)
    parser.add_argument('firmware', type=Path)
    parser.add_argument('--output', type=Path, default=HERE / 'build-C4-qnx-check')
    parser.add_argument('--docker-context', default='colima-cpmap-rgi')
    parser.add_argument('--native-build', type=Path, default=HERE / 'build-C4-native')
    parser.add_argument('--smoke-source', type=Path, default=HERE / 'observer/qnx-smoke.c')
    parser.add_argument('--pass-marker', default='C4_QNX_PASS')
    args = parser.parse_args()
    build = load('build_observer', HERE / 'build-observer.py')
    fixtures = load('pub_fixtures', HERE / 'test-rgi-publication.py')
    commit = subprocess.check_output(['git', '-C', str(args.toolchain), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != build.TOOLCHAIN_COMMIT: parser.error('unexpected toolchain commit')
    work = args.output.resolve(); work.mkdir(parents=True, exist_ok=False)
    sysroot = args.toolchain.resolve() / 'sdp/target/qnx6'
    flags = ['--target=armv7-none-eabi', '-D__QNXNTO__', '-D__QNX__', '-D__ARM__', '-D__LITTLEENDIAN__',
             '--sysroot=' + str(sysroot), '-isystem', str(sysroot / 'usr/include'), '-march=armv7-a',
             '-mfloat-abi=softfp', '-mno-unaligned-access', '-fno-short-enums', '-fno-builtin',
             '-fno-stack-protector', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror']
    for source, name, extra in [('qnx-smoke.c', 'smoke.o', [])]:
        subprocess.run(['clang', *flags, *extra, '-c', str(args.smoke_source if source == 'qnx-smoke.c' else HERE / 'observer' / source), '-o', str(work / name)], check=True)
    binary = (args.native_build / 'rgi-observer').read_bytes()
    manifest = json.loads((args.native_build / 'manifest.json').read_text())
    if hashlib.sha256(binary).hexdigest() != manifest['sha256']:
        parser.error('native reader fingerprint mismatch')
    build.verify(binary, build.firmware_libc(args.firmware))
    (work / 'rgi-observer').write_bytes(binary)
    (work / 'libc.so.3').write_bytes(build.firmware_libc(args.firmware))
    (work / 'pipe').write_bytes(build.firmware_file(args.firmware, 'sbin/pipe'))
    (work / 'snapshot.bin').write_bytes(fixtures.snapshot([(1, 0x5201, fixtures.route()), (2, 0x5202, fixtures.maneuver())]))
    for name in ('startup-virt', 'libstartup.a', 'devc-serdebug', 'u-boot.bin'):
        shutil.copy2(args.toolchain / 'tests/qemu' / name, work / name)
    (work / 'test.build').write_text('''[linker="(40;1;)arm-unknown-nto-qnx6.5.0eabi-ld -m armnto -static -Ttext 0x%t -o%o %i /w/libstartup.a -L/opt/qnx650/target/qnx6/armle-v7/lib -L/opt/qnx650/target/qnx6/armle-v7/usr/lib -llzo -lucl -ldrvr"]
[linker="(40;2;)cp %i %o"]
[image=0x40200000]
[virtual=armle-v7,raw] .bootstrap = {
 startup-virt -v -S
 PATH=:/proc/boot LD_LIBRARY_PATH=:/proc/boot procnto-smp -vvv
}
[+script] .script = {
 procmgr_symlink ../../proc/boot/libc.so.3 /usr/lib/ldqnx.so.2
 devc-serdebug -e -F -S
 waitfor /dev/ser1 4
 reopen /dev/ser1
 pipe
 waitfor /dev/pipe 4
 /proc/boot/c4-smoke ram
 /proc/boot/c4-smoke list
 waitfor /dev/hd0 4
 mkqnx6fs -q /dev/hd0
 mount -t qnx6 -o sync=none /dev/hd0 /ramdisk
 display_msg "@@C4-START@@"
 /proc/boot/c4-smoke
 display_msg "@@C4-END@@"
}
[type=link] /usr/lib/ldqnx.so.2=/proc/boot/libc.so.3
[type=link] /lib/dll/io-blk.so=/proc/boot/io-blk.so
[type=link] /lib/dll/fs-qnx6.so=/proc/boot/fs-qnx6.so
[type=link] /lib/dll/cam-disk.so=/proc/boot/cam-disk.so
[type=link] /lib/libcam.so.2=/proc/boot/libcam.so.2
[type=link] /usr/lib/libblkcache.so.2=/proc/boot/libblkcache.so.2
[type=dir] /ramdisk
[type=file]
[data=copy]
[perms=+r,+x]
libc.so.3
procnto-smp
devc-serdebug
pipe
c4-smoke
rgi-observer
snapshot.bin
devb-ram
mkqnx6fs
mount
libcam.so.2
libm.so.2
io-blk.so
fs-qnx6.so
cam-disk.so
libblkcache.so.2
''')
    root = '/opt/qnx650/target/qnx6/armle-v7'
    (work / 'prepare.sh').write_text(f'''#!/bin/sh
set -eu
T={root}
cp "$T/boot/sys/procnto-smp" /w/procnto-smp
arm-unknown-nto-qnx6.5.0eabi-ld -m armnto -Qy --dynamic-linker /usr/lib/ldqnx.so.2 -L$T/lib $T/lib/crt1.o $T/lib/crti.o $T/lib/crtbegin.o /w/smoke.o -lc $T/lib/crtend.o $T/lib/crtn.o -o /w/c4-smoke
export MKIFS_PATH=/w:$T/boot/sys:$T/bin:$T/sbin:$T/lib:$T/lib/dll:$T/usr/lib
mkifs test.build ifs.bin
mkdir fat
mv ifs.bin fat/
''')
    docker = ['docker', '--context', args.docker_context, 'run', '--rm', '--pull=never', '--network=none', '-i',
              '-v', str(work) + ':/w', '-w', '/w']
    with (work / 'prepare.log').open('w') as log:
        subprocess.run(docker + ['cpmap-qnx65-sdp', 'sh', '/w/prepare.sh'], stdout=log, stderr=subprocess.STDOUT, check=True)
    with (work / 'qemu.log').open('wb') as log:
        process = subprocess.Popen(docker + ['cpmap-qemu-arm', 'timeout', '60', 'qemu-system-arm', '-M', 'virt', '-m', '256',
            '-cpu', 'cortex-a15', '-bios', '/w/u-boot.bin', '-drive',
            'file=fat:rw:/w/fat,format=raw,media=disk', '-nic', 'none', '-display', 'none', '-serial', 'stdio'],
            stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
        def expect(token, offset=0, seconds=15):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline and process.poll() is None:
                data = (work / 'qemu.log').read_bytes()
                at = data.find(token, offset)
                if at >= 0: return at + len(token)
                time.sleep(.1)
            raise RuntimeError('QEMU boot prompt not reached; inspect dedicated qemu.log')
        def send(command):
            process.stdin.write(command); process.stdin.flush()
        try:
            offset = expect(b'Hit any key to stop autoboot:')
            send(b'\n'); offset = expect(b'=> ', offset)
            for command in [b'virtio scan\n', b'fatload virtio 0:1 0x40200000 ifs.bin\n']:
                send(command); offset = expect(b'=> ', offset)
            send(b'go 0x40200000\n')
        except (BrokenPipeError, RuntimeError):
            process.stdin.close(); process.wait(timeout=65)
            raise
        # Polling is confined to this bounded smoke test, not an on-unit shell.
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and process.poll() is None:
            if b'@@C4-END@@' in (work / 'qemu.log').read_bytes(): break
            time.sleep(1)
        process.stdin.close()
        try: process.wait(timeout=65)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
    log = (work / 'qemu.log').read_bytes()
    passed = args.pass_marker.encode() in log and b'@@C4-END@@' in log
    result = {'qnx_smoke_passed': passed, 'work': str(work),
              'factory_libc_sha256': build.FIRMWARE_LIBC_SHA,
              'reader_sha256': hashlib.sha256(binary).hexdigest()}
    (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return 0 if passed else 1


if __name__ == '__main__': raise SystemExit(main())
