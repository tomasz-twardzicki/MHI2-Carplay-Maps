#!/usr/bin/env python3
"""Build the media-only 790 observer after exact receiver-interface comparison."""
import argparse,hashlib,io,json,shutil,subprocess,zipfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
NATIVE=HERE.parents[1]/'v162-next/src/native'
p=argparse.ArgumentParser()
for name in ('upstream','tools','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(a.upstream.read_bytes())=='5b31522046f1abf397fc62723dc7a4a1c3a37e90559d3d48409c8e322b1a9cce'
with zipfile.ZipFile(a.upstream) as z:
 base='SD_ROOT/carplay/payload/wireless/profiles/'
 receivers={v:z.read(base+v+'/wcp_receiver') for v in ('AID10.5-17PM','AID12.3')}
assert sha(receivers['AID10.5-17PM'])=='396c73bcd7674483245776d0493552832f7ebbcefed399d7b9dd1182a5336c90'
assert sha(receivers['AID12.3'])=='f195665b0e9fb8a592618e64b7201ddfc536a9b082c6dd35db214b99d5e01de1'
def read(data,va,n):
 for seg in ELFFile(io.BytesIO(data)).iter_segments():
  if seg['p_type']=='PT_LOAD' and seg['p_vaddr']<=va and va+n<=seg['p_vaddr']+seg['p_memsz']:
   offset=va-seg['p_vaddr'];have=max(0,min(n,seg['p_filesz']-offset))
   at=seg['p_offset']+offset
   return data[at:at+have]+bytes(n-have)
 raise ValueError(('unmapped receiver address',hex(va),n))
anchors={}
for name,va,n in [('iap2_dispatch',0xec5ec,1600),('native_file_transfer',0xedd00,2560),
                  ('csm_format',0x1832a,64),('ft_completion_format',0x1e171,64),
                  ('ft_empty_format',0x1eb53,64),('media_subscription_ids',0x3ff26,12),
                  ('file_transfer_session_fields',0x110a14,32),('file_transfer_buffer_fields',0x135e08,16)]:
 before=read(receivers['AID12.3'],va,n);after=read(receivers['AID10.5-17PM'],va,n)
 assert before==after,(name,hex(va))
 anchors[name]=dict(address=hex(va),size=n,sha256=sha(after),byte_identical_to_audited_791=True)
src=out/'src';src.mkdir()
for name in ('media790.c','media790.S','receiver_exec790.c'):shutil.copy2(HERE/name,src/name)
for name in ('wcp_media.c','wcp_media.h','wcp_media_tap.h','wireless_session.h','wcp_sha.h'):shutil.copy2(NATIVE/name,src/name)
qnx=a.tools.resolve()/'qnx/sdp/target/qnx6'
clang='/Library/Developer/CommandLineTools/usr/bin/clang'
flags=['--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__',
 '--sysroot='+str(qnx),'-isystem',str(qnx/'usr/include'),'-march=armv7-a','-mfloat-abi=softfp','-mfpu=vfpv3-d16',
 '-mno-unaligned-access','-fno-short-enums','-fno-builtin','-fno-stack-protector','-std=gnu99','-O2',
 '-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation','-I'+str(src),
 '-ffile-prefix-map='+str(src)+'=source']
docker=['docker','--context','colima-cpmap-rgi'];lib='/opt/qnx650/target/qnx6/armle-v7/lib'
assert subprocess.check_output(docker+['image','inspect','cpmap-qnx65-sdp','--format','{{.Id}}'],text=True).strip()=='sha256:93b565ff63ba51c470c1a1e70a6d16607d36df502dfb20ae63a69911f8529bea'
for name,sources in [('libcpmap-wcp-media790.so',['media790.c','media790.S']),('wireless-receiver-exec',['receiver_exec790.c'])]:
 shared=name.endswith('.so');objects=[]
 for source in sources:
  obj=out/(source+'.o');objects.append('/w/'+obj.name)
  extra=['-fPIC'] if shared else ['-DWCP_MEDIA790_SHA256="'+sha((out/'libcpmap-wcp-media790.so').read_bytes())+'"']
  subprocess.run([clang,*flags,*extra,'-c',str(src/source),'-o',str(obj)],check=True)
 command=['arm-unknown-nto-qnx6.5.0eabi-ld','-m','armnto','-Qy','-L'+lib]
 command+=['-shared'] if shared else ['--dynamic-linker','/usr/lib/ldqnx.so.2',lib+'/crt1.o',lib+'/crti.o',lib+'/crtbegin.o']
 command+=objects+['-lc']
 if not shared:command+=[lib+'/crtend.o',lib+'/crtn.o']
 command+=['-o','/w/'+name]
 subprocess.run(docker+['run','--rm','--pull=never','--network=none','-v',str(out)+':/w','cpmap-qnx65-sdp',*command],check=True)
observer=(out/'libcpmap-wcp-media790.so').read_bytes()
e=ELFFile(io.BytesIO(observer));dyn=e.get_section_by_name('.dynsym')
exports={s.name for s in dyn.iter_symbols() if s['st_shndx']!='SHN_UNDEF'}
imports={s.name for s in dyn.iter_symbols() if s['st_shndx']=='SHN_UNDEF'}
assert {'fprintf','memcpy'}<=exports
assert not ({'send','getenv','strlcpy','pthread_create','open','fopen','write','recv'}&exports)
assert 'send' not in imports
report=dict(passed=True,receiver_sha256=sha(receivers['AID10.5-17PM']),anchors=anchors,
 files={n:sha((out/n).read_bytes()) for n in ('libcpmap-wcp-media790.so','wireless-receiver-exec')},
 source_sha256={f.name:sha(f.read_bytes()) for f in src.iterdir()},
 interposed_functions=['fprintf','memcpy'],video_changes=False,audio_changes=False,
 native_execution_verified=False,limits=['ABI equality and build only; execute actual receiver parser/file-transfer tests before delivery.'])
(out/'VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,files=report['files'],anchors=len(anchors))))
