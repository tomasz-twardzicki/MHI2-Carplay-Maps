#!/usr/bin/env python3
"""Build C4 with clang + the pinned QNX 6.5 SDP's original ARM linker/CRT.

Only the dedicated output directory is mounted into the build container.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import zlib

from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
TOOLCHAIN_COMMIT = 'baa45224f18ae6b13c2e9c77c6663bb8181eb6a1'
FIRMWARE_LIBC_SHA = '775139dc7381b8aa7001330dafe93b5cb8b0f779eb8e97d5ee32ca93bb85d2f1'


def sha(data): return hashlib.sha256(data).hexdigest()


def firmware_file(firmware, filename):
    image = (firmware / 'MMX2/mifs-stage1/50/default/mifs-stage1.img').read_bytes()
    if image[:8] != bytes.fromhex('41ff44ff4fff44ff'):
        raise ValueError('unexpected MMX stage1 wrapper')
    decoder = zlib.decompressobj()
    data = decoder.decompress(image[0x800:], 64 * 1024 * 1024 + 1)
    if not decoder.eof or len(data) > 64 * 1024 * 1024:
        raise ValueError('invalid/oversized stage1 deflate stream')
    for match in re.finditer(b'imagefs', data):
        base = match.start()
        if base + 20 > len(data): continue
        size, end, start = struct.unpack_from('<III', data, base + 8)
        if base + size == len(data) and 64 < start < end < size: break
    else: raise ValueError('stage1 imagefs header missing')
    pos = base + start
    while pos < base + end:
        size = struct.unpack_from('<H', data, pos)[0]
        if not size: break
        if size < 24 or pos + size > base + end:
            raise ValueError('invalid imagefs entry')
        mode = struct.unpack_from('<I', data, pos + 8)[0]
        if mode & 0o170000 == 0o100000:
            offset, length = struct.unpack_from('<II', data, pos + 24)
            name = data[pos + 32:pos + size].split(b'\0')[0]
            if name == filename.encode():
                return data[base + offset:base + offset + length]
        pos += size
    raise ValueError('required factory file missing')


def firmware_libc(firmware):
    libc = firmware_file(firmware, 'proc/boot/libc.so.3')
    if sha(libc) != FIRMWARE_LIBC_SHA:
        raise ValueError('factory MU1427 libc fingerprint mismatch')
    return libc


def verify(binary, libc):
    exe = ELFFile(io.BytesIO(binary))
    if exe.elfclass != 32 or not exe.little_endian or exe['e_machine'] != 'EM_ARM' or exe['e_type'] != 'ET_EXEC':
        raise ValueError('reader must be an ARM32 little-endian executable')
    if exe['e_flags'] & 0x400: raise ValueError('hard-float binary is unsupported')
    interpreters = [p.get_interp_name() for p in exe.iter_segments() if p['p_type'] == 'PT_INTERP']
    if interpreters != ['/usr/lib/ldqnx.so.2']:
        raise ValueError('unexpected reader interpreter')
    dynamic = exe.get_section_by_name('.dynamic')
    if [t.needed for t in dynamic.iter_tags() if t.entry.d_tag == 'DT_NEEDED'] != ['libc.so.3']:
        raise ValueError('reader must depend only on stock libc.so.3')
    if any(t.entry.d_tag in ('DT_RPATH', 'DT_RUNPATH', 'DT_TEXTREL') for t in dynamic.iter_tags()):
        raise ValueError('unexpected reader runtime path/text relocation')
    imports = {s.name for s in exe.get_section_by_name('.dynsym').iter_symbols()
               if s.name and s['st_shndx'] == 'SHN_UNDEF' and s['st_info']['bind'] != 'STB_WEAK'}
    stock = ELFFile(io.BytesIO(libc))
    symbols = next(p for p in stock.iter_segments() if p['p_type'] == 'PT_DYNAMIC')
    exports = {s.name for s in symbols.iter_symbols() if s['st_shndx'] != 'SHN_UNDEF'}
    if imports - exports:
        raise ValueError('reader imports unavailable in factory libc: ' + ', '.join(sorted(imports - exports)))
    return sorted(imports)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('toolchain', type=Path)
    parser.add_argument('firmware', type=Path)
    parser.add_argument('--output', type=Path, default=HERE / 'build-observer-arm')
    parser.add_argument('--docker-context', default='colima-cpmap-rgi')
    parser.add_argument('--image', default='cpmap-qnx65-sdp')
    parser.add_argument('--clang', default='clang')
    parser.add_argument('--source', type=Path, default=HERE / 'observer/observer.c')
    parser.add_argument('--revision', default='C4')
    args = parser.parse_args()
    toolchain = args.toolchain.resolve()
    commit = subprocess.check_output(['git', '-C', str(toolchain), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != TOOLCHAIN_COMMIT: parser.error('unexpected toolchain commit')
    if subprocess.check_output(['git', '-C', str(toolchain), 'status', '--porcelain', '--', 'sdp', 'Dockerfile']):
        parser.error('toolchain SDP/Dockerfile must be unchanged')
    libc = firmware_libc(args.firmware)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sysroot = toolchain / 'sdp/target/qnx6'
    flags = ['--target=armv7-none-eabi', '-D__QNXNTO__', '-D__QNX__', '-D__ARM__', '-D__LITTLEENDIAN__',
             '--sysroot=' + str(sysroot), '-isystem', str(sysroot / 'usr/include'),
             '-march=armv7-a', '-mfloat-abi=softfp', '-mno-unaligned-access', '-fno-short-enums',
             '-fno-builtin', '-fno-stack-protector', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror']
    subprocess.run([args.clang, *flags, '-c', str(args.source.resolve()), '-o', str(out / 'observer.o')], check=True)
    root = '/opt/qnx650/target/qnx6/armle-v7/lib'
    docker = ['docker', '--context', args.docker_context]
    image_id = subprocess.check_output(docker + ['image', 'inspect', args.image, '--format', '{{.Id}}'], text=True).strip()
    subprocess.run(docker + ['run', '--rm', '--pull=never', '--network=none', '-v', str(out) + ':/work', image_id,
        'arm-unknown-nto-qnx6.5.0eabi-ld', '-m', 'armnto', '-Qy', '--dynamic-linker', '/usr/lib/ldqnx.so.2',
        '-L' + root, root + '/crt1.o', root + '/crti.o', root + '/crtbegin.o', '/work/observer.o', '-lc',
        root + '/crtend.o', root + '/crtn.o', '-o', '/work/rgi-observer'], check=True)
    binary = (out / 'rgi-observer').read_bytes()
    imports = verify(binary, libc)
    (out / 'rgi-observer').chmod(0o755)
    manifest = {'revision': args.revision, 'size': len(binary), 'sha256': sha(binary),
                'source_sha256': sha(args.source.read_bytes()),
                'toolchain_commit': commit, 'image_id': image_id,
                'firmware_libc_sha256': sha(libc), 'imports_verified': imports,
                'compiler': subprocess.check_output([args.clang, '--version'], text=True).splitlines()[0],
                'flags': flags}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'binary': str(out / 'rgi-observer'), 'size': len(binary), 'sha256': sha(binary),
                      'factory_libc_imports_verified': len(imports)}))


if __name__ == '__main__': main()
