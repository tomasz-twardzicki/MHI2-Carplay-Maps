#!/usr/bin/env python3
"""Exercise the pinned patched service and validate its worker back edge."""
import argparse,hashlib,json,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser()
for n in ('tools','components','base-package','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
java=a.tools.resolve()/'zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/bin';stock=a.tools.resolve()/'stock.jar'
cpjar=a.components.resolve()/'CarPlayWireless-CP-55915411.jar'
with zipfile.ZipFile(a.base_package) as z:(out/'phone.jar').write_bytes(z.read('Custom/carplay_mu1367_wireless_native/payload/MU1367WirelessPhone.jar'))
cp=':'.join(map(str,[out,cpjar,out/'phone.jar',stock]));source=Path(__file__).with_name('TestBorrowedScreen.java')
subprocess.run([str(java/'javac'),'-source','7','-target','7','-Xlint:-options','-bootclasspath',str(stock),'-cp',cp,'-d',str(out),str(source)],check=True)
result=subprocess.check_output([str(java/'java'),'-Xverify:all','-cp',cp,'com.cpmap.audio.TestBorrowedScreen'],text=True)
dis=subprocess.check_output([str(java/'javap'),'-c','-p','-classpath',str(cpjar),'de.vw.mib.asl.internal.wcpcp.WcpCp'],text=True)
loop=dis.split('private static void loop()')[1].split('private static void maybeRegisterAndDrive')[0]
hook=int(loop.split('invokestatic')[0].split('Code:')[1].strip().rstrip(':'))
back=int(loop.rsplit('goto',1)[1].split()[0]);assert back<=hook,(back,hook)
r=dict(passed=True,result=result.strip(),loop_hook_offset=hook,loop_back_edge=back,cp_sha256=hashlib.sha256(cpjar.read_bytes()).hexdigest(),on_unit_validated=False)
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
