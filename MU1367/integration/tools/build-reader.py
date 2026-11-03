#!/usr/bin/env python3
"""Build a separate reader test with pinned QNX image and MU1367 factory libc."""
import argparse,hashlib,importlib.util,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent.parent
REPO=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('setup','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 spec=importlib.util.spec_from_file_location('reader_elf',REPO/'MU1427/route-guidance/build-observer.py')
 base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
 libc=a.setup/'libc.so.3';assert sha(libc)=='485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc'
 docker=['docker','--context','colima-cpmap-rgi']
 image=subprocess.check_output(docker+['image','inspect','cpmap-qnx65-sdp','--format','{{.Id}}'],text=True).strip()
 pin=json.loads((REPO/'MU1367/port/build-native-final/manifest.json').read_text())
 assert image==pin['image_id'],'Pinned QNX image required'
 subprocess.run(docker+['run','--rm','--pull=never','--network=none','-v',str(out)+':/w',image,'sh','-c','cp -R /opt/qnx650/target/qnx6/usr/include /w/sdk-include'],check=True)
 flags=['--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','--sysroot='+str(out),'-isystem',str(out/'sdk-include'),'-march=armv7-a','-mfloat-abi=softfp','-mno-unaligned-access','-fno-short-enums','-fno-builtin','-fno-stack-protector','-std=c99','-O2','-Wall','-Wextra','-Werror']
 src=HERE/'src/reader/reader.c'
 subprocess.run(['clang',*flags,'-c',str(src),'-o',str(out/'reader.o')],check=True)
 lib='/opt/qnx650/target/qnx6/armle-v7/lib'
 subprocess.run(docker+['run','--rm','--pull=never','--network=none','-v',str(out)+':/w',image,'arm-unknown-nto-qnx6.5.0eabi-ld','-m','armnto','-Qy','--dynamic-linker','/usr/lib/ldqnx.so.2','-L'+lib,lib+'/crt1.o',lib+'/crti.o',lib+'/crtbegin.o','/w/reader.o','-lc',lib+'/crtend.o',lib+'/crtn.o','-o','/w/rgi-observer'],check=True)
 binary=out/'rgi-observer';binary.chmod(0o755)
 r={'passed':True,'test_build':True,'sha256':sha(binary),'source_sha256':sha(src),'factory_libc_sha256':sha(libc),'image_id':image,'toolchain_commit':pin['toolchain_commit'],'imports_verified':base.verify(binary.read_bytes(),libc.read_bytes()),'flags':flags,'on_unit_validated':False}
 (out/'manifest.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
