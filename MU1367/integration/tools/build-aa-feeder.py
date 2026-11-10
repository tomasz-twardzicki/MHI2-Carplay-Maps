#!/usr/bin/env python3
"""v1.5.0-e: build aa-most-feeder for MU1367 (QNX 6.5 armv7) with the pinned SDK image, twice, and check that every
import resolves in the factory libc.so.3 / libsocket.so.3 extracted from the firmware. Needs pyelftools.
SPDX-License-Identifier: GPL-3.0-or-later
  build-aa-feeder.py --firmware K4525_DIR --output OUT
"""
import argparse, hashlib, io, json, subprocess, sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'MU1367/port'))
from firmware import image_files, stage1
IMAGE_ID = 'sha256:93b565ff63ba51c470c1a1e70a6d16607d36df502dfb20ae63a69911f8529bea'
sha = lambda b: hashlib.sha256(b).hexdigest()
LIBS = {'proc/boot/libc.so.3': '485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc',
        'lib/libsocket.so.3': '36a062617f078d20d8cf53fb879667bd41d49b5d6b8ffb69375f4ca44eeff2d4'}

def exports(data):
    e = ELFFile(io.BytesIO(data)); d = next(p for p in e.iter_segments() if p['p_type'] == 'PT_DYNAMIC')
    return {s.name for s in d.iter_symbols() if s['st_shndx'] != 'SHN_UNDEF'}

