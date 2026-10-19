#!/usr/bin/env python3
"""Assemble the full toolbox with verified automatic MU1427 native guidance.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import zipfile

HERE=Path(__file__).resolve().parent
BASE=HERE.parent.parent/'releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4'
B4_SHA='4e42651f0b8d26cb340ddfab299c6b8def45030ef0730cc548c390aefdeeb6a8'


def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hmi',type=Path,default=HERE/'build-release-hmi')
    p.add_argument('--native',type=Path,default=HERE/'build-release-native')
    p.add_argument('--output',type=Path,default=HERE/'build-release')
    a=p.parse_args()
    hmi=read(a.hmi/'manifest.json');runtime=read(a.hmi/'runtime-verification.json')
    native=read(a.native/'manifest.json');qnx=read(HERE/'build-release-qnx/result.json')
    qnx_reader=read(HERE/'build-release-reader-qnx/result.json')
    controls=read(HERE/'build-release-controls.json');reader_tests=read(HERE/'build-release-reader-tests.json')
    jar=(a.hmi/'CarPlayRouteGuidanceD1.jar').read_bytes();reader=(a.native/'rgi-observer').read_bytes()
    assert hmi['revision']=='release' and native['revision']=='release'
    assert sha(jar)==hmi['jar_sha256']==runtime['jar_sha256']==qnx['jar_sha256']==controls['jar_sha256']==reader_tests['jar_sha256']
    assert sha(reader)==native['sha256']==qnx['reader_sha256']==qnx_reader['reader_sha256']==controls['reader_sha256']
    assert all(x[k] for x,k in [(runtime,'passed'),(qnx,'passed'),(qnx,'mailbox_qnx_passed'),(qnx_reader,'qnx_smoke_passed'),(controls,'passed'),(reader_tests,'passed')])
    for name,digest in hmi['sources'].items():assert sha((HERE/'bridge'/name).read_bytes())==digest
    for path,digest in [
        ('test-live-bridge.py',runtime['test_sha256']),('build-live-bridge.py',runtime['builder_sha256']),
        ('test-live-qnx.py',qnx['test_sha256']),('bridge/LoadProbe.java',qnx['probe_sha256']),
        ('release/control.sh',controls['controller_sha256']),('test-release-control.py',controls['test_sha256']),
        ('release/reader.c',native['source_sha256']),('release/reader.c',reader_tests['reader_source_sha256']),
        ('bridge/MailboxReader.java',reader_tests['mailbox_source_sha256']),('test-release-reader.py',reader_tests['test_sha256'])]:
        assert sha((HERE/path).read_bytes())==digest,path
    with zipfile.ZipFile(a.hmi/'CarPlayRouteGuidanceD1.jar') as classes:
        assert all(struct.unpack_from('>H',classes.read(n),6)[0]==46 for n in classes.namelist() if n.endswith('.class'))
    b4=HERE/'build-B4/MU1427-route-guidance-B4-toolbox.zip';assert sha(b4.read_bytes())==B4_SHA
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    stage=out/'sd-card'
    shutil.copytree(BASE,stage,ignore=shutil.ignore_patterns('.DS_Store','cpmap_navrecon.sh','carplay_native_guidance'))
    payload=stage/'Custom/carplay_native_guidance';payload.mkdir()
    build_id='MU1427-native-guidance-1.0.0-'+sha(jar)[:8]
    (payload/'VERSION').write_text(build_id+'\n')
    (payload/'CarPlayRouteGuidanceD1.jar').write_bytes(jar)
    (payload/'rgi-observer').write_bytes(reader);(payload/'rgi-observer').chmod(0o755)
    driver=payload/'driver';driver.mkdir()
    with zipfile.ZipFile(b4) as seed:
        for n in ('ipod-drvr-iap2.so','iap2.cfg','VERSION'):
            (driver/n).write_bytes(seed.read('Custom/route_guidance_b1/'+n))
        (payload/'driver-control.sh').write_bytes(seed.read('Toolbox/scripts/cpmap_rgi_b1.sh'))
    assert sha((driver/'ipod-drvr-iap2.so').read_bytes())=='3760797aed4886a6c4480e3a8de79be427a3d8587450a56c424721306ca15d8b'
    assert sha((driver/'iap2.cfg').read_bytes())=='67b867db8eb05e0dd20645727d3216ff18b86be75d21c9fb89a92dffbcafc9f7'
    scripts=stage/'Toolbox/scripts'
    controller=(HERE/'release/control.sh').read_text()
    for name,value in {'BUILD_ID':build_id,'JAR_SIZE':str(len(jar)),'READER_SIZE':str(len(reader))}.items():
        assert controller.count('@'+name+'@')==1
        controller=controller.replace('@'+name+'@',value)
    (scripts/'cpmap_guidance.sh').write_text(controller);(scripts/'cpmap_guidance.sh').chmod(0o755)
    for action in ('install','status','disable','remove'):
        text='''#!/bin/ksh
S=/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_guidance.sh
[ -s "$S" ] || S=/net/mmx/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_guidance.sh
'''
        if action=='install':
            text+='''for V in /net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0; do
    P=$V/Custom/carplay_native_guidance
    if [ -s "$P/VERSION" ]; then /bin/ksh "$S" install "$P"; exit $?; fi
done
echo "CPMAP_GUIDANCE_FAIL=SD_PAYLOAD_NOT_FOUND"
exit 1
'''
        else:text+='/bin/ksh "$S" '+('uninstall' if action=='remove' else action)+'\n'
        script=scripts/('cpmap_guidance_'+action+'.sh');script.write_text(text);script.chmod(0o755)
    source=payload/'source';source.mkdir()
    for file in HERE.glob('*.py'):shutil.copy2(file,source/file.name)
    for directory,pattern in [('bridge','*.java'),('release','*')]:
        dest=source/directory;dest.mkdir()
        for file in (HERE/directory).glob(pattern):
            if file.is_file():shutil.copy2(file,dest/file.name)
    # Test fixtures and the legacy native reader remain available as source,
    # but no research menu/installer/capture payload is deployed.
    shutil.copytree(HERE/'observer',source/'observer',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(HERE.parent.parent/'LICENSE',source/'LICENSE')
    (source/'README.md').write_text('Source snapshot for MU1427 native guidance. Place these files in MU1427/route-guidance of the repository to rebuild with the documented firmware, Java and pinned QNX toolchain. See INSTALL.md and the repository LIVE-BRIDGE.md for architecture/provenance. Baseline project: omonob; MU1427/native guidance: tomasz-twardzicki. Protocol/maneuver adaptations retain LuKa attribution in source. GPL-3.0-or-later. Firmware-derived binaries are inputs/outputs, not source replacements.\n')
    instructions=(HERE/'INSTALL.md').read_text()
    package_line=next(line for line in instructions.splitlines() if line.startswith('Package: '))
    instructions=instructions.replace(package_line,'Full MQB Toolbox bundle with automatic MU1427 native guidance, version 1.0.0.')
    (stage/'NATIVE_GUIDANCE_INSTALL.md').write_text(instructions)
    (source/'INSTALL.md').write_text(instructions)
    # Replace the old video-only summary in the bundle with current instructions.
    (stage/'CARPLAY_MAPS_VC_README.md').write_text(instructions)
    manifest={'version':'1.0.0','build_id':build_id,'source_id':hmi['source_id'],
      'jar_sha256':sha(jar),'reader_sha256':sha(reader),'controller_sha256':sha(controller.encode()),
      'default_enabled_after_boot':True,'manual_test_gate':False,'maximum_ram_feed_bytes':70*1024,
      'route_capture_archive':False,'driver_changed_from_tested_b4':False,
      'safe_areas':{'default':[200,96,400,364],'wide-card':[160,96,480,364],'no-card':[200,80,400,380]},
      'hmi':hmi,'runtime':runtime,'native':native,'qnx_j9':qnx,
      'qnx_reader':{k:v for k,v in qnx_reader.items() if k!='work'},'controls':controls,'reader_tests':reader_tests,
      'unit_automatic_startup_and_lowered_card_check_pending':True}
    (payload/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    archive=out/'CarPlay_Maps_VC_MU1427_Native_Guidance_v1.0.0.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for file in sorted(stage.rglob('*')):
            if file.is_file():z.write(file,file.relative_to(stage))
    manifest['archive_sha256']=sha(archive.read_bytes())
    manifest['files_sha256']={str(f.relative_to(stage)):sha(f.read_bytes()) for f in stage.rglob('*') if f.is_file()}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'SHA256SUMS.txt').write_text(manifest['archive_sha256']+'  '+archive.name+'\n')
    # Keep the repository's full toolbox tree deployable as well as the ZIP.
    shutil.copytree(payload,BASE/'Custom/carplay_native_guidance',dirs_exist_ok=True)
    for file in scripts.glob('cpmap_guidance*.sh'): shutil.copy2(file,BASE/'Toolbox/scripts'/file.name)
    for name in ('NATIVE_GUIDANCE_INSTALL.md','CARPLAY_MAPS_VC_README.md'): shutil.copy2(stage/name,BASE/name)
    print(json.dumps({'archive':str(archive),'sha256':manifest['archive_sha256'],'build_id':build_id}))


if __name__=='__main__':main()
