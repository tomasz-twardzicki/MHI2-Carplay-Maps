#!/usr/bin/env python3
"""Verify map-only/card transactions with firmware ksh/gawk, plus OEM reset."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'port'))
from firmware import image_files,stage1,QNX6
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser()
 for n in ('package','reader-setup','toolchain','firmware','firmware-commands','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();custom=a.package/'sd-card/Custom';main=custom/'carplay_mu1367_guidance_v3';tuning=custom/'carplay_mu1367_v3_turn_cards'
 real='09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a';fake=sha(b'OEM reset QNX filesystem fixture\n')
 actions=(main/'actions.sh').read_text().replace(real,fake)
 controller=(main/'6/control.sh').read_text().replace(real,fake)
 card=(tuning/'6/control.sh').read_text().replace(real,fake).replace(sha((main/'6/control.sh').read_bytes()),sha(controller.encode()))
 extras={'main-actions':actions,'main-control':controller,'tuning-control':card,'legacy-check':main/'legacy-check.sh','release-versions':main/'release-versions.sh'}
 old=HERE/'revisions/release-v1.4.6/carplay_mu1367_guidance_v3/6'
 legacy=(old/'control.sh').read_text().replace(real,fake)
 legacy_check=(main/'legacy-check.sh').read_text().replace(sha((old/'control.sh').read_bytes()),sha(legacy.encode()))
 extras.update({'legacy-control':legacy,'legacy-check':legacy_check})
 for name in ('guard','VERSION','core.so','VCMenu.jar','CarPlayMU1367Guidance.jar','rgi-observer'):extras['legacy-'+name]=old/name
 # v1.4.6: compressed artwork is a default install step (its controller carries the same firmware gate).
 png=custom/'carplay_mu1367_artwork_png';art=custom/'carplay_mu1367_artwork'
 extras['png-control']=(png/'control.sh').read_text().replace(real,fake)
 for name in ('artwork-fetch','VERSION','guard'):extras['png-'+name]=png/name
 extras['art-fetch']=art/'artwork-fetch'
 # v1.5.0-e: the Android Auto layer runs as the last install step under the factory ksh with factory commands only.
 aa=custom/'carplay_mu1367_android_auto';aam=json.loads((aa/'manifest.json').read_text())
 extras['aa-control']=(aa/'control.sh').read_text().replace(real,fake)
 aa_files=('VERSION','gal.wrapper.sh')+tuple(aam['files'])
 for name in aa_files:extras['aa-'+name]=aa/name

 paths={
  'carplaymaps/core.so':custom/'carplay_mu1367_map_only/6/core.so',
  'eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar':custom/'carplay_mu1367_map_only/6/CarPlayMU1367Guidance.jar',
  'eso/hmi/lsd/jars/VCMenu.jar':custom/'carplay_mu1367_map_only/6/VCMenu.jar',
  'carplay-mu1367-map-only/control.sh':custom/'carplay_mu1367_map_only/6/control.sh',
  'armle/lib/dll/ipod-drvr-iap2.so':custom/'carplay_mu1367_artwork/ipod-drvr-iap2.so',
  'eso/hmi/lsd/jars/CarPlayMU1367Audio.jar':custom/'carplay_mu1367_artwork/CarPlayMU1367Audio.jar',
  'eso/hmi/lsd/jars/CarPlayClusterControls.jar':custom/'carplay_mu1367_settings/CarPlayClusterControls.jar',
  'carplay-mu1367/rgi-observer':custom/'carplay_mu1367/rgi-observer',
  # v1.5.1-e: the main layer replaces the settings layer's upstream video bridge.
  'carplaymaps/altscreen-most-bridge':custom/'carplay_mu1367_settings/altscreen-most-bridge'}
 for i,src in enumerate(paths.values()):extras['old-'+str(i)]=src
 for key,root in [('main',main),('tuning',tuning)]:
  for name in ('guard','VERSION','core.so','VCMenu.jar')+ (('CarPlayMU1367Guidance.jar','rgi-observer','altscreen-most-bridge') if key=='main' else ()):
   extras[key+'-'+name]=root/'6'/name
 script='''
set -eu
export PATH=/ramdisk/test-tools:/proc/boot LD_LIBRARY_PATH=/proc/boot
export CPMAP_TEST_ROOT=/ramdisk/card-suite
APP=$CPMAP_TEST_ROOT/mnt/app
P=/ramdisk/Custom/carplay_mu1367_guidance_v3
T=/ramdisk/Custom/carplay_mu1367_v3_turn_cards
mkdir -p "$P/6" "$T/6" "$CPMAP_TEST_ROOT/ifs" "$CPMAP_TEST_ROOT/ramdisk" "$APP/carplaymaps"
cp /proc/boot/fixture-jxe "$CPMAP_TEST_ROOT/ifs/lsd.jxe"
cp /proc/boot/main-actions "$P/actions.sh"
cp /proc/boot/legacy-check "$P/legacy-check.sh"
cp /proc/boot/release-versions "$P/release-versions.sh"
echo 'return 0' > "$P/payload-check.sh"
cp /proc/boot/verify "$P/verify"
chmod 755 "$P/verify"
cp /proc/boot/main-control "$P/6/control.sh"
cp /proc/boot/tuning-control "$T/6/control.sh"
echo MU1367/791 > "$APP/carplaymaps/PROFILE"
PNGP=/ramdisk/Custom/carplay_mu1367_artwork_png
mkdir -p "$PNGP" "$CPMAP_TEST_ROOT/proc/boot" "$APP/carplay-mu1367-artwork"
cp /proc/boot/png-control "$PNGP/control.sh"
for N in artwork-fetch VERSION guard;do cp /proc/boot/png-$N "$PNGP/$N";done
cp /proc/boot/verify "$PNGP/verify"
chmod 755 "$PNGP/verify"
cp /proc/boot/factory-zlib "$CPMAP_TEST_ROOT/proc/boot/libz.so.2"
cp /proc/boot/art-fetch "$APP/carplay-mu1367-artwork/artwork-fetch"
chmod 755 "$APP/carplay-mu1367-artwork/artwork-fetch"
AAP=/ramdisk/Custom/carplay_mu1367_android_auto
mkdir -p "$AAP" "$APP/eso/bin/apps"
cp /proc/boot/aa-control "$AAP/control.sh"
cp /proc/boot/verify "$AAP/verify"
chmod 755 "$AAP/verify"
cp /proc/boot/factory-gal "$APP/eso/bin/apps/gal"
chmod 755 "$APP/eso/bin/apps/gal"
echo '#!/bin/ksh' > "$APP/carplaymaps/altscreen-most-bridge"
'''
 for key,var in [('main','P'),('tuning','T')]:
  for name in ('guard','VERSION','core.so','VCMenu.jar')+ (('CarPlayMU1367Guidance.jar','rgi-observer','altscreen-most-bridge') if key=='main' else ()):
   script+='cp /proc/boot/'+key+'-'+name+' "$'+var+'/6/'+name+'"\n'
  script+='cp /proc/boot/verify "$'+var+'/6/verify"\nchmod 755 "$'+var+'/6/verify"\n'
 for name in aa_files:script+='cp /proc/boot/aa-'+name+' "$AAP/'+name+'"\n'
 for i,(dest,src) in enumerate(paths.items()):script+='mkdir -p "$APP/'+str(Path(dest).parent)+'"\ncp /proc/boot/old-'+str(i)+' "$APP/'+dest+'"\n'
 # The unit's settings layer installs the bridge 755 (export listing); the transaction keeps the target's mode.
 script+='chmod 755 "$APP/carplaymaps/altscreen-most-bridge"\n'
 for live,source in [('carplay-mu1367','carplay_mu1367'),('carplay-mu1367-settings','carplay_mu1367_settings'),('carplay-mu1367-map-only','carplay_mu1367_map_only/6'),('carplay-mu1367-artwork','carplay_mu1367_artwork')]:
  script+='mkdir -p "$APP/'+live+'"\necho installed > "$APP/'+live+'/STATE"\necho '+(custom/source/'VERSION').read_text().strip()+' > "$APP/'+live+'/VERSION"\n'
 script+='''# Exercise train recognition with the actual firmware gawk before writes.
mkdir -p "$CPMAP_TEST_ROOT/net/rcc/dev/shmem"
echo 'Current train = "MHI2_ER_VWG13_P4521"' > "$CPMAP_TEST_ROOT/net/rcc/dev/shmem/version.txt"
/bin/ksh "$P/actions.sh" lane-status "$P" > /ramdisk/train-status || exit 79
grep 'MU1367_FIRMWARE_TYPE=P4521_EXPERIMENTAL' /ramdisk/train-status || exit 79
echo 'Current train = "MHI2_ER_VWG13_P9999"' > "$CPMAP_TEST_ROOT/net/rcc/dev/shmem/version.txt"
if /bin/ksh "$P/actions.sh" install "$P";then exit 79;fi
echo 'Current train = "MHI2_ER_VWG13_K4525_1_AIO_MU1367"' > "$CPMAP_TEST_ROOT/net/rcc/dev/shmem/version.txt"
/bin/ksh "$P/actions.sh" lane-status "$P" > /ramdisk/train-status || exit 79
grep 'MU1367_FIRMWARE_TYPE=K4525' /ramdisk/train-status || exit 79
echo 'Current train = "MHI2_ER_VWG13_P4521"' > "$CPMAP_TEST_ROOT/net/rcc/dev/shmem/version.txt"
echo RELEASE_FACTORY_TRAIN_RECOGNITION_PASS
awk 'BEGIN {if(2+2!=4)exit 1}' || exit 80
/bin/ksh "$P/6/control.sh" install "$P/6" || exit 81
"$P/verify" "$APP/carplaymaps/altscreen-most-bridge" @CP_BRIDGE@ || exit 81
test -x "$APP/carplaymaps/altscreen-most-bridge" || exit 81
echo RELEASE_FACTORY_CARPLAY_BRIDGE_INSTALLED_PASS
/bin/ksh "$P/actions.sh" install "$P" > /ramdisk/install-out || exit 82
grep '^MU1367_INSTALL_STEPS=3 ' /ramdisk/install-out || exit 86
grep '^\\[1/3\\] MU1367_GUIDANCE_V3_ALREADY_INSTALLED$' /ramdisk/install-out || exit 86
grep '^\\[2/3\\] MU1367_ARTWORK_PNG_INSTALLED$' /ramdisk/install-out || exit 86
grep '^\\[3/3\\] MU1367_ANDROID_AUTO_INSTALLED$' /ramdisk/install-out || exit 86
grep '^MU1367_INSTALL_COMPLETE=3/3$' /ramdisk/install-out || exit 86
"$P/verify" "$APP/eso/bin/apps/gal" @WRAPPER@ || exit 86
"$P/verify" "$APP/carplay-mu1367-android-auto/gal.real" @FACTORY_GAL@ || exit 86
/bin/ksh -n "$APP/eso/bin/apps/gal" || exit 86
/bin/ksh "$P/actions.sh" aa-disable "$P" || exit 86
test -f "$APP/carplay-mu1367-android-auto/DISABLED" || exit 86
/bin/ksh "$P/actions.sh" aa-enable "$P" || exit 86
test ! -e "$APP/carplay-mu1367-android-auto/DISABLED" || exit 86
/bin/ksh "$P/actions.sh" install "$P" > /ramdisk/install-out2 || exit 86
grep '^\\[3/3\\] MU1367_ANDROID_AUTO_ALREADY_INSTALLED$' /ramdisk/install-out2 || exit 86
echo RELEASE_FACTORY_ANDROID_AUTO_INSTALL_PASS
"$P/verify" "$APP/carplay-mu1367-artwork/artwork-fetch" @PNG_FETCH@ || exit 86
echo RELEASE_FACTORY_DEFAULT_ARTWORK_PNG_PASS
test ! -e "$CPMAP_TEST_ROOT/ramdisk/.cpmap-install-running" || exit 86
if grep REBOOT_REQUIRED /ramdisk/install-out | grep -v RELEASE_1_5_1_E_EXPERIMENTAL_INSTALLED_FULL_REBOOT_REQUIRED;then exit 86;fi
if echo x | { IFS= read -r L; exit 1; };then exit 87;fi
echo RELEASE_FACTORY_PROGRESS_PASS
/bin/ksh "$P/actions.sh" enable-cards "$P" || exit 83
if /bin/ksh "$APP/carplay-mu1367-guidance-v3/control.sh" uninstall;then exit 84;fi
/bin/ksh "$P/actions.sh" disable-cards "$P" || exit 85
/bin/ksh "$P/actions.sh" enable-cards "$P" || exit 86
FOUND=no
for D in "$APP"/carplay-mu1367-turn-cards.removed-*;do test -f "$D/backup/menu" || exit 87;FOUND=yes;done
test "$FOUND" = yes || exit 88
/bin/ksh "$P/actions.sh" disable-cards "$P" || exit 89
/bin/ksh "$P/actions.sh" uninstall "$P" || exit 90
test ! -e "$CPMAP_TEST_ROOT/ramdisk/.carplay-guidance-install-lock" || exit 91
"$P/verify" "$APP/carplay-mu1367-artwork/artwork-fetch" @ART_FETCH@ || exit 91
test "$(cat "$APP/carplay-mu1367-artwork-png/STATE")" = removed || exit 91
"$P/verify" "$APP/eso/bin/apps/gal" @FACTORY_GAL@ || exit 91
test "$(cat "$APP/carplay-mu1367-android-auto/STATE")" = removed || exit 91
test ! -e "$APP/carplaymaps/aa" || exit 91
echo RELEASE_FACTORY_ANDROID_AUTO_REMOVE_PASS
'''.replace('@WRAPPER@',aam['wrapper_sha256']).replace('@FACTORY_GAL@',aam['factory_gal']['sha256']).replace('@PNG_FETCH@',sha((png/'artwork-fetch').read_bytes())).replace('@ART_FETCH@',sha((art/'artwork-fetch').read_bytes())).replace('@CP_BRIDGE@',json.loads((main/'6/manifest.json').read_text())['files']['bridge'])
 for dest,src in paths.items():script+='"$P/verify" "$APP/'+dest+'" '+sha(src.read_bytes())+' || exit 92\n'

 script+='\n# Install actual published v1.4.6 release, then exercise release\'s two-stage migration.\nOLD=/ramdisk/legacy\nmkdir -p "$OLD"\ncp /proc/boot/legacy-control "$OLD/control.sh"\ncp /proc/boot/verify "$OLD/verify"\nchmod 755 "$OLD/verify"\nmv "$APP/carplay-mu1367-guidance-v3" "$APP/carplay-mu1367-guidance-v3.removed-fixture"\n'
 for name in ('guard','VERSION','core.so','VCMenu.jar','CarPlayMU1367Guidance.jar','rgi-observer'):script+='cp /proc/boot/legacy-'+name+' "$OLD/'+name+'"\n'
 script+='/bin/ksh "$OLD/control.sh" install "$OLD" || exit 95\n/bin/ksh "$P/actions.sh" install "$P" || exit 96\ntest -f "$CPMAP_TEST_ROOT/ramdisk/.cpmap-release-migration-reboot" || exit 97\nif /bin/ksh "$P/actions.sh" install "$P";then exit 98;fi\nrm "$CPMAP_TEST_ROOT/ramdisk/.cpmap-release-migration-reboot"\n/bin/ksh "$P/actions.sh" install "$P" || exit 99\n/bin/ksh "$P/actions.sh" uninstall "$P" || exit 100\n"$P/verify" "$APP/eso/bin/apps/gal" '+aam['factory_gal']['sha256']+' || exit 101\necho RELEASE_FACTORY_MIGRATION_PASS\n'
 script+='echo RELEASE_FACTORY_ACTIONS_PASS main_install=1 repeat=1 optional_install_remove=2 guard=1 retain_removed=1 rollback_hashes=1\n'
 libs=a.output.parent/(a.output.name+'-libs');libs.mkdir(parents=True,exist_ok=False)
 directory=a.firmware/'MMX2'
 if not directory.is_dir():directory=a.firmware/'mmx2'
 files=image_files(stage1(directory/'mifs-stage1/50/default/mifs-stage1.img'))
 app=QNX6(directory/'app/50/default/app.img')
 try:(libs/'factory-gal').write_bytes(app.get('eso/bin/apps/gal'))
 finally:app.file.close()
 assert sha((libs/'factory-gal').read_bytes())==aam['factory_gal']['sha256'];extras['factory-gal']=libs/'factory-gal'
 zl=[b for n,b in files.items() if n.endswith('/libz.so.2')];assert len(zl)==1;(libs/'factory-zlib').write_bytes(zl[0]);extras['factory-zlib']=libs/'factory-zlib'
 for name in ('libm.so.2','libsocket.so.3'):
  matches=[b for n,b in files.items() if n.endswith('/'+name)];assert len(matches)==1;(libs/name).write_bytes(matches[0]);extras[name]=libs/name
 import factory_reset
 old=sys.argv;sys.argv=['qnx-actions','--payload',str(custom/'carplay_mu1367_oem_reset')]
 for n in ('reader-setup','toolchain','firmware-commands','output'):sys.argv+=['--'+n,str(getattr(a,n.replace('-','_')))]
 try:rc=factory_reset.main(script,extras,main/'COMMANDS.json')
 finally:sys.argv=old
 log=(a.output/'qemu.log').read_text(errors='replace');assert 'RELEASE_FACTORY_ANDROID_AUTO_INSTALL_PASS' in log and 'RELEASE_FACTORY_ANDROID_AUTO_REMOVE_PASS' in log and 'RELEASE_FACTORY_DEFAULT_ARTWORK_PNG_PASS' in log and 'RELEASE_FACTORY_MIGRATION_PASS' in log and 'RELEASE_FACTORY_TRAIN_RECOGNITION_PASS' in log and 'RELEASE_FACTORY_PROGRESS_PASS' in log and 'RELEASE_FACTORY_CARPLAY_BRIDGE_INSTALLED_PASS' in log
 r=json.loads((a.output/'result.json').read_text());r.update(factory_progress_verified=True,factory_migration_verified=True,firmware_train_recognition_verified=True,map_only_actions_sha256=sha((main/'actions.sh').read_bytes()),main_controller_sha256=sha((main/'6/control.sh').read_bytes()),tuning_controller_sha256=sha((tuning/'6/control.sh').read_bytes()),fixture_changes='Only small-JXE fingerprint and the dependent main-controller before hash; complete SD preflight is a fixture return 0, checked in full on host',map_only_and_optional_transactions_verified=True,default_artwork_png_verified=True,android_auto_layer_verified=True,carplay_bridge_install_verified=True,android_auto_controller_sha256=sha((aa/'control.sh').read_bytes()),artwork_png_controller_sha256=sha((png/'control.sh').read_bytes()),sdk_utilities_injected=False)
 (a.output/'result.json').write_text(json.dumps(r,indent=2)+'\n');return rc
if __name__=='__main__':raise SystemExit(main())
