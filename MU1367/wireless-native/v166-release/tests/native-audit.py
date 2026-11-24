#!/usr/bin/env python3
"""Resolve every owned component's imports using fresh target firmware libs."""
import argparse,hashlib,io,json,sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/'port'))
from firmware import image_files,stage1,stage2
p=argparse.ArgumentParser()
for n in ('firmware','components','output'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument("--variant",choices=("50","70"),default="50")
a=p.parse_args()
files=image_files(stage1(a.firmware/('MMX2/mifs-stage1/'+a.variant+'/default/mifs-stage1.img')))
files.update(image_files(stage2(a.firmware/('MMX2/mifs-stage2/'+a.variant+'/default/mifs-stage2.img'))))
exports={};hashes={}
for name in ('libc.so.3','libsocket.so.3','libz.so.2'):
 candidates={data for path,data in files.items() if Path(path).name==name};assert len(candidates)==1
 data=candidates.pop();e=ELFFile(io.BytesIO(data));dynamic=next(s for s in e.iter_segments() if s['p_type']=='PT_DYNAMIC')
 exports[name]={s.name for s in dynamic.iter_symbols() if s['st_shndx']!='SHN_UNDEF' and s['st_info']['bind'] in ('STB_GLOBAL','STB_WEAK')}
 hashes[name]=hashlib.sha256(data).hexdigest()
result={}
for name,h in json.loads((a.components/'COMPONENTS.json').read_text()).items():
 if name.endswith('.jar'):continue
 data=(a.components/name).read_bytes();assert hashlib.sha256(data).hexdigest()==h
 e=ELFFile(io.BytesIO(data));needed=[t.needed for t in e.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED']
 imports={s.name for s in e.get_section_by_name('.dynsym').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF' and s['st_info']['bind']=='STB_GLOBAL'}
 available=set().union(*(exports[n] for n in needed));missing=sorted(imports-available)
 result[name]=dict(sha256=h,needed=needed,strong_imports=sorted(imports),missing=missing)
assert {'fprintf','send'}<=exports['libc.so.3']|exports['libsocket.so.3']
report=dict(variant=a.variant,firmware=a.firmware.name,passed=all(not r['missing'] for r in result.values()),factory_libraries=hashes,components=result)
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));assert report['passed']
