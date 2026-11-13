#!/usr/bin/env python3
"""Verify experimental v1.5.2-e (v1.2.2 safe area, 2048-packet bridge backlog limit), its v1.5.1-e baseline and exact tested artifacts."""
import argparse,hashlib,json,os,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
# Published experimental v1.5.1-e ZIP; it is also its verified package.
BASE_SHA='54dfbbabed743a0b6f8eda6593de4be5d83e1115296557e1757e4fb0f3f7ae1f'
V151_MAIN=['mu1367-guidance-v3-15ed81a807b4','mu1367-guidance-v3-766c10540f2a','mu1367-guidance-v3-89986b9f89cf','mu1367-guidance-v3-082cca511f4d']
V151_BRIDGE='5d48424f9c2ab319613de9ddb1e075babf126e9280f35e43a27297694958f183'
# Main-layer builds of published v1.5.0-e and the first published v1.5.1-e: retired by the two-stage migration
# now that the main layer also owns the CarPlay video bridge.
V150_MAIN=['mu1367-guidance-v3-02dff707ddd2','mu1367-guidance-v3-6f2421b0eced','mu1367-guidance-v3-aed3f0d88907','mu1367-guidance-v3-2231214c28de']
BASE_PUBLISHED_SHA=BASE_SHA
# The first published v1.5.1-e ZIP, replaced by this build under the same version.
FIRST_V151_SHA='444b4c2fdffaea910867951662f53b02628cb8f63841484890cdda985db43f52'
UPSTREAM_BRIDGE='6c5210cac43699caf027b1f217dc39f4fe87c8b2aee3fa6366c20856772f9c35'
# Five runtime payloads stay byte-identical to v1.5.1-e; the base core changes only its map-only safe area.
UNCHANGED={'CarPlayMU1367Audio.jar':'c5a0f63c22b8f9b10fc4b54b8239bea57e2693cbecc15d7d71119e999feefff3',
 'CarPlayMU1367Guidance.jar':'0fd03cd1ad9b811553764d35d476408c44da6e7aef4c0a1a2efa48acd71e0f04',
 'base/core.so':'dea2af427df870a90a4159a678539a02b316a4959f1c69408a681770d8a38b55','base/VCMenu.jar':'ed60cd274415a13c64ee68819596950ab987bcd462bd0c5aa66a8000edcc6942',
 'tuning/core.so':'cb4468b9d32c7c3787cce278542c19d79bc6e19f36d74a3f5bebdc82579adf39','tuning/VCMenu.jar':'a9c922415596656623f00bd7530bfb42a289bf4bff7da3d3df70cdc562c6674f'}
