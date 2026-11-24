#!/usr/bin/env python3
"""Execute GPS core and actual patched OEM dispatchers on factory ARM/J9."""
import argparse,hashlib,json,re,shutil,struct,subprocess,time,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
for n in ('setup','host-build','tools','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();setup=a.setup.resolve();host=a.host_build.resolve()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(setup/'ifs/lsd.jxe')=='09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a'
assert sha(setup/'libc.so.3')=='485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc'
shutil.copytree(setup,out,ignore=shutil.ignore_patterns('fat','qemu.log','result.json','sdk-include','classes','src','*.o'))
for name in ('probe.jar','observer.jar','negative.jar'):
 with zipfile.ZipFile(out/name,'w') as z:
  # Same boot loader is necessary for package-private observation assertions.
  entries={}
  with zipfile.ZipFile(host/'gps-prototype.jar') as original:entries.update({n:original.read(n) for n in original.namelist()})
  for f in (host/'test').rglob('*.class'):entries[str(f.relative_to(host/'test'))]=f.read_bytes()
  if name=='negative.jar':
   n='com/cpmap/rgi/GpsProbe.class';b=bytearray(entries[n]);struct.pack_into('>H',b,6,49);entries[n]=b
  for n,b in sorted(entries.items()):z.writestr(n,b)
launcher=r'''#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
static void launch(char **a){int s;pid_t p=fork();if(!p){execv(a[0],a);_exit(127);}if(p<0)exit(1);waitpid(p,&s,0);printf("CHILD_STATUS=%d\n",s);fflush(stdout);}
int main(void){char *a[]={"/ifs/jre/bin/j9","-jcl:foun11","-noverify","-Xmx64m","-Xbootclasspath/a:/ifs/lsd.jxe","-Xbootclasspath/p:/proc/boot/observer.jar","-cp","/proc/boot/probe.jar","com.cpmap.rgi.TestGpsProbe",0};
 char *native[]={"/proc/boot/location-native",0};char *source[]={"/proc/boot/gps-source-native",0};
 setenv("LD_LIBRARY_PATH","/ifs/jre/bin:/proc/boot",1);
 puts("@@GPS-NATIVE@@");fflush(stdout);launch(native);launch(source);
 puts("@@GPS-NOVERIFY@@");fflush(stdout);launch(a);
 puts("@@GPS-VERIFY@@");fflush(stdout);a[2]="-verify";launch(a);
 puts("@@GPS-NEGATIVE@@");fflush(stdout);a[5]="-Xbootclasspath/p:/proc/boot/negative.jar";launch(a);
 puts("@@GPS-END@@");fflush(stdout);return 0;}
'''
(out/'probe.c').write_text(launcher)
qnx=a.tools.resolve()/'qnx/sdp/target/qnx6'
flags=['--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','--sysroot='+str(qnx),'-isystem',str(qnx/'usr/include'),'-march=armv7-a','-mfloat-abi=softfp','-mfpu=vfpv3-d16','-mno-unaligned-access','-fno-short-enums','-fno-stack-protector','-fno-builtin','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation']
clang='/Library/Developer/CommandLineTools/usr/bin/clang'
for source,name in [(out/'probe.c','probe'),(HERE/'location-native.c','location-native'),(HERE/'gps-source-native.c','gps-source-native')]:
 subprocess.run([clang,*flags,'-I',str(HERE.parent/'src/native'),'-c',str(source),'-o',str(out/(name+'.o'))],check=True)
template=(out/'test.build').read_text();template+='\n[type=file]\n[perms=+r,+x]\nlocation-native\ngps-source-native\n[type=link] /mnt/app=/ramdisk/app\n';(out/'test.build').write_text(template)
(out/'prepare.sh').write_text('''set -eu
T=/opt/qnx650/target/qnx6/armle-v7
for name in probe location-native gps-source-native;do
 result=$name
 if [ "$name" = probe ];then result=j9-probe;fi
 arm-unknown-nto-qnx6.5.0eabi-ld -m armnto -Qy --dynamic-linker /usr/lib/ldqnx.so.2 -L$T/lib $T/lib/crt1.o $T/lib/crti.o $T/lib/crtbegin.o /w/$name.o -lc $T/lib/crtend.o $T/lib/crtn.o -o /w/$result
done
export MKIFS_PATH=/w:$T/boot/sys:$T/bin:$T/sbin:$T/lib:$T/lib/dll:$T/usr/lib
mkifs test.build ifs.bin
mkdir fat
mv ifs.bin fat/
''')
docker=['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-i','-v',str(out)+':/w','-w','/w']
with (out/'prepare.log').open('w') as log:subprocess.run(docker+['cpmap-qnx65-sdp','sh','/w/prepare.sh'],stdout=log,stderr=subprocess.STDOUT,check=True)
with (out/'qemu.log').open('wb') as log:
 proc=subprocess.Popen(docker+['cpmap-qemu-arm','timeout','110','qemu-system-arm','-M','virt','-m','1024','-cpu','cortex-a15','-bios','/w/u-boot.bin','-drive','file=fat:rw:/w/fat,format=raw,media=disk','-nic','none','-display','none','-serial','stdio'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
 def expect(token,offset=0):
  deadline=time.monotonic()+60
  while time.monotonic()<deadline and proc.poll() is None:
   at=(out/'qemu.log').read_bytes().find(token,offset)
   if at>=0:return at+len(token)
   time.sleep(.1)
  raise RuntimeError('Missing QNX marker '+repr(token))
 def send(b):proc.stdin.write(b);proc.stdin.flush()
 try:
  at=expect(b'Hit any key to stop autoboot:');send(b'\n');at=expect(b'=> ',at)
  for c in (b'virtio scan\n',b'fatload virtio 0:1 0x40200000 ifs.bin\n'):send(c);at=expect(b'=> ',at)
  send(b'go 0x40200000\n');expect(b'@@N0-FINISHED@@',at)
 finally:
  proc.stdin.close();proc.terminate()
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
text=(out/'qemu.log').read_text(errors='replace');sections=dict(re.findall(r'@@GPS-(NATIVE|NOVERIFY|VERIFY|NEGATIVE)@@(.*?)(?=@@GPS-|\Z)',text,re.S))
assert 'LOCATION_CORE_PASS checks=' in sections['NATIVE'] and 'CHILD_STATUS=0' in sections['NATIVE']
assert 'GPS_SOURCE_PASS production_capture=1 unicode_boundary_stubbed=1' in sections['NATIVE'] and sections['NATIVE'].count('CHILD_STATUS=0')==2
for mode in ('NOVERIFY','VERIFY'):assert 'GPS_PROBE_PASS actual_factory_dispatchers=1' in sections[mode] and 'GPS_PROBE_RAM_PASS' in sections[mode] and 'CHILD_STATUS=0' in sections[mode],sections[mode]
assert 'GPS_PROBE_PASS' not in sections['NEGATIVE'] and any(s in sections['NEGATIVE'] for s in ('UnsupportedClassVersionError','NoClassDefFoundError','ClassNotFoundException'))
r=dict(passed=True,native_arm=True,factory_j9=True,verified_and_noverify=True,class49_negative_rejected=True,source_connected=False,receiver_send_hook=False,on_unit_validated=False,prototype_jar_sha256=sha(host/'gps-prototype.jar'),qemu_log_sha256=sha(out/'qemu.log'))
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
