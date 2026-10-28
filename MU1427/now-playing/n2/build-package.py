#!/usr/bin/env python3
"""Append N2 to the immutable tested full N1 toolbox after matching checks.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

HERE=Path(__file__).resolve().parent
AUDIO=HERE.parent
N1_SHA='5bf9d571d85eee87ae9a6a7a166849ab2b83c22a84aa4cd02adc2aff9afd409d'


def sha(data):return hashlib.sha256(data).hexdigest()
def require(value,why):
    if not value:raise ValueError(why)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('n1-package','driver','reader','driver-tests','controls','timeout','qnx','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    driver=a.driver.read_bytes();reader=(a.reader/'rgi-observer').read_bytes()
    dm=json.loads(a.driver.with_suffix('.json').read_text());rm=json.loads((a.reader/'manifest.json').read_text())
    dt=json.loads(a.driver_tests.read_text());ct=json.loads(a.controls.read_text())
    timeout=json.loads(a.timeout.read_text());qnx=json.loads(a.qnx.read_text())
    require(sha(a.n1_package.read_bytes())==N1_SHA,'tested N1 ZIP required')
    require(sha(driver)==dm['driver_sha256']==dt['driver_sha256']==ct['driver_sha256'],'driver evidence mismatch')
    require(sha(reader)==rm['sha256']==ct['helper_sha256']==qnx['reader_sha256'],'helper evidence mismatch')
    require(dt['passed'] and ct['passed'] and timeout['passed'] and qnx['qnx_smoke_passed'],'all checks required')
    require(sha((HERE/'artwork-hooks.S').read_bytes())==dm['source_sha256']==dt['source_sha256'],'stale ARM source')
    require(sha((HERE/'build-driver.py').read_bytes())==dm['builder_sha256']==dt['builder_sha256'],'stale driver builder')
    require(sha((HERE/'snapshot.c').read_bytes())==rm['source_sha256']==timeout['source_sha256'],'stale helper source')
    require(qnx['helper_source_sha256']==rm['source_sha256'],'stale QNX helper source')
    require(qnx['smoke_source_sha256']==sha((HERE/'qnx-smoke.c').read_bytes()),'stale QNX smoke source')
    require(qnx['test_sha256']==sha((HERE/'test-qnx.py').read_bytes()),'stale QNX runner')
    require(qnx['base_test_sha256']==sha((HERE.parents[1]/'route-guidance/test-observer-qnx.py').read_bytes()),'stale base QNX runner')
    require(sha((HERE/'test-driver.py').read_bytes())==dt['test_sha256'],'stale ARM tests')
    require(sha((HERE/'test-timeout.py').read_bytes())==timeout['test_sha256'],'stale timeout test')
    for name,digest in ct['sources'].items():require(sha((HERE/name).read_bytes())==digest,'stale controller check: '+name)
    qlog=a.qnx.parent/'qemu.log'
    require(b'N2_QNX_PASS valid_schema_short_read_and_lock' in qlog.read_bytes(),'QNX marker missing')
    build='MU1427-AUDIO-N2-'+sha(driver+reader)[:12]
    require(ct['build']==build,'controller build differs')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);stage=out/'sd-card'
    with zipfile.ZipFile(a.n1_package) as z:
        require(all(not n.startswith('/') and '..' not in Path(n).parts for n in z.namelist()),'unsafe archive path')
        z.extractall(stage)
        for info in z.infolist():
            mode=(info.external_attr>>16)&0o777
            if mode:(stage/info.filename).chmod(mode)
        baseline={n:sha(z.read(n)) for n in z.namelist() if not n.endswith('/')}
    payload=stage/'Custom/carplay_audio_n2';payload.mkdir()
    (payload/'ipod-drvr-iap2.so').write_bytes(driver);(payload/'snapshot').write_bytes(reader)
    (payload/'snapshot').chmod(0o755);(payload/'VERSION').write_text(build+'\n')
    text=(HERE/'control.sh').read_text()
    for k,v in {'BUILD':build,'DRIVER_SIZE':str(len(driver)),'READER_SIZE':str(len(reader))}.items():text=text.replace('@'+k+'@',v)
    scripts=stage/'Toolbox/scripts';(scripts/'cpmap_audio_n2.sh').write_text(text)
    prefix='''#!/bin/ksh
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && { [ ! -s /ifs/lsd.jxe ] || [ ! -d /mnt/app ]; }; then M=/net/mmx; fi
S=$M/mnt/app/carplay-artwork-n2/control.sh
[ -s "$S" ] || S=$M/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_audio_n2.sh
'''
    sd='''VOL=${CPMAP_TEST_SD:-}
if [ -z "$VOL" ]; then
    for V in /net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0; do
        if [ -s "$V/Custom/carplay_audio_n2/VERSION" ]; then VOL=$V; break; fi
    done
fi
[ -n "$VOL" ] || { echo CPMAP_AUDIO_N2_FAIL=SD_PAYLOAD_NOT_FOUND; exit 1; }
'''
    export='''if [ -z "${CPMAP_TEST_ROOT:-}" ]; then
    case "$VOL" in /net/mmx/*) on -f mmx mount -uw "${VOL#/net/mmx}" >/dev/null 2>&1 ;;
        *) mount -uw "$VOL" >/dev/null 2>&1 ;; esac
fi
[ ! -L "$VOL/Log" ] || exit 1
mkdir -p "$VOL/Log" || exit 1
for I in 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16; do
    OUT=$VOL/Log/cpmap-audio-N2-$I
    if [ ! -e "$OUT" ] && [ ! -L "$OUT" ]; then /bin/ksh "$S" export "$OUT"; exit $?; fi
done
echo CPMAP_AUDIO_N2_FAIL=EXPORT_SLOTS_FULL_PRESERVE_OLD_EXPORTS
exit 1
'''
    actions={'install':prefix+sd+'/bin/ksh "$S" install "$VOL/Custom/carplay_audio_n2"\n',
             'status':prefix+'/bin/ksh "$S" status\n',
             'export':prefix+sd+export,'remove':prefix+'/bin/ksh "$S" uninstall\n'}
    labels={'install':'Install N2 artwork observer (MU1427, reboot)',
            'status':'Show N2 artwork observer installation',
            'export':'Export N2 artwork snapshot to SD',
            'remove':'Remove N2 artwork observer (restore B4, reboot)'}
    menu='\n# N2 native artwork observer; preserves tested N1 text\n'
    for action,content in actions.items():
        script=scripts/('cpmap_audio_n2_'+action+'.sh');script.write_text(content);script.chmod(0o755)
        subprocess.run(['/bin/ksh','-n',str(script)],check=True)
        menu+='\nscript\n    value   sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/'+script.name+'"\n    label   "'+labels[action]+'"\n'
    (scripts/'cpmap_audio_n2.sh').chmod(0o755)
    subprocess.run(['/bin/ksh','-n',str(scripts/'cpmap_audio_n2.sh')],check=True)
    gem=stage/'Toolbox/GEM/carplay-maps-vc.esd';original=gem.read_bytes()
    gem.write_bytes(original+menu.encode().replace(b'\n',b'\r\n' if b'\r\n' in original else b'\n'))
    for name,digest in baseline.items():
        if name!='Toolbox/GEM/carplay-maps-vc.esd':require(sha((stage/name).read_bytes())==digest,'N1 bundle changed: '+name)
    shutil.copy2(AUDIO/'TEST-N2.md',stage/'AUDIO_N2_TEST.md')
    source=payload/'source';shutil.copytree(HERE,source,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copy2(AUDIO.parents[1]/'LICENSE',source/'LICENSE')
    record={'build':build,'image_output':False,'n1_package_sha256':N1_SHA,'driver':dm,'reader':rm,
            'driver_tests':dt,'controls':ct,'timeout':timeout,'qnx':qnx,
            'qnx_smoke_source_sha256':sha((HERE/'qnx-smoke.c').read_bytes()),
            'qnx_log_sha256':sha(qlog.read_bytes()),
            'sources':{str(f.relative_to(source)):sha(f.read_bytes()) for f in source.rglob('*') if f.is_file()},
            'preserved_n1_files':baseline,'on_unit_validated':False}
    (payload/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    archive=out/'CarPlay_Maps_VC_MU1427_Audio_N2_Test.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(stage.rglob('*')):
            if f.is_file():z.write(f,str(f.relative_to(stage)))
    with zipfile.ZipFile(archive) as z:
        require(z.read('Custom/carplay_audio_n1/CarPlayNowPlayingTextN1.jar')==
                (stage/'Custom/carplay_audio_n1/CarPlayNowPlayingTextN1.jar').read_bytes(),'N1 archive payload')
        require(sha(z.read('Custom/carplay_audio_n2/ipod-drvr-iap2.so'))==sha(driver),'N2 archive payload')
    digest=sha(archive.read_bytes());(out/'SHA256SUMS.txt').write_text(digest+'  '+archive.name+'\n')
    record.update(archive_sha256=digest,preserved_n1_file_count=len(baseline)-1)
    (out/'verification.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'archive':str(archive),'sha256':digest,'build':build,'preserved_n1_files':len(baseline)-1}))


if __name__=='__main__':main()
