#!/usr/bin/env python3
"""Check the complete SD bundle and actual four-layer no-SD factory restore.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
from pathlib import Path
import sys
import zipfile
import stage
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'port'))
from firmware import sha

EXTRA='''
  run(installed/'cpmap_lanes_install.sh')
  check((app/'carplay-mu1367-lanes/STATE').read_text().strip()=='installed','lanes installed')
  lane_manifest=json.loads((lanes/'manifest.json').read_text())
  for name,path in [('CarPlayMU1367Guidance.jar','eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar'),('VCMenu.jar','eso/hmi/lsd/jars/VCMenu.jar'),('core.so','carplaymaps/core.so')]:
   check(sha((app/path).read_bytes())==lane_manifest['runtime']['files'][name],'exact installed lane runtime '+name)
  for action in ('uninstall','recover'):
   check('LANES_LAYER_FIRST' in run(app/'carplay-mu1367-settings/control.sh',action,success=False),'settings '+action+' lane guard')
'''

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','base','base-zip','inputs','verifier','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();shared=HERE.parent/'settings-v2/test-package.py';text=shared.read_text()
 text=stage.replace(text,'CarPlay_Maps_VC_MU1367_791_MU_Settings_Test.zip','CarPlay_Maps_VC_MU1367_791_Native_Lanes_Test.zip')
 text=stage.replace(text,"layer=media/'Custom/carplay_mu1367_settings'","layer=media/'Custom/carplay_mu1367_settings';lanes=media/'Custom/carplay_mu1367_lanes'")
 text=stage.replace(text,'for d in (parent,layer):','for d in (parent,layer,lanes):')
 text=stage.replace(text,"  run(installed/'cpmap_settings_install.sh')","  run(installed/'cpmap_settings_install.sh')\n"+EXTRA)
 text=stage.replace(text,"'SETTINGS_LAYER_FIRST' in run(app/'carplay-mu1367/control.sh'","'LANES_LAYER_FIRST' in run(app/'carplay-mu1367/control.sh'")
 text=stage.replace(text,"for name in ('carplay-mu1367','carplay-mu1367-settings'):","for name in ('carplay-mu1367','carplay-mu1367-settings','carplay-mu1367-lanes'):")
 env={'__file__':str(shared),'__name__':'lane_package_fixture'};exec(compile(text,str(shared),'exec'),env)
 old=sys.argv;sys.argv=['lane-package']
 for n in ('package','base','inputs','verifier','output'):sys.argv+=['--'+n,str(getattr(a,n))]
 try:env['main']()
 finally:sys.argv=old
 # Every original native/settings/baseline payload in the published v1.3 ZIP
 # must survive unchanged alongside the new fourth payload.
 checked=0
 with zipfile.ZipFile(a.base_zip) as z:
  for n in z.namelist():
   if n.startswith(('Custom/carplay_mu1367/','Custom/carplay_mu1367_settings/','Custom/carplay_maps_vc/')):
    assert (a.package/'sd-card'/n).read_bytes()==z.read(n),n;checked+=1
 source=a.package/'sd-card/Custom/carplay_mu1367_lanes/source'
 for file in HERE.iterdir():
  if file.is_file() and not file.name.startswith('build-') and file.name!='VERIFICATION.json':
   assert (source/file.name).read_bytes()==file.read_bytes(),'Missing or outdated release source: '+file.name
 result=json.loads(a.output.read_text());result.update(full_lanes_settings_hmi_video_factory_restore_without_sd=True,original_v130_payload_files_unchanged=checked,complete_lane_source_snapshot=True,test_sha256=sha(Path(__file__).read_bytes()))
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
