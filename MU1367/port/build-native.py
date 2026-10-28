#!/usr/bin/env python3
"""Build native helpers using pinned QNX SDP, checking MU1367 libc exports.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
from pathlib import Path
import subprocess
from firmware import image_files, stage1, sha
from build_support import load

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('toolchain', 'firmware', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    base = load('native_base', REPO / 'MU1427/route-guidance/build-observer.py')
    commit = subprocess.check_output(['git', '-C', str(a.toolchain), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != base.TOOLCHAIN_COMMIT or subprocess.check_output(['git', '-C', str(a.toolchain), 'status', '--porcelain', '--', 'sdp', 'Dockerfile']):
        p.error('pinned unmodified QNX toolchain required')
    libc = image_files(stage1(a.firmware / 'MMX2/mifs-stage1/50/default/mifs-stage1.img'))['proc/boot/libc.so.3']
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = a.toolchain.resolve() / 'sdp/target/qnx6'
    flags = ['--target=armv7-none-eabi', '-D__QNXNTO__', '-D__QNX__', '-D__ARM__', '-D__LITTLEENDIAN__',
             '--sysroot=' + str(root), '-isystem', str(root / 'usr/include'), '-march=armv7-a', '-mfloat-abi=softfp',
             '-mno-unaligned-access', '-fno-short-enums', '-fno-builtin', '-fno-stack-protector',
             '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror']
    sources = {'rgi-observer': REPO / 'MU1427/route-guidance/release/reader.c',
               'artwork-capture': REPO / 'MU1427/now-playing/n3/capture.c', 'verify': HERE / 'verify.c'}
    result = {}
    docker = ['docker', '--context', 'colima-cpmap-rgi']
    image = subprocess.check_output(docker + ['image', 'inspect', 'cpmap-qnx65-sdp', '--format', '{{.Id}}'], text=True).strip()
    for name, src in sources.items():
        subprocess.run(['clang', *flags, '-c', str(src), '-o', str(out / (name + '.o'))], check=True)
        lib = '/opt/qnx650/target/qnx6/armle-v7/lib'
        subprocess.run(docker + ['run', '--rm', '--pull=never', '--network=none', '-v', str(out) + ':/work', image,
            'arm-unknown-nto-qnx6.5.0eabi-ld', '-m', 'armnto', '-Qy', '--dynamic-linker', '/usr/lib/ldqnx.so.2',
            '-L' + lib, lib + '/crt1.o', lib + '/crti.o', lib + '/crtbegin.o', '/work/' + name + '.o', '-lc',
            lib + '/crtend.o', lib + '/crtn.o', '-o', '/work/' + name], check=True)
        binary = (out / name).read_bytes()
        imports = base.verify(binary, libc)
        (out / name).chmod(0o755)
        result[name] = {'sha256': sha(binary), 'size': len(binary), 'imports_verified': imports,
                        'source_sha256': sha(src.read_bytes())}
    manifest = {'firmware': 'MU1367', 'libc_sha256': sha(libc), 'toolchain_commit': commit,
                'image_id': image, 'binaries': result, 'on_unit_validated': False}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
