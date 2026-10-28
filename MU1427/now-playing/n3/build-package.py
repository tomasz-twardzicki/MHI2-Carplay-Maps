#!/usr/bin/env python3
"""Append the verified N3 diagnostic to the immutable accepted N1 toolbox.
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
RG=HERE.parents[1]/'route-guidance'
REPO=HERE.parents[2]
N1_SHA='5bf9d571d85eee87ae9a6a7a166849ab2b83c22a84aa4cd02adc2aff9afd409d'
def sha(data):return hashlib.sha256(data).hexdigest()
def require(value,why):
    if not value:raise ValueError(why)
def check_sources(record):
    for name,digest in record['sources'].items():
        require(sha((HERE/name).read_bytes())==digest,'stale source: '+name)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('n1-package','driver','reader','driver-tests','worker-tests','controls','qnx','output'):
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();driver=a.driver.read_bytes();reader=(a.reader/'rgi-observer').read_bytes()
    dm=json.loads(a.driver.with_suffix('.json').read_text());rm=json.loads((a.reader/'manifest.json').read_text())
    dt=json.loads(a.driver_tests.read_text());wt=json.loads(a.worker_tests.read_text())
    ct=json.loads(a.controls.read_text());qt=json.loads(a.qnx.read_text())
    require(sha(a.n1_package.read_bytes())==N1_SHA,'accepted N1 package required')
    require(sha(driver)==dm['driver_sha256']==dt['driver_sha256']==ct['driver_sha256'],'driver evidence mismatch')
    require(sha(reader)==rm['sha256']==ct['helper_sha256']==qt['reader_sha256'],'worker evidence mismatch')
    require(dt['passed'] and wt['passed'] and ct['passed'] and qt['qnx_smoke_passed'],'all checks required')
    for record in (dt,wt,ct,qt,rm):check_sources(record)
    require(dm['source_sha256']==sha((HERE/'artwork-hooks.S').read_bytes()),'stale driver source')
    require(dm['builder_sha256']==sha((HERE/'build-driver.py').read_bytes()),'stale driver builder')
    require(rm['source_sha256']==sha((HERE/'capture.c').read_bytes()),'stale worker build')
    require(rm['base_builder_sha256']==sha((RG/'build-observer.py').read_bytes()),'stale native builder')
    require(qt['base_test_sha256']==sha((RG/'test-observer-qnx.py').read_bytes()),'stale QNX runner')
    qlog=a.qnx.parent/'qemu.log'
    require(b'N3_QNX_PASS PNG_JPEG_decode_original_bytes_empty_schema_short_read_lock' in qlog.read_bytes(),'QNX marker missing')
    build='MU1427-AUDIO-N3-'+sha(driver+reader)[:12]
    require(ct['build']==build,'controller build mismatch')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);stage=out/'sd-card'
    with zipfile.ZipFile(a.n1_package) as z:
        require(all(not n.startswith('/') and '..' not in Path(n).parts for n in z.namelist()),'unsafe archive path')
        z.extractall(stage)
        for info in z.infolist():
            mode=(info.external_attr>>16)&0o777
            if mode:(stage/info.filename).chmod(mode)
        baseline={i.filename:{'sha256':sha(z.read(i.filename)),'mode':(i.external_attr>>16)&0o777}
            for i in z.infolist() if not i.is_dir()}
    payload=stage/'Custom/carplay_audio_n3';payload.mkdir()
    (payload/'ipod-drvr-iap2.so').write_bytes(driver);(payload/'snapshot').write_bytes(reader)
    (payload/'snapshot').chmod(0o755);(payload/'VERSION').write_text(build+'\n')
    text=(HERE/'control.sh').read_text()
    for k,v in {'BUILD':build,'DRIVER_SIZE':str(len(driver)),'READER_SIZE':str(len(reader))}.items():
        text=text.replace('@'+k+'@',v)
    scripts=stage/'Toolbox/scripts';(scripts/'cpmap_audio_n3.sh').write_text(text)
    prefix='''#!/bin/ksh
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && { [ ! -s /ifs/lsd.jxe ] || [ ! -d /mnt/app ]; }; then M=/net/mmx; fi
S=$M/mnt/app/carplay-artwork-n3/control.sh
[ -s "$S" ] || S=$M/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_audio_n3.sh
'''
    sd='''VOL=${CPMAP_TEST_SD:-}
if [ -z "$VOL" ]; then
    for V in /net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0; do
        if [ -s "$V/Custom/carplay_audio_n3/VERSION" ]; then VOL=$V; break; fi
    done
fi
[ -n "$VOL" ] || { echo CPMAP_AUDIO_N3_FAIL=SD_PAYLOAD_NOT_FOUND; exit 1; }
'''
    export='''if [ -z "${CPMAP_TEST_ROOT:-}" ]; then
    case "$VOL" in /net/mmx/*) on -f mmx mount -uw "${VOL#/net/mmx}" >/dev/null 2>&1 ;;
        *) mount -uw "$VOL" >/dev/null 2>&1 ;; esac
fi
[ ! -L "$VOL/Log" ] || exit 1
mkdir -p "$VOL/Log" || exit 1
for I in 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16; do
    OUT=$VOL/Log/cpmap-audio-N3-$I
    if [ ! -e "$OUT" ] && [ ! -L "$OUT" ]; then /bin/ksh "$S" export "$OUT"; exit $?; fi
done
echo CPMAP_AUDIO_N3_FAIL=EXPORT_SLOTS_FULL_PRESERVE_OLD_EXPORTS
exit 1
'''
    actions={
        'remove_n2':prefix+'''OLD=$M/mnt/app/carplay-artwork-n2/control.sh
[ -s "$OLD" ] || { echo CPMAP_AUDIO_N3_FAIL=N2_SAVED_CONTROLLER_MISSING; exit 1; }
/bin/ksh "$OLD" uninstall
''',
        'install':prefix+sd+'/bin/ksh "$S" install "$VOL/Custom/carplay_audio_n3"\n',
        'status':prefix+'/bin/ksh "$S" status\n',
        'export':prefix+sd+export,'remove':prefix+'/bin/ksh "$S" uninstall\n'}
    labels={'remove_n2':'Remove installed N2 (then reboot before N3)',
        'install':'Install N3 artwork capture (MU1427, reboot)',
        'status':'Show N3 artwork capture installation',
        'export':'Export N3 artwork image to SD',
        'remove':'Remove N3 artwork capture (restore B4, reboot)'}
    menu='\n# N3 artwork image diagnostic; retains accepted N1 text\n'
    for action,content in actions.items():
        f=scripts/('cpmap_audio_n3_'+action+'.sh');f.write_text(content);f.chmod(0o755)
        subprocess.run(['/bin/ksh','-n',str(f)],check=True)
        menu+='\nscript\n    value   sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/'+f.name+'"\n    label   "'+labels[action]+'"\n'
    (scripts/'cpmap_audio_n3.sh').chmod(0o755)
    subprocess.run(['/bin/ksh','-n',str(scripts/'cpmap_audio_n3.sh')],check=True)
    gem=stage/'Toolbox/GEM/carplay-maps-vc.esd';original=gem.read_bytes()
    gem.write_bytes(original+menu.encode().replace(b'\n',b'\r\n' if b'\r\n' in original else b'\n'))
    shutil.copy2(AUDIO/'TEST-N3.md',stage/'AUDIO_N3_TEST.md')
    source=payload/'source';ignore=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store')
    for name in ('n2','n3'):
        shutil.copytree(AUDIO/name,source/'MU1427/now-playing'/name,ignore=ignore)
    shutil.copy2(AUDIO/'TEST-N3.md',source/'MU1427/now-playing/TEST-N3.md')
    # Keep the relative paths used by the native patcher and QNX runners.
    # Only maintained repository sources enter this dependency snapshot.
    tracked=subprocess.check_output(['git','-C',str(REPO),'ls-files','--','MU1427/route-guidance'],text=True).splitlines()
    for name in tracked:
        f=REPO/name
        if not f.is_file():continue
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
    shutil.copy2(REPO/'LICENSE',source/'LICENSE')
    record={'build':build,'cluster_picture_output':False,'track_identity_verified':False,
        'n1_package_sha256':N1_SHA,'driver':dm,'reader':rm,'driver_tests':dt,'worker_tests':wt,
        'controls':ct,'qnx':qt,'qnx_log_sha256':sha(qlog.read_bytes()),
        'sources':{str(f.relative_to(source)):sha(f.read_bytes()) for f in sorted(source.rglob('*')) if f.is_file()},
        'preserved_n1_files':baseline,'on_unit_validated':False}
    (payload/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    archive=out/'CarPlay_Maps_VC_MU1427_Audio_N3_Test.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(stage.rglob('*')):
            if f.is_file():z.write(f,str(f.relative_to(stage)))
    with zipfile.ZipFile(archive) as z:
        for name,meta in baseline.items():
            content=z.read(name)
            if name=='Toolbox/GEM/carplay-maps-vc.esd':require(content.startswith(original),'base menu changed')
            else:require(sha(content)==meta['sha256'],'N1 file changed: '+name)
            require(((z.getinfo(name).external_attr>>16)&0o777)==meta['mode'],'N1 mode changed: '+name)
        require(sha(z.read('Custom/carplay_audio_n3/ipod-drvr-iap2.so'))==sha(driver),'archive driver')
        require(sha(z.read('Custom/carplay_audio_n3/snapshot'))==sha(reader),'archive worker')
    digest=sha(archive.read_bytes());(out/'SHA256SUMS.txt').write_text(digest+'  '+archive.name+'\n')
    record.update(archive_sha256=digest,preserved_n1_file_count=len(baseline)-1)
    (out/'verification.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'archive':str(archive),'sha256':digest,'build':build,'preserved_n1_files':len(baseline)-1}))

if __name__=='__main__':main()
