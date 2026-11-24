#!/usr/bin/env python3
"""Check SD-only changes and allowlisted diagnostics without changing runtime."""
import argparse, hashlib, json, os, subprocess, tempfile
from pathlib import Path
p=argparse.ArgumentParser()
for n in ('build','tested-build','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();sd=a.build.resolve()/'sd-card';old=a.tested_build.resolve()/'sd-card'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
delta=[]
for f in old.rglob('*'):
 if f.is_file() and 'source' not in f.relative_to(old).parts and sha(f)!=sha(sd/f.relative_to(old)):
  delta.append(f.relative_to(old).as_posix())
assert set(delta)=={'collect-wireless.sh','Toolbox/scripts/cpmap_wireless_collect_data.sh','Custom/carplay_mu1367_oem_reset/manifest.json','Toolbox/GEM/carplay-maps-vc.esd','Toolbox/GEM/carplay-maps-vc-wireless.esd','Toolbox/GEM/carplay-maps-vc-experimental.esd'} | {f.relative_to(old).as_posix() for f in old.glob('Custom/*/payload-check.sh') if f.parent.name!='carplay_mu1367_wireless_native'},delta
# All tested controllers, native binaries, profiles and selector/tuner unchanged.
for r in ('Custom/carplay_mu1367_input_profile/790/control.sh','Custom/carplay_mu1367_input_profile/actions.sh','Custom/carplay_mu1367_input_profile/tune.sh','Custom/carplay_mu1367_oem_reset/control.sh'):
 assert sha(sd/r)==sha(old/r)
exports=[]
for relative in ('collect-wireless.sh','Toolbox/scripts/cpmap_wireless_collect_data.sh'):
 with tempfile.TemporaryDirectory(prefix='v167-export-') as tmp:
  root=Path(tmp)
  for d in ('ifs','ramdisk','dev/shmem','mnt/app/carplay-mu1367-profile-790-v167','mnt/app/carplaymaps','mnt/persist/wcp','fs/sda0'):(root/d).mkdir(parents=True,exist_ok=True)
  (root/'ifs/lsd.jxe').write_bytes(b'fixture')
  (root/'ramdisk/omonob-790-input.log').write_text('790 input fixture\n')
  (root/'ramdisk/omonob-790-input.pid').write_text('123\n')
  (root/'mnt/app/carplaymaps/PROFILE').write_text('MU1367/790\n')
  (root/'mnt/app/carplay-mu1367-profile-790-v167/STATE').write_text('installed\n')
  (root/'mnt/persist/wcp/key').write_bytes(b'PRIVATE_PAIRING_SENTINEL')
  (root/'mnt/persist/wcp_bt_disable').write_bytes(b'PRIVATE_ADDRESS_SENTINEL')
  result=subprocess.run(['/bin/ksh',str(sd/relative),'/fs/sda0'],env=dict(os.environ,CPMAP_TEST_ROOT=str(root)),capture_output=True,text=True)
  assert result.returncode==0,result.stdout+result.stderr
  out=list((root/'fs/sda0/Log').glob('wireless-diag-*'));assert len(out)==1
  for name,text in {'logs/ramdisk-omonob-790-input.log':'790 input fixture\n','state/omonob-790-input.pid':'123\n','state/PROFILE':'MU1367/790\n','state/carplay-mu1367-profile-790-v167/STATE':'installed\n'}.items():assert (out[0]/name).read_text()==text,name
  assert not any(b'PRIVATE_' in f.read_bytes() for f in out[0].rglob('*') if f.is_file())
  exports.append(dict(path=relative,sha256=sha(sd/relative),passed=True))
info=json.loads((sd/'Custom/carplay_mu1367_oem_reset/manifest.json').read_text())
assert info['controller_sha256']==sha(sd/'Custom/carplay_mu1367_oem_reset/control.sh')
assert 'carplay-mu1367-profile-790-v167' in info['layers_archived']
report=dict(passed=True,scope='Host execution of read-only SD collectors; comparison of final stage against native/host-tested stage.',delta=sorted(delta),collectors=exports,pairing_exported=False,runtime_unchanged=True)
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
