#!/usr/bin/env python3
"""Resolve the untouched 790 backend's strong imports against both MU1367 trains."""
import argparse,hashlib,io,json,sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/'port'))
from firmware import QNX6,image_files,stage1,stage2
p=argparse.ArgumentParser()
for n in ('build','firmware-k','firmware-p','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();sd=a.build/'sd-card';payload=sd/'Custom/carplay_mu1367_input_profile/790/payload'
modules={n:(payload/n).read_bytes() for n in ('core.so','wcp_receiver','wireless-entry','wireless-receiver-exec','libomonob-wireless-maps.so')}
for n in ('altscreen-most-bridge','carplay-cluster-supervisor','libcpmap-wcp-media790.so'):
 if (payload/n).is_file():modules[n]=(payload/n).read_bytes()
modules['libv75-transport.so']=(sd/'Custom/carplay_mu1367_wireless_native/payload/libv75-transport.so').read_bytes()
sha=lambda b:hashlib.sha256(b).hexdigest()
def symbols(data):
 e=ELFFile(io.BytesIO(data));d=next(s for s in e.iter_segments() if s['p_type']=='PT_DYNAMIC')
 exports={s.name for s in d.iter_symbols() if s['st_shndx']!='SHN_UNDEF' and s['st_info']['bind'] in ('STB_GLOBAL','STB_WEAK')}
 imports={s.name for s in d.iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF' and s['st_info']['bind']=='STB_GLOBAL'}
 needed=[t.needed for t in d.iter_tags() if t.entry.d_tag=='DT_NEEDED']
 return exports,imports,needed
module_symbols={n:symbols(b) for n,b in modules.items()};global_exports=set().union(*(v[0] for v in module_symbols.values()))
reports={}
for fw in (a.firmware_k,a.firmware_p):
 for variant in ('50','70'):
  files=image_files(stage1(fw/('MMX2/mifs-stage1/'+variant+'/default/mifs-stage1.img')))
  files.update(image_files(stage2(fw/('MMX2/mifs-stage2/'+variant+'/default/mifs-stage2.img'))))
  app=QNX6(fw/('MMX2/app/'+variant+'/default/app.img'));factory={}
  dio_needed=symbols(app.get('eso/bin/apps/dio_manager'))[2]
  assert {'libc.so.3','libsocket.so.3'}<=set(dio_needed)
  for name in set(n for v in module_symbols.values() for n in v[2]):
   candidates={b for path,b in files.items() if Path(path).name==name}
   if not candidates:
    for prefix in ('armle/lib','armle/lib/dll','armle/usr/lib','root/lib-target','eso/lib','usr/lib'):
     try:candidates.add(app.get(prefix+'/'+name))
     except (KeyError,ValueError):pass
   assert len(candidates)==1,(fw.name,variant,name,len(candidates))
   factory[name]=candidates.pop()
  results={}
  for name,(exports,imports,needed) in module_symbols.items():
   # Both core generations are dio_manager plugins. The upstream v3.2 core
   # has no DT_NEEDED entries at all: libc and socket imports are supplied
   # by the actual OEM host, checked above rather than assumed from an SDK.
   providers=sorted(set(needed+(['libc.so.3','libsocket.so.3'] if name=='core.so' else [])))
   available=set().union(*(symbols(factory[n])[0] for n in providers))
   preload=[]
   if name=='wcp_receiver':
    # The exact upstream 790 launcher preloads this library; it exports v75gen.
    assert b'/mnt/app/carplaymaps/libv75-transport.so:/mnt/app/carplaymaps/libomonob-wireless-maps.so' in modules['wireless-receiver-exec']
    preload=['libv75-transport.so','libomonob-wireless-maps.so']
    available|=set().union(*(module_symbols[n][0] for n in preload))
   results[name]=dict(sha256=sha(modules[name]),needed=needed,host_providers=providers,preload_providers=preload,missing=sorted(imports-available))
  assert all(not r['missing'] for r in results.values()),results
  reports[fw.name+'/'+variant]=dict(passed=True,modules=results,factory_sha256={n:sha(b) for n,b in factory.items()})
report=dict(passed=True,scope='ELF strong-import resolution only; no receiver, radio, decode or MOST hardware execution.',profiles=reports)
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'profiles':list(reports)}))
