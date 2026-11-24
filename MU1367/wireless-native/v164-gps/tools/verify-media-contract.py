#!/usr/bin/env python3
"""Read the exact matching firmware's iAP2 field tables and receiver anchors."""
import argparse,hashlib,io,json,struct,sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/'port'))
from firmware import QNX6
p=argparse.ArgumentParser()
for n in ('k4525','p4521','receiver','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();report={}
def table(data,name):
 e=ELFFile(io.BytesIO(data));symbol=next(s for s in e.get_section_by_name('.symtab').iter_symbols() if s.name==name)
 def read(va,n):
  for seg in e.iter_segments():
   if seg['p_type']=='PT_LOAD' and seg['p_vaddr']<=va and va+n<=seg['p_vaddr']+seg['p_filesz']:
    off=seg['p_offset']+va-seg['p_vaddr'];return data[off:off+n]
  raise ValueError('unmapped firmware address')
 result={}
 for at in range(0,symbol['st_size'],12):
  ptr,flags,value=struct.unpack('<III',read(symbol['st_value']+at,12))
  if ptr:result[at//12]=dict(name=read(ptr,120).split(b'\0')[0].decode(),flags=hex(flags))
 return result
for fw in (a.k4525,a.p4521):
 for hw in ('50','70'):
  driver=QNX6(fw/('MMX2/app/'+hw+'/default/app.img')).get('armle/lib/dll/ipod-drvr-iap2.so')
  assert hashlib.sha256(driver).hexdigest()=='7149a3e75b1b19e89021841759f420a6eced456b6c697a3dd1f0e436abea0b8c'
  md=table(driver,'sparams_nowplay_start_mdtypes');pb=table(driver,'sparams_nowplay_upd_pbtypes')
  for key,name in [(0,'MediaItemPersistentIdentifier'),(1,'MediaItemTitle'),(4,'MediaItemPlaybackDurationInMilliseconds'),(6,'MediaItemAlbumTitle'),(12,'MediaItemArtist'),(26,'MediaItemArtworkFileTransferIdentifier')]:assert md[key]['name']==name
  for key,name in [(0,'PlaybackStatus'),(1,'PlaybackElapsedTimeInMilliseconds'),(5,'PlaybackShuffleMode'),(6,'PlaybackRepeatMode'),(7,'PlaybackAppName')]:assert pb[key]['name']==name
  report[fw.name+'/'+hw]=dict(driver_sha256=hashlib.sha256(driver).hexdigest(),media_item=md,playback=pb)
receiver=a.receiver.read_bytes();assert hashlib.sha256(receiver).hexdigest()=='f195665b0e9fb8a592618e64b7201ddfc536a9b082c6dd35db214b99d5e01de1'
e=ELFFile(io.BytesIO(receiver))
def read(va,n):
 for seg in e.iter_segments():
  if seg['p_type']=='PT_LOAD' and seg['p_vaddr']<=va and va+n<=seg['p_vaddr']+seg['p_filesz']:
   off=seg['p_offset']+va-seg['p_vaddr'];return receiver[off:off+n]
 raise ValueError('unmapped receiver address')
assert read(0x3ff26,12)==bytes([0,1,4,6,12,26,0,1,7,12,13,16])
anchors={name:dict(address=hex(va),bytes=n,sha256=hashlib.sha256(read(va,n)).hexdigest()) for name,va,n in [('alt_sender_create_port9997',0xe658c,76),('csm_log_before_dispatch',0xecba0,44),('ft_first_chunk_copy',0xee46c,40),('ft_declaration_ack_copy',0xedd88,32),('ft_image_completion',0xee658,136),('ft_empty_completion',0xee59c,36),('info_refresh',0xce974,28)]}
r=dict(passed=True,firmware_tables=report,receiver_sha256=hashlib.sha256(receiver).hexdigest(),receiver_requested_media_ids=[0,1,4,6,12,26],receiver_requested_playback_ids=[0,1,7,12,13,16],receiver_anchors=anchors,scope='Fresh read-only matching MU1367 firmware extraction; receiver execution and lifetimes tested separately.')
a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(passed=True,firmware_variants=len(report),receiver_subscription_includes_uid_and_cover=True)))
