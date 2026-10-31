#!/usr/bin/env python3
"""Aggregate exact-runtime and release-package evidence without claiming new vehicle tests."""
import argparse,hashlib,json,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','filesystem-package','runtime','native','guidance','filesystem','migration','prefix','qnx','driver','fetch'):
  p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();pkg=a.package;manifest=read(pkg/'manifest.json')
 proofs={n:read(getattr(a,n)) for n in ('runtime','native','guidance','filesystem','migration','prefix','qnx','driver','fetch')}
 for n,r in proofs.items():assert r.get('passed',n=='driver'),n
 assert proofs['driver']['driver_sha256']=='0ca39135a9f2326d9781ae7b010b96ad0355a97562d133d6dec8a1633921ee85'
 assert proofs['fetch']['sha256']=='acbf7f676e3c2690b1ee8c5185c3bbb378962b3a8f9d4dbf56d778cd4813f11e'
 expected=read(HERE/'RUNTIME.json')['rebuild'];assert proofs['runtime']['files']==expected
 for k,n in [('core','base/core.so'),('menu','base/VCMenu.jar'),('guidance','CarPlayMU1367Guidance.jar')]:assert manifest['files'][k]==expected[n]
 assert proofs['native']['core_sha256']==manifest['files']['core']
 assert proofs['native']['menu_sha256']==manifest['files']['menu']
 assert proofs['guidance']['guidance_sha256']==manifest['files']['guidance']
 assert proofs['migration']['archive_sha256']==manifest['archive_sha256']
 assert proofs['filesystem']['archive_sha256']==read(a.filesystem_package/'manifest.json')['archive_sha256']
 assert proofs['prefix']['archive_sha256']==proofs['filesystem']['archive_sha256']
 # Final hardening changes only the generated legacy integrity gate and preflight hashes.
 before=a.filesystem_package/'sd-card';after=pkg/'sd-card'
 diffs=[]
 for f in after.rglob('*'):
  if f.is_file() and (before/f.relative_to(after)).is_file() and f.read_bytes()!=(before/f.relative_to(after)).read_bytes():diffs.append(str(f.relative_to(after)))
 assert set(diffs)=={'Custom/carplay_mu1367_guidance_v3/legacy-check.sh','Custom/carplay_mu1367_guidance_v3/payload-check.sh','Custom/carplay_mu1367_map_only/payload-check.sh','Custom/carplay_mu1367_refinements/payload-check.sh','FILES_SHA256.json'},diffs
 assert proofs['qnx']['factory_migration_verified'] and proofs['qnx']['sdk_utilities_injected'] is False
 assert proofs['qnx']['main_controller_sha256']==sha(after/'Custom/carplay_mu1367_guidance_v3/6/control.sh')
 reset=after/'Custom/carplay_mu1367_oem_reset/control.sh';assert proofs['qnx']['controller_sha256']==sha(reset)
 j9=read(HERE/'evidence/lane-type.json')['evidence']['factory_arm_j9']['result']
 for k,n in [('core.so','base/core.so'),('VCMenu.jar','base/VCMenu.jar'),('CarPlayMU1367Guidance.jar','CarPlayMU1367Guidance.jar')]:assert j9['files'][k]==expected[n]
 assert j9['audio_sha256']==expected['CarPlayMU1367Audio.jar']
 reset_proof=read(HERE/'evidence/guidance-v3.json')['evidence']['oem_reset_faults']['result']
 assert reset_proof['passed'] and reset_proof['controller_sha256']==sha(reset)
 archive=pkg/manifest['archive_name'];assert sha(archive)==manifest['archive_sha256']
 inv=read(after/'FILES_SHA256.json')
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None and len(z.namelist())==len(inv)+1
  for n,h in inv.items():assert hashlib.sha256(z.read(n)).hexdigest()==h==sha(after/n),n
 r={'passed':True,'version':'1.4.1','archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,
  'inventory_checks':len(inv),'files':manifest['files'],'runtime_rebuild':expected,
  'tests':{'filesystem':proofs['filesystem']['tests'],'final_integrity_and_migration':proofs['migration']['tests'],'published_prefixes':proofs['prefix']['tests'],'migration_scenarios':8,'prefix_scenarios':4},
  'source_and_package_refactor':True,'default_fps':30,'default_idr':5,'base_turn_cards':False,'safe_area':[200,96,400,364],
  'new_unit_commands':[],'factory_j9_proof_reused_for_identical_runtime':True,
  'factory_qnx_release_migration_verified':True,'oem_reset_sha256':sha(reset),'oem_reset_fault_proof_reused':reset_proof,
  'vehicle_feedback':'Road names, arrow progress, native lanes, placeholder, artwork and wireless guidance reported working; unused-lane blanks match OEM. Right-edge layout failed and is reverted.',
  'known_issues':['Mini Pico can override scene URLs and keep its turn card; exact Pico firmware implementation unverified.'],
  'final_package_vehicle_tested':False,
  'limits':['Host mounts/sync mocked; QNX mounts mocked. No physical power-loss/storage durability proof.','Identical runtime bytes retain their earlier factory/J9 evidence; this release adds independently tested migration/packaging.','No new adapter firmware or custom unused-lane renderer is included.'],
  'evidence':{n:{'sha256':sha(getattr(a,n)),'result':r} for n,r in proofs.items()},
  'source_sha256':{str(f.relative_to(HERE)):sha(f) for top in ('src','tools','tests') for f in (HERE/top).rglob('*') if f.is_file() and 'verify'!=f.name and '__pycache__' not in f.parts}}
 (HERE/'VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'passed':True,'archive_sha256':sha(archive),'inventory_checks':len(inv)}))
if __name__=='__main__':main()