AA_PROOFS=('aa_guidance','aa_layer','aa_e2e','aa_feeder_qnx','aa_feeder_host','aa_hook')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','base-archive','filesystem','p4521','p4521-inputs','p4521-native','qnx','reader-build','reader-host','reader-qnx','reader-transactions','guidance','guidance-rebuild','guidance-qnx','preflight','png-native','png-tx','aa-feeder-build')+tuple(n.replace('_','-') for n in AA_PROOFS):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();sd=a.package/'sd-card';m=read(a.package/'manifest.json');runtime=read(HERE/'RUNTIME.json')['rebuild'];reader_pin=read(HERE/'READER-RUNTIME.json')
 assert m['version']=='1.5.2-e' and m['experimental'] and m['prerelease'] and m['base_version']=='1.5.1-e' and m['stable_base_version']=='1.4.6'
 for name,h in UNCHANGED.items():assert runtime[name]==h,name
 assert sha(a.base_archive)==m['base_verified_package_sha256']==BASE_SHA and m['base_archive_sha256']==BASE_PUBLISHED_SHA
 assert m['guidance_build']=='MU1367-guidance-v1.5.0-e' and m['reader_build']=='MU1367-reader-v1.4.4-e'
 assert m['stream_choices'][2]=='27 fps / IDR 5 (default)' and m['stream_choices'][1]=='25 fps / IDR 5' and len(m['stream_choices'])==5 and not any('IDR 20' in c for c in m['stream_choices']) and m['stream_values']==[5,4,6,2,1] and m['guidance_recover_ms']==20000 and m['guidance_stop_grace_ms']==1500
 assert m['guidance_hold_ms']==180000 and m['reader_restart_budget']=={'per_window':3,'stable_window_ms':600000,'lifetime_ceiling':64,'backoff_ms':[1000,2000,4000]}
 assert m['reader_sha256']==reader_pin['sha256'] and m['reader_source_sha256']==sha(HERE/'src/reader/reader.c')==reader_pin['source_sha256']
 assert m['supported_firmware']==[{'train':'MHI2_ER_VWG13_K4525','experimental':False},{'train':'MHI2_ER_VWG13_P4521','experimental':True}]
 assert m['release_package_vehicle_tested'] is False and m['p4521_final_package_vehicle_tested'] is False
 assert m['defaults']=={'fps':27,'idr':5,'cards':False,'compressed_artwork':True,'safe_area':[160,20,480,440]}
 names=('filesystem','p4521','qnx','reader_host','reader_qnx','reader_transactions','guidance','guidance_rebuild','guidance_qnx','preflight','p4521_native','png_native','png_tx')+AA_PROOFS
 proofs={n:read(getattr(a,n)) for n in names}
 for n,r in proofs.items():assert r['passed'],n
 assert proofs['filesystem']['tests']>=13 and proofs['p4521']['tests']==3 and proofs['reader_host']['tests']==20 and proofs['reader_transactions']['tests']==3
 for n in ('filesystem','p4521','reader_transactions'):assert proofs[n]['archive_sha256']==m['archive_sha256'],n
 build=read(a.reader_build/'manifest.json');assert build['passed'] and build['sha256']==m['reader_sha256']==sha(a.reader_build/'rgi-observer')
 assert build['source_sha256']==proofs['reader_host']['reader_source_sha256']==m['reader_source_sha256']
 assert proofs['reader_qnx']['reader_sha256']==m['reader_sha256'] and proofs['reader_qnx']['native_timeout_and_recovery'] and proofs['reader_qnx']['new_nonce_verified']
 assert proofs['reader_host']['guidance_sha256']==proofs['guidance']['guidance_sha256']==proofs['guidance_rebuild']['guidance_sha256']==proofs['guidance_qnx']['guidance_sha256']==runtime['CarPlayMU1367Guidance.jar']
 assert proofs['guidance_qnx']['factory_arm_j9_verified'] and proofs['guidance_qnx']['modes']==['noverify','verify']
 assert 'TestQuietHold' in proofs['guidance']['results'] and 'TestReroute' in proofs['guidance']['results'] and 'TestSourceName' in proofs['guidance']['results'] and 'TestUturnSide' in proofs['guidance']['results'] and 'TestAndroidAuto' in proofs['guidance']['results']
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
 assert '1_5_2_E_EXPERIMENTAL_INSTALLED_FULL_REBOOT' in (main/'actions.sh').read_text()
 assert not set(e['build_id'] for e in m['variants'].values())&set(V150_MAIN+V151_MAIN) and 'carplay_mu1367_artwork_png/control.sh" install' in (main/'actions.sh').read_text()
 assert sorted(r['build_id'] for r in read(HERE/'tools/legacy-revisions.json').values() if r['revision']=='release-v1.5.0-e' and r['layer']=='carplay_mu1367_guidance_v3')==sorted(V150_MAIN)
 assert sorted(r['build_id'] for r in read(HERE/'tools/legacy-revisions.json').values() if r['revision']=='release-v1.5.1-e' and r['layer']=='carplay_mu1367_guidance_v3')==sorted(V151_MAIN)
 assert all(v in (main/'actions.sh').read_text() for v in V151_MAIN)
 png=sd/'Custom/carplay_mu1367_artwork_png';pm=m['artwork_png']
 assert pm['installed_by_default'] and pm['lossless'] and (png/'VERSION').read_text().strip()==pm['build_id'] and sha(png/'artwork-fetch')==pm['fetch_sha256']
 assert pm['replaces_fetch_sha256']==sha(sd/'Custom/carplay_mu1367_artwork/artwork-fetch')
 assert proofs['qnx']['default_artwork_png_verified'] and proofs['qnx']['artwork_png_controller_sha256']==sha(png/'control.sh')
 # Android Auto layer: exact payloads, controller exercised on firmware ksh and on the host, end-to-end and QNX proofs.
 aa=sd/'Custom/carplay_mu1367_android_auto';am=read(aa/'manifest.json');pin=read(HERE/'src/android-auto/PROVENANCE.json');fb=read(a.aa_feeder_build/'manifest.json')
 assert m['android_auto']==am and (aa/'VERSION').read_text().strip()==am['build_id']
 assert am['files']['libgal_hook.so']==pin['libgal_hook.so']['sha256'] and am['files']['libdmdt_flush.so']==pin['libdmdt_flush.so']['sha256']
 assert am['files']['aa-most-feeder']==fb['sha256']==proofs['aa_feeder_qnx']['feeder_sha256'] and fb['source_sha256']==sha(HERE/'src/android-auto/feeder/aa_most_feeder.c')
 for n,h in am['files'].items():assert sha(aa/n)==h,n
 assert am['wrapper_sha256']==sha(aa/'gal.wrapper.sh')==sha(HERE/'src/android-auto/unit/gal.wrapper.sh')==proofs['aa_layer']['wrapper_sha256']
 assert am['factory_gal']['sha256']==proofs['aa_layer']['factory_gal_sha256']==proofs['aa_hook']['variants']['50']['gal_sha256']==proofs['aa_hook']['variants']['70']['gal_sha256']
 assert proofs['aa_layer']['controller_sha256']==sha(aa/'control.sh')==proofs['qnx']['android_auto_controller_sha256'] and proofs['qnx']['android_auto_layer_verified']
 assert am['main_versions']==[e['build_id'] for e in m['variants'].values()]
 assert proofs['aa_guidance']['guidance_sha256']==runtime['CarPlayMU1367Guidance.jar'] and proofs['aa_e2e']['acks']==proofs['aa_e2e']['frames_sent']
 # v1.5.1-e: the Android Auto bridge build keeps delivering after a gap; the CarPlay build waits for a keyframe.
 rec=proofs['aa_e2e']['bridge_recovery'];assert rec['passed'] and rec['aa_p_slices']>=rec['p_slices_sent']-2 and not rec['aa_idr_request'] and rec['carplay_idr_request']
 assert am['files']['altscreen-most-bridge-aa']==fb['bridge_sha256']==proofs['aa_feeder_qnx']['bridge_sha256'] and proofs['aa_feeder_qnx']['aa_bridge_ran_on_qnx']
 assert fb['bridge_source_sha256']==sha(HERE/'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c') and fb['bridge_flags']==['-DALTSCREEN_AA_SINGLE_IDR']
 assert am['replaces_builds']==['mu1367-android-auto-ee74f406dd94','mu1367-android-auto-e3e4e1ce3a73','mu1367-android-auto-c1f4833dac00','mu1367-android-auto-ad7f051fd568'] and 'pmcp-aa*' in (sd/'Toolbox/scripts/cpmap_diag.sh').read_text()
 assert 'guidance-evidence.txt' in (main/'actions.sh').read_text()
 assert '@READER_VERSIONS@' not in (main/'actions.sh').read_text() and '@BRIDGE_VERSIONS@' not in (main/'actions.sh').read_text()
 # v1.5.1-e: CarPlay video bridge with boot-time MOST reclaim, built from the same source, owned by the main layer.
 cb=m['carplay_bridge'];assert cb['sha256']==fb['carplay_bridge_sha256']==proofs['aa_feeder_qnx']['carplay_bridge_sha256'] and fb['carplay_bridge_flags']==[]
 assert proofs['aa_feeder_qnx']['carplay_bridge_ran_on_qnx'] and cb['replaces_sha256']==UPSTREAM_BRIDGE==sha(sd/'Custom/carplay_mu1367_settings/altscreen-most-bridge')
 assert cb['reclaim_window_s']==180 and cb['reclaim_max']==3 and proofs['qnx']['carplay_bridge_install_verified']
 # v1.5.2-e: 2048-packet backlog limit (every stream setting), proven against the old 1024 on the host.
 assert cb['latency_limit_packets']==2048 and cb['sha256']!=V151_BRIDGE and 'TS_LOW_LATENCY_LIMIT_PACKETS 2048U' in (HERE/'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c').read_text()
 blim=proofs['aa_e2e']['backlog_limit'];assert blim['passed'] and blim['checks']==4 and blim['new_a_resets']==0 and blim['old_a_resets']>=1 and blim['new_b_resets']>=1
 # v1.5.2-e: map-only safe area of v1.2.2.
 ds=(HERE/'src/runtime/card-core/source/display_settings.h').read_text();assert '*x=160;*y=20;*w=480;*h=440;' in ds
 recl=proofs['aa_e2e']['most_reclaim'];assert recl['passed'] and recl['checks']>=18 and not recl['failed']
 src=(HERE/'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c').read_text()
 assert 'ALTSCREEN_BRIDGE_RECLAIM_WINDOW_US 180000000ULL' in src and 'ALTSCREEN_BRIDGE_RECLAIM_MAX 3U' in src and '"/eso/bin/apps/dmdt"' in src
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
  code=(folder/'control.sh').read_text();assert 'core menu guidance reader bridge parent' in code and 'reader) echo "$APP/carplay-mu1367/rgi-observer"' in code
  assert 'bridge) echo "$APP/carplaymaps/altscreen-most-bridge"' in code and sha(folder/'altscreen-most-bridge')==entry['files']['bridge']==cb['sha256'] and entry['before']['bridge']==UPSTREAM_BRIDGE
  assert 'rgi-observer' in (main/'payload-check.sh').read_text()
  for name in ('core.so','VCMenu.jar'):assert sha(tuning/v/name)==runtime['tuning/'+name]
 assert sha(sd/'Custom/carplay_mu1367_artwork/CarPlayMU1367Audio.jar')==runtime['CarPlayMU1367Audio.jar']
 legacy=read(HERE/'tools/legacy-revisions.json')
 for version in ('1.4.1','1.4.2','1.4.3','1.4.3-e','1.4.4-e','1.4.5-e','1.4.6-e','1.4.6','test-1.5.0-e-pre','1.5.0-e','1.5.1-e'):
  rows=[(h,r) for h,r in legacy.items() if r['revision']==('test-v1.5.0-e-pre' if version.startswith('test-') else 'release-v'+version)];assert len(rows)==8
  for h,r in rows:
   fixture=HERE/'tests/revisions'/r['revision']/r['layer']/r['variant']
   assert sha(fixture/'control.sh')==h and h in (main/'legacy-check.sh').read_text()
 archive=a.package/m['archive_name'];assert sha(archive)==m['archive_sha256'];inventory=read(sd/'FILES_SHA256.json')
 with zipfile.ZipFile(archive) as z,zipfile.ZipFile(a.base_archive) as base:
  assert z.testzip() is None and len(z.namelist())==len(inventory)+1
  for n,h in inventory.items():assert sha(sd/n)==h==hashlib.sha256(z.read(n)).hexdigest(),n
  changed=[n for n in base.namelist() if base.read(n)!=z.read(n)]
  allowed={'Toolbox/scripts/cpmap_diag.sh',}|{'Custom/carplay_mu1367_android_auto/'+n for n in os.listdir(aa)}|{'DEVELOPMENT.md','FILES_SHA256.json','MU1367_RELEASE_MANIFEST.json','README.md','START_HERE.md','RELEASE-NOTES.md','READER-RECOVERY.md','KNOWN-ISSUES.md','NOTICE.md','Toolbox/GEM/carplay-maps-vc.esd','Toolbox/GEM/carplay-maps-vc-tuning.esd'}
  allowed.update('Custom/'+n+'/payload-check.sh' for n in ('carplay_mu1367_map_only','carplay_mu1367_refinements','carplay_mu1367_guidance_v3'))
  allowed.update('Custom/carplay_mu1367_guidance_v3/'+n for n in ('actions.sh','legacy-check.sh','release-versions.sh'))
  for layer in ('carplay_mu1367_guidance_v3','carplay_mu1367_v3_turn_cards'):
   for v in m['variants']:
    allowed.update('Custom/'+layer+'/'+v+'/'+n for n in ('VERSION','control.sh','manifest.json'))
    allowed.update('Custom/'+layer+'/'+v+'/'+n for n in ('core.so','VCMenu.jar','altscreen-most-bridge'))
    if layer=='carplay_mu1367_guidance_v3':allowed.add('Custom/'+layer+'/'+v+'/CarPlayMU1367Guidance.jar')
  assert set(changed)<=allowed, set(changed)-allowed
  added=set(z.namelist())-set(base.namelist())
  expected_added=set()
  assert added==expected_added and set(base.namelist())<=set(z.namelist()),added^expected_added
  assert z.read('Toolbox/scripts/cpmap_reboot.sh')==(HERE/'tools/cpmap_reboot.sh').read_bytes()
  assert 'cpmap_reboot.sh' in z.read('Toolbox/GEM/carplay-maps-vc.esd').decode()
  esd=z.read('Toolbox/GEM/carplay-maps-vc.esd').decode()
  assert 'v1.5.2-e - EXPERIMENTAL' in esd and 'cpmap_suite_aa-disable.sh' in esd
 result={'passed':True,'version':'1.5.2-e','experimental':True,'prerelease':True,'base_version':'1.5.1-e','android_auto':am,'base_archive_sha256':BASE_PUBLISHED_SHA,'base_verified_package_sha256':BASE_SHA,'artwork_png':pm,'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'inventory_checks':len(inventory),'supported_firmware':m['supported_firmware'],'runtime_rebuild':runtime,'runtime_changed':['base/core.so: map-only safe area 160,20,480,440 (v1.2.2) instead of 200,96,400,364'],'v152_changes':['map-only safe area 160,20,480,440','bridge backlog limit 2048 packets (was 1024), every stream setting','published v1.5.1-e main layers retired by the two-stage migration'],'carplay_changed':['video bridge rebuilt from altscreen_most_bridge.c with boot-time MOST reclaim (dmdt release, reopen, resync; 180 s, 3 attempts), installed by the main layer over the upstream build '+UPSTREAM_BRIDGE[:12],'main layer retires published v1.5.0-e / first v1.5.1-e main layers through the two-stage migration'],'carplay_bridge':cb,'replaces_first_published_archive_sha256':FIRST_V151_SHA,'android_auto_changed':['feeder 10-mu1367.2','own bridge build altscreen-most-bridge-aa (no keyframe wait; boot-time MOST reclaim)','wrapper checks the AA bridge','in-place upgrade of v1.5.0-e and first v1.5.1-e layers'],'diagnostics_changed':['export includes /ramdisk/pmcp-aa*'],'reader_sha256':m['reader_sha256'],'reader_source_sha256':m['reader_source_sha256'],'guidance_build':m['guidance_build'],'reader_build':m['reader_build'],'runtime_and_main_layer_unchanged_from_v151e':False,'stream_choices':m['stream_choices'],'guidance_fresh_source_rebuild':True,'factory_arm_j9_guidance_rerun':True,'guidance_hold_ms':m['guidance_hold_ms'],'reader_restart_budget':m['reader_restart_budget'],'p4521_factory_variants_verified':['50','70'],'release_package_vehicle_tested':False,'vehicle_endurance_verified':False,'defaults':m['defaults'],'new_unit_commands':[],'baseline_changed_files':changed,'added_files':sorted(added),'oem_reset_sha256':sha(sd/'Custom/carplay_mu1367_oem_reset/control.sh'),'tests':{'filesystem_cases':proofs['filesystem']['tests'],'migration_combinations':88,'most_reclaim_checks':recl['checks'],'backlog_limit_checks':blim['checks'],'android_auto_layer_checks':proofs['aa_layer']['checks'],'android_auto_e2e_checks':proofs['aa_e2e']['checks'],'android_auto_feeder_qnx_checks':proofs['aa_feeder_qnx']['checks'],'android_auto_feeder_host_checks':proofs['aa_feeder_host']['checks'],'android_auto_mailbox_java_checks':proofs['aa_guidance']['java_checks'],'p4521_cases':3,'reader_host_cases':20,'reader_transaction_cases':3,'guidance_programs':len(proofs['guidance']['results']),'payload_integrity_cases':proofs['preflight']['tests']},'validation_environment':'Host reader/Java tests on macOS; full transactions in disposable Debian 12 aarch64/Python 3.11/ksh93 container without network; native and real firmware shell checks on QNX/QEMU. Mounts mocked.','limits':['No vehicle result for this package, including Android Auto on MU1367.','Safe area: whether the taller v1.2.2 area brings back a closer, lighter map and how much of the route sits under the dials is a car result; frame sizes depend on the phone app.','Backlog limit 2048: absorbs bursts up to about 250 ms of video before a reset; a real stall shows up to about 250 ms of older video before the reset (was about 125 ms).','CarPlay bridge reclaim: the cause (factory encoder taking isoTX2 at boot) is read from one full boot log and matches three exports; the reclaim itself is tested off-unit with a simulated ENOMEM and a fake dmdt. The rebuilt bridge (clang with the pinned QNX 6.5 SDK binutils) replaces the upstream GCC 4.9.4 build, which cannot be reproduced locally.','Android Auto: the hook binary is the pinned upstream build (car-tested on MU1161); the v1.5.0-e feeder and hook were tried in one MU1367 car (map froze, guidance worked); the v1.5.1-e bridge build is tested off-unit only.','The freeze diagnosis rests on code and a host reproduction; the car export lacked the AA bridge counters.','Android Auto: no first-step arrow, no remaining distance/time, lanes or road name; 30 fps; a lost picture returns only after the phone reconnects.','An OEM reset run outside the menu leaves the gal wrapper in place (it then runs the factory gal); the saved Android Auto controller restores the file.','Driving-side U-turn lanes are tested off-unit only; no left-hand-traffic capture exists.','The Apple Maps name merge covers names containing the word Apple; flip timing within a route is not captured.','Whether 25 fps reduces stutter is untested; the delivered frame rate may fall with the request.','Stream values 5 and 6 (20 and 27 fps) are unknown to v1.4.5 and older menus.','The 3-minute quiet hold can show a last maneuver for at most that time if an app stops without a route-end state.','P4521 installation remains experimental.','Physical remount/storage and power-loss durability are not established.'],'proofs':{n:{'path':str(getattr(a,n)),'sha256':sha(getattr(a,n)),'result':r} for n,r in proofs.items()},'source_sha256':{str(f.relative_to(HERE)):sha(f) for top in ('src','tools','tests') for f in sorted((HERE/top).rglob('*')) if f.is_file() and f.name!='verify' and '__pycache__' not in f.parts},'verification_script_sha256':sha(Path(__file__))}
 (HERE/'VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':True,'version':'1.5.2-e','archive_sha256':sha(archive),'inventory_checks':len(inventory)}))
if __name__=='__main__':main()
