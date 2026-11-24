#!/usr/bin/env python3
"""Build an isolated OEM-routed-touch candidate from the exact v1.6.3-e ZIP."""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sha = lambda b: hashlib.sha256(b).hexdigest()
p = argparse.ArgumentParser()
for name in ('baseline', 'tools', 'output'):
    p.add_argument('--'+name, type=Path, required=True)
a = p.parse_args()
assert sha(a.baseline.read_bytes()) == '4956ae5e9378f123d32ad371da94c0f9578b1e153586cf11d3f69b1a69234bce'
out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
java = a.tools.resolve()/'zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/bin'
stock = a.tools.resolve()/'stock.jar'
asm = ':'.join(str(a.tools.resolve()/'asm'/n) for n in ('asm-9.7.jar','asm-tree-9.7.jar'))
run = lambda *args: subprocess.run(list(map(str,args)),check=True)
for n in ('classes','tools','input','patched','tests'): (out/n).mkdir()
prefix='Custom/carplay_mu1367_wireless_native/payload/'
with zipfile.ZipFile(a.baseline) as z:
    original = {n:z.read(prefix+n) for n in ('CarPlayWireless-CP-55915411.jar','CarPlayWireless-Touch-55915411.jar','MU1367WirelessPhone.jar')}
assert sha(original['CarPlayWireless-CP-55915411.jar']) == '12f097bd4643ba2ca3a9959c01bf591cea1c5920b3ab2063429890c7a38e0c17'
assert sha(original['CarPlayWireless-Touch-55915411.jar']) == '95173d48e2de91f599748a650d9ff1c5156ef1b56a34ee0821a8e34f24c133d0'
for name,data in original.items(): (out/'input'/name).write_bytes(data)
classes={}
for name,data in original.items():
    if name=='MU1367WirelessPhone.jar': continue
    with zipfile.ZipFile(out/'input'/name) as z: classes[name]={n:z.read(n) for n in z.namelist()}
touch='de/vw/mib/asl/internal/system/input/TouchInputDeviceImpl.class'
cp='de/vw/mib/asl/internal/wcpcp/WcpCp.class'
helper='de/vw/mib/asl/internal/wcpcp/RoutedTouch.class'
with zipfile.ZipFile(stock) as z: (out/'input/factory-touch.class').write_bytes(z.read(touch))
(out/'input/upstream-touch.class').write_bytes(classes['CarPlayWireless-Touch-55915411.jar'][touch])
(out/'input/cp.class').write_bytes(classes['CarPlayWireless-CP-55915411.jar'][cp])
run(java/'javac','-source','7','-target','7','-Xlint:-options','-bootclasspath',stock,'-d',out/'classes',HERE/'src/RoutedTouch.java')
run(java/'javac','-cp',asm,'-d',out/'tools',HERE/'tools/PatchInput.java')
command=[java/'java','-cp',str(out/'tools')+':'+asm,'PatchInput']
run(*command,'touch',out/'input/factory-touch.class',out/'input/upstream-touch.class',out/'patched/touch.class')
run(*command,'cp',out/'input/cp.class',out/'patched/cp.class')
run(*command,'helper',out/'classes'/helper,out/'patched/helper.class')
classes['CarPlayWireless-Touch-55915411.jar'][touch]=(out/'patched/touch.class').read_bytes()
classes['CarPlayWireless-CP-55915411.jar'][cp]=(out/'patched/cp.class').read_bytes()
classes['CarPlayWireless-CP-55915411.jar'][helper]=(out/'patched/helper.class').read_bytes()
for name,entries in classes.items():
    with zipfile.ZipFile(out/name,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in sorted(entries.items()):
            i=zipfile.ZipInfo(n,(2026,11,22,0,0,0)); i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16;z.writestr(i,data)
cp_path=':'.join(str(p) for p in (out/'tests',out/'CarPlayWireless-CP-55915411.jar',out/'input/MU1367WirelessPhone.jar',stock))
run(java/'javac','-source','7','-target','7','-Xlint:-options','-bootclasspath',stock,'-cp',cp_path,'-d',out/'tests',HERE/'tests/TestRoutedTouch.java')
result=subprocess.check_output([str(java/'java'),'-Xverify:all','-cp',cp_path,'TestRoutedTouch',str(out/'unit')],text=True)
# Exact raw-hook removal: no global onTouch call remains in the input method.
dis=subprocess.check_output([str(java/'javap'),'-c','-p','-cp',str(out/'CarPlayWireless-Touch-55915411.jar'),'de.vw.mib.asl.internal.system.input.TouchInputDeviceImpl'],text=True)
body=dis.split('void updateTouchInput(')[1].split('private de.vw.')[0]
assert 'CpWcpTouch.onTouch' not in body
assert 'TouchInputDeviceListener.updateTouchInput' in body
assert 'CpWcpTouch.attach' in dis
report=dict(passed=True,experimental=True,on_unit_validated=False,baseline_version='1.6.3-e',
            test=result.strip(),raw_intercept_removed=True,bootstrap_preserved=True,
            files={n:sha((out/n).read_bytes()) for n in classes},
            limits=['Single-contact touchscreen path only; two-contact/touchpad events are rejected.','Stock HMI hit-testing and physical overlay behavior require vehicle acceptance.','Call audio transport is not changed by this touch patch.'])
(out/'VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
