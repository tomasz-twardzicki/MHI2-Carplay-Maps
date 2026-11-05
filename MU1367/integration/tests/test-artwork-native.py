#!/usr/bin/env python3
"""Sanitize the real R3 fetcher and independently check lossless PNG output."""
import argparse,hashlib,json,os,shutil,struct,subprocess,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pixels(path):
 b=path.read_bytes();assert b[:8]==b'\x89PNG\r\n\x1a\n';at=8;compressed=b'';dimensions=None
 while at<len(b):
  size=struct.unpack_from('>I',b,at)[0];kind=b[at+4:at+8];data=b[at+8:at+8+size]
  assert zlib.crc32(kind+data)==struct.unpack_from('>I',b,at+8+size)[0]
  if kind==b'IHDR':dimensions=struct.unpack('>IIBBBBB',data);assert dimensions==(256,256,8,2,0,0,0)
  if kind==b'IDAT':compressed+=data
  at+=size+12
 assert at==len(b) and dimensions is not None
 raw=zlib.decompress(compressed);assert len(raw)==256*769;out=bytearray()
 for y in range(256):
  row=bytearray(raw[y*769+1:(y+1)*769]);f=raw[y*769];assert f in (0,1)
  if f==1:
   for x in range(3,len(row)):row[x]=(row[x]+row[x-3])&255
  out+=row
 return out
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--native-build',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 (out/'include').mkdir()
 for name in ('zlib.h','zconf.h'):shutil.copy2(a.native_build/'sdk-include'/name,out/'include'/name)
 runner=['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-e','ASAN_OPTIONS=halt_on_error=1:detect_leaks=1','-e','UBSAN_OPTIONS=halt_on_error=1','-v',str(HERE.parents[1])+':'+str(HERE.parents[1])+':ro','-v',str(out)+':'+str(out),'-w',str(out),'cpvc-settings-host-tests']
 flags=runner+['cc','-I'+str(out/'include'),'-std=c99','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-omit-frame-pointer']
 env=dict(os.environ,ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1')
 source=(HERE/'tests/artwork-test/test-fetch.c').read_text().replace('@FETCH@',str(HERE/'src/artwork-test/native/fetch.c')).replace('st.st_size>190000&&st.st_size<200000','st.st_size>0&&st.st_size<200000')
 for name,filename in [('PNG','colors.png'),('JPEG','colors.jpg')]:source=source.replace('@'+name+'@',','.join(map(str,(HERE/'tests/artwork-test/fixtures'/filename).read_bytes())))
 (out/'fetch-test.c').write_text(source)
 subprocess.run(flags+['-DCPMAP_PNG_COMPRESSED',str(out/'fetch-test.c'),'-l:libz.so.1','-o',str(out/'fetch-test')],check=True)
 run=subprocess.run(runner+[str(out/'fetch-test'),str(out)],env=env,text=True,capture_output=True,check=True);assert 'ARTWORK_FETCH_PASS' in run.stdout and not run.stderr
 (out/'fetch.log').write_text(run.stdout)
 harness='''#include "@IMAGE@"
int main(int argc,char **argv){unsigned char rgb[256*256*3];unsigned i,r=17;struct n3_image_info info;if(argc!=3)return 1;
if(argv[1][0]=='b'){size_t before=N3_BUDGET-700000;int ok;n3_used=before;memset(rgb,42,sizeof(rgb));ok=n3_png(rgb,argv[2]);return ok||n3_used!=before||access(argv[2],F_OK)==0;}
if(argv[1][0]=='j'){FILE *f=fopen(argv[1]+1,"rb");unsigned char b[800000];size_t n;if(!f)return 2;n=fread(b,1,sizeof(b),f);fclose(f);return !n3_decode(b,n,argv[2],&info);}
for(i=0;i<sizeof(rgb);i++){r=r*1664525u+1013904223u;rgb[i]=argv[1][0]=='n'?(unsigned char)(r>>24):argv[1][0]=='g'?(unsigned char)((i/3)%256+i/(256*3)):42;}
return !n3_png(rgb,argv[2]);}
'''.replace('@IMAGE@',str(HERE/'src/artwork-test/native/image.c'))
 (out/'encode.c').write_text(harness)
 for mode in ('stored','compressed'):subprocess.run(flags+(['-DCPMAP_PNG_COMPRESSED'] if mode=='compressed' else [])+[str(out/'encode.c'),'-l:libz.so.1','-o',str(out/mode)],check=True)
 sizes={}
 cases={'flat':'f','gradient':'g','noise':'n','jpeg':'j'+str((HERE/'tests/artwork-test/fixtures/colors.jpg').resolve()),'png':'j'+str((HERE/'tests/artwork-test/fixtures/colors.png').resolve())}
 for name,case in cases.items():
  for mode in ('stored','compressed'):subprocess.run(runner+[str(out/mode),case,str(out/(name+'-'+mode+'.png'))],check=True,env=env)
  before=out/(name+'-stored.png');after=out/(name+'-compressed.png');assert pixels(before)==pixels(after);assert after.stat().st_size<200000
  sizes[name]={'stored_bytes':before.stat().st_size,'compressed_bytes':after.stat().st_size,'identical_pixels':True}
 flag=out/'png-stored-flag'
 subprocess.run(flags+['-DCPMAP_PNG_COMPRESSED','-DCPMAP_PNG_STORED_FLAG="'+str(flag)+'"',str(out/'encode.c'),'-l:libz.so.1','-o',str(out/'ab')],check=True)
 # Flag changes happen inside the container: host-side changes can be cached stale by the VM mount.
 ab=str(out/'ab');script=ab+' g ab-compressed.png && touch png-stored-flag && '+ab+' g ab-stored.png && rm png-stored-flag && '+ab+' g ab-compressed-again.png'
 subprocess.run(runner+['sh','-c',script],check=True,env=env)
 assert (out/'ab-stored.png').read_bytes()==(out/'gradient-stored.png').read_bytes()
 assert (out/'ab-compressed.png').read_bytes()==(out/'ab-compressed-again.png').read_bytes()==(out/'gradient-compressed.png').read_bytes()
 subprocess.run(runner+[str(out/'compressed'),'b',str(out/'budget-rejected.png')],check=True,env=env)
 assert not (out/'budget-rejected.png').exists()
 assert sizes['flat']['compressed_bytes']<sizes['flat']['stored_bytes']//10
 result={'passed':True,'sanitizers':['address','undefined'],'fetch_checks':run.stdout.strip().splitlines()[-1],'images':sizes,'compressor_budget_refusal_clean':True,'runtime_ab_switch_verified':True,'source_sha256':{str(p.relative_to(HERE)):sha(p) for p in (HERE/'src/artwork-native/image.c',HERE/'src/artwork-native/fetch.c',Path(__file__))},'on_unit_validated':False}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
