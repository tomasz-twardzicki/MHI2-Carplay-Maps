#!/usr/bin/env python3
"""Replay validated iAP2 metadata from a private log; report counts, not text."""
import argparse,hashlib,json,re,struct,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
for name in ('log','components','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
payloads=[];buf=bytearray();seen=0
def consume():
 global seen
 data=bytes(buf);at=0
 while at+16<=len(data):
  start=data.find(b'\xff\x5a',at)
  if start<0 or start+16>len(data):break
  n=int.from_bytes(data[start+2:start+4],'big');at=start+2
  if n<16 or n>len(data)-start:continue
  pkt=data[start:start+n]
  if sum(pkt[:9])&255 or sum(pkt[9:])&255:continue
  if pkt[7]!=10 or pkt[9:11]!=b'@@' or pkt[13:15]!=b'\x50\x01':continue
  if int.from_bytes(pkt[11:13],'big')!=len(pkt)-10:continue
  payloads.append(pkt[15:-1]);seen+=1;at=start+n
for line in a.log.read_text(errors='replace').splitlines():
 m=re.match(r'^\s+\+([0-9a-fA-F]{4,}):([^|]+)\|',line)
 if m:
  text=''.join(m[2].split())
  if not re.fullmatch('[0-9a-fA-F]+',text) or len(text)%2:continue
  offset=int(m[1],16);part=bytes.fromhex(text)
  if offset==0:consume();buf=bytearray()
  if offset==len(buf) and len(buf)+len(part)<=1048576:buf.extend(part)
  else:consume();buf=bytearray()
 else:consume();buf=bytearray()
consume();assert payloads,'No complete, checksum-valid iAP2 metadata packets found'
(out/'private-payloads.bin').write_bytes(b''.join(struct.pack('<I',len(v))+v for v in payloads))
source=r'''
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include "wcp_media.c"
int main(int argc,char **argv){
 FILE *f;struct wcp_media state;unsigned i,total=0,valid=0,invalid=0,text=0,positions=0,tracks=0;unsigned char size[4],p[8192];
 assert(argc==2);f=fopen(argv[1],"rb");assert(f);memset(&state,0,sizeof(state));
 while((i=fread(size,1,4,f))!=0){
  unsigned n;uint64_t uid=state.uid;assert(i==4);n=size[0]|(unsigned)size[1]<<8|(unsigned)size[2]<<16|(unsigned)size[3]<<24;
  assert(n&&n<=sizeof(p)&&fread(p,1,n,f)==n);total++;
  if(wcp_media_message(&state,p,n)){valid++;if(state.text[0][0]&&state.text[1][0])text++;if(state.known&8)positions++;if(uid!=state.uid)tracks++;}
  else invalid++;
 }
 assert(!ferror(f)&&!fclose(f)&&valid&&text&&positions);
 printf("{\"packets\":%u,\"accepted\":%u,\"rejected\":%u,\"with_title_and_artist\":%u,\"with_position\":%u,\"track_changes\":%u}\n",total,valid,invalid,text,positions,tracks);return 0;
}
'''
(out/'replay.c').write_text(source)
subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/clang','-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk','-std=gnu99','-O1','-g','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
 '-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(a.components.resolve()/'src'),str(out/'replay.c'),'-o',str(out/'replay')],check=True)
r=subprocess.run([str(out/'replay'),str(out/'private-payloads.bin')],capture_output=True,text=True,check=True)
assert not r.stderr,r.stderr
report=dict(passed=True,source_log_sha256=hashlib.sha256(a.log.read_bytes()).hexdigest(),
 checksum_validated=True,sanitizers=['address','undefined'],result=json.loads(r.stdout),
 scope='Replay of complete checksum-valid logged iAP2 metadata, without exporting track text, phone identifiers or packet bytes.')
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
