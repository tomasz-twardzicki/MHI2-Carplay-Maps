#!/usr/bin/env python3
"""Production worker: bounded decode, orientation, PNG bytes and supervisor.
Runs with ASan/UBSan; only the child's blocked-read seam is mocked.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import time
import zlib

HERE=Path(__file__).resolve().parent
PIN='71b4ab1c9461d5383a7aa6d56d4dda34f567ade7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def chunk(name,data):
    return struct.pack('>I',len(data))+name+data+struct.pack('>I',binascii.crc32(name+data)&0xffffffff)
def png(w,h,pixels=None):
    raw=b''.join(b'\0'+(pixels[y*w*3:(y+1)*w*3] if pixels else bytes(w*3)) for y in range(h))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
def decode_png(path):
    b=path.read_bytes();at=8;data=b'';w=h=None
    assert b[:8]==b'\x89PNG\r\n\x1a\n'
    while at<len(b):
        n,=struct.unpack_from('>I',b,at);name=b[at+4:at+8];block=b[at+8:at+8+n]
        assert struct.unpack_from('>I',b,at+8+n)[0]==binascii.crc32(name+block)&0xffffffff
        if name==b'IHDR':w,h=struct.unpack_from('>II',block);assert block[8:]==bytes([8,2,0,0,0])
        if name==b'IDAT':data+=block
        at+=n+12
    raw=zlib.decompress(data);assert len(raw)==h*(w*3+1)
    assert all(raw[y*(w*3+1)]==0 for y in range(h))
    return w,h,b''.join(raw[y*(w*3+1)+1:(y+1)*(w*3+1)] for y in range(h))
def frame(image=b'',kind=1):
    b=bytearray(128);b[:4]=b'N3AR'
    for off,val in {4:1,8:128,12:9,20:len(image),24:kind if image else 0,28:3,36:2,64:2,68:1,72:123,76:567}.items():
        struct.pack_into('<I',b,off,val)
    return b+image

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cc',default='/Library/Developer/CommandLineTools/usr/bin/clang')
    p.add_argument('--sysroot',type=Path,default=Path('/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk'))
    p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();tests=[]
    with tempfile.TemporaryDirectory(prefix='n3-worker-') as d:
        root=Path(d);flags=[a.cc,'-std=c99','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer']
        if a.sysroot:flags+=['-isysroot',str(a.sysroot)]
        exe=root/'capture'
        subprocess.run(flags+[str(HERE/'capture.c'),'-o',str(exe)],check=True)
        count=0
        def run(blob,ok=True):
            nonlocal count
            count+=1;source=root/('source'+str(count));source.write_bytes(blob)
            out=root/('out'+str(count));out.mkdir();lock=root/'lock'
            r=subprocess.run([str(exe),str(source),str(lock),str(out)],capture_output=True,text=True,timeout=8)
            assert (r.returncode==0)==ok,(r.stdout,r.stderr)
            assert not r.stderr,r.stderr
            assert not lock.exists()
            return r.stdout,out
        pixels=bytes([255,0,0,0,255,0,0,0,255,255,255,255,255,255,0,0,255,255])
        image=png(3,2,pixels);status,out=run(frame(image))
        assert (out/'original.bin').read_bytes()==image
        w,h,rgb=decode_png(out/'cover.png');assert (w,h)==(256,256)
        # 3:2 contain => 256x171, centered vertically at y=42.
        assert rgb[:42*256*3]==bytes(42*256*3)
        for x,y,index in ((0,42,0),(128,42,1),(255,42,2),(0,212,3),(128,212,4),(255,212,5)):
            assert rgb[(y*256+x)*3:(y*256+x)*3+3]==pixels[index*3:index*3+3]
        assert 'width=3 height=2 orientation=1' in status
        tests.append('PNG pixels, contain resize, CRC/adler/DEFLATE and exact original bytes')
        status,out=run(frame());assert 'bytes=0' in status and not list(out.iterdir())
        for offset,value in ((4,2),(8,64),(16,1),(20,800001),(24,2),(36,3),(68,0),(76,1000000000),(80,1)):
            bad=frame(image);struct.pack_into('<I',bad,offset,value);run(bad,False)
        run(frame(image)[:-1],False);run(frame(image)+b'x',False)
        tests.append('empty mailbox, malformed schema, signature, session, bounds and short/trailing reply')
        # Header-only PNGs fail the dimension/pixel gate before a large decode.
        for w,h in ((4097,1),(4096,4096),(0,1)):
            bad=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''))+chunk(b'IEND',b'')
            run(frame(bad),False)
        run(frame(b'\xff\xd8\xff'+bytes(597),2),False)
        tests.append('oversized dimensions, pixel budget and malformed JPEG rejection')
        jpeg=subprocess.check_output(['git','-C',str(a.reference),'show',PIN+':tests/fixtures/coverart/exif-thumbnail.jpg'])
        # Inject IFD0 first; compare every transformed output pixel against
        # the orientation-1 decode, including flips, transposes and rotations.
        base_rgb=None
        for o in range(1,9):
            exif=b'Exif\0\0II'+struct.pack('<HIHHHII',42,8,1,0x112,3,1,o)+bytes(4)
            modified=jpeg[:2]+b'\xff\xe1'+struct.pack('>H',len(exif)+2)+exif+jpeg[2:]
            status,out=run(frame(modified,2))
            assert f'orientation={o} ' in status,status
            w,h,actual=decode_png(out/'cover.png');assert (w,h)==(256,256)
            if o==1:base_rgb=actual
            expected=bytearray(len(actual))
            for y in range(256):
                for x in range(256):
                    sx,sy={1:(x,y),2:(255-x,y),3:(255-x,255-y),4:(x,255-y),
                        5:(y,x),6:(y,255-x),7:(255-y,255-x),8:(255-y,x)}[o]
                    expected[(y*256+x)*3:(y*256+x)*3+3]=base_rgb[(sy*256+sx)*3:(sy*256+sx)*3+3]
            assert actual==expected,o
        tests.append('real JPEG with embedded thumbnail and pixel checks for EXIF orientations 1 through 8')
        # Budget exhaustion and malformed EXIF fuzz exercise actual image code.
        fixture=root/'safety.c'
        fixture.write_text('''#define _POSIX_C_SOURCE 200809L
#include "'''+str(HERE/'image.c')+'''"
int main(void) {
 unsigned char b[512];unsigned i,j;uint32_t state=12345;void *p;struct n3_image_info info;
 p=n3_alloc(N3_BUDGET-8);if(!p || n3_alloc(1))return 1;
 if(n3_realloc(p,N3_BUDGET))return 1;n3_free(p);if(n3_used)return 1;
 for(i=0;i<50000;i++) {
  for(j=0;j<sizeof(b);j++){state=state*1664525u+1013904223u;b[j]=(unsigned char)(state>>24);}
  b[0]=255;b[1]=216;b[2]=255;b[3]=225;
  if(n3_orientation(b,i%sizeof(b))<1 || n3_orientation(b,i%sizeof(b))>8)return 1;
 }
 memset(b,0,sizeof(b));if(n3_decode(b,sizeof(b),"/invalid/not-written",&info))return 1;
 if(n3_used)return 1;return 0;
}
''')
        subprocess.run(flags+[str(fixture),'-o',str(root/'safety')],check=True)
        subprocess.run([str(root/'safety')],check=True,timeout=15)
        tests.append('64 MiB decoder budget, failed realloc preservation and 50000 malformed EXIF cases')
        shim=root/'shim.c';shim.write_text('''#define _POSIX_C_SOURCE 200809L
#include <unistd.h>
#include <string.h>
ssize_t n3_test_read(int fd,void *b,size_t count) {
 ssize_t n=read(fd,b,count);
 if(count==800128 && n>=4 && !memcmp(b,"WAIT",4))for(;;)pause();return n;
}
''')
        subprocess.run(flags+['-Dread=n3_test_read','-c',str(HERE/'capture.c'),'-o',str(root/'worker.o')],check=True)
        subprocess.run(flags+[str(shim),str(root/'worker.o'),'-o',str(root/'blocked')],check=True)
        source=root/'wait';source.write_bytes(b'WAIT'+bytes(124));out=root/'blocked-out';out.mkdir()
        start=time.monotonic()
        r=subprocess.run([str(root/'blocked'),str(source),str(root/'lock'),str(out)],capture_output=True,text=True,timeout=8)
        elapsed=time.monotonic()-start
        assert r.returncode and 'TIMEOUT' in r.stdout and not (root/'lock').exists() and 4.9<elapsed<7,(elapsed,r.stdout,r.stderr)
        assert not r.stderr,r.stderr
        tests.append('blocked device read killed/reaped within 5s deadline plus bounded cleanup')
        (root/'lock').mkdir()
        r=subprocess.run([str(exe),str(source),str(root/'lock'),str(out)],capture_output=True,text=True,timeout=2)
        assert r.returncode and 'LOCK_OR_STALE' in r.stdout and (root/'lock').exists()
        tests.append('stale lock refuses another child')
    result={'passed':True,'tests':tests,'sanitizers':['address','undefined'],
        'blocked_elapsed_seconds':round(elapsed,3),'reference_commit':PIN,
        'sources':{str(f.relative_to(HERE)):sha(f) for f in (HERE/'capture.c',HERE/'image.c',HERE/'vendor/stb_image.h',Path(__file__))}}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
