#!/usr/bin/env python3
"""Fresh, read-only location evidence from both MU1367 firmware/hardware variants."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/'port'))
from firmware import QNX6
p=argparse.ArgumentParser()
for n in ('k4525','p4521','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();pins={
 'eso/bin/apps/dio_manager':'ead570d45071bb4dafe4a4667003bb9f82a72f58178f30dc86a08f11ce62a3ae',
 'armle/lib/dll/ipod-drvr-iap2.so':'7149a3e75b1b19e89021841759f420a6eced456b6c697a3dd1f0e436abea0b8c',
 'eso/bin/apps/esoposprovider':'a3e4d7dec7edc6083458109c441107b546fd98c832c3520ae676bde237016eaf'}
def mapped(b,address,size):
 assert b[:7]==b'\x7fELF\x01\x01\x01'
 phoff=struct.unpack_from('<I',b,28)[0];ents,num=struct.unpack_from('<HH',b,42)
 for i in range(num):
  typ,off,va,pa,filesz,memsz,flags,align=struct.unpack_from('<8I',b,phoff+i*ents)
  if typ==1 and va<=address and address+size<=va+filesz:return b[off+address-va:off+address-va+size]
 raise ValueError('unmapped VA '+hex(address))
profiles={}
for name,root in [('K4525',a.k4525),('P4521',a.p4521)]:
 directory=root/('MMX2' if (root/'MMX2').is_dir() else 'mmx2')
 for variant in ('50','70'):
  app=QNX6(directory/'app'/variant/'default/app.img')
  try:inputs={n:app.get(n) for n in pins}
  finally:app.file.close()
  hashes={n:hashlib.sha256(b).hexdigest() for n,b in inputs.items()};assert hashes==pins
  dio=inputs['eso/bin/apps/dio_manager']
  assert struct.unpack('<I',mapped(dio,0x1a43d8+12*4,4))[0]==0x1649c0
  assert struct.unpack('<I',mapped(dio,0x1a43d8+42*4,4))[0]==0x1649b8
  phoff=struct.unpack_from('<I',dio,28)[0];ents,num=struct.unpack_from('<HH',dio,42);writable=False
  for i in range(num):
   typ,off,va,pa,filesz,memsz,flags,align=struct.unpack_from('<8I',dio,phoff+i*ents)
   if typ==1 and va<=0x1a43d8 and 0x1a43d8+188<=va+filesz:writable=bool(flags&2)
  assert writable,'NMEA-specific callback slots must be in writable factory .data'
  driver=inputs['armle/lib/dll/ipod-drvr-iap2.so']
  word=lambda va:struct.unpack('<I',mapped(driver,va,4))[0]
  signed=lambda n:n-(1<<32) if n>>31 else n
  table=0xcb88+signed(word(0xce78))+signed(word(0xce7c))+4
  types={}
  for i in range(7):
   ptr,identifier=struct.unpack('<IH2x',mapped(driver,table+i*8,8))
   types[mapped(driver,ptr,8).split(b'\0')[0].decode('ascii')]=identifier
  assert table==0x27db0 and types['GPGGA']==17 and types['GPRMC']==18
  # Exact ARM message selection and serializer contracts, independently of C prototype.
  for va,expected in {0x1359c:0xe30f2ffa,0x135a8:0xe2822002,0x9758:0xe30f2ffb,0x973c:0xe3a02000,0xce54:0xe3a02016}.items():assert word(va)==expected
  profiles[name+'-HW'+variant]=dict(sha256=hashes,identification_sentence_ids=types,location_messages=['0xfffa','0xfffb','0xfffc'])
r=dict(passed=True,profiles=profiles,on_unit_validated=False)
a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(passed=True,profiles=list(profiles))))
