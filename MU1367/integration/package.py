#!/usr/bin/env python3
"""Assemble the maintained Toolbox and verified compatibility migrations (GPL-3.0+)."""
import argparse, hashlib, importlib.util, json, re, shlex, shutil, subprocess, zipfile
from pathlib import Path
from tools.payload_checks import write_payload_checks
HERE=Path(__file__).resolve().parent
ARCHIVE='CarPlay_Maps_VC_MU1367_791_v1.5.3.zip'
# Published experimental v1.5.3-e ZIP (its verified package), vehicle-tested before this stable release.
BASE_ARCHIVE_SHA256='28de02d35fc8ed91b0c3b58bbfdb30afc23731cfe2624c1bd77351b6b4ae6312'
BASE_VERIFIED_SHA256=BASE_ARCHIVE_SHA256
# Android Auto layer builds replaced in place: published v1.5.0-e, the car-tested pre-release build, both published v1.5.1-e builds, v1.5.2-e, v1.5.2 and v1.5.3-e.
AA_PREVIOUS=('mu1367-android-auto-ee74f406dd94','mu1367-android-auto-e3e4e1ce3a73','mu1367-android-auto-c1f4833dac00','mu1367-android-auto-ad7f051fd568','mu1367-android-auto-32e92312bde1','mu1367-android-auto-74fd41b287c3','mu1367-android-auto-95f7bc5f3cc4')
# v1.5.2: tuning-menu actions for saved snapshots of earlier installations and rollbacks.
SNAPSHOT_ENTRIES=[('snapshots','List saved snapshots (read only)'),('snapshot-next','Select next snapshot'),
                  ('snapshot-remove','Remove selected snapshot'),('snapshots-remove-all','Remove all saved snapshots')]
def sha(f): return hashlib.sha256(f.read_bytes()).hexdigest()
def toolbox_input(name):
    # The SD's upstream Git attributes belong to its distribution, not this
    # source checkout: they would otherwise rewrite pinned legacy bytes/LFS.
    return HERE/'tools/toolbox-attributes.txt' if name=='.gitattributes' else HERE/'toolbox'/name
