#!/usr/bin/env python3
"""Assemble the maintained Toolbox and verified compatibility migrations (GPL-3.0+)."""
import argparse, hashlib, importlib.util, json, re, shutil, subprocess, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ARCHIVE='CarPlay_Maps_VC_MU1367_791_v1.4.1.zip'
def sha(f): return hashlib.sha256(f.read_bytes()).hexdigest()
def toolbox_input(name):
    # The SD's upstream Git attributes belong to its distribution, not this
    # source checkout: they would otherwise rewrite pinned legacy bytes/LFS.
    return HERE/'tools/toolbox-attributes.txt' if name=='.gitattributes' else HERE/'toolbox'/name
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('runtime','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();a.runtime=a.runtime.resolve()
    pinned=json.loads((HERE/'RUNTIME.json').read_text())['rebuild']
    for name,h in pinned.items(): assert sha(a.runtime/name)==h,name
    for name,h in json.loads((HERE/'toolbox-inputs.json').read_text()).items():assert sha(toolbox_input(name))==h,name
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);sd=out/'sd-card';shutil.copytree(HERE/'toolbox',sd)
    shutil.copy2(toolbox_input('.gitattributes'),sd/'.gitattributes')
    custom=sd/'Custom';root=custom/'carplay_mu1367_guidance_v3';root.mkdir();tuning=custom/'carplay_mu1367_v3_turn_cards';tuning.mkdir()
    parent=custom/'carplay_mu1367_map_only'
    for n in ('verify','COMMANDS.json'):shutil.copy2(parent/n,root/n)
    spec=importlib.util.spec_from_file_location('transactions',HERE/'tools/transaction.py');tx=importlib.util.module_from_spec(spec);spec.loader.exec_module(tx)
    variants={};tv={}
    for v in ('6','7','6-road','7-road'):
        pm=json.loads((parent/v/'manifest.json').read_text());before=dict(pm['files']);before['parent']=sha(parent/v/'control.sh')
        payload={k:(a.runtime/path,name) for k,path,name in [('core','base/core.so','core.so'),('menu','base/VCMenu.jar','VCMenu.jar'),('guidance','CarPlayMU1367Guidance.jar','CarPlayMU1367Guidance.jar')]}
        variants[v]=tx.transaction(sd,root,v,payload,before,'carplay-mu1367-map-only','guidance-v3','MU1367_GUIDANCE_V3',pm['build_id'])
        before={k:variants[v]['files'][k] for k in ('core','menu')};before['parent']=sha(root/v/'control.sh')
        payload={k:(a.runtime/'tuning'/name,name) for k,name in [('core','core.so'),('menu','VCMenu.jar')]}
        tv[v]=tx.transaction(sd,tuning,v,payload,before,'carplay-mu1367-guidance-v3','turn-cards','MU1367_TURN_CARDS',variants[v]['build_id'])
    actions=(HERE/'tools/actions.sh').read_text()
    code=(HERE/'tools/migrate.sh').read_text()
    # Diagnose old tuning before requesting ordinary release tuning removal.
    needle='if [ -d "$CARDS" ];then\n regular "$CARDS/STATE"'
    pos=actions.index(needle)
    # Migration must run before the ordinary "remove tuning first" gate.
    actions=actions[:pos]+'. "$P/legacy-check.sh" || fail LEGACY_CHECK_SCRIPT\n'+actions[pos:]
    # migrate.sh handles both latest and old tuning; the existing gate runs afterwards.
    actions=actions.replace('. "$P/legacy-check.sh" || fail LEGACY_CHECK_SCRIPT\n','. "$P/legacy-check.sh" || fail LEGACY_CHECK_SCRIPT\n'+code+'\n')
    actions=actions.replace('echo MU1367_GUIDANCE_V3_SUITE_INSTALLED_FULL_REBOOT_REQUIRED','echo MU1367_RELEASE_1_4_1_INSTALLED_FULL_REBOOT_REQUIRED')
    (root/'actions.sh').write_text(actions)
    legacy=json.loads((HERE/'tools/legacy-revisions.json').read_text())
    sh='''# Generated exact identities of supported local revisions. No saved code runs before this gate.
legacy_check(){
 LROOT=$1;IDENTITY=$2
 parents "$LROOT/control.sh" && regular "$LROOT/control.sh" && regular "$IDENTITY" || return 1
 regular "$LROOT/STATE" && regular "$LROOT/VERSION" && regular "$LROOT/BACKUPS_READY" || return 1
 [ "$(cat "$LROOT/STATE")" = installed ] || return 1
 [ -d "$LROOT/backup" ] && [ ! -L "$LROOT/backup" ] || return 1
 regular "$LROOT/verify" && "$P/verify" "$LROOT/verify" "$("$P/verify" "$P/verify")" || return 1
 case "$("$P/verify" "$IDENTITY")" in
'''
    for h,m in legacy.items():
        sh+=' '+h+')\n  [ "$(cat "$LROOT/VERSION")" = '+m['build_id']+' ] || return 1\n'
        for k,before in m['before'].items():
            sh+='  regular "$LROOT/backup/'+k+'" && regular "$LROOT/backup/'+k+'.sha256" || return 1\n'
            sh+='  [ "$(cat "$LROOT/backup/'+k+'.sha256")" = '+before+' ] && "$P/verify" "$LROOT/backup/'+k+'" '+before+' || return 1\n'
        paths={'core':'carplaymaps/core.so','menu':'eso/hmi/lsd/jars/VCMenu.jar','guidance':'eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar'}
        for k,hfile in m['files'].items():
            sh+='  if [ "$IDENTITY" = "$LROOT/control.sh" ] || [ '+k+' = guidance ];then\n'
            sh+='   parents "$APP/'+paths[k]+'" && regular "$APP/'+paths[k]+'" && "$P/verify" "$APP/'+paths[k]+'" '+hfile+' || return 1\n  fi\n'
        sh+='  regular "$LROOT/parent.sha256" && "$P/verify" "$APP/'+m['parent']+'/control.sh" "$(cat "$LROOT/parent.sha256")" || return 1\n'
        sh+='  return 0;;\n'
    sh+=' *) return 1;;\n esac\n}\n'
    (root/'legacy-check.sh').write_text(sh)
    (root/'release-versions.sh').write_text('case "$(cat "$MAIN/VERSION")" in\n '+ '|'.join(m['build_id'] for m in variants.values())+') RELEASE_CURRENT=yes;;\n *) RELEASE_CURRENT=no;;\nesac\n')
    for n in ('INSTALL.md','KNOWN-ISSUES.md','DEVELOPMENT.md'):
        shutil.copy2(HERE/n,sd/('START_HERE.md' if n=='INSTALL.md' else n))
    shutil.copy2(HERE/'RECOVERY.md',sd/'MU1367_OEM_RESET_INSTALL.md')
    (sd/'README.md').write_text('# MU1367 / 791 v1.4.1\n\nStart with [START_HERE.md](START_HERE.md).\n')
    shutil.copy2(HERE/'NOTICE.md',sd/'NOTICE.md')
    manifest={'version':'1.4.1','archive_name':ARCHIVE,'firmware':'K4525 MU1367','cluster':'791','variants':variants,'tuning_variants':tv,
        'files':variants['6']['files'],'defaults':{'fps':30,'idr':5,'cards':False,'safe_area':[200,96,400,364]},
        'guidance_build':'MU1367-guidance-31dfc8d5a6f2','mini_pico_card_suppression':False,'inactive_lane_blanks':'OEM behavior',
        'release_package_vehicle_tested':False,'feature_vehicle_results':'See KNOWN-ISSUES.md; final packaging and migration verified off-unit.'}
    (sd/'MU1367_RELEASE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # One inventory covers all migration payloads before the first persistent write.
    checks=[]
    for f in sorted(custom.rglob('*')):
        if f.is_file() and f.name!='payload-check.sh':checks.append('"$P/verify" "$CUSTOM_CHECK/'+str(f.relative_to(custom))+'" '+sha(f)+' || return 1')
    body='CUSTOM_CHECK=${P%/*}\n'+'\n'.join(checks)+'\n'
    for r in (root,parent,custom/'carplay_mu1367_refinements'):(r/'payload-check.sh').write_text(body)
    for f in [*custom.rglob('*.sh'),*(sd/'Toolbox/scripts').glob('cpmap*.sh')]:
        subprocess.run(['/bin/ksh','-n',str(f)],check=True,capture_output=True);f.chmod(0o755)
    inventory={str(f.relative_to(sd)):sha(f) for f in sorted(sd.rglob('*')) if f.is_file()}
    (sd/'FILES_SHA256.json').write_text(json.dumps(inventory,indent=2)+'\n')
    archive=out/ARCHIVE
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(sd.rglob('*')):
            if f.is_file():z.write(f,f.relative_to(sd))
    manifest.update(archive_sha256=sha(archive),archive_bytes=archive.stat().st_size)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'SHA256SUMS.txt').write_text(sha(archive)+'  '+ARCHIVE+'\n')
    print(json.dumps({'archive':str(archive),'sha256':sha(archive),'files':len(inventory)}))
if __name__=='__main__':main()
