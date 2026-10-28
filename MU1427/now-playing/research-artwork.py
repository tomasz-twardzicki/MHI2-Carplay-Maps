#!/usr/bin/env python3
"""Fingerprint MU1427's stock artwork path and check the pinned LuKa reference.

Host research only: no firmware patch or installable payload is produced.
Requires pyelftools, capstone, Git and a C compiler with ASan/UBSan.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
from elftools.elf.elffile import ELFFile

STOCK_SHA = '0ac13f43d3fb259eee328c272fa1211bb558b6e2cd97c6e38ef38e4e71469d51'
REFERENCE_COMMIT = '71b4ab1c9461d5383a7aa6d56d4dda34f567ade7'
FUNCTIONS = (
    'nowplay_start', 'nowplay_update_recv', 'nowplay_getartwork',
    'file_xfer_init', 'file_xfer_setup', 'file_xfer_data',
    'file_xfer_destroy', 'file_xfer_read', 'link_handle_iap2pkt', 'iap2_msg',
)
DOCUMENTS = (
    'docs/altscreen-and-video/COVER_ART_PIPELINE.md',
    'docs/audio/BUFFERED_AUDIO_PATH.md',
    'docs/audio/STEREO_TO_5_1_UPMIX.md',
    'docs/audio/INTERNAL_AMP_PATH.md',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(args, **kwargs):
    try:
        return subprocess.check_output(args, stderr=subprocess.STDOUT,
                                       timeout=60, **kwargs)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(error.output.decode(errors='replace')) from error


def native_contract(path):
    data = path.read_bytes()
    if len(data) != 739925 or sha(data) != STOCK_SHA:
        raise ValueError('exact unpatched MU1427 iAP2 driver required')
    elf = ELFFile(io.BytesIO(data))
    if elf.elfclass != 32 or not elf.little_endian or elf['e_machine'] != 'EM_ARM':
        raise ValueError('ARM32 little-endian ELF required')

    def read(va, length):
        for segment in elf.iter_segments():
            if (segment['p_type'] == 'PT_LOAD'
                    and segment['p_vaddr'] <= va
                    and va + length <= segment['p_vaddr'] + segment['p_filesz']):
                offset = segment['p_offset'] + va - segment['p_vaddr']
                return data[offset:offset + length]
        raise ValueError('unmapped native address')

    symbols = {s.name: s for s in elf.get_section_by_name('.symtab').iter_symbols()
               if s.name and s['st_value']}
    decoder = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    functions = {}
    destinations = {symbols[name]['st_value']: name for name in FUNCTIONS}
    calls = []
    for name in FUNCTIONS:
        sym = symbols[name]
        code = read(sym['st_value'], sym['st_size'])
        functions[name] = {'va': hex(sym['st_value']), 'bytes': len(code),
                           'sha256': sha(code)}
        for insn in decoder.disasm(code, sym['st_value']):
            if insn.mnemonic == 'bl' and insn.op_str.startswith('#'):
                destination = destinations.get(int(insn.op_str[1:], 16))
                if destination:
                    calls.append({'caller': name, 'va': hex(insn.address),
                                  'callee': destination})

    sym = symbols['sparams_nowplay_start_mdtypes']
    fields = []
    for offset in range(0, sym['st_size'], 12):
        pointer, flags, value = struct.unpack('<III', read(sym['st_value'] + offset, 12))
        if pointer:
            name = read(pointer, 96).split(b'\0', 1)[0].decode('ascii')
            fields.append({'id': offset // 12, 'name': name,
                           'flags': hex(flags), 'default_value': value})
    # Record the exact operands behind the proposed complete-buffer seam and
    # the consuming reader. These are fingerprints, not a patch recipe.
    anchors = {
        'artwork_file_id_to_init': (0x1c878, 28),
        'data_complete_state_before_notifications': (0x877c, 28),
        'reader_advances_shared_cursor': (0x1bacc, 16),
    }
    return {'sha256': sha(data), 'bytes': len(data), 'functions': functions,
            'direct_calls_between_selected_functions': calls,
            'nowplaying_metadata_table': fields,
            'instruction_anchors': {
                name: {'va': hex(va), 'bytes': length,
                       'sha256': sha(read(va, length))}
                for name, (va, length) in anchors.items()},
            'scope': 'static ELF inspection; no live delivery or buffer lifetime proof'}


def reference_checks(reference, cc, sysroot):
    def git(*args):
        return run(['git', '-C', str(reference), *args])

    if git('rev-parse', REFERENCE_COMMIT + '^{commit}').decode().strip() != REFERENCE_COMMIT:
        raise ValueError('pinned reference commit missing')
    names = git('ls-tree', '-r', '--name-only', REFERENCE_COMMIT, '--',
                'hook/coverart', 'hook/framework',
                'tests/coverart_stream_test.c', 'tests/coverart_safety_test.c',
                'tests/coverart_pipeline_test.c',
                'tests/fixtures/coverart/exif-thumbnail.jpg').decode().splitlines()
    # Compile pristine blobs, independently of the clone's checkout or edits.
    selected = [n for n in names if n.endswith('.h') or n in (
        'hook/coverart/coverart_stream.c', 'hook/coverart/jpeg_safety.c',
        'hook/coverart/coverart_hook.c', 'hook/framework/iap2_protocol.c',
        'tests/coverart_stream_test.c', 'tests/coverart_safety_test.c',
        'tests/coverart_pipeline_test.c', 'tests/fixtures/coverart/exif-thumbnail.jpg')]
    hashes, tests = {}, []
    with tempfile.TemporaryDirectory(prefix='mu1427-artwork-reference-') as work:
        root = Path(work)
        for name in selected:
            data = git('show', REFERENCE_COMMIT + ':' + name)
            hashes[name] = sha(data)
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        common = [cc, '-std=gnu99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                  '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-Ihook']
        if sysroot:
            common += ['-isysroot', str(sysroot)]
        suites = {
            'coverart_stream': ['tests/coverart_stream_test.c',
                               'hook/coverart/coverart_stream.c',
                               'hook/framework/iap2_protocol.c'],
            'coverart_safety': ['tests/coverart_safety_test.c',
                               'hook/coverart/jpeg_safety.c'],
            'coverart_pipeline': [
                '-Wno-unused-parameter', '-Wno-unused-variable',
                '-Wno-unused-but-set-variable',
                '-DCOVERART_DIR="' + str(root / 'artwork') + '"',
                'tests/coverart_pipeline_test.c', 'hook/coverart/jpeg_safety.c',
                'hook/coverart/coverart_stream.c', 'hook/framework/iap2_protocol.c',
                '-lpthread', '-lz', '-lm'],
        }
        for name, sources in suites.items():
            binary = root / name
            run(common + sources + ['-o', str(binary)], cwd=root)
            output = run([str(binary)], cwd=root).decode()
            tests.append({'suite': name, 'passed': True, 'stdout': output.strip()})
            print(name + ': PASS (ASan/UBSan)', flush=True)
    for name in DOCUMENTS:
        hashes[name] = sha(git('show', REFERENCE_COMMIT + ':' + name))
    return {'repository': 'https://github.com/luka-dev/mib2q-carplay-rgi',
            'commit': REFERENCE_COMMIT, 'files_sha256': hashes,
            'compiler': run([cc, '--version']).decode().splitlines()[0],
            'sysroot': str(sysroot) if sysroot else None,
            'sanitizers': ['address', 'undefined'], 'tests': tests,
            'scope': 'upstream synthetic host fixtures; not MU1427/QNX or AID acceptance'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--cc', default='clang')
    parser.add_argument('--sysroot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'schema': 1, 'phase': 'artwork_feasibility',
              'hardware_validated': False, 'deployable_payload': False,
              'probe_sha256': sha(Path(__file__).read_bytes()),
              'native': native_contract(args.driver),
              'reference': reference_checks(args.reference, args.cc, args.sysroot)}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'output': str(args.output),
                      'reference_suites_passed': len(result['reference']['tests']),
                      'native_functions': len(result['native']['functions']),
                      'hardware_validated': False}))


if __name__ == '__main__':
    main()
