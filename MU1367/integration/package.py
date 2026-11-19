#!/usr/bin/env python3
"""Assemble the maintained Toolbox and verified compatibility migrations (GPL-3.0+)."""
import argparse, hashlib, importlib.util, json, re, shlex, shutil, subprocess, zipfile
from pathlib import Path
from tools.payload_checks import write_payload_checks
HERE=Path(__file__).resolve().parent
ARCHIVE='CarPlay_Maps_VC_MU1367_791_v1.5.4.zip'
# Published stable v1.5.3 ZIP (its verified package), vehicle-tested through v1.5.3-e.
BASE_ARCHIVE_SHA256='011d37a7206739d77843f96e5446078d2175e4cbc12fc8702d1842c4035665d8'
BASE_VERIFIED_SHA256=BASE_ARCHIVE_SHA256
# Android Auto layer builds replaced in place: published v1.5.0-e, the car-tested pre-release build, both published v1.5.1-e builds, v1.5.2-e, v1.5.2, v1.5.3-e and v1.5.3.
AA_PREVIOUS=('mu1367-android-auto-ee74f406dd94','mu1367-android-auto-e3e4e1ce3a73','mu1367-android-auto-c1f4833dac00','mu1367-android-auto-ad7f051fd568','mu1367-android-auto-32e92312bde1','mu1367-android-auto-74fd41b287c3','mu1367-android-auto-95f7bc5f3cc4','mu1367-android-auto-05631145bd45')
# v1.5.2: tuning-menu actions for saved snapshots of earlier installations and rollbacks.
SNAPSHOT_ENTRIES=[('snapshots','List saved snapshots (read only)'),('snapshot-next','Select next snapshot'),
                  ('snapshot-remove','Remove selected snapshot'),('snapshots-remove-all','Remove all saved snapshots')]
