#!/usr/bin/env python3
"""Resolve the new supervisor's strong imports against fresh factory libc."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys

from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'MU1367/port'))
from firmware import image_files, stage1, stage2


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--firmware', type=Path, required=True)
    a = p.parse_args()
    factory = image_files(stage1(a.firmware / 'MMX2/mifs-stage1/50/default/mifs-stage1.img'))
    factory.update(image_files(stage2(a.firmware / 'MMX2/mifs-stage2/50/default/mifs-stage2.img')))
    candidates = {data for name, data in factory.items() if Path(name).name == 'libc.so.3'}
    assert len(candidates) == 1, 'Ambiguous/missing factory libc'
    libc = candidates.pop()
    binary = (a.build / 'sd-card/Custom/carplay_mu1367_wireless_native/payload/carplay-cluster-supervisor').read_bytes()
    supervisor = ELFFile(io.BytesIO(binary))
    needed = [tag.needed for tag in supervisor.get_section_by_name('.dynamic').iter_tags() if tag.entry.d_tag == 'DT_NEEDED']
    assert needed == ['libc.so.3'], needed
    imports = {s.name for s in supervisor.get_section_by_name('.dynsym').iter_symbols() if s.name and s['st_shndx'] == 'SHN_UNDEF' and s['st_info']['bind'] == 'STB_GLOBAL'}
    dynamic = next(s for s in ELFFile(io.BytesIO(libc)).iter_segments() if s['p_type'] == 'PT_DYNAMIC')
    exports = {s.name for s in dynamic.iter_symbols() if s['st_shndx'] != 'SHN_UNDEF' and s['st_info']['bind'] in ('STB_GLOBAL', 'STB_WEAK')}
    missing = sorted(imports - exports)
    result = dict(passed=not missing, supervisor_sha256=hashlib.sha256(binary).hexdigest(), factory_libc_sha256=hashlib.sha256(libc).hexdigest(), strong_imports=sorted(imports), missing=missing)
    (a.build / 'native-check.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    assert result['passed'], missing


if __name__ == '__main__':
    main()