def check(binary, libs):
    exe = ELFFile(io.BytesIO(binary))
    assert exe.elfclass == 32 and exe.little_endian and exe['e_machine'] == 'EM_ARM' and exe['e_type'] == 'ET_EXEC'
    assert not exe['e_flags'] & 0x400, 'hard-float'
    assert [p.get_interp_name() for p in exe.iter_segments() if p['p_type'] == 'PT_INTERP'] == ['/usr/lib/ldqnx.so.2']
    dyn = exe.get_section_by_name('.dynamic')
    needed = [t.needed for t in dyn.iter_tags() if t.entry.d_tag == 'DT_NEEDED']
    assert set(needed) <= {'libsocket.so.3', 'libc.so.3'}, needed
    assert not any(t.entry.d_tag in ('DT_RPATH', 'DT_RUNPATH', 'DT_TEXTREL') for t in dyn.iter_tags())
    imports = {s.name for s in exe.get_section_by_name('.dynsym').iter_symbols()
               if s.name and s['st_shndx'] == 'SHN_UNDEF' and s['st_info']['bind'] != 'STB_WEAK'}
    have = set().union(*(exports(b) for b in libs.values()))
    assert not imports - have, 'imports missing in factory libraries: %s' % sorted(imports - have)
    return needed, sorted(imports)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--firmware', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    files = image_files(stage1(a.firmware / 'MMX2/mifs-stage1/50/default/mifs-stage1.img'))
    libs = {}
    for name, h in LIBS.items():
        assert sha(files[name]) == h, name
        libs[name] = files[name]
    docker = ['docker', '--context', 'colima-cpmap-rgi']
    image = subprocess.check_output(docker + ['image', 'inspect', 'cpmap-qnx65-sdp', '--format', '{{.Id}}'], text=True).strip()
    assert image == IMAGE_ID, 'Pinned QNX image required (DEVELOPMENT.md: cpmap-qnx65-sdp 93b565ff63ba)'
    subprocess.run(docker + ['run', '--rm', '--pull=never', '--network=none', '-v', str(out) + ':/w', image, 'sh', '-c',
                             'cp -R /opt/qnx650/target/qnx6/usr/include /w/sdk-include'], check=True)
    src = HERE / 'src/android-auto/feeder/aa_most_feeder.c'
    conv = HERE / 'src/android-auto/feeder/aeabi_conv.c'
    flags = ['--target=armv7-none-eabi', '-D__QNXNTO__', '-D__QNX__', '-D__ARM__', '-D__LITTLEENDIAN__', '--sysroot=' + str(out),
             '-isystem', str(out / 'sdk-include'), '-I', str(HERE / 'src/runtime/vc-runtime/runtime'), '-march=armv7-a',
             '-mfloat-abi=softfp', '-mfpu=vfpv3-d16', '-mno-unaligned-access', '-fno-short-enums', '-fno-builtin', '-fno-stack-protector',
             '-std=gnu99', '-O2', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-ffile-prefix-map=' + str(HERE) + '=.']
    lib = '/opt/qnx650/target/qnx6/armle-v7/lib'
    built = []
    for n in (1, 2):
        subprocess.run(['clang', *flags, '-c', str(src), '-o', str(out / ('feeder%d.o' % n))], check=True)
        subprocess.run(['clang', *flags, '-c', str(conv), '-o', str(out / ('conv%d.o' % n))], check=True)
        subprocess.run(docker + ['run', '--rm', '--pull=never', '--network=none', '-v', str(out) + ':/w', image, 'sh', '-c',
                       'arm-unknown-nto-qnx6.5.0eabi-ld -m armnto -Qy --dynamic-linker /usr/lib/ldqnx.so.2 -L%s %s/crt1.o '
                       '%s/crti.o %s/crtbegin.o /w/feeder%d.o /w/conv%d.o -lsocket -lc %s/crtend.o %s/crtn.o -o /w/aa-most-feeder.%d && '
                       'arm-unknown-nto-qnx6.5.0eabi-strip /w/aa-most-feeder.%d' % (lib, lib, lib, lib, n, n, lib, lib, n, n)], check=True)
        built.append((out / ('aa-most-feeder.%d' % n)).read_bytes())
    assert built[0] == built[1], 'two builds differ'
    (out / 'aa-most-feeder').write_bytes(built[0]); (out / 'aa-most-feeder').chmod(0o755)
    needed, imports = check(built[0], libs)
    # v1.5.0-e: the Android Auto build of the MU1367 bridge (no keyframe wait, ALTSCREEN_AA_SINGLE_IDR).
    # v1.5.1-e: the CarPlay build of the same source (boot-time MOST reclaim), installed by the main layer.
    bsrc = HERE / 'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c'
    def build_bridge(name, extra):
        built = []
        for n in (1, 2):
            subprocess.run(['clang', *flags, *extra, '-c', str(bsrc), '-o', str(out / ('%s%d.o' % (name, n)))], check=True)
            subprocess.run(['clang', *flags, '-c', str(conv), '-o', str(out / ('%s-conv%d.o' % (name, n)))], check=True)
            subprocess.run(docker + ['run', '--rm', '--pull=never', '--network=none', '-v', str(out) + ':/w', image, 'sh', '-c',
                           'arm-unknown-nto-qnx6.5.0eabi-ld -m armnto -Qy --dynamic-linker /usr/lib/ldqnx.so.2 -L%s %s/crt1.o '
                           '%s/crti.o %s/crtbegin.o /w/%s%d.o /w/%s-conv%d.o -lsocket -lc %s/crtend.o %s/crtn.o -o /w/%s.%d && '
                           'arm-unknown-nto-qnx6.5.0eabi-strip /w/%s.%d' % (lib, lib, lib, lib, name, n, name, n, lib, lib, name, n, name, n)], check=True)
            built.append((out / ('%s.%d' % (name, n))).read_bytes())
        assert built[0] == built[1], 'two %s builds differ' % name
        (out / name).write_bytes(built[0]); (out / name).chmod(0o755)
        return built[0]
    bridge = build_bridge('altscreen-most-bridge-aa', ['-DALTSCREEN_AA_SINGLE_IDR'])
    bneeded, bimports = check(bridge, libs)
    cp_bridge = build_bridge('altscreen-most-bridge', [])
    cneeded, cimports = check(cp_bridge, libs)
    r = {'passed': True, 'sha256': sha(built[0]), 'size': len(built[0]), 'source_sha256': sha(src.read_bytes()), 'aeabi_conv_sha256': sha(conv.read_bytes()),
         'bridge_sha256': sha(bridge), 'bridge_size': len(bridge), 'bridge_source_sha256': sha(bsrc.read_bytes()), 'bridge_needed': bneeded,
         'bridge_imports': bimports, 'bridge_flags': ['-DALTSCREEN_AA_SINGLE_IDR'],
         'carplay_bridge_sha256': sha(cp_bridge), 'carplay_bridge_size': len(cp_bridge), 'carplay_bridge_needed': cneeded,
         'carplay_bridge_imports': cimports, 'carplay_bridge_flags': [],
         'needed': needed, 'imports': imports, 'factory_libraries': LIBS, 'image_id': image, 'reproducible': True,
         'on_unit_validated': False}
    (out / 'manifest.json').write_text(json.dumps(r, indent=2) + '\n'); print(json.dumps({k: r[k] for k in ('sha256', 'size', 'needed')}))

if __name__ == '__main__':
    main()
