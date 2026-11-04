#!/usr/bin/env python3
"""Run rebuilt guidance and U-turn factory-path probes on matching firmware ARM/J9."""
import argparse,hashlib,json,shutil,subprocess,time,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','java-home','stock-jar','asm-dir','sysroot','j9-setup','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();w=a.output.resolve();w.mkdir(parents=True,exist_ok=False)
 java=a.java_home/'bin/java';javac=a.java_home/'bin/javac';seed=a.j9_setup.resolve()
 for name in ('startup-virt','libstartup.a','devc-serdebug','u-boot.bin','libc.so.3','pipe','c4-smoke','libm.so.2','libsocket.so.3'):
  shutil.copy2(seed/name,w/name)
 assert sha(w/'libc.so.3')=='485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc'
 shutil.copytree(seed/'ifs',w/'ifs')
 assert sha(w/'ifs/lsd.jxe')=='09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a'
 shutil.copy2(a.build/'CarPlayMU1367Guidance.jar',w/'observer.jar')
 helpers=w/'helpers';helpers.mkdir();tools=w/'tools';tools.mkdir()
 cp=str(a.build.resolve()/'CarPlayMU1367Guidance.jar')+':'+str(a.stock_jar.resolve())
 sources=[HERE/'java'/n for n in ('TestUturnQnx.java','TestRoadQnx.java','TestArrowQnx.java','TestQuietQnx.java')]
 subprocess.run([str(javac),'-source','7','-target','7','-Xlint:-options','-bootclasspath',str(a.stock_jar),'-cp',cp,'-d',str(helpers),*map(str,sources)],check=True)
 (w/'ProbeClasses.java').write_text('''import java.nio.file.*;import org.objectweb.asm.*;import org.objectweb.asm.tree.*;
public class ProbeClasses implements Opcodes {public static void main(String[] a)throws Exception{Files.walk(Paths.get(a[0])).filter(p->p.toString().endsWith(".class")).forEach(p->{try{ClassNode c=new ClassNode();new ClassReader(Files.readAllBytes(p)).accept(c,ClassReader.SKIP_FRAMES);c.version=V1_2;for(MethodNode m:c.methods)for(AbstractInsnNode n:m.instructions.toArray()){if(n instanceof LdcInsnNode&&((LdcInsnNode)n).cst instanceof Type)throw new IllegalStateException("class literal");if(n instanceof InvokeDynamicInsnNode)throw new IllegalStateException("invokedynamic");if(n instanceof MethodInsnNode&&((MethodInsnNode)n).owner.equals("java/lang/StringBuilder"))throw new IllegalStateException("StringBuilder");}ClassWriter w=new ClassWriter(ClassWriter.COMPUTE_MAXS);c.accept(w);Files.write(p,w.toByteArray());}catch(Exception e){throw new RuntimeException(e);}});}}''')
 asm=':'.join(str((a.asm_dir/n).resolve()) for n in ('asm-9.7.jar','asm-tree-9.7.jar'))
 subprocess.run([str(javac),'-cp',asm,'-d',str(tools),str(w/'ProbeClasses.java')],check=True)
 subprocess.run([str(java),'-cp',str(tools)+':'+asm,'ProbeClasses',str(helpers)],check=True)
 with zipfile.ZipFile(w/'probe.jar','w',zipfile.ZIP_DEFLATED) as z:
  for f in sorted(helpers.rglob('*.class')):z.write(f,f.relative_to(helpers))
 (w/'probe.c').write_text('''#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
int main(void){int i,status;char *args[]={"/ifs/jre/bin/j9","-jcl:foun11","-noverify","-Xmx64m","-Xbootclasspath/a:/ifs/lsd.jxe","-Xbootclasspath/p:/proc/boot/probe.jar:/proc/boot/observer.jar","-cp","/proc/boot/probe.jar","com.cpmap.rgi.TestUturnQnx",0};setenv("LD_LIBRARY_PATH","/ifs/jre/bin:/proc/boot",1);for(i=0;i<2;i++){pid_t p;args[2]=i?"-verify":"-noverify";p=fork();if(!p){execv(args[0],args);_exit(127);}if(p<0)return 2;waitpid(p,&status,0);printf("UTURN_J9_CHILD_STATUS=%d\\n",status);fflush(stdout);if(status)return 1;}puts("UTURN_J9_BOTH_MODES_PASS");return 0;}''')
 root=a.sysroot.resolve()/'sdp/target/qnx6'
 flags=['--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','--sysroot='+str(root),'-isystem',str(root/'usr/include'),'-march=armv7-a','-mfloat-abi=softfp','-mno-unaligned-access','-fno-short-enums','-fno-stack-protector','-fno-builtin','-O2']
 subprocess.run(['clang',*flags,'-c',str(w/'probe.c'),'-o',str(w/'probe.o')],check=True)
 template=(seed/'test.build').read_text();template=template[:template.index('[type=file]')]+'''[type=file]
[data=copy]
[perms=+r,+x]
libc.so.3
procnto-smp
devc-serdebug
pipe
c4-smoke
j9-probe
probe.jar
observer.jar
libsocket.so.3
devb-ram
mkqnx6fs
mount
libcam.so.2
libm.so.2
io-blk.so
fs-qnx6.so
cam-disk.so
libblkcache.so.2
'''
 template+='\n'.join(line for line in (seed/'test.build').read_text().splitlines() if line.startswith('/ifs/'))+'\n'
 (w/'test.build').write_text(template)
 (w/'prepare.sh').write_text('''set -eu
T=/opt/qnx650/target/qnx6/armle-v7
cp "$T/boot/sys/procnto-smp" /w/procnto-smp
arm-unknown-nto-qnx6.5.0eabi-ld -m armnto -Qy --dynamic-linker /usr/lib/ldqnx.so.2 -L$T/lib $T/lib/crt1.o $T/lib/crti.o $T/lib/crtbegin.o /w/probe.o -lc $T/lib/crtend.o $T/lib/crtn.o -o /w/j9-probe
export MKIFS_PATH=/w:$T/boot/sys:$T/bin:$T/sbin:$T/lib:$T/lib/dll:$T/usr/lib
mkifs test.build ifs.bin
mkdir fat
mv ifs.bin fat/
''')
 docker=['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-i','-v',str(w)+':/w','-w','/w']
 with (w/'prepare.log').open('w') as log:subprocess.run(docker+['cpmap-qnx65-sdp','sh','/w/prepare.sh'],stdout=log,stderr=subprocess.STDOUT,check=True)
 with (w/'qemu.log').open('wb') as log:
  proc=subprocess.Popen(docker+['cpmap-qemu-arm','timeout','90','qemu-system-arm','-M','virt','-m','256','-cpu','cortex-a15','-bios','/w/u-boot.bin','-drive','file=fat:rw:/w/fat,format=raw,media=disk','-nic','none','-display','none','-serial','stdio'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
  def expect(token,offset=0,seconds=20):
   until=time.monotonic()+seconds
   while time.monotonic()<until and proc.poll() is None:
    text=(w/'qemu.log').read_bytes();at=text.find(token,offset)
    if at>=0:return at+len(token)
    time.sleep(.1)
   raise RuntimeError('QNX/J9 output missing: '+repr(token))
  def send(text):proc.stdin.write(text);proc.stdin.flush()
  try:
   off=expect(b'Hit any key to stop autoboot:');send(b'\n');off=expect(b'=> ',off)
   for cmd in (b'virtio scan\n',b'fatload virtio 0:1 0x40200000 ifs.bin\n'):
    send(cmd);off=expect(b'=> ',off)
   send(b'go 0x40200000\n');expect(b'UTURN_J9_BOTH_MODES_PASS',off,60)
  finally:
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
 log=(w/'qemu.log').read_text(errors='replace');assert log.count('UTURN_FACTORY_J9_PASS cases=5')==2 and log.count('UTURN_J9_CHILD_STATUS=0')==2 and log.count('QUIET_FACTORY_J9_PASS')==2
 r={'passed':True,'guidance_sha256':sha(w/'observer.jar'),'factory_arm_j9_verified':True,'modes':['noverify','verify'],'uturn_cases_per_mode':5,'actual_factory_builder':True,'factory_serializer':True,'road_and_arrow_regressions':True,'qemu_log_sha256':sha(w/'qemu.log'),'on_unit_validated':False,'test_sha256':sha(Path(__file__))}
 (w/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
