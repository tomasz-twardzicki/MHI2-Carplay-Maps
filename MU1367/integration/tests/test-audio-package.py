#!/usr/bin/env python3
"""Verify the full audio test archive, unchanged release payloads and transaction proof."""
import argparse,hashlib,json,zipfile
from pathlib import Path
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','base-archive','transactions','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();m=json.loads((a.package/'manifest.json').read_text());tx=json.loads(a.transactions.read_text())
 sd=a.package/'sd-card';ctrl=sd/'Custom/carplay_mu1367_audio_progress/control.sh'
 custom=m.get('custom_layer','carplay_mu1367_audio_progress');ctrl=sd/'Custom'/custom/'control.sh';r2=m.get('revision')=='r2';r3=m.get('revision')=='artwork-r3';prefix='cpmap_artwork_r3_' if r3 else 'cpmap_audio_progress_'
 assert tx['passed'] and tx['audio_sha256']==m['audio_sha256'] and tx['controller_sha256']==sha(ctrl.read_bytes())
 assert tx['sdk_utilities_injected'] is False and tx['actual_qnx_ksh']
 archive=a.package/m['archive_name'];assert sha(archive.read_bytes())==m['archive_sha256']
 assert sha(a.base_archive.read_bytes())==m['base_archive_sha256']
 with zipfile.ZipFile(a.base_archive) as base,zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  changed=[n for n in base.namelist() if base.read(n)!=z.read(n)]
  checkers={'Custom/'+name+'/payload-check.sh' for name in ('carplay_mu1367_guidance_v3','carplay_mu1367_map_only','carplay_mu1367_refinements')}
  assert set(changed)=={'FILES_SHA256.json','README.md','RELEASE-NOTES.md','Toolbox/GEM/carplay-maps-vc-tuning.esd'}|checkers if r3 else set(changed)=={'FILES_SHA256.json','README.md','Toolbox/GEM/carplay-maps-vc.esd'}|checkers,changed
  for name in checkers:
   code=z.read(name).decode()
   assert '$CUSTOM_CHECK/GreenMenu/' not in code
   assert '$CUSTOM_CHECK/carplay_mu1367_oem_reset/payload/boot"' in code
   assert '$CUSTOM_CHECK/'+custom+'/CarPlayMU1367Audio.jar"' in code
  added=set(z.namelist())-set(base.namelist())
  expected={('ARTWORK-R3.md' if r3 else 'AUDIO-PROGRESS.md'),*('Custom/'+custom+'/'+n for n in ('CarPlayMU1367Audio.jar','VERSION','control.sh','guard','verify')),*('Toolbox/scripts/'+prefix+n+'.sh' for n in ('install','uninstall','recover','status')+(('png-stored','png-compressed') if r3 else ()))}
  if r2:expected.add('AUDIO-NATIVE-R2.md')
  if r3:expected.add('Custom/'+custom+'/artwork-fetch')
  assert added==expected,added
  inv=json.loads(z.read('FILES_SHA256.json'));assert len(z.namelist())==len(inv)+1
  for n,h in inv.items():assert sha(z.read(n))==h==sha((sd/n).read_bytes()),n
  menu=z.read('Toolbox/GEM/carplay-maps-vc-tuning.esd' if r3 else 'Toolbox/GEM/carplay-maps-vc.esd').decode()
  for action in ('install','uninstall','recover','status')+(('png-stored','png-compressed') if r3 else ()):
   name=prefix+action+'.sh';assert name in menu
   code=z.read('Toolbox/scripts/'+name).decode()
   assert '"$P/control.sh" '+action+' "$P"' in code and 'exec on -f mmx /bin/ksh' in code
  assert sha(z.read('Custom/'+custom+'/CarPlayMU1367Audio.jar'))==m['audio_sha256']
 if r3:
  assert tx['r2_upgrade_verified'] and tx['two_file_restore_verified']
  assert sha((sd/'Custom'/custom/'artwork-fetch').read_bytes())==m['fetch_sha256']
  with zipfile.ZipFile(sd/'Custom'/custom/'CarPlayMU1367Audio.jar') as jar:
   names=jar.namelist()
   assert not any(any(x in n for x in ('TrackProgress','ProgressModel','AudioDiagnostics','BAPDispatcherTarget','BAPServiceProxy','BAPAudioSDDataPool','FunctionList')) for n in names)
 r={'passed':True,'archive_sha256':m['archive_sha256'],'audio_sha256':m['audio_sha256'],'controller_sha256':tx['controller_sha256'],'verified_files':len(inv),'baseline_changed_files':changed,'added_files':sorted(added),'transaction_scenarios':tx['tests'],'on_unit_validated':False}
 a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
