#!/usr/bin/env python3
"""Load the exact release JAR using factory ARM J9 under QNX/QEMU.
Requires the already-extracted exact MMX IFS files and pinned QNX toolchain.
No firmware/JAR bytes are committed or sent over the network.
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
IFS_SHA = 'b0d0af28862512941603f2682d6901a76ba643b8eb878851a10caec964272950'


def sha(b): return hashlib.sha256(b).hexdigest()


def tree(path, digest):
    b = path.read_bytes()
    if sha(b) != digest: raise ValueError('exact MU1427 MMX IFS required')
    return image_files(b)


def image_files(b):
    for match in re.finditer(b'imagefs', b):
        base = match.start()
        if base+20>len(b): continue
        size, end, pos = struct.unpack_from('<III', b, base + 8)
        if base+size==len(b) and 64<pos<end<size: break
    else: raise ValueError('valid imagefs header missing')
    result = {}
    while pos < end:
        n = struct.unpack_from('<H', b, base + pos)[0]
        if not n: break
        if n < 24 or pos + n > end: raise ValueError('invalid IFS directory')
        mode = struct.unpack_from('<I', b, base + pos + 8)[0]
        if mode & 0o170000 == 0o100000:
            off, length = struct.unpack_from('<II', b, base + pos + 24)
            name = b[base + pos + 32:base + pos + n].split(b'\0')[0].decode('utf-8')
            if off + length > size: raise ValueError('invalid IFS file bounds')
            result[name] = b[base + off:base + off + length]
        pos += n
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('hmi_build', type=Path)
    p.add_argument('--stage2', type=Path, required=True)
    p.add_argument('--firmware', type=Path, required=True)
    p.add_argument('--java-home', type=Path, required=True)
    p.add_argument('--stock-jar', type=Path, required=True)
    p.add_argument('--toolchain', type=Path, required=True)
    p.add_argument('--failed-jar', type=Path, required=True)
    p.add_argument('--output', type=Path, default=HERE / 'build-D1-r2-qnx')
    p.add_argument('--docker-context', default='colima-cpmap-rgi')
    p.add_argument('--reader-build', type=Path)
    a = p.parse_args(); work = a.output.resolve(); work.mkdir(parents=True, exist_ok=False)
    files = tree(a.stage2, IFS_SHA)
    stage1 = (a.firmware / 'MMX2/mifs-stage1/50/default/mifs-stage1.img').read_bytes()
    if stage1[:8] != bytes.fromhex('41ff44ff4fff44ff'): p.error('invalid factory stage1 wrapper')
    decoder = zlib.decompressobj(); image = decoder.decompress(stage1[0x800:], 64*1024*1024+1)
    if not decoder.eof or len(image)>64*1024*1024: p.error('invalid factory stage1 deflate stream')
    files.update(image_files(image))
    manifest = json.loads((a.hmi_build / 'manifest.json').read_text())
    fixed = (a.hmi_build / 'CarPlayRouteGuidanceD1.jar').read_bytes()
    if sha(fixed) != manifest['jar_sha256']: p.error('HMI manifest mismatch')
    failed = a.failed_jar.read_bytes()
    if sha(failed) != 'b8f0d3599f43419c8cbf3cf748cba4ce16ac4038263d082802359e8fdf47b774': p.error('exact failed D1 negative control required')
    with zipfile.ZipFile(a.hmi_build / 'CarPlayRouteGuidanceD1.jar') as z:
        if any(struct.unpack_from('>H', z.read(n), 6)[0] != 46 for n in z.namelist() if n.endswith('.class')):
            p.error('every installed class must target 46')
    for name, data in files.items():
        if name.startswith('ifs/jre/') or name == 'ifs/lsd.jxe':
            dest = work / name; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
    for short in ('libc.so.3', 'libsocket.so.3', 'libm.so.2'):
        matches = [data for name, data in files.items() if name.endswith('/' + short)]
        if not matches: p.error('required factory native library missing')
        (work / short).write_bytes(matches[0])
    if sha((work / 'libc.so.3').read_bytes()) != '775139dc7381b8aa7001330dafe93b5cb8b0f779eb8e97d5ee32ca93bb85d2f1':
        p.error('factory MMX libc mismatch')
    (work / 'fixed.jar').write_bytes(fixed); (work / 'failed.jar').write_bytes(failed)
    java = a.java_home / 'bin/javac'
    subprocess.run([str(java), '-source', '7', '-target', '7', '-Xlint:-options', '-bootclasspath', str(a.stock_jar), '-d', str(work), str(HERE / 'bridge/LoadProbe.java')], check=True)
    probe = bytearray((work / 'LoadProbe.class').read_bytes()); probe[6:8] = struct.pack('>H', 46)
    with zipfile.ZipFile(work / 'probe.jar', 'w') as z: z.writestr('LoadProbe.class', probe)
    c = '''#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <unistd.h>
#include <sys/wait.h>
#include <stdlib.h>
static void launch(char **a){int s;pid_t p=fork();if(!p){execv(a[0],a);perror("j9 exec");_exit(127);}if(p<0)exit(1);waitpid(p,&s,0);printf("J9_CHILD_STATUS=%d\\n",s);}
int main(void){
 char *stock[]={"/ifs/jre/bin/j9","-jcl:foun11","-noverify","-Xmx64m","-Xbootclasspath/a:/ifs/lsd.jxe","-cp","/proc/boot/probe.jar","LoadProbe","stock",0};
 char *patch[]={"/ifs/jre/bin/j9","-jcl:foun11","-noverify","-Xmx64m","-Xbootclasspath/a:/ifs/lsd.jxe","-Xbootclasspath/p:/proc/boot/failed.jar","-cp","/proc/boot/probe.jar","LoadProbe","patch",0};
 setenv("LD_LIBRARY_PATH","/ifs/jre/bin:/proc/boot",1);
 puts("@@J9-STOCK@@");fflush(stdout);launch(stock);
 puts("@@J9-FAILED-D1@@");fflush(stdout);launch(patch);
 puts("@@J9-FIXED@@");fflush(stdout);patch[5]="-Xbootclasspath/p:/proc/boot/fixed.jar";launch(patch);
 puts("@@J9-VERIFIED@@");fflush(stdout);patch[2]="-verify";launch(patch);
 puts("@@J9-END@@");return 0;}
'''
    reader_digest = None
    if a.reader_build:
        binary=(a.reader_build/'rgi-observer').read_bytes()
        reader_manifest=json.loads((a.reader_build/'manifest.json').read_text())
        reader_digest=sha(binary)
        if reader_digest!=reader_manifest['sha256']: p.error('reader fingerprint mismatch')
        (work/'rgi-observer').write_bytes(binary)
        spec=importlib.util.spec_from_file_location('fixture',HERE/'test-rgi-publication.py')
        fixture=importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
        events=[(1,0x5201,fixture.route()),(2,0x5202,fixture.maneuver())]
        (work/'snapshot.bin').write_bytes(fixture.snapshot(events))
        events.append((3,0x5201,fixture.route()+fixture.tlv(7,(1000).to_bytes(4,'big'))+fixture.tlv(6,(120).to_bytes(8,'big'))))
        (work/'next.bin').write_bytes(fixture.snapshot(events))
        helper = r'''static int copy(const char *src,const char *dst){char b[4096];size_t n;int failed=0;FILE *a=fopen(src,"rb"),*o;if(!a)return 1;o=fopen(dst,"wb");if(!o){fclose(a);return 1;}while((n=fread(b,1,sizeof(b),a)))if(fwrite(b,1,n,o)!=n){failed=1;break;}if(ferror(a))failed=1;fclose(a);if(fclose(o))failed=1;return failed;}
'''
        c=c.replace('int main(void){',helper+'int main(void){')
        extra = r''' char *reader[]={"/proc/boot/rgi-observer","start-live","/ramdisk/live-source","/ramdisk/rgi-live",0};
 char *stop[]={"/proc/boot/rgi-observer","stop","/ramdisk/rgi-live",0};
 pid_t updater;int status;
 puts("@@J9-MAILBOX@@");fflush(stdout);
 if(copy("/proc/boot/snapshot.bin","/ramdisk/live-source"))return 1;
 launch(reader);
 updater=fork();if(updater<0)return 1;
 if(!updater){sleep(3);if(copy("/proc/boot/next.bin","/ramdisk/live-source.new") || rename("/ramdisk/live-source.new","/ramdisk/live-source"))_exit(1);_exit(0);}
 patch[9]="mailbox";launch(patch);waitpid(updater,&status,0);launch(stop);
'''
        c=c.replace(' puts("@@J9-END@@");return 0;}',extra+' puts("@@J9-END@@");return 0;}')
    (work / 'probe.c').write_text(c)
    root = a.toolchain.resolve() / 'sdp/target/qnx6'
    flags = ['--target=armv7-none-eabi', '-D__QNXNTO__', '-D__QNX__', '-D__ARM__', '-D__LITTLEENDIAN__', '--sysroot=' + str(root),
             '-isystem', str(root / 'usr/include'), '-march=armv7-a', '-mfloat-abi=softfp', '-mno-unaligned-access', '-fno-short-enums',
             '-fno-builtin', '-fno-stack-protector', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror']
    subprocess.run(['clang', *flags, '-c', str(work / 'probe.c'), '-o', str(work / 'probe.o')], check=True)
    # Reuse the already-tested C4 QNX RAM-disk setup; this binary runs only
    # its setup subcommands, never its recorder test.
    setup = HERE / 'build-C4-qnx-check'
    for name in ('c4-smoke', 'startup-virt', 'libstartup.a', 'devc-serdebug', 'u-boot.bin', 'pipe'):
        shutil.copy2(setup / name, work / name)
    text = (setup / 'test.build').read_text().replace('display_msg "@@C4-START@@"\n /proc/boot/c4-smoke\n display_msg "@@C4-END@@"',
                'display_msg "@@J9-START@@"\n /proc/boot/j9-probe\n display_msg "@@J9-END@@"')
    text = text.replace('rgi-observer\nsnapshot.bin\n', 'j9-probe\nprobe.jar\nfailed.jar\nfixed.jar\nlibsocket.so.3\n')
    if a.reader_build: text += '\nrgi-observer\nsnapshot.bin\nnext.bin\n'
    for file in sorted((work / 'ifs').rglob('*')):
        if file.is_file(): text += '\n/' + str(file.relative_to(work)) + '=' + str(file.relative_to(work))
    (work / 'test.build').write_text(text + '\n')
    prepare = (setup / 'prepare.sh').read_text().replace('/w/smoke.o', '/w/probe.o').replace('-o /w/c4-smoke', '-o /w/j9-probe')
    (work / 'prepare.sh').write_text(prepare)
    docker = ['docker', '--context', a.docker_context, 'run', '--rm', '--pull=never', '--network=none', '-i', '-v', str(work) + ':/w', '-w', '/w']
    with (work / 'prepare.log').open('w') as log:
        subprocess.run(docker + ['cpmap-qnx65-sdp', 'sh', '/w/prepare.sh'], stdout=log, stderr=subprocess.STDOUT, check=True)
    logpath = work / 'qemu.log'
    with logpath.open('wb') as log:
        proc = subprocess.Popen(docker + ['cpmap-qemu-arm', 'timeout', '60', 'qemu-system-arm', '-M', 'virt', '-m', '1024', '-cpu', 'cortex-a15', '-bios', '/w/u-boot.bin',
            '-drive', 'file=fat:rw:/w/fat,format=raw,media=disk', '-nic', 'none', '-display', 'none', '-serial', 'stdio'], stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
        def expect(token, offset=0, seconds=20):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline and proc.poll() is None:
                data = logpath.read_bytes(); at = data.find(token, offset)
                if at >= 0: return at + len(token)
                time.sleep(.1)
            raise RuntimeError('QNX/J9 test did not reach its marker; inspect dedicated qemu.log')
        def send(command): proc.stdin.write(command); proc.stdin.flush()
        try:
            at = expect(b'Hit any key to stop autoboot:'); send(b'\n'); at = expect(b'=> ', at)
            for command in (b'virtio scan\n', b'fatload virtio 0:1 0x40200000 ifs.bin\n'):
                send(command); at = expect(b'=> ', at)
            send(b'go 0x40200000\n'); expect(b'@@J9-END@@', at, 30)
        finally:
            proc.stdin.close(); proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
    log = logpath.read_text(errors='replace')
    sections = {}
    for name, text in re.findall(r'@@J9-(STOCK|FAILED-D1|FIXED|VERIFIED)@@(.*?)(?=@@J9-|\Z)', log, re.S):
        m = re.search(r'RGI_J9_PROBE passed=(\d+) failed=(\d+)', text)
        if m: sections[name] = dict(passed=int(m[1]), failed=int(m[2]))
    passed = (sections.get('STOCK') == dict(passed=6, failed=0) and sections.get('FAILED-D1', {}).get('failed', 0) >= 4
              and sections.get('FIXED') == dict(passed=13, failed=0) and sections.get('VERIFIED') == dict(passed=13, failed=0))
    mailbox_passed = not a.reader_build or 'RGI_MAILBOX_PASS' in log
    passed = passed and mailbox_passed
    result = {'mailbox_qnx_passed': mailbox_passed if a.reader_build else None, 'reader_sha256': reader_digest, 'passed': passed, 'jar_sha256': sha(fixed), 'negative_control_sha256': sha(failed), 'all_class_major': 46,
              'qnx_actual_firmware_j9': True, 'sections': sections, 'qemu_log_sha256': sha(logpath.read_bytes()),
              'ifs_sha256': IFS_SHA, 'test_sha256': sha(Path(__file__).read_bytes()), 'probe_sha256': sha((HERE / 'bridge/LoadProbe.java').read_bytes())}
    (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n'); print(json.dumps(result)); return int(not passed)


if __name__ == '__main__': raise SystemExit(main())
