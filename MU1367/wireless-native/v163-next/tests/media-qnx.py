#!/usr/bin/env python3
"""Reuse the audited factory-J9 harness; run the exact dispatcher and both image paths."""
import argparse,importlib.util,json,sys,hashlib,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(add_help=False)
for n in ('baseline-tests','components','base-package'):p.add_argument('--'+n,type=Path,required=True)
a,remaining=p.parse_known_args();sys.argv=[sys.argv[0],*remaining]
out=Path(remaining[remaining.index('--output')+1]).resolve();sources=out.with_name(out.name+'-sources');(sources/'java').mkdir(parents=True,exist_ok=False)
for n in ('TestText','TestCover'):(sources/'java'/(n+'.java')).write_bytes((a.baseline_tests/('artwork-test/java' if n=='TestText' else 'java')/(n+'.java')).read_bytes())
for n in ('TestWirelessMedia.java','TestWirelessWorker.java.in','TestBorrowedScreen.java','TestArtworkTrace.java'):(sources/n).write_bytes((HERE/n).read_bytes())
fixture=','.join(str(v if v<128 else v-256) for v in (a.baseline_tests/'artwork-png/fixtures/colors.jpg').read_bytes())
(sources/'java/TestWirelessMedia.java').write_bytes((HERE/'TestWirelessMedia.java').read_bytes())
(sources/'java/TestBorrowedScreen.java').write_bytes((HERE/'TestBorrowedScreen.java').read_bytes())
(sources/'java/TestArtworkTrace.java').write_bytes((HERE/'TestArtworkTrace.java').read_bytes())
with zipfile.ZipFile(a.base_package) as z:(sources/'phone.jar').write_bytes(z.read('Custom/carplay_mu1367_wireless_native/payload/MU1367WirelessPhone.jar'))
(sources/'java/TestWirelessWorker.java').write_text((HERE/'TestWirelessWorker.java.in').read_text().replace('@IMAGE@',fixture))
(sources/'TestCoverWorker.java.in').write_bytes((a.baseline_tests/'TestCoverWorker.java.in').read_bytes())
(sources/'artwork-test/fixtures').mkdir(parents=True)
(sources/'artwork-test/fixtures/colors.png').write_bytes((a.baseline_tests/'artwork-test/fixtures/colors.png').read_bytes())
script=(a.baseline_tests/'test-audio-qnx.py').read_text()
script=script.replace("revision=json.loads((a.build/'manifest.json').read_text()).get('revision','r2')","revision='r2'")
script=script.replace("extra='TestProgress' if revision=='r2' else 'TestArtworkR3'","extra='TestWirelessMedia'")
script=script.replace("for n in ('TestText','TestCover',extra):","for n in ('TestText','TestCover',extra,'TestWirelessWorker','TestBorrowedScreen','TestArtworkTrace'):")
script=script.replace('CoverBridge.started=true; TestText.main(a); TestCover.main(a); @EXTRA@.main(a); TestCoverWorker.main(a);','CoverBridge.started=true; WirelessMedia.started=true; @EXTRA@.main(a); TestCover.main(a); TestArtworkTrace.main(a); WirelessMedia.usb=true; TestCoverWorker.main(a); TestWirelessWorker.main(a); TestBorrowedScreen.main(a);')
script=script.replace('worker=(HERE/','worker=(HERE/').replace('if revision!=\'r2\':\n  worker=',"if True:\n  worker=",1)
script=script.replace("  worker=worker.replace('capacity();\\n            }','capacity();check(CoverTiming.status().indexOf(\"png_bytes=\")>=0);\\n            }')",'')
script=script.replace("template=(setup/'test.build').read_text()","template=(setup/'test.build').read_text()\n shutil.copy2(Path("+repr(str(a.components.resolve()))+")/'wireless-artwork-fetch',out/'wireless-artwork-fetch')\n shutil.copy2(setup.parent/'build-artwork-r3-native-final-2/libz.so.2',out/'libz.so.2')\n template+='\\n[type=file]\\n[perms=+r,+x]\\nwireless-artwork-fetch\\nlibz.so.2\\n[type=link] /mnt/app/carplay-mu1367-wireless-media=/proc/boot\\n'")
script=script.replace("['clang','--target", "['/Library/Developer/CommandLineTools/usr/bin/clang','--target")
script=script.replace("('AUDIO_PROGRESS_PASS' if revision=='r2' else 'ARTWORK_R3_PASS')","'WIRELESS_MEDIA_JAVA_PASS'")
script=script.replace("'ARTWORK_WORKER_PASS tracks=10 cache_files=8','CHILD_STATUS=0'","'ARTWORK_WORKER_PASS tracks=10 cache_files=8','WIRELESS_ARTWORK_WORKER_PASS','CHILD_STATUS=0'")
script=script.replace("str(jar)+':'+str(stock)","str(jar)+':'+str(stock)+':'+"+repr(str(a.components.resolve()/'CarPlayWireless-CP-55915411.jar'))+"+':'+"+repr(str(sources/'phone.jar')))
append="\n with zipfile.ZipFile(out/'observer.jar','a') as z:\n  for dependency in "+repr([str(a.components.resolve()/'CarPlayWireless-CP-55915411.jar'),str(sources/'phone.jar')])+":\n   with zipfile.ZipFile(dependency) as dep:\n    for name in dep.namelist():\n     if name.endswith('.class'):z.writestr(name,dep.read(name))\n"
script=script.replace(" # Package-private probes",append+" # Package-private probes")
script=script.replace("'WIRELESS_ARTWORK_WORKER_PASS','CHILD_STATUS=0'","'WIRELESS_ARTWORK_WORKER_PASS','WIRELESS_SCREEN_RETURN_PASS','ARTWORK_TRACE_PASS','CHILD_STATUS=0'")
spec=importlib.util.spec_from_file_location('fixture',a.baseline_tests/'test-audio-qnx.py');fixture_module=importlib.util.module_from_spec(spec)
exec(compile(script,str(a.baseline_tests/'test-audio-qnx.py'),'exec'),fixture_module.__dict__);fixture_module.HERE=sources;fixture_module.main()
r=json.loads((out/'result.json').read_text());r['wireless_media_factory_j9']=True;r['wireless_screen_factory_j9']=True;r['cp_sha256']=hashlib.sha256((a.components/'CarPlayWireless-CP-55915411.jar').read_bytes()).hexdigest();r['wireless_native_decoder_sha256']=hashlib.sha256((a.components/'wireless-artwork-fetch').read_bytes()).hexdigest();(out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
