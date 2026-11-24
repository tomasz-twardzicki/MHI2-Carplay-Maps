#!/usr/bin/env python3
"""Load/verify the exact candidate input classes on the matching factory ARM J9."""
import argparse,hashlib,json,shutil,struct,subprocess,time,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
for n in ('components','tools','setup','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
setup=a.setup.resolve();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(setup/'ifs/lsd.jxe')=='09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a'
shutil.copytree(setup,out,dirs_exist_ok=True,ignore=shutil.ignore_patterns('fat','qemu.log','result.json','sdk-include','classes','src','*.o','ifs.bin'))
classes=out/'classes';classes.mkdir();java=a.tools/'zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/bin';stock=a.tools/'stock.jar'
cp=':'.join(str(p) for p in (a.components/'CarPlayWireless-CP-55915411.jar',stock))
subprocess.run([str(java/'javac'),'-source','7','-target','7','-Xlint:-options','-bootclasspath',str(stock),'-cp',cp,'-d',str(classes),str(HERE/'TestRoutedLoad.java')],check=True)
entries={}
for dep in (a.components/'CarPlayWireless-CP-55915411.jar',a.components/'CarPlayWireless-Touch-55915411.jar',a.components/'input/MU1367WirelessPhone.jar'):
 with zipfile.ZipFile(dep) as z:
  for n in z.namelist():
   if n.endswith('.class'):assert n not in entries;entries[n]=z.read(n)
for f in classes.rglob('*.class'):
 b=bytearray(f.read_bytes());b[6:8]=struct.pack('>H',46);entries[f.relative_to(classes).as_posix()]=b
with zipfile.ZipFile(out/'observer.jar','w') as z:
 for n,b in entries.items():z.writestr(n,b)
with zipfile.ZipFile(out/'negative.jar','w') as z:
 for n,b in entries.items():
  if n.endswith('/RoutedTouch.class'):b=bytearray(b);b[6:8]=struct.pack('>H',49)
  z.writestr(n,b)
shutil.copy2(out/'observer.jar',out/'probe.jar')
(out/'probe.c').write_text(r'''#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
static void launch(char **a){int s;pid_t p=fork();if(!p){execv(a[0],a);_exit(127);}if(p<0)exit(1);waitpid(p,&s,0);printf("CHILD_STATUS=%d\n",s);fflush(stdout);}
int main(void){char *a[]={"/ifs/jre/bin/j9","-jcl:foun11","-verify","-Xmx64m","-Xbootclasspath/a:/ifs/lsd.jxe","-Xbootclasspath/p:/proc/boot/observer.jar","-cp","/proc/boot/probe.jar","TestRoutedLoad",0};
setenv("LD_LIBRARY_PATH","/ifs/jre/bin:/mnt/app/root/lib-target:/eso/lib:/mnt/app/usr/lib:/mnt/app/armle/lib:/mnt/app/armle/lib/dll:/mnt/app/armle/usr/lib",1);
puts("@@INPUT-VERIFY@@");fflush(stdout);launch(a);
puts("@@INPUT-NEGATIVE@@");fflush(stdout);a[5]="-Xbootclasspath/p:/proc/boot/negative.jar";launch(a);
puts("@@INPUT-END@@");fflush(stdout);return 0;}
''')
docker=['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-i','-v',str(out)+':/w','-w','/w']
subprocess.run(docker+['cpmap-qnx65-sdp','sh','-c','cp -R /opt/qnx650/target/qnx6/usr/include /w/sdk-include'],check=True)
subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/clang','--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','--sysroot='+str(out),'-isystem',str(out/'sdk-include'),'-march=armv7-a','-mfloat-abi=softfp','-fno-short-enums','-fno-stack-protector','-fno-builtin','-c',str(out/'probe.c'),'-o',str(out/'probe.o')],check=True)
# Passing setup already maps the exact firmware/JRE and all required libs.
prepare=(out/'prepare.sh').read_text().replace('mkdir fat','mkdir -p fat')
(out/'prepare.sh').write_text(prepare)
with (out/'prepare.log').open('w') as log:subprocess.run(docker+['cpmap-qnx65-sdp','sh','/w/prepare.sh'],stdout=log,stderr=subprocess.STDOUT,check=True)
logpath=out/'qemu.log'
with logpath.open('wb') as log:
 proc=subprocess.Popen(docker+['cpmap-qemu-arm','timeout','120','qemu-system-arm','-M','virt','-m','1024','-cpu','cortex-a15','-bios','/w/u-boot.bin','-drive','file=fat:rw:/w/fat,format=raw,media=disk','-nic','none','-display','none','-serial','stdio'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
 def expect(token,offset=0):
  deadline=time.monotonic()+90
  while time.monotonic()<deadline and proc.poll() is None:
   at=logpath.read_bytes().find(token,offset)
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
log=logpath.read_text(errors='replace');positive=log.split('@@INPUT-VERIFY@@')[1].split('@@INPUT-NEGATIVE@@')[0];negative=log.split('@@INPUT-NEGATIVE@@')[1]
assert 'ROUTED_TOUCH_FACTORY_J9_PASS' in positive and 'CHILD_STATUS=0' in positive
assert 'ROUTED_TOUCH_FACTORY_J9_PASS' not in negative and any(n in negative for n in ('UnsupportedClassVersionError','NoClassDefFoundError','ClassNotFoundException'))
report=dict(passed=True,factory_j9_verified=True,class49_negative_rejected=True,network_boundary='Host UDP packet test is separate; factory check loads/links classes and rejects inactive input.',components={n:sha(a.components/n) for n in ('CarPlayWireless-CP-55915411.jar','CarPlayWireless-Touch-55915411.jar')},log_sha256=sha(logpath),on_unit_validated=False)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
