#!/usr/bin/env python3
"""Generate firmware-pinned snapshot transactions for release and optional tuning."""
import hashlib,json,shlex,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def change(s,old,new):
    assert s.count(old)==1,old
    return s.replace(old,new)

def transaction(sd,root,variant,payloads,old,parent,layer,prefix,parent_build):
    p=root/variant;p.mkdir()
    template=(HERE/'transaction.sh').read_text()
    template=template.replace('# SPDX-License-Identifier: GPL-3.0-or-later','# SPDX-License-Identifier: GPL-3.0-or-later\n# MU1367 integration release 1.4.6')
    c=template.replace('carplay-mu1367-lanes','carplay-mu1367-'+layer).replace('MU1367_LANES',prefix).replace('.lanes-new','.'+layer+'-new').replace('for K in parent settings;','for K in parent;')
    c=change(c,'  echo "Cards: App-Connect > Virtual Cockpit settings > navigation card ON/OFF; reconnect after changing"','  echo "See START_HERE.md for map-only and optional turn-card tuning"')
    guard='''# Preserve the child layer snapshot before removing its parent.
case "${1:-status}" in uninstall|recover|install)
 G=${CPMAP_TEST_ROOT:-}
 if [ -z "$G" ] && [ ! -s /ifs/lsd.jxe ];then G=/net/mmx;fi
 G=$G/mnt/app/carplay-mu1367-LAYER
 if [ -d "$G" ];then
  [ -f "$G/STATE" ] && [ ! -L "$G/STATE" ] && [ "$(cat "$G/STATE")" = removed ] || { echo PREFIX_REMOVE_CHILD_FIRST;exit 1; }
 fi;;esac
'''.replace('LAYER',layer).replace('PREFIX',prefix)
    (p/'guard').write_text(guard)
    keys=list(payloads)+['parent']
    targets={'core':'carplaymaps/core.so','guidance':'eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar','menu':'eso/hmi/lsd/jars/VCMenu.jar','reader':'carplay-mu1367/rgi-observer','parent':parent+'/control.sh'}
    new={k:sha(src.read_bytes()) for k,(src,_) in payloads.items()}
    gates=' [ "$(cat "$APP/'+parent+'/STATE" 2>/dev/null)" = installed ] && [ "$(cat "$APP/'+parent+'/VERSION" 2>/dev/null)" = '+shlex.quote(parent_build)+' ] || fail EXACT_IMMEDIATE_PARENT_REQUIRED\n'
    art=sd/'Custom/carplay_mu1367_artwork'
    for path,source in [('armle/lib/dll/ipod-drvr-iap2.so',art/'ipod-drvr-iap2.so'),('eso/hmi/lsd/jars/CarPlayMU1367Audio.jar',art/'CarPlayMU1367Audio.jar'),('eso/hmi/lsd/jars/CarPlayClusterControls.jar',sd/'Custom/carplay_mu1367_settings/CarPlayClusterControls.jar')]:
        gates+=' check "$APP/'+path+'" '+sha(source.read_bytes())+' || fail UNEXPECTED_UNCHANGED_RUNTIME\n'
    c=change(c,' || fail EXACT_V130_SETTINGS_REQUIRED\n',' || fail EXACT_V130_SETTINGS_REQUIRED\n'+gates)
    build=prefix.lower().replace('_','-')+'-'+sha(json.dumps({'before':old,'after':new,'controller':c,'guard':guard},sort_keys=True).encode())[:12]
    table='KEYS='+shlex.quote(' '.join(keys))+'\nFILES='+shlex.quote(' '.join(payloads))+'\nGUARD_SHA='+sha(guard.encode())+'\n'
    for var,name in [('PARENT_BUILD','carplay_mu1367'),('SETTINGS_BUILD','carplay_mu1367_settings')]:table+=var+'='+shlex.quote((sd/'Custom'/name/'VERSION').read_text().strip())+'\n'
    for fn,values in [('target',{k:'$APP/'+targets[k] for k in keys}),('payload',{k:name for k,(_,name) in payloads.items()}),('before',old),('expected',new)]:
        table+=fn+'(){ case "$1" in\n'+''.join(' '+k+') echo "'+v+'";;\n' for k,v in values.items())+' *) return 1;;esac; }\n'
    c=c.replace('@BUILD@',shlex.quote(build)).replace('@TABLE@',table)
    (p/'control.sh').write_text(c);(p/'VERSION').write_text(build+'\n')
    for src,name in payloads.values():shutil.copy2(src,p/name)
    shutil.copy2(art/'verify',p/'verify')
    result={'build_id':build,'before':old,'files':new,'parent':parent,'variant':variant,'on_unit_validated':False}
    (p/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');return result
