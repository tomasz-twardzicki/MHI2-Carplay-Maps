#!/usr/bin/env python3
"""Assemble the maintained Toolbox and verified compatibility migrations (GPL-3.0+)."""
import argparse, hashlib, importlib.util, json, re, shutil, subprocess, zipfile
from pathlib import Path
from tools.payload_checks import write_payload_checks
HERE=Path(__file__).resolve().parent
ARCHIVE='CarPlay_Maps_VC_MU1367_791_v1.4.6.zip'
# Published v1.4.6-e ZIP and its verified package before the optional artwork layer was added.
BASE_ARCHIVE_SHA256='d38a53b325052bba028c819e24b4eb6cd042b7dfcc46ecad51320207f9800417'
BASE_VERIFIED_SHA256='a33c03d4340db84c6151820a43477d057c1295c1626b597827ca1749de394a1d'
def sha(f): return hashlib.sha256(f.read_bytes()).hexdigest()
def toolbox_input(name):
    # The SD's upstream Git attributes belong to its distribution, not this
    # source checkout: they would otherwise rewrite pinned legacy bytes/LFS.
    return HERE/'tools/toolbox-attributes.txt' if name=='.gitattributes' else HERE/'toolbox'/name
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('runtime','reader-build','artwork-png-build','artwork-png-host','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();a.runtime=a.runtime.resolve()
    pinned=json.loads((HERE/'RUNTIME.json').read_text())['rebuild']
    for name,h in pinned.items(): assert sha(a.runtime/name)==h,name
    reader=json.loads((a.reader_build/'manifest.json').read_text())
    reader_pin=json.loads((HERE/'READER-RUNTIME.json').read_text())
    assert reader['passed'] and sha(a.reader_build/'rgi-observer')==reader['sha256']==reader_pin['sha256']
    assert sha(HERE/'src/reader/reader.c')==reader['source_sha256']==reader_pin['source_sha256']
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
        before['reader']=sha(custom/'carplay_mu1367/rgi-observer')
        payload={k:(a.runtime/path,name) for k,path,name in [('core','base/core.so','core.so'),('menu','base/VCMenu.jar','VCMenu.jar'),('guidance','CarPlayMU1367Guidance.jar','CarPlayMU1367Guidance.jar')]}
        payload['reader']=(a.reader_build/'rgi-observer','rgi-observer')
        variants[v]=tx.transaction(sd,root,v,payload,before,'carplay-mu1367-map-only','guidance-v3','MU1367_GUIDANCE_V3',pm['build_id'])
        before={k:variants[v]['files'][k] for k in ('core','menu')};before['parent']=sha(root/v/'control.sh')
        payload={k:(a.runtime/'tuning'/name,name) for k,name in [('core','core.so'),('menu','VCMenu.jar')]}
        tv[v]=tx.transaction(sd,tuning,v,payload,before,'carplay-mu1367-guidance-v3','turn-cards','MU1367_TURN_CARDS',variants[v]['build_id'])
    # Compressed album artwork: built into the package and installed by default since v1.4.6.
    spec=importlib.util.spec_from_file_location('artwork_png',HERE/'tools/package-artwork-png.py');png=importlib.util.module_from_spec(spec);spec.loader.exec_module(png)
    artwork_png=png.add_layer(sd,a.artwork_png_build.resolve(),a.artwork_png_host.resolve(),True)
    actions=(HERE/'tools/actions.sh').read_text()
    # Main snapshots that own the reader: this release and archived v1.4.3-e, v1.4.4-e and v1.4.5-e.
    legacy=json.loads((HERE/'tools/legacy-revisions.json').read_text())
    owners=[m['build_id'] for m in variants.values()]+sorted(m['build_id'] for m in legacy.values() if 'reader' in m['before'])
    actions=actions.replace('@READER_VERSIONS@','|'.join(owners))
    code=(HERE/'tools/migrate.sh').read_text()
    # Diagnose old tuning before requesting ordinary release tuning removal.
    needle='if [ -d "$CARDS" ];then\n regular "$CARDS/STATE"'
    pos=actions.index(needle)
    # Migration must run before the ordinary "remove tuning first" gate.
    actions=actions[:pos]+'. "$P/legacy-check.sh" || fail LEGACY_CHECK_SCRIPT\n'+actions[pos:]
    # migrate.sh handles both latest and old tuning; the existing gate runs afterwards.
    actions=actions.replace('. "$P/legacy-check.sh" || fail LEGACY_CHECK_SCRIPT\n','. "$P/legacy-check.sh" || fail LEGACY_CHECK_SCRIPT\n'+code+'\n')
    actions=actions.replace('echo MU1367_GUIDANCE_V3_SUITE_INSTALLED_FULL_REBOOT_REQUIRED','echo MU1367_RELEASE_1_4_6_INSTALLED_FULL_REBOOT_REQUIRED')
    (root/'actions.sh').write_text(actions)
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
        paths={'core':'carplaymaps/core.so','menu':'eso/hmi/lsd/jars/VCMenu.jar','guidance':'eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar','reader':'carplay-mu1367/rgi-observer'}
        for k,hfile in m['files'].items():
            sh+='  if [ "$IDENTITY" = "$LROOT/control.sh" ] || [ '+k+' = guidance ];then\n'
            sh+='   parents "$APP/'+paths[k]+'" && regular "$APP/'+paths[k]+'" && "$P/verify" "$APP/'+paths[k]+'" '+hfile+' || return 1\n  fi\n'
        sh+='  regular "$LROOT/parent.sha256" && "$P/verify" "$APP/'+m['parent']+'/control.sh" "$(cat "$LROOT/parent.sha256")" || return 1\n'
        sh+='  return 0;;\n'
    sh+=' *) return 1;;\n esac\n}\n'
    (root/'legacy-check.sh').write_text(sh)
    (root/'release-versions.sh').write_text('case "$(cat "$MAIN/VERSION")" in\n '+ '|'.join(m['build_id'] for m in variants.values())+') RELEASE_CURRENT=yes;;\n *) RELEASE_CURRENT=no;;\nesac\n')
    shutil.copy2(HERE/'evidence/p4521-factory.json',sd/'P4521_FACTORY.json')
    for n in ('INSTALL.md','KNOWN-ISSUES.md','DEVELOPMENT.md','READER-RECOVERY.md','RELEASE-NOTES.md'):
        shutil.copy2(HERE/n,sd/('START_HERE.md' if n=='INSTALL.md' else n))
    shutil.copy2(HERE/'RECOVERY.md',sd/'MU1367_OEM_RESET_INSTALL.md')
    guide=sd/'READER-RECOVERY.md'
    guide.write_text(guide.read_text().replace('](INSTALL.md)','](START_HERE.md)'))
    menu=sd/'Toolbox/GEM/carplay-maps-vc.esd'
    menu_text=menu.read_text()
    old_banner='MU1367 / 791 v1.4.3 - P4521 experimental'
    assert old_banner in menu_text
    menu_text=menu_text.replace(old_banner,'MU1367 / 791 v1.4.6')
    # GEM menus are static, so the reboot entry is permanent; the script refuses
    # while an install runs and then uses the Toolbox's own reboot helper.
    install_entry='    label "Reset saved MU UI settings (reboot)"\n'
    assert menu_text.count(install_entry)==1
    menu_text=menu_text.replace(install_entry,install_entry+'\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_reboot.sh"\n    label "Reboot unit (after install completes)"\n')
    menu.write_text(menu_text)
    shutil.copy2(HERE/'tools/cpmap_reboot.sh',sd/'Toolbox/scripts/cpmap_reboot.sh')
    (sd/'README.md').write_text('# MU1367 / 791 v1.4.6\n\nStable release, based on v1.4.6-e.\n\nRight U-turn lane arrows in left-hand traffic, Apple Maps guidance with any phone language, 27 fps / IDR 5 as the default map stream and compressed album artwork by default. Start with [START_HERE.md](START_HERE.md) and [RELEASE-NOTES.md](RELEASE-NOTES.md).\n')
    shutil.copy2(HERE/'NOTICE.md',sd/'NOTICE.md')
    manifest={'version':'1.4.6','experimental':False,'prerelease':False,'base_version':'1.4.6-e','base_archive_sha256':BASE_ARCHIVE_SHA256,'base_verified_package_sha256':BASE_VERIFIED_SHA256,'artwork_png':artwork_png,'reader_build':'MU1367-reader-v1.4.4-e','guidance_hold_ms':180000,'reader_restart_budget':{'per_window':3,'stable_window_ms':600000,'lifetime_ceiling':64,'backoff_ms':[1000,2000,4000]},'reader_sha256':reader['sha256'],'reader_source_sha256':reader['source_sha256'],'release_changes':'Stable v1.4.6: v1.4.6-e with 27 fps / IDR 5 as the default stream and compressed album artwork installed by default.','guidance_recover_ms':20000,'guidance_stop_grace_ms':1500,'archive_name':ARCHIVE,'firmware':'K4525 / P4521 MU1367','supported_firmware':[{'train':'MHI2_ER_VWG13_K4525','experimental':False},{'train':'MHI2_ER_VWG13_P4521','experimental':True}],'p4521_prior_experimental_vehicle_tested':True,'p4521_final_package_vehicle_tested':False,'cluster':'791','variants':variants,'tuning_variants':tv,
        'files':variants['6']['files'],'defaults':{'fps':27,'idr':5,'cards':False,'compressed_artwork':True,'safe_area':[200,96,400,364]},
        'stream_choices':['20 fps / IDR 5','25 fps / IDR 5','27 fps / IDR 5 (default)','30 fps / IDR 5','40 fps / IDR 5'],'stream_values':[5,4,6,2,1],'guidance_build':'MU1367-guidance-v1.4.6-e','mini_pico_card_suppression':False,'inactive_lane_blanks':'OEM behavior',
        'release_package_vehicle_tested':False,'feature_vehicle_results':'See KNOWN-ISSUES.md; final packaging and migration verified off-unit.'}
    (sd/'MU1367_RELEASE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Check every CarPlay migration/recovery payload before persistent writes.
    write_payload_checks(custom)
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
