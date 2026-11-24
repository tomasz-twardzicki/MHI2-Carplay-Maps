#!/usr/bin/env python3
"""Run rebuilt reader and real worker recovery on QNX with MU1367 factory libc/pipe."""
import argparse,hashlib,json,shutil,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','setup','reader-setup','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 build=json.loads((a.build/'manifest.json').read_text());binary=a.build/'rgi-observer'
 assert sha(binary)==build['sha256']
 setup=a.setup.resolve();reader_setup=a.reader_setup.resolve()
 for n in ('startup-virt','libstartup.a','devc-serdebug','u-boot.bin','libc.so.3','pipe','snapshot.bin'):shutil.copy2(reader_setup/n,out/n)
 assert sha(out/'libc.so.3')==build['factory_libc_sha256']
 assert sha(out/'pipe')==sha(setup/'pipe')
 shutil.copy2(binary,out/'rgi-observer')
 flags=build['flags'];docker=['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-i','-v',str(out)+':/w','-w','/w']
 src=HERE.parent/'src/reader/reader.c'
 for source,name,extra in [(src,'fault-reader.o',['-Dread=fault_read','-Dwrite=fault_write','-Dwaitpid=fault_waitpid','-Drename=fault_rename','-Dfopen=fault_fopen']),(HERE/'reader-faults.c','faults.o',[]),(REPO/'MU1427/route-guidance/release/qnx-smoke.c','base-smoke.o',['-Dmain=baseline_main']),(HERE/'reader-qnx.c','smoke.o',[])]:
  subprocess.run(['clang',*flags,*extra,'-c',str(source),'-o',str(out/name)],check=True)
 lib='/opt/qnx650/target/qnx6/armle-v7/lib'
 for objs,target in [(['fault-reader.o','faults.o'],'fault-reader'),(['smoke.o','base-smoke.o'],'c4-smoke')]:
  subprocess.run(docker+[build['image_id'],'arm-unknown-nto-qnx6.5.0eabi-ld','-m','armnto','-Qy','--dynamic-linker','/usr/lib/ldqnx.so.2','-L'+lib,lib+'/crt1.o',lib+'/crti.o',lib+'/crtbegin.o',*['/w/'+n for n in objs],'-lc',lib+'/crtend.o',lib+'/crtn.o','-o','/w/'+target],check=True)
 template=(reader_setup/'test.build').read_text();assert '@@C4-START@@' in template
 template=template.replace('\nrgi-observer\n','\n[+raw]\nrgi-observer\n[-raw]\n')+'\n[type=file]\n[data=copy]\n[perms=+r,+x]\n[+raw]\nfault-reader\n'
 (out/'test.build').write_text(template)
 (out/'prepare.sh').write_text('''set -eu
T=/opt/qnx650/target/qnx6/armle-v7
cp "$T/boot/sys/procnto-smp" /w/procnto-smp
export MKIFS_PATH=/w:$T/boot/sys:$T/bin:$T/sbin:$T/lib:$T/lib/dll:$T/usr/lib
mkifs test.build ifs.bin
mkdir fat
mv ifs.bin fat/
''')
 with (out/'prepare.log').open('w') as log:subprocess.run(docker+[build['image_id'],'sh','/w/prepare.sh'],stdout=log,stderr=subprocess.STDOUT,check=True)
 logpath=out/'qemu.log'
 with logpath.open('wb') as log:
  proc=subprocess.Popen(docker+['cpmap-qemu-arm','timeout','75','qemu-system-arm','-M','virt','-m','256','-cpu','cortex-a15','-bios','/w/u-boot.bin','-drive','file=fat:rw:/w/fat,format=raw,media=disk','-nic','none','-display','none','-serial','stdio'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
  def expect(token,offset=0):
   end=time.monotonic()+45
   while time.monotonic()<end and proc.poll() is None:
    pos=logpath.read_bytes().find(token,offset)
    if pos>=0:return pos+len(token)
    time.sleep(.1)
   raise RuntimeError('QNX marker missing: '+token.decode())
  def send(b):proc.stdin.write(b);proc.stdin.flush()
  try:
   at=expect(b'Hit any key to stop autoboot:');send(b'\n');at=expect(b'=> ',at)
   for c in (b'virtio scan\n',b'fatload virtio 0:1 0x40200000 ifs.bin\n'):send(c);at=expect(b'=> ',at)
   send(b'go 0x40200000\n');expect(b'@@C4-END@@',at)
  finally:
   proc.stdin.close();proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
 log=logpath.read_text(errors='replace');assert 'READER_RECOVERY_QNX_PASS' in log,log[-6000:]
 r={'passed':True,'reader_sha256':sha(binary),'factory_libc_sha256':sha(out/'libc.so.3'),'factory_pipe_sha256':sha(out/'pipe'),'native_timeout_and_recovery':True,'new_nonce_verified':True,'first_failure_retained':True,'foreground_and_daemon':True,'qemu_log_sha256':sha(logpath),'test_sha256':sha(Path(__file__)),'on_unit_validated':False}
 (out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
