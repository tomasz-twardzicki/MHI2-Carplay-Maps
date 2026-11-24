#!/usr/bin/env python3
"""Extend released factory-J9 probes with the real wireless component/lease path."""
import argparse,importlib.util,sys,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(add_help=False);p.add_argument('--baseline-tests',type=Path,required=True);p.add_argument('--factory-setup',type=Path,required=True)
a,remaining=p.parse_known_args();sys.argv=[sys.argv[0],*remaining]
out=Path(remaining[remaining.index('--output')+1]);source=out.with_name(out.name+'-sources');(source/'java').mkdir(parents=True,exist_ok=False)
provenance={}
for name in ('TestUturnQnx.java','TestRoadQnx.java','TestArrowQnx.java','TestQuietQnx.java'):
 text=(a.baseline_tests/'java'/name).read_text();provenance[name]=hashlib.sha256(text.encode()).hexdigest()
 if name=='TestUturnQnx.java':
  text=text.replace('public static void main(String[] args)throws Exception {','public static void main(String[] args)throws Exception {\n  TestWirelessQnx.run();')
  wireless=(HERE/'TestWirelessQnx.java').read_text().replace('package com.cpmap.rgi;','')
  text+='\n'+wireless
  split=(HERE/'TestPositionSplit.java').read_text().replace('package com.cpmap.rgi;','').replace('public final class TestPositionSplit','final class TestPositionSplit')
  text+='\n'+split
  text=text.replace('TestRoadQnx.main(args);','TestRoadQnx.main(args);TestPositionSplit.run();')
 if name=='TestRoadQnx.java':text=text.replace('if(n.equals("getTurnToInfoStreet"))','if(n.equals("getCurrentPositionInfo"))return "OEM Current";\n                if(n.equals("getTurnToInfoStreet"))')
 (source/'java'/name).write_text(text)
spec=importlib.util.spec_from_file_location('fixture',a.baseline_tests/'test-guidance-qnx.py');fixture=importlib.util.module_from_spec(spec)
code=(a.baseline_tests/'test-guidance-qnx.py').read_text()
extra=" for name in ('devb-ram','mkqnx6fs','mount','libcam.so.2','io-blk.so','fs-qnx6.so','cam-disk.so','libblkcache.so.2'):\n  shutil.copy2(Path("+repr(str(a.factory_setup.resolve()))+")/name,w/name)\n"
code=code.replace(" assert sha(w/'libc.so.3')",extra+" assert sha(w/'libc.so.3')")
code=code.replace("template+='\\n'.join", "template+='[type=link] /mnt/persist=/ramdisk/driver-persist\\n[+raw]\\n'\n template+='\\n'.join")
exec(compile(code,str(a.baseline_tests/'test-guidance-qnx.py'),'exec'),fixture.__dict__)
fixture.HERE=source.resolve();fixture.main()
r=json.loads((out/'result.json').read_text());log=(out/'qemu.log').read_text(errors='replace')
assert log.count('WIRELESS_FACTORY_J9_PASS checks=10')==2
assert log.count('POSITION_SPLIT_FACTORY_PASS checks=13')==2
r.update(current_position_split_factory_j9=True,position_split_test_sha256=hashlib.sha256((HERE/'TestPositionSplit.java').read_bytes()).hexdigest(),wireless_component_and_lease_factory_j9=True,baseline_test_sources_sha256=provenance,wireless_source_sha256=hashlib.sha256((HERE/'TestWirelessQnx.java').read_bytes()).hexdigest())
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