# v1.5.4: Toolbox > CarPlay diagnostics stream test (actions.sh stream-*): any fps 20-40 and key frame every 5-15 frames.
STREAM_ENTRIES=[('stream-show','Stream test: show current fps / IDR (read only)'),('stream-fps-up5','Stream test: fps +5'),('stream-fps-down5','Stream test: fps -5'),
                ('stream-fps-up1','Stream test: fps +1'),('stream-fps-down1','Stream test: fps -1'),('stream-idr-up','Stream test: IDR every +1 frame'),
                ('stream-idr-down','Stream test: IDR every -1 frame'),('stream-reset','Stream test: off (back to the MU UI choice)')]
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
    # Main snapshots that own the CarPlay bridge: this release and archived v1.5.1-e, v1.5.2-e, v1.5.2, v1.5.3-e and v1.5.3.
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
    actions=actions.replace('echo MU1367_GUIDANCE_V3_SUITE_INSTALLED_FULL_REBOOT_REQUIRED','echo MU1367_RELEASE_1_5_4_INSTALLED_FULL_REBOOT_REQUIRED')
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
    menu_text=menu_text.replace(old_banner,'MU1367 / 791 v1.5.4 (CarPlay + Android Auto)')
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
    for act in ('aa-disable','aa-enable')+tuple(a for a,_ in SNAPSHOT_ENTRIES+STREAM_ENTRIES):(sd/'Toolbox/scripts'/('cpmap_suite_'+act+'.sh')).write_text(wrapper.replace(' install "$P"',' '+act+' "$P"'))
    with (sd/'Toolbox/GEM/carplay-maps-vc-tuning.esd').open('a') as tuning_menu:
        tuning_menu.write('\nkeyValue\n    value String sys 0x00000000 0\n    label "Saved snapshots of earlier installations"\n    poll 0\n')
        for a,l in SNAPSHOT_ENTRIES:tuning_menu.write('\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_suite_'+a+'.sh"\n    label "'+l+'"\n')
    with (sd/'Toolbox/GEM/carplay-maps-vc-diagnostics.esd').open('a') as diag_menu:
        diag_menu.write('\nkeyValue\n    value String sys 0x00000000 0\n    label "Stream test (any fps 20-40, key frame every 5-15)"\n    poll 0\n')
        for a,l in STREAM_ENTRIES:diag_menu.write('\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_suite_'+a+'.sh"\n    label "'+l+'"\n')
    (sd/'README.md').write_text('# MU1367 / 791 v1.5.4\n\nStable release: v1.5.3 plus two changes.\n\n- **Arrival time on the AID.** When the OEM navigation setup is set to show the arrival time, CarPlay guidance now shows the arrival time on the AID (the unit\'s clock plus the remaining time from the phone) instead of always the remaining time. Time to destination is unchanged.\n- **Stream test** (Toolbox > CarPlay diagnostics): try any map rate from 20 to 40 fps and a key frame every 5 to 15 frames. It overrides the MU UI stream choice until *Stream test: off* and applies on the next phone connection.\n\nEverything else is v1.5.3. Android Auto on the AID is included but not yet fully tested. Start with [START_HERE.md](START_HERE.md) and [RELEASE-NOTES.md](RELEASE-NOTES.md).\n')
    shutil.copy2(HERE/'NOTICE.md',sd/'NOTICE.md')
    manifest={'version':'1.5.4','experimental':False,'prerelease':False,'base_version':'1.5.3','previous_stable_version':'1.5.3','base_archive_sha256':BASE_ARCHIVE_SHA256,'base_verified_package_sha256':BASE_VERIFIED_SHA256,'base_vehicle_tested':True,'artwork_png':artwork_png,'android_auto':aa,'android_auto_fully_tested':False,'reader_build':'MU1367-reader-v1.4.4-e','guidance_hold_ms':180000,'reader_restart_budget':{'per_window':3,'stable_window_ms':600000,'lifetime_ceiling':64,'backoff_ms':[1000,2000,4000]},'reader_sha256':reader['sha256'],'reader_source_sha256':reader['source_sha256'],
        'release_changes':'Stable v1.5.4: v1.5.3 plus two changes. Arrival time: when the OEM navigation setup selects the arrival time (NavigationService.getTimeToDestinationTimeInfo()==1, datapool 1110059), CarPlay guidance sends TimeToDestination with timeInfoType 1: the HMI clock (datapool TIME__HOUR 1640 / TIME__MINUTE 1641, only while TIME_VALID 3572) plus the phone remaining time, rounded to the minute, 12/24 h flag as stock, no date; time to destination, or no valid HMI clock, sends the remaining time exactly as v1.5.3. Stream test: Toolbox > CarPlay diagnostics sets any fps 20-40 and a key frame every 5-15 frames in /mnt/icab/persistent/cpmap-ui/stream-test.conf, which overrides the MU UI stream until removed; the core logs the fps/IDR it asks for (stream-settings, stream-idr-interval) and re-reads the IDR interval on each video connection. Startup animation and bridge priority 14 unchanged; the CarPlay bridge, Android Auto bridge and feeder are the v1.5.3 sources rebuilt with Apple clang 21 (v1.5.3: clang 17).',
        'stream_test':{'file':'/mnt/icab/persistent/cpmap-ui/stream-test.conf','fps':[20,40],'idr':[5,15],'actions':[a for a,_ in STREAM_ENTRIES],'default':'off (MU UI choice)'},
        'arrival_time':{'setting':'NavigationService.getTimeToDestinationTimeInfo() (datapool 1110059), 1 = arrival time','clock':'HMI clock datapool 1640/1641 while TIME_VALID 3572','date_sent':False,'fallback':'remaining time'},
        'startup_animation':{'clip':'intro/cp_intro_badge_baseline.h264','clip_sha256':sha(HERE/'src/runtime/vc-runtime/intro/cp_intro_badge_baseline.h264'),'frames':126,'fps':30,'profile':'Constrained Baseline','size':[800,480],'modes':['every connection','once per boot (default)','off'],'default':'once per boot','preference':'/mnt/icab/persistent/cpmap-ui/animation.state','android_auto':False},
        'snapshot_actions':[a for a,_ in SNAPSHOT_ENTRIES],
        'carplay_bridge':{'build':'altscreen_most_bridge.c (clang, pinned QNX 6.5 SDK binutils)','sha256':fm['carplay_bridge_sha256'],'replaces_sha256':'6c5210cac43699caf027b1f217dc39f4fe87c8b2aee3fa6366c20856772f9c35','reclaim_window_s':180,'reclaim_max':3,'latency_limit_packets':2048,'priority':14,'startup_animation':True},'guidance_recover_ms':20000,'guidance_stop_grace_ms':1500,'archive_name':ARCHIVE,'firmware':'K4525 / P4521 MU1367','supported_firmware':[{'train':'MHI2_ER_VWG13_K4525','experimental':False},{'train':'MHI2_ER_VWG13_P4521','experimental':False}],'p4521_vehicle_tested':True,'cluster':'791','variants':variants,'tuning_variants':tv,
        'files':variants['6']['files'],'defaults':{'fps':40,'idr':5,'cards':False,'compressed_artwork':True,'safe_area':[160,20,480,440],'startup_animation':'once per boot'},
        'stream_choices':['25 fps / IDR 5','30 fps / IDR 5','40 fps / IDR 5 (default)'],'stream_values':[4,2,1],'retired_stream_values':{'5':'20 fps, runs as 40 fps','6':'27 fps, runs as 40 fps'},'guidance_build':'MU1367-guidance-v1.5.4','mini_pico_card_suppression':False,'inactive_lane_blanks':'OEM behavior',
        'release_package_vehicle_tested':False,'feature_vehicle_results':'v1.5.3 base vehicle-tested (as v1.5.3-e). The arrival-time output and the stream test are verified off-unit (host, QNX J9, firmware shell), not yet in a car.'}
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
