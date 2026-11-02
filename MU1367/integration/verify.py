#!/usr/bin/env python3
"""Verify the v1.4.3 combined K4525/P4521 package and its installation evidence."""
import argparse,hashlib,json,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('package','tested-package','preflight','filesystem','p4521','qnx'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();sd=a.package/'sd-card';m=read(a.package/'manifest.json')
    prior=read(HERE/'evidence/release-v1.4.2.json');runtime=read(HERE/'RUNTIME.json')['rebuild']
    assert prior['passed'] and prior['version']=='1.4.2'
    assert runtime==prior['runtime_rebuild']
    assert m['version']=='1.4.3' and m['guidance_build']=='MU1367-guidance-v1.4.2'
    assert m['supported_firmware']==[{'train':'MHI2_ER_VWG13_K4525','experimental':False},{'train':'MHI2_ER_VWG13_P4521','experimental':True}]
    assert m['p4521_prior_experimental_vehicle_tested'] and m['p4521_final_package_vehicle_tested'] is False
    assert m['defaults']=={'fps':30,'idr':5,'cards':False,'safe_area':[200,96,400,364]}
    proofs={name:read(getattr(a,name)) for name in ('filesystem','p4521','qnx','preflight')}
    for name,result in proofs.items():assert result['passed'],name
    assert proofs['filesystem']['tests']==11 and proofs['p4521']['tests']==3
    tested=read(a.tested_package/'manifest.json')
    for name in ('filesystem','p4521'):assert proofs[name]['archive_sha256']==tested['archive_sha256']
    assert proofs['preflight']['passed'] and proofs['preflight']['tests']==1 and proofs['preflight']['archive_sha256']==m['archive_sha256']
    before=a.tested_package/'sd-card'
    differences=[str(f.relative_to(sd)) for f in sd.rglob('*') if f.is_file() and f.read_bytes()!=(before/f.relative_to(sd)).read_bytes()]
    assert set(differences)=={'START_HERE.md','FILES_SHA256.json'},differences
    assert proofs['qnx']['factory_migration_verified'] and proofs['qnx']['firmware_train_recognition_verified']
    assert proofs['qnx']['sdk_utilities_injected'] is False and proofs['qnx']['actual_qnx_ksh']
    assert proofs['qnx']['main_controller_sha256']==sha(sd/'Custom/carplay_mu1367_guidance_v3/6/control.sh')
    assert proofs['qnx']['map_only_actions_sha256']==sha(sd/'Custom/carplay_mu1367_guidance_v3/actions.sh')
    assert proofs['qnx']['tuning_controller_sha256']==sha(sd/'Custom/carplay_mu1367_v3_turn_cards/6/control.sh')
    factory=read(HERE/'evidence/p4521-factory.json');extraction=read(HERE/'evidence/p4521-extraction.json');commands=read(HERE/'evidence/p4521-commands.json')
    assert extraction['firmware']==factory['firmware']
    for variant in ('50','70'):
        assert extraction['variants'][variant]=={key:factory[key] for key in ('files','stage1_runtime','stage2_runtime')}
        assert commands['variants'][variant]==proofs['qnx']['factory_utilities_sha256']
    assert sha(sd/'P4521_FACTORY.json')==sha(HERE/'evidence/p4521-factory.json')
    for variant,entry in m['variants'].items():
        folder=sd/'Custom/carplay_mu1367_guidance_v3'/variant
        for key,name,path in [('core','core.so','base/core.so'),('menu','VCMenu.jar','base/VCMenu.jar'),('guidance','CarPlayMU1367Guidance.jar','CarPlayMU1367Guidance.jar')]:
            assert sha(folder/name)==entry['files'][key]==runtime[path]
        folder=sd/'Custom/carplay_mu1367_v3_turn_cards'/variant
        for name in ('core.so','VCMenu.jar'):assert sha(folder/name)==runtime['tuning/'+name]
    assert sha(sd/'Custom/carplay_mu1367_artwork/CarPlayMU1367Audio.jar')==runtime['CarPlayMU1367Audio.jar']
    assert sha(sd/'Custom/carplay_mu1367_artwork/ipod-drvr-iap2.so')==read(HERE/'evidence/release-v1.4.1.json')['evidence']['driver']['result']['driver_sha256']
    reset=sd/'Custom/carplay_mu1367_oem_reset/control.sh';assert sha(reset)==prior['oem_reset_sha256']==proofs['qnx']['controller_sha256']
    legacy=read(HERE/'tools/legacy-revisions.json')
    for revision in ('release-v1.4.1','release-v1.4.2'):
        entries=[(h,record) for h,record in legacy.items() if record['revision']==revision];assert len(entries)==8
        for h,record in entries:
            fixture=HERE/'tests/revisions'/revision/record['layer']/record['variant']
            assert sha(fixture/'control.sh')==h and h in (sd/'Custom/carplay_mu1367_guidance_v3/legacy-check.sh').read_text()
    archive=a.package/m['archive_name'];assert sha(archive)==m['archive_sha256']
    inventory=read(sd/'FILES_SHA256.json')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(inventory)+1
        for name,h in inventory.items():assert sha(sd/name)==h==hashlib.sha256(z.read(name)).hexdigest(),name
    assert 'MU1367-guidance-v1.4.2' in (sd/'START_HERE.md').read_text()
    assert 'MU1367-guidance-v1.4.3' not in (sd/'START_HERE.md').read_text()
    assert '1_4_3_INSTALLED' in (sd/'Custom/carplay_mu1367_guidance_v3/actions.sh').read_text()
    assert 'P4521' in (sd/'START_HERE.md').read_text() and 'remains experimental' in (sd/'START_HERE.md').read_text()
    result={'passed':True,'version':'1.4.3','archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'inventory_checks':len(inventory),'files':m['files'],'runtime_rebuild':runtime,'runtime_changed':[],
            'guidance_build':m['guidance_build'],'supported_firmware':m['supported_firmware'],'prior_p4521_experimental_vehicle_tested':True,'prior_p4521_vehicle_report_date':'2026-11-02','final_package_vehicle_tested':False,
            'factory_arm_j9_guidance_evidence_reused':True,'factory_qnx_release_migration_verified':True,'p4521_factory_shell_train_detection_verified':True,'p4521_factory_variants_verified':['50','70'],
            'filesystem_test_environment':'Disposable Debian 12 aarch64 container, Python 3.11, ksh93; network disconnected; Mac P4521-specific and final-preflight proofs retained separately.',
            'tests':{'filesystem':11,'p4521_install_and_identity':3,'final_archive_preflight':1,'integrated_release_migration_variants':16,'older_test_revision_migrations':8,'factory_commands_per_variant':17},
            'defaults':m['defaults'],'new_unit_commands':[],'oem_reset_sha256':sha(reset),'prior_release_verification_sha256':sha(HERE/'evidence/release-v1.4.2.json'),
            'runtime_evidence':'All six runtime payloads match v1.4.2 exactly; its native, host-guidance and ARM/J9 runtime proofs are retained in evidence/release-v1.4.2.json. Installation/firmware recognition and migration were freshly tested.',
            'limits':['P4521 installation remains experimental; prior experimental vehicle success does not establish final combined-package acceptance.','Separate P4521 packages and dormant upstream menus require the documented OEM reset/reboot before installation.','Mounts are mocked; physical storage/power-loss durability is not established.','Existing Mini Pico card override and navigation-app limits remain.'],
            'verification_script_sha256':sha(Path(__file__)),'final_vs_full_tested_package_differences':differences,
            'evidence':{name:{'sha256':sha(getattr(a,name)),'result':result} for name,result in proofs.items()},
            'firmware_evidence_sha256':{name:sha(HERE/'evidence'/name) for name in ('p4521-factory.json','p4521-extraction.json','p4521-commands.json')},
            'source_sha256':{str(f.relative_to(HERE)):sha(f) for top in ('src','tools','tests') for f in sorted((HERE/top).rglob('*')) if f.is_file() and f.name!='verify' and '__pycache__' not in f.parts}}
    (HERE/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':True,'archive_sha256':sha(archive),'inventory_checks':len(inventory)}))
if __name__=='__main__':main()
