#!/usr/bin/env python3
"""Reproduce guidance output failure and stress the shipped v2 log limits.
No unit files are modified and no filesystem is actually filled.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import zipfile
HERE=Path(__file__).resolve().parent
RG=HERE.parents[1]/'MU1427/route-guidance'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

FAULTS=r'''#define _POSIX_C_SOURCE 200809L
#include <sys/stat.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
static int fired,status_writes;
static int mode(const char *name){const char *s=getenv("RGI_OUTPUT_FAULT");return s&&!strcmp(s,name);}
ssize_t resource_write(int fd,const void *b,size_t n){struct stat st;
 if(!fired&&mode("mailbox_write")&&n>32&&!fstat(fd,&st)&&S_ISREG(st.st_mode)){fired=1;errno=ENOSPC;return -1;}
 return write(fd,b,n);
}
FILE *resource_fopen(const char *name,const char *flags){
 if(mode("status_write")&&!strcmp(name,"status.tmp")&&++status_writes==2){fired=1;errno=ENOSPC;return NULL;}
 return fopen(name,flags);
}
int resource_rename(const char *from,const char *to){
 if(!fired&&mode("mailbox_rename")&&!strcmp(to,"latest.bin")){fired=1;errno=ENOSPC;return -1;}
 return rename(from,to);
}
'''

STRESS=r'''
int main(int argc,char **argv){
 struct stat st;FILE *other;unsigned i;unsigned long core_high=0,bridge_high=0;int checks=0;
 assert(argc==3);assert(!setenv("CARPLAY_ALTSCREEN_LOG",argv[1],1));
 for(i=0;i<60000;i++){
  log_status("resource-stress-real-core",NULL,0);
  assert(!stat(argv[1],&st));assert(st.st_size<=CPMAP_VIDEO_LOG_LIMIT);
  if((unsigned long)st.st_size>core_high)core_high=(unsigned long)st.st_size;
 }
 other=fopen(argv[2],"w");assert(other);
 for(i=0;i<60000;i++){
  assert(cpmap_log_fprintf(other,CPMAP_BRIDGE_LOG_LIMIT,"bridge-log-stress %u retained-frame=1 bounded-capture=1\n",i)>0);
  assert(!stat(argv[2],&st));assert(st.st_size<=CPMAP_BRIDGE_LOG_LIMIT);
  if((unsigned long)st.st_size>bridge_high)bridge_high=(unsigned long)st.st_size;
 }
 assert(!fclose(other));checks+=120000;
 /* An old open descriptor must not create a sparse file after another
  * descriptor truncates that same inode. This is the shipped helper. */
 other=fopen(argv[2],"w");assert(other);assert(!setvbuf(other,NULL,_IONBF,0));
 for(i=0;i<CPMAP_BRIDGE_LOG_LIMIT+4096;i++)assert(fputc('x',other)!=EOF);
 cpmap_limit_path(argv[2],CPMAP_BRIDGE_LOG_LIMIT);assert(!stat(argv[2],&st));assert(st.st_size==0);
 assert(cpmap_log_fprintf(other,CPMAP_BRIDGE_LOG_LIMIT,"still-appending\n")==16);assert(!fclose(other));
 assert(!stat(argv[2],&st));assert(st.st_size==16);checks+=2;
 printf("RESOURCE_LOG_BOUNDS_PASS checks=%d core_high=%lu bridge_high=%lu same_inode=1 ring_bytes=%lu\n",checks,core_high,bridge_high,(unsigned long)sizeof(AltFrameRing));return 0;
}
'''


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('runtime','package','logs','java-home','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 runtime=a.runtime.resolve();manifest=json.loads((runtime/'manifest.json').read_text())
 packaged=a.package/'sd-card/Custom/carplay_mu1367_settings'
 for n,h in manifest['files'].items():assert sha(runtime/n)==sha(packaged/n)==h,n
 resource_header=runtime/'src/card-core/source/cpmap_resources.h'
 bridge_header=runtime/'src/vc-runtime/runtime/cpmap_resources.h'
 assert resource_header.read_bytes()==bridge_header.read_bytes()
 # The runtime source snapshot must correspond to the pinned v2 source.
 pins=json.loads((HERE/'UPSTREAM.json').read_text())['source_files']
 for name in ('card-core/source/cpmap_resources.h','vc-runtime/runtime/cpmap_resources.h'):
  assert sha(runtime/'src'/name)==pins[name]
 cc=['clang','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function']
 sdk=Path('/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk')
 if sys.platform=='darwin' and sdk.exists():cc+=['-isysroot',str(sdk)]
 matrix=out/'resources.c'
 matrix.write_text('#define main ignored_fixture_main\n#include "'+str(runtime/'src/card-core/tests/test_scene_contract.original.c')+'"\n#undef main\n'+STRESS)
 binary=out/'resources'
 subprocess.run([*cc,'-DCPMAP_FIRMWARE=1367','-DCPMAP_CLUSTER=791','-pthread','-include',str(runtime/'src/card-core/source/profile_card.h'),str(matrix),'-o',str(binary)],check=True)
 stress=subprocess.check_output([str(binary),str(out/'video.log'),str(out/'bridge.log')],text=True).strip()
 # Inject ENOSPC only into reader-owned output operations, never a disk fill.
 shim=out/'faults.c';shim.write_text(FAULTS);obj=out/'reader.o';reader=out/'reader'
 subprocess.run([*cc,'-Dwrite=resource_write','-Dfopen=resource_fopen','-Drename=resource_rename','-c',str(RG/'release/reader.c'),'-o',str(obj)],check=True)
 subprocess.run([*cc,str(obj),str(shim),'-o',str(reader)],check=True)
 sys.path.insert(0,str(RG));spec=importlib.util.spec_from_file_location('output_failure_fixture',RG/'test-observer.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
 source=out/'source';source.write_bytes(fixtures.guiding());fault_results={}
 for fault in ('mailbox_write','status_write','mailbox_rename'):
  ram=out/fault;r=subprocess.run([str(reader),'serve',str(source),str(ram)],env=dict(os.environ,RGI_OUTPUT_FAULT=fault),capture_output=True,text=True,timeout=5)
  assert r.returncode==1,(fault,r.stdout,r.stderr)
  mailbox=(ram/'latest.bin').read_bytes();header=struct.unpack('<4s7I',mailbox)
  assert len(mailbox)==32 and header[4:6]==(5,4),header
  status=(ram/'status.txt').read_text().strip();assert 'status=ended' in status and 'reason=4' in status,status
  fault_results[fault]=status
 # Compare the real exported terminal record with the reproduced terminal.
 capture=a.logs/'ramdisk/carplay-route-guidance/latest.bin';captured=capture.read_bytes()
 h=struct.unpack('<4s7I',captured);assert h[:3]==(b'RGM1',1,32) and h[4:6]==(5,4),h
 jdk=a.java_home/'bin';jar=a.package/'sd-card/Custom/carplay_mu1367/CarPlayMU1367Guidance.jar'
 subprocess.run([str(jdk/'javac'),'-cp',str(jar),'-d',str(out),str(RG/'release/TestMailbox.java')],check=True)
 cp=str(out)+os.pathsep+str(jar.resolve());java={}
 for name,path in [('captured',capture),('reproduced',out/'mailbox_write/latest.bin')]:
  r=subprocess.run([str(jdk/'java'),'-Xverify:all','-cp',cp,'com.cpmap.rgi.TestMailbox',str(path)],input='1000\n2000\n',capture_output=True,text=True,check=True)
  lines=r.stdout.splitlines();assert len(lines)==2 and lines[0].startswith('0,') and lines[1]=='same',lines;java[name]=lines
 binaries={n:sha(packaged/n) for n in ('core.so','altscreen-most-bridge','carplay-cluster-supervisor')}
 result={'passed':True,'test_sha256':sha(Path(__file__)),'bundle_sha256':json.loads((a.package/'manifest.json').read_text())['archive_sha256'],
  'resource_stress':stress,'enospc_faults':fault_results,'java_terminal_record':java,
  'reader_source_sha256':sha(RG/'release/reader.c'),'resource_header_sha256':sha(resource_header),
  'core_includes_shipped_logging':True,'runtime_binary_sha256':binaries,'input_log_sha256':{str(f.relative_to(a.logs)):sha(f) for f in sorted(a.logs.rglob('*')) if f.is_file()},
  'elapsed_40_minute_vehicle_run':False,'on_unit_validated':False}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
