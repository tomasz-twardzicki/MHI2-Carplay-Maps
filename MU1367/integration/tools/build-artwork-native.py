#!/usr/bin/env python3
"""Build R3 lossless PNG fetcher using the matching firmware's zlib and libc."""
import argparse,hashlib,io,json,subprocess,sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(HERE.parent/'port'))
from firmware import image_files,stage1
IMAGE_ID='sha256:93b565ff63ba51c470c1a1e70a6d16607d36df502dfb20ae63a69911f8529bea'
TOOLCHAIN_COMMIT='baa45224f18ae6b13c2e9c77c6663bb8181eb6a1'
# The on-unit LD_LIBRARY_PATH seen in diagnostics omits /proc/boot, where the factory libz lives.
RPATH='/proc/boot'
def sha(b):return hashlib.sha256(b).hexdigest()
def exports(b):
 e=ELFFile(io.BytesIO(b));d=next(s for s in e.iter_segments() if s['p_type']=='PT_DYNAMIC')
 return {s.name for s in d.iter_symbols() if s['st_shndx']!='SHN_UNDEF'}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('firmware','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 docker=['docker','--context','colima-cpmap-rgi']
 image=subprocess.check_output(docker+['image','inspect','cpmap-qnx65-sdp','--format','{{.Id}}'],text=True).strip()
 assert image==IMAGE_ID,'Pinned QNX image required'
 subprocess.run(docker+['run','--rm','--pull=never','--network=none','-v',str(out)+':/w',image,'sh','-c','cp -R /opt/qnx650/target/qnx6/usr/include /w/sdk-include'],check=True)
 factory={}
 for variant in ('50','70'):
  files=image_files(stage1(a.firmware/('MMX2/mifs-stage1/'+variant+'/default/mifs-stage1.img')))
  for name in ('libc.so.3','libz.so.2'):
   b=files['proc/boot/'+name]
   if name in factory:assert factory[name]==b
   factory[name]=b
 for n,b in factory.items():(out/n).write_bytes(b)
 assert sha(factory['libc.so.3'])=='485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc'
 root=out;src=HERE/'src/artwork-test/native/fetch.c'
 flags=['--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','-DCPMAP_PNG_COMPRESSED','--sysroot='+str(root),'-isystem',str(out/'sdk-include'),'-march=armv7-a','-mfloat-abi=softfp','-mno-unaligned-access','-fno-short-enums','-fno-builtin','-fno-stack-protector','-std=c99','-O2','-Wall','-Wextra','-Werror']
 subprocess.run(['clang',*flags,'-c',str(src),'-o',str(out/'fetch.o')],check=True)
 lib='/opt/qnx650/target/qnx6/armle-v7/lib'
 subprocess.run(['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-v',str(out)+':/w','cpmap-qnx65-sdp','arm-unknown-nto-qnx6.5.0eabi-ld','-m','armnto','-Qy','--dynamic-linker','/usr/lib/ldqnx.so.2','-rpath',RPATH,'-L'+lib,'-L/opt/qnx650/target/qnx6/armle-v7/usr/lib',lib+'/crt1.o',lib+'/crti.o',lib+'/crtbegin.o','/w/fetch.o','-lz','-lc',lib+'/crtend.o',lib+'/crtn.o','-o','/w/artwork-fetch'],check=True)
 binary=(out/'artwork-fetch').read_bytes();e=ELFFile(io.BytesIO(binary));assert e.elfclass==32 and e.little_endian and e['e_machine']=='EM_ARM' and e['e_type']=='ET_EXEC' and not e['e_flags']&0x400
 assert [s.get_interp_name() for s in e.iter_segments() if s['p_type']=='PT_INTERP']==['/usr/lib/ldqnx.so.2']
 dynamic=list(e.get_section_by_name('.dynamic').iter_tags());assert set(t.needed for t in dynamic if t.entry.d_tag=='DT_NEEDED')=={'libz.so.2','libc.so.3'}
 assert [t.rpath for t in dynamic if t.entry.d_tag=='DT_RPATH']==[RPATH]
 assert not any(t.entry.d_tag in ('DT_RUNPATH','DT_TEXTREL') for t in dynamic)
 imports={s.name for s in e.get_section_by_name('.dynsym').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF' and s['st_info']['bind']!='STB_WEAK'}
 assert not imports-exports(factory['libc.so.3'])-exports(factory['libz.so.2'])
 (out/'artwork-fetch').chmod(0o755)
 sources=[src,HERE/'src/artwork-test/native/image.c',HERE/'src/artwork-test/native/vendor/stb_image.h',Path(__file__)]
 result={'passed':True,'sha256':sha(binary),'factory_libraries':{n:sha(b) for n,b in factory.items()},'imports':sorted(imports),'toolchain_commit':TOOLCHAIN_COMMIT,'sources':{str(f.relative_to(HERE)):sha(f.read_bytes()) for f in sources},'on_unit_validated':False}
 (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
