#!/usr/bin/env python3
"""Verify the v1.4.2 artifact and its exact runtime, firmware and migration proofs."""
import argparse,hashlib,json,struct,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','filesystem-package','preflight','runtime','native','guidance','filesystem','qnx','guidance-qnx'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();manifest=read(a.package/'manifest.json');sd=a.package/'sd-card'
 assert manifest['version']=='1.4.2' and manifest['guidance_build']=='MU1367-guidance-v1.4.2'
 proofs={n:read(getattr(a,n)) for n in ('runtime','native','guidance','filesystem','preflight','qnx','guidance_qnx')}
 for name,result in proofs.items():assert result['passed'],name
 assert proofs['filesystem']['tests']==11 and proofs['preflight']['tests']==1
 expected=read(HERE/'RUNTIME.json')['rebuild'];prior=read(HERE/'evidence/release-v1.4.1.json')
 assert proofs['runtime']['files']==expected
 changed=[name for name,h in expected.items() if h!=prior['runtime_rebuild'][name]]
 assert changed==['CarPlayMU1367Guidance.jar'],changed
 for key,name in [('core','base/core.so'),('menu','base/VCMenu.jar'),('guidance','CarPlayMU1367Guidance.jar')]:assert manifest['files'][key]==expected[name]
 assert proofs['guidance']['guidance_sha256']==proofs['guidance_qnx']['guidance_sha256']==expected['CarPlayMU1367Guidance.jar']
 assert proofs['guidance_qnx']['factory_arm_j9_verified'] and proofs['guidance_qnx']['modes']==['noverify','verify']
 assert proofs['native']['core_sha256']==expected['base/core.so'] and proofs['native']['menu_sha256']==expected['base/VCMenu.jar']
 assert proofs['filesystem']['archive_sha256']==read(a.filesystem_package/'manifest.json')['archive_sha256']
 assert proofs['preflight']['archive_sha256']==manifest['archive_sha256']
 before=a.filesystem_package/'sd-card'
 differences=[str(f.relative_to(sd)) for f in sd.rglob('*') if f.is_file() and f.read_bytes()!=(before/f.relative_to(sd)).read_bytes()]
 assert set(differences)=={'DEVELOPMENT.md','FILES_SHA256.json'},differences
 assert proofs['qnx']['factory_migration_verified'] and proofs['qnx']['sdk_utilities_injected'] is False
 assert proofs['qnx']['main_controller_sha256']==sha(sd/'Custom/carplay_mu1367_guidance_v3/6/control.sh')
 assert proofs['qnx']['map_only_actions_sha256']==sha(sd/'Custom/carplay_mu1367_guidance_v3/actions.sh')
 assert proofs['qnx']['factory_utilities_sha256']==prior['evidence']['qnx']['result']['factory_utilities_sha256']
 assert sha(sd/'Custom/carplay_mu1367_artwork/ipod-drvr-iap2.so')==prior['evidence']['driver']['result']['driver_sha256']
 assert sha(sd/'Custom/carplay_mu1367_artwork/artwork-fetch')==prior['evidence']['fetch']['result']['sha256']
 reset=sd/'Custom/carplay_mu1367_oem_reset/control.sh'
 assert proofs['qnx']['controller_sha256']==sha(reset)==prior['oem_reset_sha256']
 assert manifest['defaults']=={'fps':30,'idr':5,'cards':False,'safe_area':[200,96,400,364]}
 for variant,entry in manifest['variants'].items():
  assert entry['files']==manifest['files']
  folder=sd/'Custom/carplay_mu1367_guidance_v3'/variant
  for key,name in [('core','core.so'),('menu','VCMenu.jar'),('guidance','CarPlayMU1367Guidance.jar')]:assert sha(folder/name)==entry['files'][key]
  assert sha(sd/'Custom/carplay_mu1367_v3_turn_cards'/variant/'core.so')==expected['tuning/core.so']
  assert sha(sd/'Custom/carplay_mu1367_v3_turn_cards'/variant/'VCMenu.jar')==expected['tuning/VCMenu.jar']
 legacy=read(HERE/'tools/legacy-revisions.json');previous=[(h,m) for h,m in legacy.items() if m['revision']=='release-v1.4.1'];assert len(previous)==8
 for h,m in previous:
  fixture=HERE/'tests/revisions/release-v1.4.1'/m['layer']/m['variant']
  assert sha(fixture/'control.sh')==h
  assert h in (sd/'Custom/carplay_mu1367_guidance_v3/legacy-check.sh').read_text()
  for key,name in [('core','core.so'),('menu','VCMenu.jar'),('guidance','CarPlayMU1367Guidance.jar')]:
   if key in m['files']:assert sha(fixture/name)==m['files'][key]
 archive=a.package/manifest['archive_name'];assert sha(archive)==manifest['archive_sha256']
 inventory=read(sd/'FILES_SHA256.json')
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None and len(z.namelist())==len(inventory)+1
  for name,h in inventory.items():assert hashlib.sha256(z.read(name)).hexdigest()==h==sha(sd/name),name
 with zipfile.ZipFile(sd/'Custom/carplay_mu1367_guidance_v3/6/CarPlayMU1367Guidance.jar') as z:
  for name in z.namelist():assert struct.unpack_from('>H',z.read(name),6)[0]==46,name
 assert '1.4.2' in (sd/'START_HERE.md').read_text() and '1_4_2_INSTALLED' in (sd/'Custom/carplay_mu1367_guidance_v3/actions.sh').read_text()
 r={'passed':True,'version':'1.4.2','archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'inventory_checks':len(inventory),'files':manifest['files'],'runtime_rebuild':expected,
  'runtime_changed':changed,'pull_request':8,'reviewed_commit':'48a3dee979e422d643cd7ccc0660bf954a2d876f',
  'guidance_build':manifest['guidance_build'],'verification_script_sha256':sha(Path(__file__)),'firmware_evidence':read(HERE/'evidence/uturn-mu1367.json'),'factory_arm_j9_guidance_verified':True,'factory_qnx_release_migration_verified':True,
  'tests':{'filesystem':proofs['filesystem']['tests'],'host_guidance_suites':len(proofs['guidance']['results']),'previous_release_migration_variants':8,'older_test_revision_migrations':8,'uturn_transport_angles':361,'uturn_side_branches':5,'factory_j9_uturn_cases_per_mode':5},
  'default_fps':30,'default_idr':5,'base_turn_cards':False,'safe_area':[200,96,400,364],'new_unit_commands':[],
  'oem_reset_sha256':sha(reset),'oem_reset_fault_proof_reused':prior['oem_reset_fault_proof_reused'],
  'prior_release_verification_sha256':sha(HERE/'evidence/release-v1.4.1.json'),
  'unchanged_runtime_evidence':'Five unchanged payload hashes retain the v1.4.1 evidence; native base/tuning sanitizer and settings parity tests were rerun. The rebuilt guidance received fresh host and ARM/J9 verification.',
  'final_package_vehicle_tested':False,'mu1367_uturn_vehicle_tested':False,
  'limits':['Host mounts/sync and QNX mounts are mocked; physical storage/power-loss durability is not established.','MU1367 U-turn rendering requires vehicle acceptance; PR #8 reports MU1161 + AID 791 vehicle success.','The reviewed U-turn threshold starts at 170 degrees; +/-169 remains 128 and exactly +180 selects left for right-hand traffic.','The Mini Pico card override remains unresolved.'],
  'evidence':{n:{'sha256':sha(getattr(a,n)),'result':result} for n,result in proofs.items()},
  'source_sha256':{str(f.relative_to(HERE)):sha(f) for top in ('src','tools','tests') for f in sorted((HERE/top).rglob('*')) if f.is_file() and f.name!='verify' and '__pycache__' not in f.parts}}
 (HERE/'VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'passed':True,'archive_sha256':sha(archive),'inventory_checks':len(inventory)}))
if __name__=='__main__':main()
