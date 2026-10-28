#!/usr/bin/env python3
"""Check the full ZIP and exercise its actual GEM install/export/remove scripts.
Uses a temporary MU1427 filesystem; ARM helper execution is covered by QNX.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('package',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
tests=[]
with tempfile.TemporaryDirectory(prefix='n3-package-') as d:
    root=Path(d);sd=root/'sd';payload=sd/'Custom/carplay_audio_n3'
    with zipfile.ZipFile(a.package) as z:
        assert all(not n.startswith('/') and '..' not in Path(n).parts for n in z.namelist())
        z.extractall(sd)
        for info in z.infolist():
            mode=(info.external_attr>>16)&0o777
            if mode:(sd/info.filename).chmod(mode)
        record=json.loads(z.read('Custom/carplay_audio_n3/manifest.json'))
        for name,meta in record['preserved_n1_files'].items():
            if name!='Toolbox/GEM/carplay-maps-vc.esd':assert sha(z.read(name))==meta['sha256'],name
            assert (sd/name).stat().st_mode&0o777==meta['mode'],name
        for name,digest in record['sources'].items():assert sha((payload/'source'/name).read_bytes())==digest,name
        for f in HERE.rglob('*'):
            if f.is_file() and '__pycache__' not in f.parts:
                name='MU1427/now-playing/n3/'+str(f.relative_to(HERE))
                assert name in record['sources'],'missing canonical source: '+name
                assert sha(f.read_bytes())==record['sources'][name],name
        assert sha((payload/'ipod-drvr-iap2.so').read_bytes())==record['driver']['driver_sha256']
        assert sha((payload/'snapshot').read_bytes())==record['reader']['sha256']
        assert z.read('AUDIO_N3_TEST.md')==(HERE.parent/'TEST-N3.md').read_bytes()
    tests.append('archive source/runtime hashes, accepted N1 files/modes and instructions')
    gem=(sd/'Toolbox/GEM/carplay-maps-vc.esd').read_text()
    for action in ('remove_n2','install','status','export','remove'):
        name='cpmap_audio_n3_'+action+'.sh'
        assert name in gem
        subprocess.run(['/bin/ksh','-n',str(sd/'Toolbox/scripts'/name)],check=True)
    # Reuse the already-tested restricted PATH/firmware fixture, not the
    # controller source: install/run the actual extracted ZIP scripts.
    before=sys.argv
    sys.argv=[str(HERE/'test-controls.py'),str(payload/'ipod-drvr-iap2.so'),str(payload/'snapshot'),str(root/'unused')]
    spec=importlib.util.spec_from_file_location('n3_package_controls',HERE/'test-controls.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture);sys.argv=before
    case=fixture.Controls('test_install_idempotent_remove_no_sd_and_reinstall');case.setUp()
    try:
        scripts=sd/'Toolbox/scripts';installed=case.root/'mnt/app/eso/hmi/engdefs/scripts/mqb'
        installed.mkdir(parents=True)
        for f in scripts.glob('cpmap_audio_n3*.sh'):shutil.copy2(f,installed/f.name)
        env=dict(case.env,CPMAP_TEST_SD=str(sd))
        def run(action,ok=True):
            r=subprocess.run(['/bin/ksh',str(scripts/('cpmap_audio_n3_'+action+'.sh'))],
                env=env,capture_output=True,text=True,timeout=8)
            assert (r.returncode==0)==ok,(action,r.stdout,r.stderr)
            return r.stdout
        assert 'INSTALLED_REBOOT_REQUIRED' in run('install')
        assert case.driver.read_bytes()==(payload/'ipod-drvr-iap2.so').read_bytes()
        assert record['build'] in run('status')
        assert 'ALREADY_INSTALLED' in run('install')
        tests.append('actual GEM scripts: install, marker/status and idempotence')
        # Only the machine-code execution seam is replaced for this host-only
        # dispatch/slot test. Production image decoding is verified separately.
        stub=b'#!/bin/ksh\necho N3_ERROR=TEST_DEVICE_UNAVAILABLE\nexit 1\n#'
        stub+=b' '*(record['reader']['size']-len(stub))
        (case.saved/'snapshot').write_bytes(stub);(case.saved/'snapshot').chmod(0o755)
        for i in range(1,17):
            run('export');out=sd/'Log'/('cpmap-audio-N3-%02d'%i)
            assert 'snapshot_result=1' in (out/'install.txt').read_text()
            assert 'TEST_DEVICE_UNAVAILABLE' in (out/'native.txt').read_text()
        first=(sd/'Log/cpmap-audio-N3-01/native.txt').read_bytes()
        assert 'EXPORT_SLOTS_FULL' in run('export',False)
        assert (sd/'Log/cpmap-audio-N3-01/native.txt').read_bytes()==first
        tests.append('16 non-overwriting SD exports and retained helper errors')
        # Saved removal still works after the original payload disappears.
        shutil.rmtree(payload);run('remove')
        assert case.driver.read_bytes()==bytes(743196)
        tests.append('actual GEM saved-controller removal without payload restores B4')
        case.tearDown()
    finally:case.doCleanups()
result={'passed':True,'tests':tests,'archive_sha256':sha(a.package.read_bytes()),
    'source_sha256':sha(Path(__file__).read_bytes()),'on_unit_validated':False}
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
