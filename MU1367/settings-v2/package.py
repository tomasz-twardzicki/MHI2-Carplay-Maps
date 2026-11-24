#!/usr/bin/env python3
"""Extend the verified MU1367 bundle without overwriting its original archive.
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

UPSTREAM_FILES={
 'carplay-cluster-supervisor':'350f617c5618046cef806d38c66a422fe5ac7d34ded50b70393d72f8582c4794',
 'altscreen-most-bridge':'6c5210cac43699caf027b1f217dc39f4fe87c8b2aee3fa6366c20856772f9c35',
 'libcpvc-mirror-tap.so':'647f3dbdd51245e16785c2ddc46afc2158fc2c06292f9d1e9e4077b17de0c69c',
 'libcpvc-dmdt-query.so':'9b72ea95c21a9ad2170a0b855a4c691f3b2629c590b85b0e85f7fd177236f729',
 'cpvc-mirror-canvas-791':'618b6bda53a2ee635be594734874dc5d20b2d92505ae24027b0876d33e75abc0',
 'dio_manager.wrapper.sh':'1e2cecd872d864db9404d1d89e0f6ba5ba64fb1d162263b3f4e9ee010225863f'}
TARGETS={
 'menu':('eso/hmi/lsd/jars/VCMenu.jar','VCMenu.jar','644'),
 'controls':('eso/hmi/lsd/jars/CarPlayClusterControls.jar','CarPlayClusterControls.jar','644'),
 'core':('carplaymaps/core.so','core.so','644'),
 'supervisor':('carplaymaps/carplay-cluster-supervisor','carplay-cluster-supervisor','755'),
 'bridge':('carplaymaps/altscreen-most-bridge','altscreen-most-bridge','755'),
 'tap':('carplaymaps/libcpvc-mirror-tap.so','libcpvc-mirror-tap.so','644'),
 'query':('carplaymaps/libcpvc-dmdt-query.so','libcpvc-dmdt-query.so','644'),
 'canvas':('carplaymaps/cpvc-mirror-canvas','cpvc-mirror-canvas-791','755'),
 'wrapper':('carplaymaps/dio_manager.wrapper.sh','dio_manager.wrapper.sh','755'),
 'launcher':('eso/bin/apps/dio_manager','dio_manager.wrapper.sh','755'),
 'parent':('carplay-mu1367/control.sh',None,'755'),
 'boot':('eso/hmi/lsd/lsd.sh',None,'755')}


def render(payload,base):
 common=base/'sd-card/Custom/carplay_maps_vc/payload/common'
 parent=base/'sd-card/Custom/carplay_mu1367/control.sh'
 display=json.loads((base/'manifest.json').read_text())['display']
 old={k:[] for k in TARGETS}
 old['controls']=[sha((common/'CarPlayClusterControls.jar').read_bytes())]
 old['core']=[h for n,h in display.items() if n.startswith('791/')]
 for k in ('supervisor','bridge','wrapper','launcher'):old[k]=[sha((common/TARGETS[k][1]).read_bytes())]
 old['parent']=[sha(parent.read_bytes())]
 hashes={k:sha((payload/name).read_bytes()) for k,(_,name,_) in TARGETS.items() if name}
 guard_hash=sha((payload/'guard').read_bytes())
 identity={'files':hashes,'guard':guard_hash,'controller':sha((HERE/'control.sh').read_bytes()),'targets':TARGETS}
 build='MU1367-settings-v2-'+sha(json.dumps(identity,sort_keys=True).encode())[:12]
 table='KEYS='+shlex.quote(' '.join(TARGETS))+'\nFILES='+shlex.quote(' '.join(hashes))+'\n'
 table+='PARENT_BUILD='+shlex.quote((base/'sd-card/Custom/carplay_mu1367/VERSION').read_text().strip())+'\n'
 table+='GUARD_SHA='+guard_hash+'\n'
 for function,which in [('target',0),('payload',1),('mode',2)]:
  table+=function+'(){ case "$1" in\n'
  for k,fields in TARGETS.items():
   if fields[which] is not None:
    value=fields[which]
    table+=' '+k+') echo '+('"$APP/'+value+'"' if function=='target' else shlex.quote(value))+' ;;\n'
  table+=' *) return 1 ;; esac; }\n'
 table+='expected(){ case "$1" in\n'+''.join(' '+k+') echo '+h+' ;;\n' for k,h in hashes.items())+' *) return 1 ;; esac; }\n'
 table+='before(){ case "$1" in\n'
 for k,values in old.items():
  if k=='boot':continue
  expr=' || '.join('check "$2" '+h for h in values) if values else 'absent "$2"'
  table+=' '+k+') '+expr+' ;;\n'
 table+=' *) return 1 ;; esac; }\n'
 return build,(HERE/'control.sh').read_text().replace('@BUILD@',shlex.quote(build)).replace('@TABLE@',table)


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('base','runtime','upstream-toolbox','host-result','qnx-result','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();runtime=json.loads((a.runtime/'manifest.json').read_text());host=json.loads(a.host_result.read_text());qnx=json.loads(a.qnx_result.read_text())
 if not host['passed'] or host['files']!=runtime['files'] or not qnx['passed'] or qnx['files']!=runtime['files']:p.error('Exact passing host and factory runtime evidence required')
 original=json.loads((a.base/'manifest.json').read_text())
 original_archive=a.base/'CarPlay_Maps_VC_MU1367_791_Integration_Test.zip'
 if sha(original_archive.read_bytes())!=original['archive_sha256']:p.error('Original verified integration package required')
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);stage=out/'sd-card'
 shutil.copytree(a.base/'sd-card',stage,ignore=shutil.ignore_patterns('.DS_Store'))
 payload=stage/'Custom/carplay_mu1367_settings';payload.mkdir()
 for name,h in runtime['files'].items():
  if sha((a.runtime/name).read_bytes())!=h:p.error('Runtime changed since verification')
  shutil.copy2(a.runtime/name,payload/name)
 upstream=a.upstream_toolbox/'Custom/carplay_maps_vc/payload/common'
 for name,h in UPSTREAM_FILES.items():
  if sha((upstream/name).read_bytes())!=h:p.error('Wrong upstream release binary: '+name)
  shutil.copy2(upstream/name,payload/name)
 shutil.copy2(stage/'Custom/carplay_mu1367/verify',payload/'verify')
 guard='''# Preserve the settings layer's recovery order.
case "${1:-status}" in uninstall|recover)
 S=${CPMAP_TEST_ROOT:-}
 if [ -z "$S" ] && [ ! -s /ifs/lsd.jxe ]; then S=/net/mmx; fi
 S=$S/mnt/app/carplay-mu1367-settings
 if [ -s "$S/STATE" ] && [ "$(cat "$S/STATE")" != removed ]; then
  echo MU1367_REMOVE_OR_RECOVER_SETTINGS_LAYER_FIRST; exit 1
 fi ;;
esac
'''
 (payload/'guard').write_text(guard)
 build,controller=render(payload,a.base)
 (payload/'VERSION').write_text(build+'\n');(payload/'control.sh').write_text(controller);(payload/'control.sh').chmod(0o755)
 subprocess.run(['/bin/ksh','-n',str(payload/'control.sh')],check=True)
 scripts=stage/'Toolbox/scripts'
 for action,label in [('install','3. Add MU UI settings + map/mirror runtime (791)'),('status','Show MU UI settings status'),('uninstall','Remove MU UI settings layer (reboot)'),('recover','Recover interrupted settings layer (reboot)')]:
  name='cpmap_settings_'+action+'.sh'
  script='''#!/bin/ksh
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ]; then M=/net/mmx; fi
P=""
for V in ${CPMAP_TEST_MEDIA:-/fs/sda0 /fs/sdb0 /net/mmx/fs/sda0 /net/mmx/fs/sdb0}; do
 if [ -s "$V/Custom/carplay_mu1367_settings/VERSION" ]; then P=$V/Custom/carplay_mu1367_settings; break; fi
done
S=$M/mnt/app/carplay-mu1367-settings/control.sh
'''
  if action=='install':script+='[ -n "$P" ] || exit 1\nS=$P/control.sh\n'
  script+='/bin/ksh "$S" '+action+' "$P"\n'
  (scripts/name).write_text(script);(scripts/name).chmod(0o755)
  menu=stage/'Toolbox/GEM/carplay-maps-vc.esd'
  block='\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/'+name+'"\n    label "'+label+'"\n'
  if action=='install':
   text=menu.read_text();needle='    label "2. Install MU1367 / 791 guidance + audio text"\n'
   if text.count(needle)!=1:raise ValueError('Base install menu changed')
   menu.write_text(text.replace(needle,needle+block))
  else:
   with menu.open('a') as f:f.write(block)
 menu.write_text(menu.read_text().replace('MU1367 test -','MU1367 settings v2 test -'))
 restore=scripts/'cpmap_restore.sh';text=restore.read_text();needle='U=$M/mnt/app/carplay-mu1367'
 if text.count(needle)!=1:raise ValueError('Base restore wrapper changed')
 text=text.replace(needle,'''S=$M/mnt/app/carplay-mu1367-settings
if [ -s "$S/STATE" ] && [ "$(cat "$S/STATE")" != removed ]; then
 /bin/ksh "$S/control.sh" uninstall || exit $?
fi
'''+needle);restore.write_text(text)
 tune=scripts/'cpmap_tune.sh';text=tune.read_text();needle='PROFILE=`cat "$ROOT/PROFILE" 2>/dev/null`'
 if text.count(needle)!=1:raise ValueError('Base tuning wrapper changed')
 text=text.replace(needle,'''S=$MMX/mnt/app/carplay-mu1367-settings
if [ -s "$S/STATE" ] && [ "$(cat "$S/STATE")" != removed ]; then
 echo MU1367_USE_APP_CONNECT_DISPLAY_SETTINGS; exit 1
fi
'''+needle);tune.write_text(text)
 # Direct base restoration must also honor the reverse installation order.
 core_restore=scripts/'cpmap_restore_core.sh';text=core_restore.read_text();needle='#!/bin/ksh\n'
 check='''M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && [ ! -s /ifs/lsd.jxe ]; then M=/net/mmx; fi
if [ -s "$M/mnt/app/carplay-mu1367-settings/STATE" ] && [ "$(cat "$M/mnt/app/carplay-mu1367-settings/STATE")" != removed ]; then
 echo MU1367_REMOVE_SETTINGS_LAYER_FIRST; exit 1
fi
'''
 if needle not in text:raise ValueError('Base core restore header changed')
 core_restore.write_text(text.replace(needle,needle+check,1))
 for name in ('README.md','INSTALL.md','UPSTREAM-REVIEW.md'):
  if (HERE/name).exists():
   text=(HERE/name).read_text()
   for old,new in [('INSTALL.md','MU1367_SETTINGS_INSTALL.md'),('UPSTREAM-REVIEW.md','MU1367_SETTINGS_UPSTREAM-REVIEW.md'),('VERIFICATION.json','Custom/carplay_mu1367_settings/manifest.json'),('../port/README.md','MU1367_README.md')]:
    text=text.replace(']('+old+')',']('+new+')')
   (stage/('MU1367_SETTINGS_'+name)).write_text(text)
 overview=stage/'MU1367_README.md'
 overview.write_text('This bundle also includes step 3: native MU settings. Read '
  '`MU1367_SETTINGS_README.md` and `MU1367_SETTINGS_INSTALL.md` before installing.\n\n'+overview.read_text())
 shutil.copytree(HERE,payload/'source',ignore=lambda d,n:[x for x in n if x.startswith('build-') or x in ('__pycache__','VERIFICATION.json')])
 manifest={'build_id':build,'firmware':'MU1367','cluster':'791','upstream_tag':'toolbox-plaintext-v2.0.0','upstream_binaries':UPSTREAM_FILES,'runtime':runtime,'host':host,'qnx':qnx,'parent_build_id':original['build_id'],'parent_archive_sha256':original['archive_sha256'],'guidance_audio_driver_payloads_unchanged':True,'on_unit_validated':False}
 (payload/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 archive=out/'CarPlay_Maps_VC_MU1367_791_MU_Settings_Test.zip'
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for file in sorted(stage.rglob('*')):
   if file.is_file():z.write(file,file.relative_to(stage))
 manifest['archive_sha256']=sha(archive.read_bytes());(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (out/'SHA256SUMS.txt').write_text(manifest['archive_sha256']+'  '+archive.name+'\n');print(json.dumps({'archive':str(archive),'sha256':manifest['archive_sha256']}))


if __name__=='__main__':main()
