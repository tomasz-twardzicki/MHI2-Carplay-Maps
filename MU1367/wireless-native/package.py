#!/usr/bin/env python3
"""Seal a tested local wireless candidate; never upload or publish it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
from archive_fix import apply as fix_archive_names
from diagnostics import add as add_wireless_diagnostics

HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('build','qnx-result','archive-result','baseline-zip','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    m=json.loads((a.build/'manifest.json').read_text());q=json.loads(a.qnx_result.read_text())
    assert q['passed'] and q['build_id']==m['build_id']
    assert q['rollback_cases']==q['resume_cases']==q['commit_sites']==len(m['rows'])
    native=json.loads((a.build/'native-check.json').read_text());assert native['passed'] and not native['missing']
    assert native['supervisor_sha256']==next(r['sha256'] for r in m['rows'] if r['source']=='carplay-cluster-supervisor')
    assert sha(a.baseline_zip.read_bytes())==m['baseline_zip_sha256']
    alt_gate=json.loads((HERE/'RECEIVER-ALT-GATE.json').read_text())
    assert alt_gate['passed'] and alt_gate['receiver_sha256']==next(r['sha256'] for r in m['rows'] if r['source']=='wcp_receiver')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    sd=out/'sd-card';shutil.copytree(a.build/'sd-card',sd)
    diagnostics=add_wireless_diagnostics(sd)
    archive_fix=fix_archive_names(sd)
    archive_test=json.loads(a.archive_result.read_text())
    assert archive_test['passed'] and archive_test['changes']==archive_fix
    # Root shortcuts must enforce the same recovery order as the Green Menu.
    guard='\nW=${CPMAP_TEST_ROOT:-}\nif [ -z "$W" ] && [ ! -s /ifs/lsd.jxe ];then W=/net/mmx;fi\nif [ -s "$W/mnt/app/carplay-mu1367-wireless-native/STATE" ] && [ "$(cat "$W/mnt/app/carplay-mu1367-wireless-native/STATE")" != removed ];then\n echo REMOVE_OR_RECOVER_WIRELESS_LAYER_AND_REBOOT_FIRST\n exit 1\nfi\n'
    for name in ('RUN_INSTALL.sh','RUN_RESTORE.sh','RUN_RESET_SETTINGS.sh'):
        script=sd/name
        text=script.read_text();assert text.count('set -u\n')==1
        script.write_text(text.replace('set -u\n','set -u\n'+guard))
    (sd/'START_HERE.md').rename(sd/'BASELINE_START_HERE.md')
    (sd/'RELEASE-NOTES.md').rename(sd/'BASELINE_RELEASE_NOTES.md')
    for name in ('README.md','FILES_SHA256.json','MU1367_RELEASE_MANIFEST.json'):
        (sd/name).rename(sd/('BASELINE_'+name))
    (sd/'README.md').write_text('# MU1367 / AID 791 v1.6.0-e test1\n\nExperimental native wireless connection/video layer over v1.5.3. Read [START_HERE.md](START_HERE.md) before installation. Wireless guidance, media text and artwork remain pending. No vehicle wireless test is claimed.\n\nThe original stable runtime binaries and documentation are retained; see [BASELINE_README.md](BASELINE_README.md). The base installer has a factory-QNX-tested fix for retained-snapshot archive names colliding after PID reuse. Existing snapshots are preserved. WIRELESS-FILES.sha256 covers the complete candidate. BASELINE_FILES_SHA256.json describes the original v1.5.3 archive only.\n')
    (sd/'BASELINE_README.md').write_text((sd/'BASELINE_README.md').read_text().replace('](START_HERE.md)','](BASELINE_START_HERE.md)').replace('](RELEASE-NOTES.md)','](BASELINE_RELEASE_NOTES.md)'))
    (sd/'START_HERE.md').write_text((HERE/'TEST-PACKAGE.md').read_text())
    (sd/'RELEASE-NOTES.md').write_text('# MU1367 v1.6.0-e test1\n\nExperimental native wireless connection/video layer over the exact v1.5.3 baseline. Read START_HERE.md before enabling it. Wireless guidance, media text and artwork remain pending. No on-car wireless result is claimed.\n\nThe original stable release notes are in BASELINE_RELEASE_NOTES.md.\n')
    # The stable documentation retains a valid link to its own release notes.
    base=(sd/'BASELINE_START_HERE.md').read_text().replace('](RELEASE-NOTES.md)','](BASELINE_RELEASE_NOTES.md)')
    (sd/'BASELINE_START_HERE.md').write_text(base)
    (sd/'WIRELESS_VERSION').write_text(m['version']+'\n')
    source=sd/'Custom/carplay_mu1367_wireless_native/source'
    shutil.copytree(a.build/'native/src',source/'native')
    shutil.copytree(HERE/'tests',source/'tests',ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('build.py','package.py','archive_fix.py','diagnostics.py','collect-wireless.sh','gem-collect-wireless.sh','enable-alt-probe.sh','TEST-PACKAGE.md','P4521-COMPATIBILITY.json','RECEIVER-ALT-GATE.json','VEHICLE-30117947.md'):shutil.copy2(HERE/name,source/name)
    m['installation_tested']=True
    m['installation_test_scope']='Factory-QNX isolated transaction fixture; seeded v1.5.3 installed bytes, substituted fixture JXE gate; no vehicle installation.'
    (sd/'Custom/carplay_mu1367_wireless_native/manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    (sd/'MU1367_RELEASE_MANIFEST.json').write_text(json.dumps(dict(version=m['version'],experimental=True,prerelease=True,base_version='1.5.3',base_archive_sha256=m['baseline_zip_sha256'],build_id=m['build_id'],on_unit_validated=False,wireless_information_features_integrated=False,verification='WIRELESS-VERIFICATION.json',baseline_manifest='BASELINE_MU1367_RELEASE_MANIFEST.json'),indent=2)+'\n')
    verification=dict(version=m['version'],build_id=m['build_id'],wireless_diagnostics=diagnostics,base_installer_archive_fix=archive_test,qnx=q,native=native,firmware=json.loads((HERE/'FIRMWARE-VERIFICATION.json').read_text()),p4521=json.loads((HERE/'P4521-COMPATIBILITY.json').read_text()),on_unit_validated=False,wireless_information_features_integrated=False,native_menu_switch_integrated=False)
    verification['alternate_display_gate']=alt_gate
    (sd/'WIRELESS-VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n')
    # Check all existing runtime payload bytes against the published baseline.
    differences=[]
    with zipfile.ZipFile(a.baseline_zip) as z:
        for item in z.infolist():
            if item.is_dir():continue
            target=sd/item.filename
            if not target.exists() or target.read_bytes()!=z.read(item):differences.append(item.filename)
    allowed=lambda n:n in archive_fix or n in ('START_HERE.md','RELEASE-NOTES.md','README.md','FILES_SHA256.json','MU1367_RELEASE_MANIFEST.json','RUN_INSTALL.sh','RUN_RESTORE.sh','RUN_RESET_SETTINGS.sh') or n.startswith('Toolbox/scripts/cpmap_suite_')
    assert all(allowed(n) for n in differences),differences
    assert {n for n in differences if n.startswith('Custom/')}==set(archive_fix)
    guarded=[]
    with tempfile.TemporaryDirectory(prefix='mu1367-wireless-guard-') as fixture:
        state=Path(fixture)/'mnt/app/carplay-mu1367-wireless-native/STATE'
        state.parent.mkdir(parents=True);state.write_text('installed\n')
        for name in differences:
            script=sd/name
            if script.suffix!='.sh' or name in archive_fix:continue
            subprocess.run(['/bin/sh','-n',str(script)],check=True)
            result=subprocess.run(['/bin/sh',str(script)],env=dict(os.environ,CPMAP_TEST_ROOT=fixture),capture_output=True,text=True)
            assert result.returncode==1 and result.stdout.strip()=='REMOVE_OR_RECOVER_WIRELESS_LAYER_AND_REBOOT_FIRST',(name,result)
            assert state.read_text()=='installed\n'
            guarded.append(name)
    verification['guarded_base_actions_checked']=guarded
    verification['baseline_differences']=differences
    (sd/'WIRELESS-VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n')
    files={str(f.relative_to(sd)):sha(f.read_bytes()) for f in sorted(sd.rglob('*')) if f.is_file()}
    (sd/'WIRELESS-FILES.sha256').write_text(''.join(h+'  '+n+'\n' for n,h in files.items()))
    files['WIRELESS-FILES.sha256']=sha((sd/'WIRELESS-FILES.sha256').read_bytes())
    archive=out/'CarPlay_Maps_VC_MU1367_791_v1.6.0-e-test1.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in sorted(files):
            f=sd/name;entry=zipfile.ZipInfo(name,(2026,11,17,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
            executable=f.suffix=='.sh' or f.name in ('verify','config-patch')
            entry.external_attr=(0o100755 if executable else 0o100644)<<16
            z.writestr(entry,f.read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(set(z.namelist()))==len(files)
        assert {n:sha(z.read(n)) for n in z.namelist()}==files
        assert z.testzip() is None
    h=sha(archive.read_bytes())
    (out/'SHA256SUMS.txt').write_text(h+'  '+archive.name+'\n')
    report=dict(passed=True,version=m['version'],build_id=m['build_id'],archive=archive.name,archive_sha256=h,files=len(files),wireless_diagnostics=diagnostics,baseline_runtime_binaries_byte_identical=True,base_installer_archive_fix=archive_test,baseline_differences=differences,guarded_base_actions_checked=guarded,zip_readback_verified=True,on_unit_validated=False)
    (out/'PACKAGE-VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
    shutil.copy2(HERE/'TEST-PACKAGE.md',out/'START_HERE.md')
    shutil.copy2(sd/'WIRELESS-VERIFICATION.json',out/'WIRELESS-VERIFICATION.json')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
