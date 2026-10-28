#!/usr/bin/env python3
"""Check N0 linking and RAM writes using factory ARM J9 under QNX/QEMU.

Reuses the navigation project's pinned QNX extraction and C4 VM setup.
No unit access, networking, or firmware redistribution.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time
import zipfile
import zlib

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('build', type=Path)
    p.add_argument('--stage2', type=Path, required=True)
    p.add_argument('--firmware', type=Path, required=True)
    p.add_argument('--java-home', type=Path, required=True)
    p.add_argument('--stock-jar', type=Path, required=True)
    p.add_argument('--toolchain', type=Path, required=True)
    p.add_argument('--setup', type=Path, required=True)
    p.add_argument('--docker-context', default='colima-cpmap-rgi')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    spec = importlib.util.spec_from_file_location(
        'guidance_qnx', HERE.parent / 'route-guidance/test-live-qnx.py')
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    manifest = json.loads((a.build / 'manifest.json').read_text())
    jar = a.build / manifest.get('jar_name', 'CarPlayNowPlayingObserverN0.jar')
    probe_source = HERE / manifest.get('probe_source', 'java/LoadObserver.java')
    probe_class = manifest.get('probe_class', 'com.cpmap.audio.LoadObserver')
    if sha(jar.read_bytes()) != manifest['jar_sha256']:
        p.error('observer manifest mismatch')
    work = a.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    (work / 'probe').mkdir()
    files = baseline.tree(a.stage2, baseline.IFS_SHA)
    stage1 = (a.firmware / 'MMX2/mifs-stage1/50/default/mifs-stage1.img').read_bytes()
    if stage1[:8] != bytes.fromhex('41ff44ff4fff44ff'):
        p.error('invalid stage1 wrapper')
    decoder = zlib.decompressobj()
    image = decoder.decompress(stage1[0x800:], 64 * 1024 * 1024 + 1)
    if not decoder.eof or len(image) > 64 * 1024 * 1024:
        p.error('invalid stage1 stream')
    files.update(baseline.image_files(image))
    if sha(files['ifs/lsd.jxe']) != manifest['factory_jxe_sha256']:
        p.error('factory JXE mismatch')
    for name, data in files.items():
        if name.startswith('ifs/jre/') or name == 'ifs/lsd.jxe':
            dest = work / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
    for short in ('libc.so.3', 'libsocket.so.3', 'libm.so.2'):
        (work / short).write_bytes(next(d for n, d in files.items() if n.endswith('/' + short)))
    if sha((work / 'libc.so.3').read_bytes()) != '775139dc7381b8aa7001330dafe93b5cb8b0f779eb8e97d5ee32ca93bb85d2f1':
        p.error('factory libc mismatch')
    shutil.copy2(jar, work / 'observer.jar')
    with zipfile.ZipFile(jar) as src, zipfile.ZipFile(work / 'negative.jar', 'w') as dst:
        for name in src.namelist():
            data = bytearray(src.read(name))
            if struct.unpack_from('>H', data, 6)[0] != 46:
                p.error('observer must target class 46 throughout')
            if name.endswith('/HsmTarget.class'):
                data[6:8] = struct.pack('>H', 49)
            dst.writestr(name, data)
    subprocess.run([str(a.java_home / 'bin/javac'), '-source', '7', '-target', '7',
                    '-Xlint:-options', '-bootclasspath', str(a.stock_jar), '-cp', str(jar),
                    '-d', str(work / 'probe'), str(probe_source)], check=True)
    with zipfile.ZipFile(work / 'probe.jar', 'w') as z:
        for f in (work / 'probe').rglob('*.class'):
            data = bytearray(f.read_bytes())
            data[6:8] = struct.pack('>H', 46)
            z.writestr(str(f.relative_to(work / 'probe')), data)
    c = r'''#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
static void launch(char **args){int status;pid_t p=fork();if(!p){execv(args[0],args);_exit(127);}if(p<0)exit(1);waitpid(p,&status,0);printf("N0_CHILD_STATUS=%d\n",status);}
int main(void){
 char *args[]={"/ifs/jre/bin/j9","-jcl:foun11","-noverify","-Xmx64m","-Xbootclasspath/a:/ifs/lsd.jxe","-Xbootclasspath/p:/proc/boot/observer.jar","-cp","/proc/boot/probe.jar","com.cpmap.audio.LoadObserver",0};
 setenv("LD_LIBRARY_PATH","/ifs/jre/bin:/proc/boot",1);
 puts("@@N0-NOVERIFY@@");fflush(stdout);launch(args);
 puts("@@N0-VERIFY@@");fflush(stdout);args[2]="-verify";launch(args);
 puts("@@N0-NEGATIVE@@");fflush(stdout);args[5]="-Xbootclasspath/p:/proc/boot/negative.jar";launch(args);
 puts("@@N0-END@@");fflush(stdout);return 0;}
'''
    (work / 'probe.c').write_text(c.replace('com.cpmap.audio.LoadObserver', probe_class))
    root = a.toolchain.resolve() / 'sdp/target/qnx6'
    flags = ['--target=armv7-none-eabi', '-D__QNXNTO__', '-D__QNX__', '-D__ARM__',
             '-D__LITTLEENDIAN__', '--sysroot=' + str(root), '-isystem', str(root / 'usr/include'),
             '-march=armv7-a', '-mfloat-abi=softfp', '-mno-unaligned-access', '-fno-short-enums',
             '-fno-builtin', '-fno-stack-protector', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror']
    subprocess.run(['clang', *flags, '-c', str(work / 'probe.c'), '-o', str(work / 'probe.o')], check=True)
    for name in ('c4-smoke', 'startup-virt', 'libstartup.a', 'devc-serdebug', 'u-boot.bin', 'pipe'):
        shutil.copy2(a.setup / name, work / name)
    template = (a.setup / 'test.build').read_text().replace(
        'display_msg "@@C4-START@@"\n /proc/boot/c4-smoke\n display_msg "@@C4-END@@"',
        'display_msg "@@N0-START@@"\n /proc/boot/j9-probe\n display_msg "@@N0-FINISHED@@"')
    template = template.replace('rgi-observer\nsnapshot.bin\n',
        'j9-probe\nprobe.jar\nobserver.jar\nnegative.jar\nlibsocket.so.3\n')
    for f in sorted((work / 'ifs').rglob('*')):
        if f.is_file():
            template += '\n/' + str(f.relative_to(work)) + '=' + str(f.relative_to(work))
    (work / 'test.build').write_text(template + '\n')
    prepare = (a.setup / 'prepare.sh').read_text().replace('/w/smoke.o', '/w/probe.o').replace('-o /w/c4-smoke', '-o /w/j9-probe')
    (work / 'prepare.sh').write_text(prepare)
    docker = ['docker', '--context', a.docker_context, 'run', '--rm', '--pull=never',
              '--network=none', '-i', '-v', str(work) + ':/w', '-w', '/w']
    with (work / 'prepare.log').open('w') as log:
        subprocess.run(docker + ['cpmap-qnx65-sdp', 'sh', '/w/prepare.sh'], stdout=log, stderr=subprocess.STDOUT, check=True)
    logpath = work / 'qemu.log'
    with logpath.open('wb') as log:
        proc = subprocess.Popen(docker + ['cpmap-qemu-arm', 'timeout', '60', 'qemu-system-arm',
            '-M', 'virt', '-m', '1024', '-cpu', 'cortex-a15', '-bios', '/w/u-boot.bin',
            '-drive', 'file=fat:rw:/w/fat,format=raw,media=disk', '-nic', 'none',
            '-display', 'none', '-serial', 'stdio'], stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
        def expect(token, offset=0):
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and proc.poll() is None:
                at = logpath.read_bytes().find(token, offset)
                if at >= 0:
                    return at + len(token)
                time.sleep(.1)
            raise RuntimeError('QNX marker missing; inspect qemu.log')
        def send(value):
            proc.stdin.write(value)
            proc.stdin.flush()
        try:
            at = expect(b'Hit any key to stop autoboot:')
            send(b'\n')
            at = expect(b'=> ', at)
            for command in (b'virtio scan\n', b'fatload virtio 0:1 0x40200000 ifs.bin\n'):
                send(command)
                at = expect(b'=> ', at)
            send(b'go 0x40200000\n')
            expect(b'@@N0-FINISHED@@', at)
        finally:
            proc.stdin.close()
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    log = logpath.read_text(errors='replace')
    sections = dict(re.findall(r'@@N0-(NOVERIFY|VERIFY|NEGATIVE)@@(.*?)(?=@@N0-|\Z)', log, re.S))
    passed = all('N0_J9_PASS checks=12' in sections.get(n, '') and 'N0_CHILD_STATUS=0' in sections[n]
                 for n in ('NOVERIFY', 'VERIFY'))
    negative = sections.get('NEGATIVE', '')
    # This factory J9 can expose an unsupported prepended class as missing,
    # rather than surface UnsupportedClassVersionError. The negative JAR is
    # identical to the positive JAR except for HsmTarget's major 46 -> 49.
    rejected = ('UnsupportedClassVersionError' in negative or
                'ClassNotFoundException: de.vw.mib.asl.internal.carplay.target.HsmTarget' in negative)
    child = re.search(r'N0_CHILD_STATUS=(\d+)', negative)
    rejected = bool(rejected and child and int(child[1]) != 0 and 'N0_J9_PASS' not in negative)
    passed = passed and rejected
    result = {'passed': passed, 'jar_sha256': manifest['jar_sha256'],
              'factory_j9_verified': passed, 'checks_per_mode': 12,
              'class49_negative_rejected': rejected,
              'qemu_log_sha256': sha(logpath.read_bytes()),
              'test_sha256': sha(Path(__file__).read_bytes()),
              'probe_sha256': sha(probe_source.read_bytes()),
              'on_unit_validated': False}
    (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