def android_auto(sd,custom,feeder_build,main_versions):
    """v1.5.0-e: the Android Auto layer, installed by the same suite action after the main layer."""
    src=HERE/'src/android-auto';pin=json.loads((src/'PROVENANCE.json').read_text())
    fm=json.loads((feeder_build/'manifest.json').read_text())
    assert fm['passed'] and fm['reproducible'] and sha(feeder_build/'aa-most-feeder')==fm['sha256']
    assert fm['source_sha256']==sha(src/'feeder/aa_most_feeder.c') and fm['aeabi_conv_sha256']==sha(src/'feeder/aeabi_conv.c')
    assert fm['bridge_sha256']==sha(feeder_build/'altscreen-most-bridge-aa') and fm['bridge_source_sha256']==sha(HERE/'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c')
    runtime={'libgal_hook.so':(src/'prebuilt/libgal_hook.so','644'),'libdmdt_flush.so':(src/'prebuilt/libdmdt_flush.so','644'),
             'aa-most-feeder':(feeder_build/'aa-most-feeder','755'),'altscreen-most-bridge-aa':(feeder_build/'altscreen-most-bridge-aa','755'),'gal-hook.conf':(src/'unit/gal-hook.conf','644'),'feeder.conf':(src/'unit/feeder.conf','644')}
    for n in ('libgal_hook.so','libdmdt_flush.so'):assert sha(runtime[n][0])==pin[n]['sha256'],n
    files={n:sha(f) for n,(f,_) in runtime.items()};wrapper=src/'unit/gal.wrapper.sh'
    table='FACTORY_GAL='+pin['factory_gal']['sha256']+'\nWRAPPER='+sha(wrapper)+'\nRUNTIME='+shlex.quote(' '.join(runtime))+'\n'
    table+='expected(){ case "$1" in\n'+''.join(' '+n+') echo '+h+';;\n' for n,h in files.items())+' *) return 1;;esac; }\n'
    table+='mode(){ case "$1" in\n'+''.join(' '+n+') echo '+m+';;\n' for n,(_,m) in runtime.items())+' *) return 1;;esac; }\n'
    code=(HERE/'tools/android-auto.sh').read_text().replace('@TABLE@',table).replace('@MAIN_VERSIONS@','|'.join(main_versions)).replace('@AA_PREVIOUS@','|'.join(AA_PREVIOUS))
    build='mu1367-android-auto-'+sha_text(json.dumps({'controller':code,'wrapper':sha(wrapper),'files':files},sort_keys=True))[:12]
    code=code.replace('@BUILD@',build);assert '@BUILD@' not in code and '@TABLE@' not in code and '@MAIN_VERSIONS@' not in code and '@AA_PREVIOUS@' not in code
    root=custom/'carplay_mu1367_android_auto';root.mkdir()
    (root/'control.sh').write_text(code);(root/'VERSION').write_text(build+'\n')
    shutil.copy2(custom/'carplay_mu1367_artwork/verify',root/'verify');shutil.copy2(wrapper,root/'gal.wrapper.sh')
    for n,(f,_) in runtime.items():shutil.copy2(f,root/n)
    result={'build_id':build,'factory_gal':pin['factory_gal'],'wrapper_sha256':sha(wrapper),'files':files,'main_versions':main_versions,
            'hook':{k:pin['libgal_hook.so'][k] for k in ('sha256','build_tag','vehicle_tested')},'hook_profile':pin['profile']['name'],
            'feeder_version':'10-mu1367.2','bridge':{'build':'altscreen_most_bridge.c -DALTSCREEN_AA_SINGLE_IDR','sha256':fm['bridge_sha256']},'replaces_builds':list(AA_PREVIOUS),'source':{k:pin[k] for k in ('source_repository','source_commit','hook_upstream','hook_upstream_commit')},
            'on_unit_validated':False}
    (root/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');return result
def sha_text(t):return hashlib.sha256(t.encode()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('runtime','reader-build','artwork-png-build','artwork-png-host','aa-feeder-build','output'):p.add_argument('--'+n,type=Path,required=True)
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
    fm=json.loads((a.aa_feeder_build/'manifest.json').read_text());cp_bridge=a.aa_feeder_build.resolve()/'altscreen-most-bridge'
    assert fm['passed'] and fm['reproducible'] and sha(cp_bridge)==fm['carplay_bridge_sha256'] and fm['carplay_bridge_flags']==[]
    assert fm['bridge_source_sha256']==sha(HERE/'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c')
    assert sha(custom/'carplay_mu1367_settings/altscreen-most-bridge')=='6c5210cac43699caf027b1f217dc39f4fe87c8b2aee3fa6366c20856772f9c35'
    variants={};tv={}
    for v in ('6','7','6-road','7-road'):
        pm=json.loads((parent/v/'manifest.json').read_text());before=dict(pm['files']);before['parent']=sha(parent/v/'control.sh')
        before['reader']=sha(custom/'carplay_mu1367/rgi-observer')
        payload={k:(a.runtime/path,name) for k,path,name in [('core','base/core.so','core.so'),('menu','base/VCMenu.jar','VCMenu.jar'),('guidance','CarPlayMU1367Guidance.jar','CarPlayMU1367Guidance.jar')]}
        payload['reader']=(a.reader_build/'rgi-observer','rgi-observer')
        # v1.5.1-e: the CarPlay video bridge with boot-time MOST reclaim replaces the settings layer's upstream build.
        before['bridge']=sha(custom/'carplay_mu1367_settings/altscreen-most-bridge')
        payload['bridge']=(cp_bridge,'altscreen-most-bridge')
        variants[v]=tx.transaction(sd,root,v,payload,before,'carplay-mu1367-map-only','guidance-v3','MU1367_GUIDANCE_V3',pm['build_id'])
        before={k:variants[v]['files'][k] for k in ('core','menu')};before['parent']=sha(root/v/'control.sh')
        payload={k:(a.runtime/'tuning'/name,name) for k,name in [('core','core.so'),('menu','VCMenu.jar')]}
        tv[v]=tx.transaction(sd,tuning,v,payload,before,'carplay-mu1367-guidance-v3','turn-cards','MU1367_TURN_CARDS',variants[v]['build_id'])
    # Compressed album artwork: built into the package and installed by default since v1.4.6.
    spec=importlib.util.spec_from_file_location('artwork_png',HERE/'tools/package-artwork-png.py');png=importlib.util.module_from_spec(spec);spec.loader.exec_module(png)
    artwork_png=png.add_layer(sd,a.artwork_png_build.resolve(),a.artwork_png_host.resolve(),True)
    aa=android_auto(sd,custom,a.aa_feeder_build.resolve(),[m['build_id'] for m in variants.values()])
    actions=(HERE/'tools/actions.sh').read_text()
    # Main snapshots that own the reader: this release and archived v1.4.3-e, v1.4.4-e and v1.4.5-e.
    legacy=json.loads((HERE/'tools/legacy-revisions.json').read_text())
    owners=[m['build_id'] for m in variants.values()]+sorted(m['build_id'] for m in legacy.values() if 'reader' in m['before'])
    actions=actions.replace('@READER_VERSIONS@','|'.join(owners))
    # Main snapshots that own the CarPlay bridge: this release and archived v1.5.1-e, v1.5.2-e, v1.5.2 and v1.5.3-e.
    bridge_owners=[m['build_id'] for m in variants.values()]+sorted(m['build_id'] for m in legacy.values() if 'bridge' in m['before'])
    actions=actions.replace('@BRIDGE_VERSIONS@','|'.join(bridge_owners))
    code=(HERE/'tools/migrate.sh').read_text()
    # Diagnose old tuning before requesting ordinary release tuning removal.
    needle='if [ -d "$CARDS" ];then\n regular "$CARDS/STATE"'
    pos=actions.index(needle)
    # Migration must run before the ordinary "remove tuning first" gate.
    actions=actions[:pos]+'. "$P/legacy-check.sh" || fail LEGACY_CHECK_SCRIPT\n'+actions[pos:]
    # migrate.sh handles both latest and old tuning; the existing gate runs afterwards.
    actions=actions.replace('. "$P/legacy-check.sh" || fail LEGACY_CHECK_SCRIPT\n','. "$P/legacy-check.sh" || fail LEGACY_CHECK_SCRIPT\n'+code+'\n')
    actions=actions.replace('echo MU1367_GUIDANCE_V3_SUITE_INSTALLED_FULL_REBOOT_REQUIRED','echo MU1367_RELEASE_1_5_3_INSTALLED_FULL_REBOOT_REQUIRED')
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
        paths={'core':'carplaymaps/core.so','menu':'eso/hmi/lsd/jars/VCMenu.jar','guidance':'eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar','reader':'carplay-mu1367/rgi-observer','bridge':'carplaymaps/altscreen-most-bridge'}
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
    menu_text=menu_text.replace(old_banner,'MU1367 / 791 v1.5.3 (CarPlay + Android Auto)')
    # GEM menus are static, so the reboot entry is permanent; the script refuses
    # while an install runs and then uses the Toolbox's own reboot helper.
    install_entry='    label "Reset saved MU UI settings (reboot)"\n'
    assert menu_text.count(install_entry)==1
    menu_text=menu_text.replace(install_entry,install_entry+'\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_reboot.sh"\n    label "Reboot unit (after install completes)"\n')
    entry='    label "Install / update CarPlay integration (reboot)"\n'
    assert menu_text.count(entry)==1
    # The same install entry installs CarPlay and Android Auto; these switch only the AA cluster-map hook.
    menu_text=menu_text.replace(entry,entry+'\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_suite_aa-disable.sh"\n    label "Android Auto cluster map: off"\n'
        '\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_suite_aa-enable.sh"\n    label "Android Auto cluster map: on"\n')
    menu.write_text(menu_text)
    shutil.copy2(HERE/'tools/cpmap_reboot.sh',sd/'Toolbox/scripts/cpmap_reboot.sh')
    wrapper=(sd/'Toolbox/scripts/cpmap_suite_install.sh').read_text()
    assert wrapper.count(' install "$P"')==2
    for act in ('aa-disable','aa-enable')+tuple(a for a,_ in SNAPSHOT_ENTRIES):(sd/'Toolbox/scripts'/('cpmap_suite_'+act+'.sh')).write_text(wrapper.replace(' install "$P"',' '+act+' "$P"'))
    with (sd/'Toolbox/GEM/carplay-maps-vc-tuning.esd').open('a') as tuning_menu:
        tuning_menu.write('\nkeyValue\n    value String sys 0x00000000 0\n    label "Saved snapshots of earlier installations"\n    poll 0\n')
        for a,l in SNAPSHOT_ENTRIES:tuning_menu.write('\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_suite_'+a+'.sh"\n    label "'+l+'"\n')
    (sd/'README.md').write_text('# MU1367 / 791 v1.5.3\n\nStable release, built from v1.5.3-e after vehicle tests.\n\nAdds a startup animation on the AID: a 4.2 s clip plays when CarPlay first takes the cluster map after the unit starts, then the live map follows. MU UI > App-Connect > Virtual Cockpit settings > Startup animation: once per boot (default), every connection or off. Without Tuning it is a new row on that page; with Tuning it replaces the Wireless CarPlay (test) row, which never had a function. The CarPlay video bridge also runs at a higher priority (14 instead of 10), so it keeps getting CPU while the navigation and the reverse camera load the unit. Everything else is v1.5.2. Android Auto on the AID is included but not yet fully tested. Start with [START_HERE.md](START_HERE.md) and [RELEASE-NOTES.md](RELEASE-NOTES.md).\n')
    shutil.copy2(HERE/'NOTICE.md',sd/'NOTICE.md')
    manifest={'version':'1.5.3','experimental':False,'prerelease':False,'base_version':'1.5.3-e','previous_stable_version':'1.5.2','base_archive_sha256':BASE_ARCHIVE_SHA256,'base_verified_package_sha256':BASE_VERIFIED_SHA256,'base_vehicle_tested':True,'artwork_png':artwork_png,'android_auto':aa,'android_auto_fully_tested':False,'reader_build':'MU1367-reader-v1.4.4-e','guidance_hold_ms':180000,'reader_restart_budget':{'per_window':3,'stable_window_ms':600000,'lifetime_ceiling':64,'backoff_ms':[1000,2000,4000]},'reader_sha256':reader['sha256'],'reader_source_sha256':reader['source_sha256'],
        'release_changes':'Stable v1.5.3: v1.5.3-e (vehicle-tested) plus one fix: after the startup clip the CarPlay bridge records the ring position it skips to before it requests the IDR, so a fast answer is never skipped. Startup animation: the CarPlay bridge plays a built-in 4.2 s clip (800x480 Constrained Baseline H.264, 126 frames at 30 fps) before the live map, then waits for a fresh IDR from the phone. MU UI selector: once per boot (default), every connection, off; with Tuning it replaces the Wireless CarPlay (test) row. The CarPlay and Android Auto bridges raise their threads to priority 14 (from the inherited 10). The Android Auto bridge has no intro.',
        'startup_animation':{'clip':'intro/cp_intro_badge_baseline.h264','clip_sha256':sha(HERE/'src/runtime/vc-runtime/intro/cp_intro_badge_baseline.h264'),'frames':126,'fps':30,'profile':'Constrained Baseline','size':[800,480],'modes':['every connection','once per boot (default)','off'],'default':'once per boot','preference':'/mnt/icab/persistent/cpmap-ui/animation.state','android_auto':False},
        'snapshot_actions':[a for a,_ in SNAPSHOT_ENTRIES],
        'carplay_bridge':{'build':'altscreen_most_bridge.c (clang, pinned QNX 6.5 SDK binutils)','sha256':fm['carplay_bridge_sha256'],'replaces_sha256':'6c5210cac43699caf027b1f217dc39f4fe87c8b2aee3fa6366c20856772f9c35','reclaim_window_s':180,'reclaim_max':3,'latency_limit_packets':2048,'priority':14,'startup_animation':True},'guidance_recover_ms':20000,'guidance_stop_grace_ms':1500,'archive_name':ARCHIVE,'firmware':'K4525 / P4521 MU1367','supported_firmware':[{'train':'MHI2_ER_VWG13_K4525','experimental':False},{'train':'MHI2_ER_VWG13_P4521','experimental':False}],'p4521_vehicle_tested':True,'cluster':'791','variants':variants,'tuning_variants':tv,
        'files':variants['6']['files'],'defaults':{'fps':40,'idr':5,'cards':False,'compressed_artwork':True,'safe_area':[160,20,480,440],'startup_animation':'once per boot'},
        'stream_choices':['25 fps / IDR 5','30 fps / IDR 5','40 fps / IDR 5 (default)'],'stream_values':[4,2,1],'retired_stream_values':{'5':'20 fps, runs as 40 fps','6':'27 fps, runs as 40 fps'},'guidance_build':'MU1367-guidance-v1.5.0-e','mini_pico_card_suppression':False,'inactive_lane_blanks':'OEM behavior',
        'release_package_vehicle_tested':False,'feature_vehicle_results':'v1.5.3-e vehicle-tested with good results (startup animation and bridge priority 14). Final packaging, the intro IDR-request fix and migration verified off-unit.'}
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
