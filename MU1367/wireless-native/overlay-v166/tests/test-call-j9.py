#!/usr/bin/env python3
"""Run real WcpCp handoff decisions on factory ARM J9; observe requests only."""
import argparse,hashlib,json,shutil,struct,sys,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(add_help=False)
p.add_argument('--components',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a,rest=p.parse_known_args();original=a.components.resolve();fixture=a.output.resolve().with_name(a.output.name+'-components');fixture.mkdir(parents=True,exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
paths={s:('/ramdisk/cpmap-call-contract'+s).encode() for s in ('/mnt/persist/wcp_btaudio_release','/dev/shmem/wcp_bt_disable','/dev/shmem/wcp_bt_released')}
def relocate(data):
 count=struct.unpack_from('>H',data,8)[0];parts=[data[:10]];at=10;index=1;changed=[]
 sizes={3:4,4:4,5:8,6:8,7:2,8:2,9:4,10:4,11:4,12:4,15:3,16:2,18:4}
 while index<count:
  start=at;tag=data[at];at+=1
  if tag==1:
   n=struct.unpack_from('>H',data,at)[0];at+=2;value=data[at:at+n];at+=n
   text=next((s for s in paths if s.encode()==value),None)
   if text in paths:
    changed.append(text);replacement=paths[text];parts.append(b'\x01'+struct.pack('>H',len(replacement))+replacement)
   else:parts.append(data[start:at])
  else:
   at+=sizes[tag];parts.append(data[start:at])
   if tag in (5,6):index+=1
  index+=1
 assert set(changed)==set(paths)
 parts.append(data[at:]);result=b''.join(parts)
 return result
with zipfile.ZipFile(original/'CarPlayWireless-CP-55915411.jar') as z,zipfile.ZipFile(fixture/'CarPlayWireless-CP-55915411.jar','w') as f:
 for name in z.namelist():
  b=z.read(name)
  if name.endswith('/WcpCp.class'):b=relocate(b)
  f.writestr(name,b)
shutil.copy2(original/'CarPlayWireless-Touch-55915411.jar',fixture/'CarPlayWireless-Touch-55915411.jar')
shutil.copytree(original/'input',fixture/'input')
script=(HERE/'test-j9.py').read_text().replace('TestRoutedLoad','TestCallRelease').replace('ROUTED_TOUCH_FACTORY_J9_PASS','CALL_RELEASE_CONTRACT_PASS')
sys.argv=[sys.argv[0],'--components',str(fixture),'--output',str(a.output),*rest]
ns=dict(__file__=str(HERE/'test-j9.py'),__name__='call_j9_fixture');exec(compile(script,str(HERE/'test-j9.py'),'exec'),ns)
report=json.loads((a.output/'result.json').read_text())
report.update(original_cp_sha256=sha((original/'CarPlayWireless-CP-55915411.jar').read_bytes()),
 fixture_changes='Only three file-path UTF8 constants relocated; method bytecode and stock APIs unchanged.',
 fixture_services=['synthetic trusted devices','configuration contact capacity','persistence callbacks','disabled trace logger'],
 network_boundary='Observe the addressed service request; no Bluetooth ACK or call-audio success is simulated.',
 bluetooth_acknowledged=False,
 scope='Real adapter bytecode on factory ARM/J9, synthetic trusted devices, observed OEM service request. No Bluetooth disconnect ACK, radio or physical call execution.')
(a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
