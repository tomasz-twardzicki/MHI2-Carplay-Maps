#!/usr/bin/env python3
"""ASan/UBSan parser/decoder checks and real factory Java dispatcher regression."""
import argparse,hashlib,json,struct,subprocess,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
for n in ('tools','components','baseline-tests','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
native=HERE.parent/'src/native';art=HERE.parent/'src/artwork';clang='/Library/Developer/CommandLineTools/usr/bin/clang'
flags=['-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk','-std=gnu99','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-omit-frame-pointer']
subprocess.run([clang,*flags,'-I',str(native),str(HERE/'media-native.c'),'-o',str(out/'policy')],check=True)
policy=subprocess.check_output([str(out/'policy')],text=True).strip()
subprocess.run([clang,*flags,'-DCPMAP_PNG_COMPRESSED',str(art/'wireless_fetch.c'),'-lz','-o',str(out/'decode')],check=True)
cases={}
for ext in ('jpg','png'):
 image=(a.baseline_tests/'artwork-png/fixtures'/('colors.'+ext)).read_bytes();header=bytearray(64);header[:4]=b'WCA1'
 for at,value in [(4,1),(8,64+len(image)),(12,23),(16,123),(24,1),(28,42),(32,42),(40,0x84),(44,1),(48,len(image))]:struct.pack_into('<I',header,at,value)
 snapshot=out/('cover-'+ext+'.bin');snapshot.write_bytes(header+image)
 def command(uid='2a',serial='1',png=out/('image-'+ext+'.png')):return list(map(str,[out/'decode',snapshot,out/'decode-lock',png,'23','7b','1','42',uid,'132',serial,len(image)]))
 result=subprocess.run(command(),capture_output=True,text=True);assert result.returncode==0,result.stdout
 b=(out/('image-'+ext+'.png')).read_bytes();assert b[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack_from('>II',b,16)==(256,256)
 assert subprocess.run(command(uid='2b',png=out/'wrong-uid.png'),capture_output=True).returncode==1
 assert subprocess.run(command(serial='2',png=out/'wrong-serial.png'),capture_output=True).returncode==1
 snapshot.write_bytes(header+image[:-1]);assert subprocess.run(command(png=out/'truncated.png'),capture_output=True).returncode==1
 assert not any((out/f).exists() for f in ['wrong-uid.png','wrong-serial.png','truncated.png','decode-lock'])
 cases[ext]=dict(normalized_dimensions=[256,256],wrong_uid_rejected=True,wrong_generation_rejected=True,truncated_rejected=True)
java=a.tools.resolve()/'zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/bin';stock=a.tools.resolve()/'stock.jar';audio=a.components.resolve()/'CarPlayMU1367Audio.jar';cp=str(out)+':'+str(audio)+':'+str(stock)
subprocess.run([str(java/'javac'),'-source','7','-target','7','-Xlint:-options','-bootclasspath',str(stock),'-cp',cp,'-d',str(out),str(HERE/'TestWirelessMedia.java'),str(HERE/'TestArtworkTrace.java'),str(a.baseline_tests/'artwork-test/java/TestText.java')],check=True)
result=subprocess.check_output([str(java/'java'),'-Xverify:all','-cp',cp,'com.cpmap.audio.TestWirelessMedia'],text=True).strip()
trace=subprocess.check_output([str(java/'java'),'-Xverify:all','-cp',cp,'com.cpmap.audio.TestArtworkTrace'],text=True).strip()
r=dict(trace=trace,passed=True,sanitizers=['address','undefined'],parser=policy,decoders=cases,java=result,components=json.loads((a.components/'COMPONENTS.json').read_text()),on_unit_validated=False)
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(passed=True,parser=policy,java=result,decoder_cases=len(cases))))
