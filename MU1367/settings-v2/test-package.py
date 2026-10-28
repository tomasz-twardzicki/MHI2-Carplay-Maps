#!/usr/bin/env python3
"""Check exact archive, unchanged adapters and actual three-layer OEM restore.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'port'))
from firmware import sha


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','base','inputs','verifier','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();stage=a.package/'sd-card';scripts=stage/'Toolbox/scripts';checks=0
 def check(value,message):
  nonlocal checks
  if not value:raise AssertionError(message)
  checks+=1
 archive=a.package/'CarPlay_Maps_VC_MU1367_791_MU_Settings_Test.zip'
 with zipfile.ZipFile(archive) as z:
  check(z.testzip() is None,'archive CRC')
  for name in z.namelist():
   f=stage/name;check(z.read(name)==f.read_bytes(),'archive bytes '+name)
   check((z.getinfo(name).external_attr>>16)&0o777==f.stat().st_mode&0o777,'archive mode '+name)
 for f in (stage/'Toolbox/GEM').glob('carplay-maps-vc*.esd'):
  for name in re.findall(r'/eso/hmi/engdefs/scripts/mqb/([^"\s]+)',f.read_text()):
   check((scripts/name).is_file(),'menu script '+name);subprocess.run(['/bin/ksh','-n',str(scripts/name)],check=True)
 # Parent native/HMI payloads and standalone baseline are not rebuilt here.
 for subtree in ('Custom/carplay_mu1367','Custom/carplay_maps_vc'):
  for f in (a.base/'sd-card'/subtree).rglob('*'):
   if f.is_file():check(f.read_bytes()==(stage/f.relative_to(a.base/'sd-card')).read_bytes(),'unchanged parent payload '+str(f))
 with tempfile.TemporaryDirectory(prefix='mu1367-settings-package-') as temp:
  root=Path(temp)/'mmx';app=root/'mnt/app'
  for dest,src in [('ifs/lsd.jxe','lsd.jxe'),('mnt/app/armle/lib/dll/ipod-drvr-iap2.so','driver'),('mnt/system/etc/mm/iap2.cfg','iap2.cfg'),('mnt/app/eso/hmi/lsd/lsd.sh','boot'),('mnt/app/eso/bin/apps/dio_manager','dio')]:
   f=root/dest;f.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a.inputs/src,f)
  (root/'ramdisk').mkdir();(app/'eso/hmi/lsd/jars').mkdir()
  installed=app/'eso/hmi/engdefs/scripts/mqb';shutil.copytree(scripts,installed)
  boot=app/'eso/hmi/lsd/lsd.sh';dio=app/'eso/bin/apps/dio_manager';o_boot=boot.read_bytes();o_dio=dio.read_bytes()
  # Substitute only the test host verifier; retain real controller/payload bytes.
  media=Path(temp)/'sd';shutil.copytree(stage/'Custom',media/'Custom',ignore=shutil.ignore_patterns('source'))
  parent=media/'Custom/carplay_mu1367';layer=media/'Custom/carplay_mu1367_settings'
  for d in (parent,layer):shutil.copy2(a.verifier,d/'verify')
  env=dict(os.environ,CPMAP_TEST_ROOT=str(root),CPMAP_TEST_MEDIA=str(media))
  def run(file,*args,success=True):
   r=subprocess.run(['/bin/ksh',str(file),*map(str,args)],env=env,capture_output=True,text=True,timeout=60)
   check((r.returncode==0)==success,r.stdout+r.stderr);return r.stdout
  maps=media/'Custom/carplay_maps_vc/payload'
  run(maps/'common/install-carplay-maps.sh',maps,'MU1367','791')
  run(parent/'control.sh','install',parent)
  run(installed/'cpmap_settings_install.sh')
  check((app/'carplay-mu1367-settings/STATE').read_text().strip()=='installed','settings installed')
  check(boot.read_text().count('-Xbootclasspath/p:')==1,'one effective prepend')
  for name in ('VCMenu','CarPlayClusterControls','CarPlayMU1367Guidance','CarPlayMU1367Audio','CarPlayMU1367NavIgnore'):
   check(boot.read_text().count(name+'.jar')==1,'one JAR token '+name)
  check('USE_APP_CONNECT_DISPLAY_SETTINGS' in run(installed/'cpmap_tune.sh','wide-card',success=False),'GEM tuning guard')
  check('REMOVE_SETTINGS_LAYER_FIRST' in run(installed/'cpmap_restore_core.sh',success=False),'direct base restore guard')
  for action in ('uninstall','recover'):
   check('SETTINGS_LAYER_FIRST' in run(app/'carplay-mu1367/control.sh',action,success=False),'parent '+action+' guard')
  run(installed/'cpmap_install_791.sh',success=False)
  # No SD: actual full wrapper must remove settings, then native/audio, then base.
  shutil.rmtree(media);run(installed/'cpmap_restore.sh')
  check(boot.read_bytes()==o_boot,'exact factory boot restored')
  check(dio.read_bytes()==o_dio,'exact factory DIO restored')
  check((app/'armle/lib/dll/ipod-drvr-iap2.so').read_bytes()==(a.inputs/'driver').read_bytes(),'exact OEM driver restored')
  check((root/'mnt/system/etc/mm/iap2.cfg').read_bytes()==(a.inputs/'iap2.cfg').read_bytes(),'exact OEM config restored')
  check(not (app/'carplaymaps').exists(),'base video state removed')
  for name in ('VCMenu','CarPlayClusterControls','CarPlayMU1367Guidance','CarPlayMU1367Audio','CarPlayMU1367NavIgnore'):
   check(not (app/'eso/hmi/lsd/jars'/(name+'.jar')).exists(),'JAR absence restored '+name)
  for name in ('carplay-mu1367','carplay-mu1367-settings'):
   check((app/name/'STATE').read_text().strip()=='removed','retained recovery '+name)
 result={'passed':True,'checks':checks,'archive_sha256':sha(archive.read_bytes()),'test_sha256':sha(Path(__file__).read_bytes()),'full_settings_hmi_video_factory_restore_without_sd':True,'parent_payloads_unchanged':True,'on_unit_validated':False}
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
