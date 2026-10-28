#!/usr/bin/env python3
"""Block only the child's device-read seam and exercise the real supervisor.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--cc',default='clang');p.add_argument('--sysroot',type=Path)
p.add_argument('--output',type=Path,required=True);a=p.parse_args()
with tempfile.TemporaryDirectory(prefix='n2-timeout-') as d:
    root=Path(d);shim=root/'shim.c'
    shim.write_text('''#define _POSIX_C_SOURCE 200809L
#include <unistd.h>
#include <string.h>
ssize_t n2_test_read(int fd,void *b,size_t count) {
    ssize_t n=read(fd,b,count);
    if (count==128 && n==128 && !memcmp(b,"WAIT",4)) for (;;) pause();
    return n;
}
''')
    flags=[a.cc,'-std=c99','-O2','-Wall','-Wextra','-Werror']
    if a.sysroot:flags+=['-isysroot',str(a.sysroot)]
    subprocess.run(flags+['-Dread=n2_test_read','-c',str(HERE/'snapshot.c'),'-o',str(root/'helper.o')],check=True)
    subprocess.run(flags+[str(shim),str(root/'helper.o'),'-o',str(root/'helper')],check=True)
    source=root/'source';source.write_bytes(b'WAIT'+bytes(124));lock=root/'lock'
    start=time.monotonic()
    r=subprocess.run([str(root/'helper'),str(source),str(lock)],capture_output=True,text=True,timeout=4)
    elapsed=time.monotonic()-start
    assert r.returncode and 'DEVICE_TIMEOUT' in r.stdout and not lock.exists(),r.stdout
    assert 1.4<elapsed<3,elapsed
result={'passed':True,'device_deadline_ms':1500,'observed_elapsed_seconds':round(elapsed,3),
        'child_reaped_and_lock_removed':True,
        'scope':'host device-read mock; real production-source supervisor',
        'source_sha256':hashlib.sha256((HERE/'snapshot.c').read_bytes()).hexdigest(),
        'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
