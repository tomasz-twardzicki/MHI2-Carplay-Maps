#!/usr/bin/env python3
"""Test source qualification against the unchanged sealed v1.6.6-e consumer."""
import argparse,hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent
BASE=SOURCE.parent/'v166-release'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
pins=json.loads((BASE/'VERIFICATION.json').read_text())['source_sha256'];consumer={}
for name in ('wcp_location.c','wcp_location.h','wcp_location_source.h'):
 key='v166-release/src/native/'+name;f=SOURCE.parent/key
 assert sha(f)==pins[key];consumer[name]=sha(f)
clang='/Library/Developer/CommandLineTools/usr/bin/clang'
subprocess.run([clang,'-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk','-std=gnu99','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',str(SOURCE),'-I',str(BASE/'src/native'),str(HERE/'source-consumer.c'),str(BASE/'src/native/wcp_location.c'),'-o',str(out/'source-consumer')],check=True)
result=subprocess.check_output([str(out/'source-consumer')],text=True).strip()
report=dict(passed=True,scope='Source core plus actual unchanged WGPS/iAP2 protocol consumer; no ASI transport or target daemon.',result=result,sanitizers=['address','undefined'],consumer_sha256=consumer,source_core_sha256=sha(SOURCE/'source_core.h'),test_sha256=sha(HERE/'source-consumer.c'),independent_client_implemented=False,on_unit_validated=False)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
