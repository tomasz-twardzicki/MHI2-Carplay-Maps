#!/usr/bin/env python3
"""Read-only evidence for the MU1367 independent position-service client.

Checks actual K4525/P4521 HW50/HW70 images, including the generated ASI factory.
No target process is started. No native IPC or radio acceptance is claimed.
"""
import argparse,hashlib,io,json,struct,sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'port'))
from firmware import QNX6,image_files,stage1,stage2

PINS={
 'eso/bin/apps/dio_manager':'ead570d45071bb4dafe4a4667003bb9f82a72f58178f30dc86a08f11ce62a3ae',
 'eso/bin/apps/esoposprovider':'a3e4d7dec7edc6083458109c441107b546fd98c832c3520ae676bde237016eaf',
 'eso/lib/factories/libasimmxesoposproviderfullproxy.so':'4e95c32c9be86b11dfffe2bc62ceaee1d8ba46ac106f00193b3a921fcb299439',
 'eso/lib/factories/libasimmxesoposproviderproxy.so':'d2b6ae0b2924b6ecd5dbfaef6504a50e3155f4e1fd5325fbb632225748276fba',
 'eso/lib/libcomm.so':'a1be938a6a7e4f27db16d76bfef2981fc0b31f0b7869a37042fca2f1c91c0972',
 'eso/lib/libutil.so':'b9f4e0c7618737859095fb28bae3cd72e9b89c259b382d0b90545c3c884d7106',
 'eso/lib/libosal.so':'f4a23a6d508ff28720b930f49ab80daf74631b6eaea026613110f924e54dbc83',
 'eso/lib/libiplcommon.so':'b7be363bce6441010e940a106725bfb8324e9b3d30e32497acfca9c62e176b56',
}
sha=lambda b:hashlib.sha256(b).hexdigest()
class Binary:
 def __init__(self,data):self.data=data;self.elf=ELFFile(io.BytesIO(data))
 def at(self,va,n):
  for s in self.elf.iter_segments():
   if s['p_type']=='PT_LOAD' and s['p_vaddr']<=va and va+n<=s['p_vaddr']+s['p_filesz']:
    off=va-s['p_vaddr'];return s.data()[off:off+n]
  raise ValueError(('unmapped',hex(va),n))
 def word(self,va):return struct.unpack('<I',self.at(va,4))[0]
 def text(self,va):return self.at(va,256).split(b'\0',1)[0].decode('ascii')
 def got(self):return next(t.entry.d_val for t in self.elf.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_PLTGOT')
 def relative_text(self,va):return self.text((self.word(va)+self.got())&0xffffffff)
 def assert_word(self,va,word):assert self.word(va)==word,(hex(va),hex(self.word(va)),hex(word))
 def immediate(self,va,top=False):
  word=self.word(va);assert word&0x0ff00000==(0x03400000 if top else 0x03000000)
  return ((word>>4)&0xf000)|(word&0xfff)
 def plt(self):
  section=self.elf.get_section_by_name('.plt');rel=self.elf.get_section_by_name('.rel.plt');symbols=self.elf.get_section(rel['sh_link'])
  return {section['sh_addr']+20+12*i:symbols.get_symbol(v['r_info_sym']).name for i,v in enumerate(rel.iter_relocations())}

def inspect(inputs):
 d=Binary(inputs['eso/bin/apps/dio_manager']);s=Binary(inputs['eso/bin/apps/esoposprovider']);f=Binary(inputs['eso/lib/factories/libasimmxesoposproviderfullproxy.so'])
 assert d.text(0x19a424)=='asi.navigation.esoposproviderfull.EsoPosProviderFull'
 assert d.text(0x19a45c)=='asi.navigation.esoposproviderfull.EsoPosProviderFullReply'
 # These are the two slots used by the old passive capture, including thunk.
 assert d.word(0x1a43d8+12*4)==0x1649c0 and d.word(0x1a43d8+42*4)==0x1649b8
 assert 'ASI version:' in d.relative_text(0x164afc)
 assert d.relative_text(0x164b00)=='updateASIVersion'
 assert d.relative_text(0x163a84)=='updatePosition'
 d.assert_word(0x1639bc,0xe285500c) # vector<CIPtr<CIString>> element stride 12
 assert d.plt()[0x11235c]=='_ZN4util14UnicodeString8aSERKS0_'
 # DIO's ordinary service and reply identities, independent of HMI PosPosition.
 assert d.immediate(0x1643b4)|(d.immediate(0x1643c0,True)<<16)==0x3a8ac390
 assert d.immediate(0x164438)|(d.immediate(0x164440,True)<<16)==0x4325a74a
 assert d.immediate(0x1647cc)|(d.immediate(0x1647d4,True)<<16)==0x995a4140
 assert d.immediate(0x164708)|(d.immediate(0x16470c,True)<<16)==0x2c5da29e
 # Actual generated proxy/stub, not guessed plain-text NMEA framing.
 f.assert_word(0x77b4,0xe3a0200f) # setConfig call ID 15
 f.assert_word(0xaf4c,0xe3a02019) # updatePosition call ID 25
 assert 'CIString' in f.plt()[0x1f54] and 'sPosition' in f.plt()[0x1f60]
 assert f.plt()[0x21c4]=='_ZN4util10serializer11deserializeERNS0_19IStreamDeserializerERNS_14UnicodeString8E'
 # Provider client lookup precedes its configuration writes; no sensor/global
 # nav setting is altered by this handler. Initial raw GNSS mode is 1 Hz.
 for va,word in {0x121a24:0xca000001,0x121a28:0xe3530ffa,0x121aec:0xe3530000,
                 0x121af8:0xe3530000,0x121b04:0xe3530000,0x121b54:0xe5878008,
                 0x121b88:0xe5879000}.items():s.assert_word(va,word)
 assert s.relative_text(0x121be8)=='[eppF] setConfig -> config accepted'
 assert s.text(0x142350)=='Got GNSS time fix, UTC timestamp is valid now'
 assert s.text(0x14308c).startswith('GPGGA,') and s.text(0x1430dc).startswith('GPRMC,')
 ranges={
  'dio_proxy_identity':(d,0x164304,0x164898),
  'dio_client_config':(d,0x163b18,0x163d04),
  'dio_data_callback':(d,0x163918,0x163a88),
  'dio_wrong_old_hook':(d,0x1649b8,0x164b14),
  'provider_config_per_client':(s,0x121950,0x121bf0),
  'provider_client_output':(s,0x111f44,0x112218),
  'asi_config_serializer':(f,0x7748,0x7bdc),
  'asi_data_deserializer':(f,0xcdf8,0xdc64),
 }
 return {name:dict(start=hex(start),end=hex(end),sha256=sha(binary.at(start,end-start))) for name,(binary,start,end) in ranges.items()}

def main():
 p=argparse.ArgumentParser()
 for n in ('k4525','p4521','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();profiles={}
 for name,fw in [('K4525',a.k4525),('P4521',a.p4521)]:
  for hw in ('50','70'):
   base=fw/'MMX2';app=QNX6(base/('app/'+hw+'/default/app.img'))
   try:inputs={n:app.get(n) for n in PINS if '/lib/' not in n or '/factories/' in n}
   finally:app.file.close()
   ifs=image_files(stage1(base/('mifs-stage1/'+hw+'/default/mifs-stage1.img')))
   ifs.update(image_files(stage2(base/('mifs-stage2/'+hw+'/default/mifs-stage2.img'))))
   for n in PINS:
    if n not in inputs:inputs[n]=ifs[n]
   hashes={n:sha(b) for n,b in inputs.items()};assert hashes==PINS,(name,hw,hashes)
   profiles[name+'-HW'+hw]=dict(passed=True,sha256=hashes,anchors=inspect(inputs))
 result=dict(schema=1,passed=True,date='2026-11-24',scope='Static binary/IDL contract; not a running independent client.',profiles=profiles,
  service=dict(name='asi.navigation.esoposproviderfull.EsoPosProviderFull',reply='asi.navigation.esoposproviderfull.EsoPosProviderFullReply',
   instance='3a8ac390-4251-11e3-9434-000c29e68a4a',interface='995a4140-c7f3-5205-8335-d13059867b08',reply_interface='2c5da29e-82ab-5b99-8f06-68cfdd97c847',
   transport='OEM ASI/COMM proxy-stub RPC; not a raw NMEA socket',set_config_method=15,update_position_method=25,
   update_position_fields=['optional vector<CIPtr<CIString>> NMEA sentences','optional sPosition','optional vector<CIPtr<sPosition>> predictions']),
  old_dio_capture=dict(correct=False,callback='updateASIVersion',data_callback='updatePosition',old_primary='0x1649c0',actual_data='0x163920'),
  raw_gnss_candidate_config=dict(update_period_ms=1000,pred_length=0,pred_duration=0,dead_reckoning=False,map_positioning=False,offset12=0,offset24=1,offset28=0),
  receiver=dict(wgps_version=1,sentences=['GPGGA','GPRMC'],estimated_fixes_accepted=False,source_required_before_identification=True),
  independent_client_implemented=False,on_unit_validated=False)
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,profiles=list(profiles),old_capture_callback='updateASIVersion')))
if __name__=='__main__':main()
