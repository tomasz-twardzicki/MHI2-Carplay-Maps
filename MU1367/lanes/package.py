#!/usr/bin/env python3
"""Add a reversible lane layer to the immutable MU1367 v1.3.0 SD bundle.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import zipfile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'port'))
from firmware import sha

BASE_SHA='19a136685d1e55d8630bfe38146a75a8b999fad0198a3a0f850f075f631a50b9'
TARGETS={
 'guidance':('eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar','CarPlayMU1367Guidance.jar'),
 'menu':('eso/hmi/lsd/jars/VCMenu.jar','VCMenu.jar'),
 'core':('carplaymaps/core.so','core.so'),
 'parent':('carplay-mu1367/control.sh',None),
 'settings':('carplay-mu1367-settings/control.sh',None)}

GUARD='''# Keep lane recovery ahead of either parent layer.
case "${1:-status}" in uninstall|recover)
 L=${CPMAP_TEST_ROOT:-}
 if [ -z "$L" ] && [ ! -s /ifs/lsd.jxe ];then L=/net/mmx;fi
 L=$L/mnt/app/carplay-mu1367-lanes
 if [ -s "$L/STATE" ] && [ "$(cat "$L/STATE")" != removed ];then
  echo MU1367_REMOVE_OR_RECOVER_LANES_LAYER_FIRST;exit 1
 fi;;
esac
'''

def guarded(controller,guard):
 needle='set -u\n'
 if controller.count(needle)!=1:raise ValueError('Controller header changed')
 return controller.replace(needle,needle+guard)

def render(payload,stage):
 parent=stage/'Custom/carplay_mu1367';settings=stage/'Custom/carplay_mu1367_settings'
 old={'guidance':sha((parent/'CarPlayMU1367Guidance.jar').read_bytes()),
      'menu':sha((settings/'VCMenu.jar').read_bytes()),'core':sha((settings/'core.so').read_bytes()),
      'parent':sha(guarded((parent/'control.sh').read_text(),(settings/'guard').read_text()).encode()),
      'settings':sha((settings/'control.sh').read_bytes())}
 hashes={k:sha((payload/n).read_bytes()) for k,(_,n) in TARGETS.items() if n}
 guard_sha=sha(GUARD.encode())
 identity={'files':hashes,'before':old,'guard':guard_sha,'controller':sha((HERE/'control.sh').read_bytes())}
 build='MU1367-lanes-'+sha(json.dumps(identity,sort_keys=True).encode())[:12]
 table='KEYS='+shlex.quote(' '.join(TARGETS))+'\nFILES='+shlex.quote(' '.join(hashes))+'\n'
 table+='PARENT_BUILD='+shlex.quote((parent/'VERSION').read_text().strip())+'\n'
 table+='SETTINGS_BUILD='+shlex.quote((settings/'VERSION').read_text().strip())+'\nGUARD_SHA='+guard_sha+'\n'
 table+='target(){ case "$1" in\n'+''.join(' '+k+') echo "$APP/'+v[0]+'" ;;\n' for k,v in TARGETS.items())+' *) return 1;;esac; }\n'
 table+='payload(){ case "$1" in\n'+''.join(' '+k+') echo '+shlex.quote(v[1])+' ;;\n' for k,v in TARGETS.items() if v[1])+' *) return 1;;esac; }\n'
 for name,values in [('expected',hashes),('before',old)]:
  table+=name+'(){ case "$1" in\n'+''.join(' '+k+') echo '+v+' ;;\n' for k,v in values.items())+' *) return 1;;esac; }\n'
 controller=(HERE/'control.sh').read_text().replace('@BUILD@',shlex.quote(build)).replace('@TABLE@',table)
 return build,controller,old

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('base-zip','build','host-result','qnx-result','output'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();runtime=json.loads((a.build/'manifest.json').read_text())
 host=json.loads(a.host_result.read_text());qnx=json.loads(a.qnx_result.read_text())
 if sha(a.base_zip.read_bytes())!=BASE_SHA:p.error('Exact published v1.3.0 ZIP required')
 for result in (host,qnx):
  if not result['passed'] or result['files']!=runtime['files']:p.error('Exact passing runtime evidence required')
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);stage=out/'sd-card';stage.mkdir()
 with zipfile.ZipFile(a.base_zip) as z:
  for item in z.infolist():
   path=Path(item.filename)
   if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe base archive path')
   dest=stage/path;dest.parent.mkdir(parents=True,exist_ok=True)
   if item.is_dir():dest.mkdir(exist_ok=True);continue
   dest.write_bytes(z.read(item));dest.chmod((item.external_attr>>16)&0o777 or 0o644)
 payload=stage/'Custom/carplay_mu1367_lanes';payload.mkdir()
 for name,h in runtime['files'].items():
  source=a.build/('hmi' if name=='CarPlayMU1367Guidance.jar' else 'runtime')/name
  if sha(source.read_bytes())!=h:p.error('Runtime changed since verification')
  shutil.copy2(source,payload/name)
 shutil.copy2(stage/'Custom/carplay_mu1367/verify',payload/'verify')
 (payload/'guard').write_text(GUARD)
 build,controller,before=render(payload,stage)
 (payload/'VERSION').write_text(build+'\n');(payload/'control.sh').write_text(controller);(payload/'control.sh').chmod(0o755)
 subprocess.run(['/bin/ksh','-n',str(payload/'control.sh')],check=True)
 scripts=stage/'Toolbox/scripts';menu=stage/'Toolbox/GEM/carplay-maps-vc.esd'
 for action,label in [('install','4. Add native lanes + default cards OFF (791)'),('status','Show native lane adapter status'),('uninstall','Remove native lane layer (reboot)'),('recover','Recover interrupted lane layer (reboot)')]:
  name='cpmap_lanes_'+action+'.sh'
  script='''#!/bin/ksh
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ];then M=/net/mmx;fi
P=""
for V in ${CPMAP_TEST_MEDIA:-/fs/sda0 /fs/sdb0 /net/mmx/fs/sda0 /net/mmx/fs/sdb0};do
 if [ -s "$V/Custom/carplay_mu1367_lanes/VERSION" ];then P=$V/Custom/carplay_mu1367_lanes;break;fi
done
S=$M/mnt/app/carplay-mu1367-lanes/control.sh
'''
  if action=='install':script+='[ -n "$P" ] || exit 1\nS=$P/control.sh\n'
  script+='/bin/ksh "$S" '+action+' "$P"\n'
  (scripts/name).write_text(script);(scripts/name).chmod(0o755)
  block='\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/'+name+'"\n    label "'+label+'"\n'
  with menu.open('a') as f:f.write(block)
 restore=scripts/'cpmap_restore.sh';text=restore.read_text();needle='S=$M/mnt/app/carplay-mu1367-settings\n'
 if text.count(needle)!=1:raise ValueError('Full restore wrapper changed')
 text=text.replace(needle,'''L=$M/mnt/app/carplay-mu1367-lanes
if [ -s "$L/STATE" ] && [ "$(cat "$L/STATE")" != removed ];then
 /bin/ksh "$L/control.sh" uninstall || exit $?
fi
'''+needle);restore.write_text(text)
 for name in ('README.md','INSTALL.md','RESEARCH.md'):
  (stage/('MU1367_LANES_'+name)).write_text((HERE/name).read_text().replace('](INSTALL.md)','](MU1367_LANES_INSTALL.md)').replace('](RESEARCH.md)','](MU1367_LANES_RESEARCH.md)'))
 overview=stage/'MU1367_README.md';overview.write_text('Optional step 4 adds native lane guidance and defaults turn cards OFF. Read `MU1367_LANES_INSTALL.md`. This lane layer is not yet vehicle validated.\n\n'+overview.read_text())
 shutil.copytree(HERE,payload/'source',ignore=lambda d,n:[x for x in n if x.startswith('build-') or x in ('__pycache__','VERIFICATION.json')])
 manifest={'build_id':build,'firmware':'MU1367','cluster':'791','runtime':runtime,'before':before,'host':host,'qnx':qnx,
  'parent_archive_sha256':BASE_SHA,'native_driver_and_reader_changed':False,'existing_preferences_retained':True,'card_default':'off','on_unit_validated':False}
 (payload/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 archive=out/'CarPlay_Maps_VC_MU1367_791_Native_Lanes_Test.zip'
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for file in sorted(stage.rglob('*')):
   if file.is_file():z.write(file,file.relative_to(stage))
 manifest['archive_sha256']=sha(archive.read_bytes());(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (out/'SHA256SUMS.txt').write_text(manifest['archive_sha256']+'  '+archive.name+'\n')
 print(json.dumps({'archive':str(archive),'sha256':manifest['archive_sha256'],'build_id':build}))

if __name__=='__main__':main()
