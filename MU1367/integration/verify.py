#!/usr/bin/env python3
"""Verify stable v1.4.6, its v1.4.6-e baseline and exact tested artifacts."""
import argparse,hashlib,json,os,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
# v1.4.6-e verified package (the published ZIP d38a53b3... adds only the optional artwork layer to it).
BASE_SHA='a33c03d4340db84c6151820a43477d057c1295c1626b597827ca1749de394a1d'
BASE_PUBLISHED_SHA='d38a53b325052bba028c819e24b4eb6cd042b7dfcc46ecad51320207f9800417'
# Runtime payloads v1.4.6 must leave byte-identical to v1.4.6-e; the reader is pinned separately.
UNCHANGED={'CarPlayMU1367Audio.jar':'c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3',
 'CarPlayMU1367Guidance.jar':'723005758477c39e723725774b2ea2a52535e0567537dd55be2db62a63df3166'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','base-archive','filesystem','p4521','p4521-inputs','p4521-native','qnx','reader-build','reader-host','reader-qnx','reader-transactions','guidance','guidance-rebuild','guidance-qnx','preflight','png-native','png-tx'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();sd=a.package/'sd-card';m=read(a.package/'manifest.json');runtime=read(HERE/'RUNTIME.json')['rebuild'];reader_pin=read(HERE/'READER-RUNTIME.json')
 assert m['version']=='1.4.6' and not m['experimental'] and not m['prerelease'] and m['base_version']=='1.4.6-e'
 for name,h in UNCHANGED.items():assert runtime[name]==h,name
 assert sha(a.base_archive)==m['base_verified_package_sha256']==BASE_SHA and m['base_archive_sha256']==BASE_PUBLISHED_SHA
 assert m['guidance_build']=='MU1367-guidance-v1.4.6-e' and m['reader_build']=='MU1367-reader-v1.4.4-e'
 assert m['stream_choices'][2]=='27 fps / IDR 5 (default)' and m['stream_choices'][1]=='25 fps / IDR 5' and len(m['stream_choices'])==5 and not any('IDR 20' in c for c in m['stream_choices']) and m['stream_values']==[5,4,6,2,1] and m['guidance_recover_ms']==20000 and m['guidance_stop_grace_ms']==1500
 assert m['guidance_hold_ms']==180000 and m['reader_restart_budget']=={'per_window':3,'stable_window_ms':600000,'lifetime_ceiling':64,'backoff_ms':[1000,2000,4000]}
 assert m['reader_sha256']==reader_pin['sha256'] and m['reader_source_sha256']==sha(HERE/'src/reader/reader.c')==reader_pin['source_sha256']
 assert m['supported_firmware']==[{'train':'MHI2_ER_VWG13_K4525','experimental':False},{'train':'MHI2_ER_VWG13_P4521','experimental':True}]
 assert m['release_package_vehicle_tested'] is False and m['p4521_final_package_vehicle_tested'] is False
 assert m['defaults']=={'fps':27,'idr':5,'cards':False,'compressed_artwork':True,'safe_area':[200,96,400,364]}
 names=('filesystem','p4521','qnx','reader_host','reader_qnx','reader_transactions','guidance','guidance_rebuild','guidance_qnx','preflight','p4521_native','png_native','png_tx')
 proofs={n:read(getattr(a,n)) for n in names}
 for n,r in proofs.items():assert r['passed'],n
 assert proofs['filesystem']['tests']>=13 and proofs['p4521']['tests']==3 and proofs['reader_host']['tests']==20 and proofs['reader_transactions']['tests']==3
 for n in ('filesystem','p4521','reader_transactions'):assert proofs[n]['archive_sha256']==m['archive_sha256'],n
 build=read(a.reader_build/'manifest.json');assert build['passed'] and build['sha256']==m['reader_sha256']==sha(a.reader_build/'rgi-observer')
 assert build['source_sha256']==proofs['reader_host']['reader_source_sha256']==m['reader_source_sha256']
 assert proofs['reader_qnx']['reader_sha256']==m['reader_sha256'] and proofs['reader_qnx']['native_timeout_and_recovery'] and proofs['reader_qnx']['new_nonce_verified']
 assert proofs['reader_host']['guidance_sha256']==proofs['guidance']['guidance_sha256']==proofs['guidance_rebuild']['guidance_sha256']==proofs['guidance_qnx']['guidance_sha256']==runtime['CarPlayMU1367Guidance.jar']
 assert proofs['guidance_qnx']['factory_arm_j9_verified'] and proofs['guidance_qnx']['modes']==['noverify','verify']
 assert 'TestQuietHold' in proofs['guidance']['results'] and 'TestReroute' in proofs['guidance']['results'] and 'TestSourceName' in proofs['guidance']['results'] and 'TestUturnSide' in proofs['guidance']['results']
 for name,h in proofs['guidance_rebuild']['source_sha256'].items():assert sha(HERE/name)==h,name
 assert sha(HERE/'tests/test-reader.py')==proofs['reader_host']['test_sha256']
 assert sha(HERE/'tests/test-reader-qnx.py')==proofs['reader_qnx']['test_sha256']
 assert proofs['qnx']['factory_migration_verified'] and proofs['qnx']['firmware_train_recognition_verified'] and proofs['qnx']['actual_qnx_ksh']
 assert proofs['qnx']['sdk_utilities_injected'] is False and proofs['qnx']['factory_progress_verified']
 main=sd/'Custom/carplay_mu1367_guidance_v3';tuning=sd/'Custom/carplay_mu1367_v3_turn_cards'
 assert proofs['qnx']['map_only_actions_sha256']==sha(main/'actions.sh')
 assert proofs['qnx']['main_controller_sha256']==sha(main/'6/control.sh')
 assert proofs['qnx']['tuning_controller_sha256']==sha(tuning/'6/control.sh')
 assert proofs['qnx']['controller_sha256']==sha(sd/'Custom/carplay_mu1367_oem_reset/control.sh')
 assert '1_4_6_INSTALLED_FULL_REBOOT' in (main/'actions.sh').read_text() and 'carplay_mu1367_artwork_png/control.sh" install' in (main/'actions.sh').read_text()
 png=sd/'Custom/carplay_mu1367_artwork_png';pm=m['artwork_png']
 assert pm['installed_by_default'] and pm['lossless'] and (png/'VERSION').read_text().strip()==pm['build_id'] and sha(png/'artwork-fetch')==pm['fetch_sha256']
 assert pm['replaces_fetch_sha256']==sha(sd/'Custom/carplay_mu1367_artwork/artwork-fetch')
 assert proofs['qnx']['default_artwork_png_verified'] and proofs['qnx']['artwork_png_controller_sha256']==sha(png/'control.sh')
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
 for version in ('1.4.1','1.4.2','1.4.3','1.4.3-e','1.4.4-e','1.4.5-e','1.4.6-e'):
  rows=[(h,r) for h,r in legacy.items() if r['revision']=='release-v'+version];assert len(rows)==8
  for h,r in rows:
   fixture=HERE/'tests/revisions'/r['revision']/r['layer']/r['variant']
   assert sha(fixture/'control.sh')==h and h in (main/'legacy-check.sh').read_text()
 archive=a.package/m['archive_name'];assert sha(archive)==m['archive_sha256'];inventory=read(sd/'FILES_SHA256.json')
 with zipfile.ZipFile(archive) as z,zipfile.ZipFile(a.base_archive) as base:
  assert z.testzip() is None and len(z.namelist())==len(inventory)+1
  for n,h in inventory.items():assert sha(sd/n)==h==hashlib.sha256(z.read(n)).hexdigest(),n
  changed=[n for n in base.namelist() if base.read(n)!=z.read(n)]
  allowed={'DEVELOPMENT.md','FILES_SHA256.json','MU1367_RELEASE_MANIFEST.json','README.md','START_HERE.md','RELEASE-NOTES.md','READER-RECOVERY.md','KNOWN-ISSUES.md','NOTICE.md','Toolbox/GEM/carplay-maps-vc.esd','Toolbox/GEM/carplay-maps-vc-tuning.esd'}
  allowed.update('Custom/'+n+'/payload-check.sh' for n in ('carplay_mu1367_map_only','carplay_mu1367_refinements','carplay_mu1367_guidance_v3'))
  allowed.update('Custom/carplay_mu1367_guidance_v3/'+n for n in ('actions.sh','legacy-check.sh','release-versions.sh'))
  for layer in ('carplay_mu1367_guidance_v3','carplay_mu1367_v3_turn_cards'):
   for v in m['variants']:
    allowed.update('Custom/'+layer+'/'+v+'/'+n for n in ('VERSION','control.sh','manifest.json'))
    allowed.update('Custom/'+layer+'/'+v+'/'+n for n in ('core.so','VCMenu.jar'))
    if layer=='carplay_mu1367_guidance_v3':allowed.add('Custom/'+layer+'/'+v+'/CarPlayMU1367Guidance.jar')
  assert set(changed)<=allowed, set(changed)-allowed
  added=set(z.namelist())-set(base.namelist())
  expected_added={'Custom/carplay_mu1367_artwork_png/'+n for n in os.listdir(png)}|{'Toolbox/scripts/'+n for n in os.listdir(sd/'Toolbox/scripts') if n.startswith('cpmap_artwork_png_')}
  assert added==expected_added and set(base.namelist())<=set(z.namelist()),added^expected_added
  assert z.read('Toolbox/scripts/cpmap_reboot.sh')==(HERE/'tools/cpmap_reboot.sh').read_bytes()
  assert 'cpmap_reboot.sh' in z.read('Toolbox/GEM/carplay-maps-vc.esd').decode()
  esd=z.read('Toolbox/GEM/carplay-maps-vc.esd').decode()
  assert 'MU1367 / 791 v1.4.6"' in esd and 'EXPERIMENTAL' not in esd
 result={'passed':True,'version':'1.4.6','experimental':False,'prerelease':False,'base_version':'1.4.6-e','base_archive_sha256':BASE_PUBLISHED_SHA,'base_verified_package_sha256':BASE_SHA,'artwork_png':pm,'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'inventory_checks':len(inventory),'supported_firmware':m['supported_firmware'],'runtime_rebuild':runtime,'runtime_changed':['base and tuning core.so (27 fps default)','base and tuning VCMenu.jar (27 fps default)'],'default_layers_added':['compressed album artwork'],'reader_sha256':m['reader_sha256'],'reader_source_sha256':m['reader_source_sha256'],'guidance_build':m['guidance_build'],'reader_build':m['reader_build'],'guidance_audio_and_reader_unchanged_from_v146e':True,'stream_choices':m['stream_choices'],'guidance_fresh_source_rebuild':True,'factory_arm_j9_guidance_rerun':True,'guidance_hold_ms':m['guidance_hold_ms'],'reader_restart_budget':m['reader_restart_budget'],'p4521_factory_variants_verified':['50','70'],'release_package_vehicle_tested':False,'vehicle_endurance_verified':False,'defaults':m['defaults'],'new_unit_commands':[],'baseline_changed_files':changed,'added_files':sorted(added),'oem_reset_sha256':sha(sd/'Custom/carplay_mu1367_oem_reset/control.sh'),'tests':{'filesystem_cases':proofs['filesystem']['tests'],'migration_combinations':56,'p4521_cases':3,'reader_host_cases':20,'reader_transaction_cases':3,'guidance_programs':len(proofs['guidance']['results']),'payload_integrity_cases':proofs['preflight']['tests']},'validation_environment':'Host reader/Java tests on macOS; full transactions in disposable Debian 12 aarch64/Python 3.11/ksh93 container without network; native and real firmware shell checks on QNX/QEMU. Mounts mocked.','limits':['No vehicle result for this package; v1.4.6-e had none either.','27 fps is the new default; its effect on stutter is untested in a car.','Compressed artwork is lossless and default; the original helper stays in its snapshot.','Driving-side U-turn lanes are tested off-unit only; no left-hand-traffic capture exists.','The Apple Maps name merge covers names containing the word Apple; flip timing within a route is not captured.','Whether 25 fps reduces stutter is untested; the delivered frame rate may fall with the request.','Stream values 5 and 6 (20 and 27 fps) are unknown to v1.4.5 and older menus.','The 3-minute quiet hold can show a last maneuver for at most that time if an app stops without a route-end state.','P4521 installation remains experimental.','Physical remount/storage and power-loss durability are not established.'],'proofs':{n:{'path':str(getattr(a,n)),'sha256':sha(getattr(a,n)),'result':r} for n,r in proofs.items()},'source_sha256':{str(f.relative_to(HERE)):sha(f) for top in ('src','tools','tests') for f in sorted((HERE/top).rglob('*')) if f.is_file() and f.name!='verify' and '__pycache__' not in f.parts},'verification_script_sha256':sha(Path(__file__))}
 (HERE/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':True,'version':'1.4.6','archive_sha256':sha(archive),'inventory_checks':len(inventory)}))
if __name__=='__main__':main()
