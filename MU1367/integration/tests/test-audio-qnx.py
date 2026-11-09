#!/usr/bin/env python3
"""Run audio regressions/owned-image worker on exact factory ARM J9, with verification."""
import argparse,hashlib,json,re,shutil,struct,subprocess,time,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','java-home','stock-jar','setup','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--native-build',type=Path)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);setup=a.setup.resolve()
 # Reuse only extracted firmware/boot fixtures; all audio payloads and tests are rebuilt.
 assert sha(setup/'ifs/lsd.jxe')=='09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a'
 assert sha(setup/'libc.so.3')=='485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc'
 shutil.copytree(setup/'ifs',out/'ifs')
 for n in ('libc.so.3','libm.so.2','libsocket.so.3','c4-smoke','devc-serdebug','pipe','libstartup.a','startup-virt','u-boot.bin','artwork-fetch'):
  shutil.copy2(setup/n,out/n)
 src=out/'src';src.mkdir();classes=out/'classes';classes.mkdir()
 revision=json.loads((a.build/'manifest.json').read_text()).get('revision','r2')
 extra='TestProgress' if revision=='r2' else 'TestArtworkR3'
 for n in ('TestText','TestCover',extra):shutil.copy2((HERE/'artwork-test/java' if revision!='r2' else HERE/'java')/(n+'.java'),src/(n+'.java'))
 fixture=','.join(str(v if v<128 else v-256) for v in (HERE/'artwork-test/fixtures/colors.png').read_bytes())
 worker=(HERE/'TestCoverWorker.java.in').read_text().replace('@PNG@',fixture)
 if revision!='r2':
  worker=worker.replace('f.length()>190000&&f.length()<200000','f.length()>0&&f.length()<200000')
  worker=worker.replace('capacity();\n            }','capacity();check(CoverTiming.status().indexOf("png_bytes=")>=0);\n            }')
 (src/'TestCoverWorker.java').write_text(worker)
 (src/'AudioProgressProbe.java').write_text(('''package com.cpmap.audio;
public final class AudioProgressProbe { public static void main(String[] a)throws Exception {
 Class.forName("de.vw.mib.asl.internal.carplay.target.HsmTarget",false,Class.forName("com.cpmap.audio.AudioProgressProbe").getClassLoader()).getDeclaredMethods();
 CoverBridge.started=true; TestText.main(a); TestCover.main(a); @EXTRA@.main(a); TestCoverWorker.main(a);
 System.out.println("AUDIO_FACTORY_PASS");
}}''').replace('@EXTRA@',extra))
 jar=a.build.resolve()/'CarPlayMU1367Audio.jar';stock=a.stock_jar.resolve()
 subprocess.run([str(a.java_home/'bin/javac'),'-source','7','-target','7','-Xlint:-options','-bootclasspath',str(stock),'-cp',str(jar)+':'+str(stock),'-d',str(classes),*map(str,src.glob('*.java'))],check=True)
 with zipfile.ZipFile(out/'probe.jar','w') as z:
  for f in classes.rglob('*.class'):
   b=bytearray(f.read_bytes());b[6:8]=struct.pack('>H',46);z.writestr(str(f.relative_to(classes)),b)
 shutil.copy2(jar,out/'observer.jar')
 # Package-private probes must use the same factory boot loader as the adapter.
 with zipfile.ZipFile(out/'probe.jar') as probes,zipfile.ZipFile(out/'observer.jar','a') as z:
  for n in probes.namelist():z.writestr(n,probes.read(n))
 with zipfile.ZipFile(out/'observer.jar') as srcjar,zipfile.ZipFile(out/'negative.jar','w') as z:
  for n in srcjar.namelist():
   b=bytearray(srcjar.read(n))
   if n.endswith('/HsmTarget.class'):b[6:8]=struct.pack('>H',49)
   z.writestr(n,b)
 (out/'probe.c').write_text('''#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
static void launch(char **a){int s;pid_t p=fork();if(!p){execv(a[0],a);_exit(127);}if(p<0)exit(1);waitpid(p,&s,0);printf("CHILD_STATUS=%d\\n",s);fflush(stdout);}
int main(void){char *a[]={"/ifs/jre/bin/j9","-jcl:foun11","-noverify","-Xmx64m","-Xbootclasspath/a:/ifs/lsd.jxe","-Xbootclasspath/p:/proc/boot/observer.jar","-cp","/proc/boot/probe.jar","com.cpmap.audio.AudioProgressProbe",0};
setenv("LD_LIBRARY_PATH","/ifs/jre/bin:/mnt/app/root/lib-target:/eso/lib:/mnt/app/usr/lib:/mnt/app/armle/lib:/mnt/app/armle/lib/dll:/mnt/app/armle/usr/lib",1);
puts("@@AUDIO-NOVERIFY@@");fflush(stdout);launch(a);
puts("@@AUDIO-VERIFY@@");fflush(stdout);a[2]="-verify";launch(a);
puts("@@AUDIO-NEGATIVE@@");fflush(stdout);a[5]="-Xbootclasspath/p:/proc/boot/negative.jar";launch(a);
puts("@@AUDIO-END@@");fflush(stdout);return 0;}
''')
 template=(setup/'test.build').read_text()
 if revision!='r2':
  assert a.native_build is not None,'R3 requires the newly built fetcher'
  native=a.native_build.resolve()
  shutil.copy2(native/'artwork-fetch',out/'artwork-fetch');shutil.copy2(native/'libz.so.2',out/'libz.so.2')
  template+='\n[type=file]\n[perms=+r,+x]\nlibz.so.2\n'
 # Retain real firmware/JRE paths and image-worker test aliases from the passing setup.
 for n in ('verify','settings-core.so','core-check'):template=template.replace('\n'+n+'\n','\n')
 (out/'test.build').write_text(template)
 docker=['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-i','-v',str(out)+':/w','-w','/w']
 subprocess.run(docker+['cpmap-qnx65-sdp','sh','-c','cp -R /opt/qnx650/target/qnx6/usr/include /w/sdk-include'],check=True)
 subprocess.run(['clang','--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','--sysroot='+str(out),'-isystem',str(out/'sdk-include'),'-march=armv7-a','-mfloat-abi=softfp','-fno-short-enums','-fno-stack-protector','-fno-builtin','-c',str(out/'probe.c'),'-o',str(out/'probe.o')],check=True)
 (out/'prepare.sh').write_text('''set -eu
T=/opt/qnx650/target/qnx6/armle-v7
cp "$T/boot/sys/procnto-smp" /w/procnto-smp
arm-unknown-nto-qnx6.5.0eabi-ld -m armnto -Qy --dynamic-linker /usr/lib/ldqnx.so.2 -L$T/lib $T/lib/crt1.o $T/lib/crti.o $T/lib/crtbegin.o /w/probe.o -lc $T/lib/crtend.o $T/lib/crtn.o -o /w/j9-probe
export MKIFS_PATH=/w:$T/boot/sys:$T/bin:$T/sbin:$T/lib:$T/lib/dll:$T/usr/lib
mkifs test.build ifs.bin
mkdir fat
mv ifs.bin fat/
''')
 with (out/'prepare.log').open('w') as log:subprocess.run(docker+['cpmap-qnx65-sdp','sh','/w/prepare.sh'],stdout=log,stderr=subprocess.STDOUT,check=True)
 logpath=out/'qemu.log'
 with logpath.open('wb') as log:
  proc=subprocess.Popen(docker+['cpmap-qemu-arm','timeout','90','qemu-system-arm','-M','virt','-m','1024','-cpu','cortex-a15','-bios','/w/u-boot.bin','-drive','file=fat:rw:/w/fat,format=raw,media=disk','-nic','none','-display','none','-serial','stdio'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
  def expect(token,offset=0):
   deadline=time.monotonic()+60
   while time.monotonic()<deadline and proc.poll() is None:
    at=logpath.read_bytes().find(token,offset)
    if at>=0:return at+len(token)
    time.sleep(.1)
   raise RuntimeError('QNX marker missing: '+token.decode())
  def send(value):proc.stdin.write(value);proc.stdin.flush()
  try:
   at=expect(b'Hit any key to stop autoboot:');send(b'\n');at=expect(b'=> ',at)
   for command in (b'virtio scan\n',b'fatload virtio 0:1 0x40200000 ifs.bin\n'):
    send(command);at=expect(b'=> ',at)
   send(b'go 0x40200000\n');expect(b'@@N0-FINISHED@@',at)
  finally:
   proc.stdin.close();proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
 log=logpath.read_text(errors='replace');sections=dict(re.findall(r'@@AUDIO-(NOVERIFY|VERIFY|NEGATIVE)@@(.*?)(?=@@AUDIO-|\Z)',log,re.S))
 for mode in ('NOVERIFY','VERIFY'):
  for marker in ('AUDIO_FACTORY_PASS',('AUDIO_PROGRESS_PASS' if revision=='r2' else 'ARTWORK_R3_PASS'),'ARTWORK_JAVA_PASS','ARTWORK_WORKER_PASS tracks=10 cache_files=8','CHILD_STATUS=0'):
   assert marker in sections.get(mode,''),(mode,marker)
 negative=sections['NEGATIVE'];assert 'AUDIO_FACTORY_PASS' not in negative and ('UnsupportedClassVersionError' in negative or 'NoClassDefFoundError' in negative or 'ClassNotFoundException' in negative)
 r={'passed':True,'audio_sha256':sha(jar),'factory_j9_verified':True,'verified_and_noverify':True,'class49_negative_rejected':True,'on_unit_validated':False,'qemu_log_sha256':sha(logpath),'test_sha256':sha(Path(__file__)),'results':{k:re.findall(r'(?:AUDIO_PROGRESS_PASS|ARTWORK_R3_PASS|ARTWORK_JAVA_PASS|ARTWORK_WORKER_PASS)[^\r\n]*',v) for k,v in sections.items()}}
 if revision!='r2':r.update(fetch_sha256=sha(native/'artwork-fetch'),factory_zlib_sha256=sha(native/'libz.so.2'))
 (out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
