#!/usr/bin/env python3
"""v1.5.0-e: run the release aa-most-feeder on QNX 6.5 (QEMU) with the MU1367 factory libc.so.3 and libsocket.so.3.
SPDX-License-Identifier: GPL-3.0-or-later
  test-aa-feeder-qnx.py --build AA_FEEDER_BUILD --reader-setup READER_SETUP --firmware K4525_DIR --output OUT
"""
import argparse, hashlib, json, shutil, subprocess, sys, time, zlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'port'))
from firmware import image_files, stage1
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('build', 'reader-setup', 'firmware', 'output'): p.add_argument('--' + n, type=Path, required=True)
    a = p.parse_args(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    m = json.loads((a.build / 'manifest.json').read_text()); feeder = a.build / 'aa-most-feeder'
    assert sha(feeder) == m['sha256'] and m['passed']
    rs = a.reader_setup.resolve()
    for n in ('startup-virt', 'libstartup.a', 'devc-serdebug', 'u-boot.bin', 'libc.so.3', 'pipe', 'snapshot.bin', 'c4-smoke'): shutil.copy2(rs / n, out / n)
    files = image_files(stage1(a.firmware / 'MMX2/mifs-stage1/50/default/mifs-stage1.img'))
    (out / 'libsocket.so.3').write_bytes(files['lib/libsocket.so.3'])
    assert sha(out / 'libc.so.3') == m['factory_libraries']['proc/boot/libc.so.3']
    assert sha(out / 'libsocket.so.3') == m['factory_libraries']['lib/libsocket.so.3']
    shutil.copy2(feeder, out / 'aa-most-feeder')
    body = b'format=3\nvc_map_mask=0\nvc_mirror_mask=0\ncarplay_information=0\ngeneration=7\n'
    flags = ['--target=armv7-none-eabi', '-D__QNXNTO__', '-D__QNX__', '-D__ARM__', '-D__LITTLEENDIAN__', '--sysroot=' + str(a.build.resolve()),
             '-isystem', str(a.build.resolve() / 'sdk-include'), '-march=armv7-a', '-mfloat-abi=softfp', '-mno-unaligned-access',
             '-fno-short-enums', '-fno-builtin', '-fno-stack-protector', '-std=gnu99', '-O2', '-Wall', '-Wextra', '-Werror',
             '-DPREF_CRC="%x"' % zlib.crc32(body)]
    subprocess.run(['clang', *flags, '-c', str(HERE / 'android-auto/aa-qnx-smoke.c'), '-o', str(out / 'smoke.o')], check=True)
    docker = ['docker', '--context', 'colima-cpmap-rgi', 'run', '--rm', '--pull=never', '--network=none', '-i', '-v', str(out) + ':/w', '-w', '/w']
    lib = '/opt/qnx650/target/qnx6/armle-v7/lib'
    subprocess.run(docker + [m['image_id'], 'arm-unknown-nto-qnx6.5.0eabi-ld', '-m', 'armnto', '-Qy', '--dynamic-linker', '/usr/lib/ldqnx.so.2',
                             '-L' + lib, lib + '/crt1.o', lib + '/crti.o', lib + '/crtbegin.o', '/w/smoke.o', '-lc', lib + '/crtend.o', lib + '/crtn.o',
                             '-o', '/w/aa-qnx-smoke'], check=True)
    for n in ('aa-dmdt-stub', 'aa-bridge-stub'): shutil.copy2(out / 'aa-qnx-smoke', out / n)
    t = (rs / 'test.build').read_text()
    # c4-smoke (reader setup) only provides the RAM disk for /ramdisk here: 'ram' and 'list'.
    t = t.replace(' display_msg "@@C4-START@@"\n /proc/boot/c4-smoke\n display_msg "@@C4-END@@"\n',
                  ' display_msg "@@C4-START@@"\n /proc/boot/aa-qnx-smoke\n display_msg "@@C4-END@@"\n')
    assert '/proc/boot/aa-qnx-smoke' in t and 'c4-smoke' in t
    t = t.replace('\nc4-smoke\nrgi-observer\n', '\nc4-smoke\naa-qnx-smoke\naa-dmdt-stub\naa-bridge-stub\naa-most-feeder\nlibsocket.so.3\n')
    t = t.replace('[type=link] /usr/lib/ldqnx.so.2=/proc/boot/libc.so.3\n',
                  '[type=link] /usr/lib/ldqnx.so.2=/proc/boot/libc.so.3\n[type=link] /lib/libsocket.so.3=/proc/boot/libsocket.so.3\n')
    assert 'aa-most-feeder' in t and 'rgi-observer' not in t
    (out / 'test.build').write_text(t)
    (out / 'prepare.sh').write_text('''set -eu
T=/opt/qnx650/target/qnx6/armle-v7
cp "$T/boot/sys/procnto-smp" /w/procnto-smp
export MKIFS_PATH=/w:$T/boot/sys:$T/bin:$T/sbin:$T/lib:$T/lib/dll:$T/usr/lib
mkifs test.build ifs.bin
mkdir fat
mv ifs.bin fat/
''')
    with (out / 'prepare.log').open('w') as log:
        subprocess.run(docker + [m['image_id'], 'sh', '/w/prepare.sh'], stdout=log, stderr=subprocess.STDOUT, check=True)
    logpath = out / 'qemu.log'
    with logpath.open('wb') as log:
        proc = subprocess.Popen(docker + ['cpmap-qemu-arm', 'timeout', '120', 'qemu-system-arm', '-M', 'virt', '-m', '256', '-cpu', 'cortex-a15',
                                          '-bios', '/w/u-boot.bin', '-drive', 'file=fat:rw:/w/fat,format=raw,media=disk', '-nic', 'none',
                                          '-display', 'none', '-serial', 'stdio'], stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
        def expect(token, offset=0, wait=90):
            end = time.monotonic() + wait
            while time.monotonic() < end and proc.poll() is None:
                pos = logpath.read_bytes().find(token, offset)
                if pos >= 0: return pos + len(token)
                time.sleep(.1)
            raise RuntimeError('QNX marker missing: ' + token.decode())
        def send(b): proc.stdin.write(b); proc.stdin.flush()
        try:
            at = expect(b'Hit any key to stop autoboot:'); send(b'\n'); at = expect(b'=> ', at)
            for c in (b'virtio scan\n', b'fatload virtio 0:1 0x40200000 ifs.bin\n'): send(c); at = expect(b'=> ', at)
            send(b'go 0x40200000\n'); expect(b'@@C4-END@@', at)
        finally:
            proc.stdin.close(); proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
    log = logpath.read_text(errors='replace')
    assert 'AA_FEEDER_QNX_PASS' in log, log[-5000:]
    r = {'passed': True, 'feeder_sha256': sha(feeder), 'factory_libc_sha256': sha(out / 'libc.so.3'),
         'factory_libsocket_sha256': sha(out / 'libsocket.so.3'), 'checks': log.count('ok    '),
         'qemu_log_sha256': sha(logpath), 'test_sha256': sha(Path(__file__)), 'on_unit_validated': False}
    (out / 'result.json').write_text(json.dumps(r, indent=2) + '\n'); print(json.dumps(r))

if __name__ == '__main__':
    main()
