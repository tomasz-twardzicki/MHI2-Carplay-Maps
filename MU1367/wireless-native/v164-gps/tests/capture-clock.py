#!/usr/bin/env python3
"""Build and run the capture clock's sanitizer scenarios."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
header=HERE.parent/'src/native/wcp_capture_clock.h';source=HERE/'capture-clock.c'
flags=['-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk','-std=gnu99','-O1','-g',
       '-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(header.parent)]
subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/clang',*flags,str(source),'-o',str(out/'clock')],check=True)
log=subprocess.check_output([str(out/'clock')],text=True)
assert 'CAPTURE_CLOCK_PASS simulated_frames=50000' in log
r=dict(passed=True,output=log.strip(),header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),
       test_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),sanitizers=['address','undefined'])
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
