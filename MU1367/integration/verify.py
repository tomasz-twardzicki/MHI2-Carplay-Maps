#!/usr/bin/env python3
"""Verify experimental v1.4.4-e, its v1.4.3-e baseline and exact tested artifacts."""
import argparse,hashlib,json,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE_SHA='3ecb5304c8a9e85c43a01dd532dfc5c920c3e1a866321a7c1d667d750260afa5'
# The five v1.4.3-e runtime payloads that v1.4.4-e must leave byte-identical.
UNCHANGED={'CarPlayMU1367Audio.jar':'c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3','base/core.so':'edf7fd6ed4371e8530a6a6f3278b9574735d661e18f143c8f0459daa5619e3a5','base/VCMenu.jar':'1fb90298ddccdcad00bcfe9deb752d4da0f00e02e3fcac704bbc2ae9b2ef5c37','tuning/core.so':'74ab9299cb22a1be29ad7697f6920330c6c07e416aebc7e68fa42ace2cdb30e6','tuning/VCMenu.jar':'8e628647fedc4d798aeecb0c41ac0d17a4d575d9bf559c439565b5989046487d'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','base-archive','filesystem','p4521','p4521-inputs','p4521-native','qnx','reader-build','reader-host','reader-qnx','reader-transactions','guidance','guidance-rebuild','guidance-qnx','preflight'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();sd=a.package/'sd-card';m=read(a.package/'manifest.json');runtime=read(HERE/'RUNTIME.json')['rebuild'];reader_pin=read(HERE/'READER-RUNTIME.json')
 assert m['version']=='1.4.4-e' and m['experimental'] and m['prerelease'] and m['base_version']=='1.4.3-e'
 for name,h in UNCHANGED.items():assert runtime[name]==h,name
 assert sha(a.base_archive)==m['base_archive_sha256']==BASE_SHA
 assert m['guidance_build']=='MU1367-guidance-v1.4.4-e' and m['reader_build']=='MU1367-reader-v1.4.4-e'
 assert m['guidance_hold_ms']==180000 and m['reader_restart_budget']=={'per_window':3,'stable_window_ms':600000,'lifetime_ceiling':64,'backoff_ms':[1000,2000,4000]}
 assert m['reader_sha256']==reader_pin['sha256'] and m['reader_source_sha256']==sha(HERE/'src/reader/reader.c')==reader_pin['source_sha256']
 assert m['supported_firmware']==[{'train':'MHI2_ER_VWG13_K4525','experimental':False},{'train':'MHI2_ER_VWG13_P4521','experimental':True}]
 assert m['release_package_vehicle_tested'] is False and m['p4521_final_package_vehicle_tested'] is False
 assert m['defaults']=={'fps':30,'idr':5,'cards':False,'safe_area':[200,96,400,364]}
 names=('filesystem','p4521','qnx','reader_host','reader_qnx','reader_transactions','guidance','guidance_rebuild','guidance_qnx','preflight','p4521_native')
 proofs={n:read(getattr(a,n)) for n in names}
 for n,r in proofs.items():assert r['passed'],n
 assert proofs['filesystem']['tests']>=11 and proofs['p4521']['tests']==3 and proofs['reader_host']['tests']==20 and proofs['reader_transactions']['tests']==3
 for n in ('filesystem','p4521','reader_transactions'):assert proofs[n]['archive_sha256']==m['archive_sha256'],n
 build=read(a.reader_build/'manifest.json');assert build['passed'] and build['sha256']==m['reader_sha256']==sha(a.reader_build/'rgi-observer')
 assert build['source_sha256']==proofs['reader_host']['reader_source_sha256']==m['reader_source_sha256']
 assert proofs['reader_qnx']['reader_sha256']==m['reader_sha256'] and proofs['reader_qnx']['native_timeout_and_recovery'] and proofs['reader_qnx']['new_nonce_verified']
 assert proofs['reader_host']['guidance_sha256']==proofs['guidance']['guidance_sha256']==proofs['guidance_rebuild']['guidance_sha256']==proofs['guidance_qnx']['guidance_sha256']==runtime['CarPlayMU1367Guidance.jar']
 assert proofs['guidance_qnx']['factory_arm_j9_verified'] and proofs['guidance_qnx']['modes']==['noverify','verify']
 assert 'TestQuietHold' in proofs['guidance']['results']
 for name,h in proofs['guidance_rebuild']['source_sha256'].items():assert sha(HERE/name)==h,name
 assert sha(HERE/'tests/test-reader.py')==proofs['reader_host']['test_sha256']
 assert sha(HERE/'tests/test-reader-qnx.py')==proofs['reader_qnx']['test_sha256']
 assert proofs['qnx']['factory_migration_verified'] and proofs['qnx']['firmware_train_recognition_verified'] and proofs['qnx']['actual_qnx_ksh']
 assert proofs['qnx']['sdk_utilities_injected'] is False
 main=sd/'Custom/carplay_mu1367_guidance_v3';tuning=sd/'Custom/carplay_mu1367_v3_turn_cards'
 assert proofs['qnx']['map_only_actions_sha256']==sha(main/'actions.sh')
 assert proofs['qnx']['main_controller_sha256']==sha(main/'6/control.sh')
 assert proofs['qnx']['tuning_controller_sha256']==sha(tuning/'6/control.sh')
 assert proofs['qnx']['controller_sha256']==sha(sd/'Custom/carplay_mu1367_oem_reset/control.sh')
 assert '1_4_4_E_EXPERIMENTAL_INSTALLED' in (main/'actions.sh').read_text()
 assert 'guidance-evidence.txt' in (main/'actions.sh').read_text()
 assert '@READER_VERSIONS@' not in (main/'actions.sh').read_text()
 factory=read(HERE/'evidence/p4521-factory.json');extracted=read(a.p4521_inputs/'metadata.json');commands=read(HERE/'evidence/p4521-commands.json')
 for v in ('50','70'):
  assert extracted['variants'][v]=={k:factory[k] for k in ('files','stage1_runtime','stage2_runtime')}
  assert commands['variants'][v]==proofs['qnx']['factory_utilities_sha256']
  assert proofs['p4521_native']['variants'][v]['proc/boot/libc.so.3']==build['factory_libc_sha256']==proofs['reader_qnx']['factory_libc_sha256']
  assert proofs['p4521_native']['variants'][v]['sbin/pipe']==proofs['reader_qnx']['factory_pipe_sha256']
 assert sha(sd/'P4521_FACTORY.json')==sha(HERE/'evidence/p4521-factory.json')
 for v,entry in m['variants'].items():
  folder=main/v
  for k,name,path in [('core','core.so','base/core.so'),('menu','VCMenu.jar','base/VCMenu.jar'),('guidance','CarPlayMU1367Guidance.jar','CarPlayMU1367Guidance.jar')]:assert sha(folder/name)==entry['files'][k]==runtime[path]
  assert sha(folder/'rgi-observer')==entry['files']['reader']==m['reader_sha256']
  assert entry['before']['reader']==sha(sd/'Custom/carplay_mu1367/rgi-observer')
  code=(folder/'control.sh').read_text();assert 'core menu guidance reader parent' in code and 'reader) echo "$APP/carplay-mu1367/rgi-observer"' in code
  assert 'rgi-observer' in (main/'payload-check.sh').read_text()
  for name in ('core.so','VCMenu.jar'):assert sha(tuning/v/name)==runtime['tuning/'+name]
 assert sha(sd/'Custom/carplay_mu1367_artwork/CarPlayMU1367Audio.jar')==runtime['CarPlayMU1367Audio.jar']
 legacy=read(HERE/'tools/legacy-revisions.json')
 for version in ('1.4.1','1.4.2','1.4.3','1.4.3-e'):
  rows=[(h,r) for h,r in legacy.items() if r['revision']=='release-v'+version];assert len(rows)==8
  for h,r in rows:
   fixture=HERE/'tests/revisions'/r['revision']/r['layer']/r['variant']
   assert sha(fixture/'control.sh')==h and h in (main/'legacy-check.sh').read_text()
 archive=a.package/m['archive_name'];assert sha(archive)==m['archive_sha256'];inventory=read(sd/'FILES_SHA256.json')
 with zipfile.ZipFile(archive) as z,zipfile.ZipFile(a.base_archive) as base:
  assert z.testzip() is None and len(z.namelist())==len(inventory)+1
  for n,h in inventory.items():assert sha(sd/n)==h==hashlib.sha256(z.read(n)).hexdigest(),n
  changed=[n for n in base.namelist() if base.read(n)!=z.read(n)]
  allowed={'DEVELOPMENT.md','FILES_SHA256.json','MU1367_RELEASE_MANIFEST.json','README.md','START_HERE.md','RELEASE-NOTES.md','READER-RECOVERY.md','KNOWN-ISSUES.md','Toolbox/GEM/carplay-maps-vc.esd'}
  allowed.update('Custom/'+n+'/payload-check.sh' for n in ('carplay_mu1367_map_only','carplay_mu1367_refinements','carplay_mu1367_guidance_v3'))
  allowed.update('Custom/carplay_mu1367_guidance_v3/'+n for n in ('actions.sh','legacy-check.sh','release-versions.sh'))
  for layer in ('carplay_mu1367_guidance_v3','carplay_mu1367_v3_turn_cards'):
   for v in m['variants']:
    allowed.update('Custom/'+layer+'/'+v+'/'+n for n in ('VERSION','control.sh','manifest.json'))
    if layer=='carplay_mu1367_guidance_v3':allowed.update('Custom/'+layer+'/'+v+'/'+n for n in ('CarPlayMU1367Guidance.jar','rgi-observer'))
  assert set(changed)<=allowed, set(changed)-allowed
  added=set(z.namelist())-set(base.namelist())
  assert added==set() and set(base.namelist())<=set(z.namelist()),added
  for n in ('README.md','START_HERE.md','RELEASE-NOTES.md','READER-RECOVERY.md'):
   assert 'experimental' in z.read(n).decode().lower(),n
  assert 'v1.4.4-e - EXPERIMENTAL guidance' in z.read('Toolbox/GEM/carplay-maps-vc.esd').decode()
 result={'passed':True,'version':'1.4.4-e','experimental':True,'prerelease':True,'base_version':'1.4.3-e','base_archive_sha256':BASE_SHA,'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'inventory_checks':len(inventory),'supported_firmware':m['supported_firmware'],'runtime_rebuild':runtime,'runtime_changed':['guidance JAR','native guidance reader'],'reader_sha256':m['reader_sha256'],'reader_source_sha256':m['reader_source_sha256'],'guidance_build':m['guidance_build'],'reader_build':m['reader_build'],'five_v143e_runtime_payloads_unchanged':True,'guidance_fresh_source_rebuild':True,'factory_arm_j9_guidance_rerun':True,'guidance_hold_ms':m['guidance_hold_ms'],'reader_restart_budget':m['reader_restart_budget'],'p4521_factory_variants_verified':['50','70'],'release_package_vehicle_tested':False,'vehicle_endurance_verified':False,'defaults':m['defaults'],'new_unit_commands':[],'baseline_changed_files':changed,'added_files':sorted(added),'oem_reset_sha256':sha(sd/'Custom/carplay_mu1367_oem_reset/control.sh'),'tests':{'filesystem_cases':proofs['filesystem']['tests'],'migration_combinations':40,'p4521_cases':3,'reader_host_cases':20,'reader_transaction_cases':3,'guidance_programs':len(proofs['guidance']['results']),'payload_integrity_cases':proofs['preflight']['tests']},'validation_environment':'Host reader/Java tests on macOS; full transactions in disposable Debian 12 aarch64/Python 3.11/ksh93 container without network; native and real firmware shell checks on QNX/QEMU. Mounts mocked.','limits':['No vehicle result for this package; Apple Maps and Waze delivery are inferred from captures and synthetic replays.','Waze may send no active route or maneuvers; the evidence file will establish this.','The 3-minute quiet hold can show a last maneuver for at most that time if an app stops without a route-end state.','Experimental worker recovery; the original device interruption trigger is not reproduced.','P4521 installation remains experimental.','Physical remount/storage and power-loss durability are not established.'],'proofs':{n:{'path':str(getattr(a,n)),'sha256':sha(getattr(a,n)),'result':r} for n,r in proofs.items()},'source_sha256':{str(f.relative_to(HERE)):sha(f) for top in ('src','tools','tests') for f in sorted((HERE/top).rglob('*')) if f.is_file() and f.name!='verify' and '__pycache__' not in f.parts},'verification_script_sha256':sha(Path(__file__))}
 (HERE/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':True,'version':'1.4.4-e','archive_sha256':sha(archive),'inventory_checks':len(inventory)}))
if __name__=='__main__':main()
