#!/usr/bin/env python3
"""Verify the routed-touch merge in the newly built v1.6.6-e components."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
for n in ('components','baseline','tools','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pins=json.loads((a.components/'COMPONENTS.json').read_text());files={}
for name in ('CarPlayWireless-CP-55915411.jar','CarPlayWireless-Touch-55915411.jar'):
 assert sha(a.components/name)==pins[name];shutil.copy2(a.components/name,out/name);files[name]=pins[name]
(out/'input').mkdir()
with zipfile.ZipFile(a.baseline) as z:(out/'input/MU1367WirelessPhone.jar').write_bytes(z.read('Custom/carplay_mu1367_wireless_native/payload/MU1367WirelessPhone.jar'))
java=a.tools.resolve()/'zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/bin';stock=a.tools.resolve()/'stock.jar'
(out/'tests').mkdir();cp=':'.join(map(str,[out/'tests',out/'CarPlayWireless-CP-55915411.jar',out/'input/MU1367WirelessPhone.jar',stock]))
subprocess.run([str(java/'javac'),'-source','7','-target','7','-Xlint:-options','-bootclasspath',str(stock),'-cp',cp,'-d',str(out/'tests'),str(HERE/'tests/TestRoutedTouch.java')],check=True)
result=subprocess.check_output([str(java/'java'),'-Xverify:all','-cp',cp,'TestRoutedTouch',str(out/'unit')],text=True)
dis=subprocess.check_output([str(java/'javap'),'-c','-p','-cp',str(out/'CarPlayWireless-Touch-55915411.jar'),'de.vw.mib.asl.internal.system.input.TouchInputDeviceImpl'],text=True)
body=dis.split('void updateTouchInput(')[1].split('private de.vw.')[0]
assert 'CpWcpTouch.onTouch' not in body and 'TouchInputDeviceListener.updateTouchInput' in body and 'CpWcpTouch.attach' in dis
r=dict(passed=True,files=files,test=result.strip(),raw_intercept_removed=True,bootstrap_preserved=True,on_unit_validated=False)
(out/'VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
