#!/usr/bin/env python3
"""Build the bounded artwork worker and verify imports against the factory libc."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'port'))
from firmware import image_files,stage1
from build_support import load
p=argparse.ArgumentParser(description=__doc__)
for n in ('firmware','toolchain','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
libc=image_files(stage1(a.firmware/'MMX2/mifs-stage1/50/default/mifs-stage1.img'))['proc/boot/libc.so.3']
assert hashlib.sha256(libc).hexdigest()=='485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc'
root=a.toolchain.resolve()/'sdp/target/qnx6'
flags=['--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','--sysroot='+str(root),'-isystem',str(root/'usr/include'),'-march=armv7-a','-mfloat-abi=softfp','-mno-unaligned-access','-fno-short-enums','-fno-builtin','-fno-stack-protector','-std=c99','-O2','-Wall','-Wextra','-Werror']
# Preserve the already validated assertion filename, independent of checkout location.
flags += ['-fmacro-prefix-map='+str(HERE.parent/'src/artwork-native')+'=/Users/tomasz/Documents/github/personal/MHI2-Carplay-Maps-rg/MU1367/artwork/../../MU1427/now-playing/n3']
subprocess.run(['clang',*flags,'-c',str(HERE.parent/'src/artwork-native/fetch.c'),'-o',str(out/'artwork-fetch.o')],check=True)
lib='/opt/qnx650/target/qnx6/armle-v7/lib'
subprocess.run(['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-v',str(out)+':/w','cpmap-qnx65-sdp','arm-unknown-nto-qnx6.5.0eabi-ld','-m','armnto','-Qy','--dynamic-linker','/usr/lib/ldqnx.so.2','-L'+lib,lib+'/crt1.o',lib+'/crti.o',lib+'/crtbegin.o','/w/artwork-fetch.o','-lc',lib+'/crtend.o',lib+'/crtn.o','-o','/w/artwork-fetch'],check=True)
f=out/'artwork-fetch';f.chmod(0o755)
verify=load('native_imports',HERE.parents[2]/'MU1427/route-guidance/build-observer.py').verify
imports=verify(f.read_bytes(),libc)
h=hashlib.sha256(f.read_bytes()).hexdigest()
assert h=='acbf7f676e3c2690b1ee8c5185c3bbb378962b3a8f9d4dbf56d778cd4813f11e'
(out/'manifest.json').write_text(json.dumps({'passed':True,'sha256':h,'imports_verified':imports},indent=2)+'\n')
print('Artwork fetcher rebuild matches validated payload.')
