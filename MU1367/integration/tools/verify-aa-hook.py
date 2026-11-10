#!/usr/bin/env python3
"""v1.5.0-e: check the pinned Android Auto gal hook against the factory gal of both MU1367 firmware variants.

Read-only. Extracts gal and libautoreceiver.so from the K4525 app images (HW 50 and 70), then checks that the
prebuilt libgal_hook.so carries a firmware profile whose build fingerprint (dlsym addresses of three exported gal
symbols) and hidden-constructor guard word match this gal. Without a match the hook leaves Android Auto stock.
Needs pyelftools. SPDX-License-Identifier: GPL-3.0-or-later
  verify-aa-hook.py FIRMWARE_DIR OUTPUT_JSON
"""
import hashlib, json, struct, sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'port'))
from firmware import QNX6
AA = HERE.parent / 'src/android-auto'
PIN = json.loads((AA / 'PROVENANCE.json').read_text())
SYMS = ('_ZN3gal14CGALController10s_instanceE', '_ZTVN3gal14CVideoSinkImplE', '_ZTVN3gal25CVideoSinkCallbackHandlerE')
sha = lambda b: hashlib.sha256(b).hexdigest()

def elf(data):
    import io
    return ELFFile(io.BytesIO(data))

def word_at(e, data, vaddr):
    for seg in e.iter_segments():
        if seg['p_type'] == 'PT_LOAD' and seg['p_vaddr'] <= vaddr < seg['p_vaddr'] + seg['p_filesz']:
            off = seg['p_offset'] + vaddr - seg['p_vaddr']
            return struct.unpack_from('<I', data, off)[0]
    raise ValueError('address not loaded: %#x' % vaddr)

def main():
    fw, out = Path(sys.argv[1]), Path(sys.argv[2])
    hook = (AA / 'prebuilt/libgal_hook.so').read_bytes(); flush = (AA / 'prebuilt/libdmdt_flush.so').read_bytes()
    assert sha(hook) == PIN['libgal_hook.so']['sha256'] and len(hook) == PIN['libgal_hook.so']['size'], 'hook pin'
    assert sha(flush) == PIN['libdmdt_flush.so']['sha256'] and len(flush) == PIN['libdmdt_flush.so']['size'], 'dmdt_flush pin'
    result = {'hook_sha256': sha(hook), 'variants': {}}
    he = elf(hook)
    needed = sorted(t.needed for t in he.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag == 'DT_NEEDED')
    tag = PIN['libgal_hook.so']['build_tag'].encode()
    assert tag + b'\0' in hook, 'build tag'
    assert b'/mnt/app/carplaymaps/aa/libdmdt_flush.so' in hook and b'/fs/sd' not in hook, 'hook paths'
    for v in ('50', '70'):
        app = QNX6(fw / f'MMX2/app/{v}/default/app.img')
        try:
            gal = app.get('eso/bin/apps/gal'); recv = app.get('eso/lib/libautoreceiver.so')
        finally:
            app.file.close()
        assert sha(gal) == PIN['factory_gal']['sha256'] and len(gal) == PIN['factory_gal']['size'], 'gal ' + v
        assert sha(recv) == PIN['factory_libautoreceiver']['sha256'], 'receiver ' + v
        ge = elf(gal); dyn = ge.get_section_by_name('.dynsym')
        addrs = [dyn.get_symbol_by_name(s)[0]['st_value'] for s in SYMS]
        p = PIN['profile']
        assert addrs == [int(x, 16) for x in p['fingerprint']], ('fingerprint', [hex(a) for a in addrs])
        first = word_at(ge, gal, int(p['ctor'], 16))
        assert first == int(p['ctor_first_word'], 16), ('ctor word', hex(first))
        record = struct.pack('<14I', *addrs, int(p['ctor'], 16), first, *[int(x, 16) for x in p['layout']])
        assert hook.count(record) == 1, 'profile record not in hook'
        result['variants'][v] = {'gal_sha256': sha(gal), 'receiver_sha256': sha(recv),
                                 'fingerprint': [hex(a) for a in addrs], 'ctor_first_word': hex(first), 'profile_in_hook': True}
    result.update(passed=True, profile=PIN['profile']['name'], hook_needed=needed, build_tag=tag.decode())
    out.write_text(json.dumps(result, indent=2) + '\n'); print(json.dumps(result))

if __name__ == '__main__':
    main()
