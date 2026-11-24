#!/usr/bin/env python3
"""Check the complete reader test ZIP and its exact firmware transaction proof."""
import argparse,hashlib,json,zipfile
from pathlib import Path
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','base-archive','transactions','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();m=json.loads((a.package/'manifest.json').read_text());tx=json.loads(a.transactions.read_text())
 sd=a.package/'sd-card';custom=m['custom_layer'];ctrl=sd/'Custom'/custom/'control.sh'
 assert tx['passed'] and tx['reader_sha256']==m['reader_sha256'] and tx['controller_sha256']==sha(ctrl.read_bytes())
 assert tx['actual_qnx_ksh'] and tx['sdk_utilities_injected'] is False
 archive=a.package/m['archive_name'];assert sha(archive.read_bytes())==m['archive_sha256']
 assert sha(a.base_archive.read_bytes())==m['base_archive_sha256']
 with zipfile.ZipFile(a.base_archive) as base,zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  changed=[n for n in base.namelist() if base.read(n)!=z.read(n)]
  checkers={'Custom/'+n+'/payload-check.sh' for n in ('carplay_mu1367_guidance_v3','carplay_mu1367_map_only','carplay_mu1367_refinements')}
  assert set(changed)=={'FILES_SHA256.json','README.md','Toolbox/GEM/carplay-maps-vc.esd'}|checkers,changed
  for n in checkers:
   code=z.read(n).decode();assert '$CUSTOM_CHECK/'+custom+'/rgi-observer"' in code
   assert '$CUSTOM_CHECK/GreenMenu/' not in code
  added=set(z.namelist())-set(base.namelist())
  expected={'READER-RECOVERY.md',*('Custom/'+custom+'/'+n for n in ('rgi-observer','VERSION','control.sh','guard','verify')),*('Toolbox/scripts/cpmap_reader_'+n+'.sh' for n in ('install','uninstall','recover','status'))}
  assert added==expected,added
  inv=json.loads(z.read('FILES_SHA256.json'));assert len(z.namelist())==len(inv)+1
  for n,h in inv.items():assert sha(z.read(n))==h==sha((sd/n).read_bytes()),n
  menu=z.read('Toolbox/GEM/carplay-maps-vc.esd').decode()
  for action in ('install','uninstall','recover','status'):
   name='cpmap_reader_'+action+'.sh';assert name in menu
   code=z.read('Toolbox/scripts/'+name).decode()
   assert '"$P/control.sh" '+action+' "$P"' in code and 'exec on -f mmx /bin/ksh' in code
  assert sha(z.read('Custom/'+custom+'/rgi-observer'))==m['reader_sha256']
  assert z.read('Custom/carplay_mu1367/rgi-observer')==base.read('Custom/carplay_mu1367/rgi-observer')
  code=ctrl.read_text();assert '@BUILD@' not in code and '@TABLE@' not in code
  for variant in ('6','6-road','7','7-road'):
   path='Custom/carplay_mu1367_guidance_v3/'+variant
   version=z.read(path+'/VERSION').decode().strip()
   assert sha(z.read(path+'/control.sh'))==m['parent_controllers'][version]
   assert m['parent_controllers'][version] in code
 r={'passed':True,'archive_sha256':m['archive_sha256'],'reader_sha256':m['reader_sha256'],'controller_sha256':tx['controller_sha256'],'verified_files':len(inv),'baseline_changed_files':changed,'added_files':sorted(added),'transaction_scenarios':tx['tests'],'baseline_runtime_payloads_unchanged':True,'on_unit_validated':False}
 a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
