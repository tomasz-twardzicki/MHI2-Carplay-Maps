#!/usr/bin/env python3
"""Verify map-only/card transactions with firmware ksh/gawk, plus OEM reset."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'port'))
from firmware import image_files,stage1
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
 old=HERE/'revisions/release-v1.4.3-e/carplay_mu1367_guidance_v3/6'
 legacy=(old/'control.sh').read_text().replace(real,fake)
 legacy_check=(main/'legacy-check.sh').read_text().replace(sha((old/'control.sh').read_bytes()),sha(legacy.encode()))
 extras.update({'legacy-control':legacy,'legacy-check':legacy_check})
 for name in ('guard','VERSION','core.so','VCMenu.jar','CarPlayMU1367Guidance.jar','rgi-observer'):extras['legacy-'+name]=old/name

 paths={
  'carplaymaps/core.so':custom/'carplay_mu1367_map_only/6/core.so',
  'eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar':custom/'carplay_mu1367_map_only/6/CarPlayMU1367Guidance.jar',
  'eso/hmi/lsd/jars/VCMenu.jar':custom/'carplay_mu1367_map_only/6/VCMenu.jar',
  'carplay-mu1367-map-only/control.sh':custom/'carplay_mu1367_map_only/6/control.sh',
  'armle/lib/dll/ipod-drvr-iap2.so':custom/'carplay_mu1367_artwork/ipod-drvr-iap2.so',
  'eso/hmi/lsd/jars/CarPlayMU1367Audio.jar':custom/'carplay_mu1367_artwork/CarPlayMU1367Audio.jar',
  'eso/hmi/lsd/jars/CarPlayClusterControls.jar':custom/'carplay_mu1367_settings/CarPlayClusterControls.jar',
  'carplay-mu1367/rgi-observer':custom/'carplay_mu1367/rgi-observer'}
 for i,src in enumerate(paths.values()):extras['old-'+str(i)]=src
 for key,root in [('main',main),('tuning',tuning)]:
  for name in ('guard','VERSION','core.so','VCMenu.jar')+ (('CarPlayMU1367Guidance.jar','rgi-observer') if key=='main' else ()):
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
'''
 for key,var in [('main','P'),('tuning','T')]:
  for name in ('guard','VERSION','core.so','VCMenu.jar')+ (('CarPlayMU1367Guidance.jar','rgi-observer') if key=='main' else ()):
   script+='cp /proc/boot/'+key+'-'+name+' "$'+var+'/6/'+name+'"\n'
  script+='cp /proc/boot/verify "$'+var+'/6/verify"\nchmod 755 "$'+var+'/6/verify"\n'
 for i,(dest,src) in enumerate(paths.items()):script+='mkdir -p "$APP/'+str(Path(dest).parent)+'"\ncp /proc/boot/old-'+str(i)+' "$APP/'+dest+'"\n'
 for live,source in [('carplay-mu1367','carplay_mu1367'),('carplay-mu1367-settings','carplay_mu1367_settings'),('carplay-mu1367-map-only','carplay_mu1367_map_only/6')]:
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
/bin/ksh "$P/actions.sh" install "$P" > /ramdisk/install-out || exit 82
grep '^MU1367_INSTALL_STEPS=1 ' /ramdisk/install-out || exit 86
grep '^\\[1/1\\] MU1367_GUIDANCE_V3_ALREADY_INSTALLED$' /ramdisk/install-out || exit 86
grep '^MU1367_INSTALL_COMPLETE=1/1$' /ramdisk/install-out || exit 86
test ! -e "$CPMAP_TEST_ROOT/ramdisk/.cpmap-install-running" || exit 86
if grep REBOOT_REQUIRED /ramdisk/install-out | grep -v RELEASE_1_4_4_E_EXPERIMENTAL_INSTALLED_FULL_REBOOT_REQUIRED;then exit 86;fi
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
'''
 for dest,src in paths.items():script+='"$P/verify" "$APP/'+dest+'" '+sha(src.read_bytes())+' || exit 92\n'

 script+='\n# Install actual published v1.4.3-e release, then exercise release\'s two-stage migration.\nOLD=/ramdisk/legacy\nmkdir -p "$OLD"\ncp /proc/boot/legacy-control "$OLD/control.sh"\ncp /proc/boot/verify "$OLD/verify"\nchmod 755 "$OLD/verify"\nmv "$APP/carplay-mu1367-guidance-v3" "$APP/carplay-mu1367-guidance-v3.removed-fixture"\n'
 for name in ('guard','VERSION','core.so','VCMenu.jar','CarPlayMU1367Guidance.jar','rgi-observer'):script+='cp /proc/boot/legacy-'+name+' "$OLD/'+name+'"\n'
 script+='/bin/ksh "$OLD/control.sh" install "$OLD" || exit 95\n/bin/ksh "$P/actions.sh" install "$P" || exit 96\ntest -f "$CPMAP_TEST_ROOT/ramdisk/.cpmap-release-migration-reboot" || exit 97\nif /bin/ksh "$P/actions.sh" install "$P";then exit 98;fi\nrm "$CPMAP_TEST_ROOT/ramdisk/.cpmap-release-migration-reboot"\n/bin/ksh "$P/actions.sh" install "$P" || exit 99\n/bin/ksh "$P/actions.sh" uninstall "$P" || exit 100\necho RELEASE_FACTORY_MIGRATION_PASS\n'
 script+='echo RELEASE_FACTORY_ACTIONS_PASS main_install=1 repeat=1 optional_install_remove=2 guard=1 retain_removed=1 rollback_hashes=1\n'
 libs=a.output.parent/(a.output.name+'-libs');libs.mkdir(parents=True,exist_ok=False)
 directory=a.firmware/'MMX2'
 if not directory.is_dir():directory=a.firmware/'mmx2'
 files=image_files(stage1(directory/'mifs-stage1/50/default/mifs-stage1.img'))
 for name in ('libm.so.2','libsocket.so.3'):
  matches=[b for n,b in files.items() if n.endswith('/'+name)];assert len(matches)==1;(libs/name).write_bytes(matches[0]);extras[name]=libs/name
 import factory_reset
 old=sys.argv;sys.argv=['qnx-actions','--payload',str(custom/'carplay_mu1367_oem_reset')]
 for n in ('reader-setup','toolchain','firmware-commands','output'):sys.argv+=['--'+n,str(getattr(a,n.replace('-','_')))]
 try:rc=factory_reset.main(script,extras,main/'COMMANDS.json')
 finally:sys.argv=old
 log=(a.output/'qemu.log').read_text(errors='replace');assert 'RELEASE_FACTORY_MIGRATION_PASS' in log and 'RELEASE_FACTORY_TRAIN_RECOGNITION_PASS' in log and 'RELEASE_FACTORY_PROGRESS_PASS' in log
 r=json.loads((a.output/'result.json').read_text());r.update(factory_progress_verified=True,factory_migration_verified=True,firmware_train_recognition_verified=True,map_only_actions_sha256=sha((main/'actions.sh').read_bytes()),main_controller_sha256=sha((main/'6/control.sh').read_bytes()),tuning_controller_sha256=sha((tuning/'6/control.sh').read_bytes()),fixture_changes='Only small-JXE fingerprint and the dependent main-controller before hash; complete SD preflight is a fixture return 0, checked in full on host',map_only_and_optional_transactions_verified=True,sdk_utilities_injected=False)
 (a.output/'result.json').write_text(json.dumps(r,indent=2)+'\n');return rc
if __name__=='__main__':raise SystemExit(main())
