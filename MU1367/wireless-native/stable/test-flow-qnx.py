#!/usr/bin/env python3
"""Factory-ksh flow/boot-boundary and real combined diagnostics checks.

The new release controller and collectors are production source. Base/wireless
children use explicit tiny stand-ins here; complete real-controller migration
and OEM restoration are separately exercised by test-host.py. The fixture
substitutes the small JXE digest and matching compatibility/checker hashes.
"""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
at=sys.argv.index('--build');build=Path(sys.argv[at+1]).resolve();del sys.argv[at:at+2]
out=Path(sys.argv[sys.argv.index('--output')+1]).resolve();inputs=out.with_name(out.name+'-inputs');inputs.mkdir(parents=True,exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
sd=build/'sd-card';release=sd/'Custom/carplay_mu1367_release'
control=(release/'control.sh').read_text().replace('09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a',sha(b'flow JXE fixture\n'))
child=r'''#!/bin/ksh
set -u
A=$1
P=$2
M=$CPMAP_TEST_ROOT
case "$P" in
 *guidance_v3)
  case "$A" in
   install)
    case "$(cat "$M/base")" in 153) echo previous > "$M/base";;*) echo 154 > "$M/base";;esac;;
   restore-oem) echo OEM > "$M/base";;
   recover|uninstall) echo previous > "$M/base";;
  esac
  echo BASE_FIXTURE_ACTION=$A
  exit 0;;
 *oem_reset)
  [ "$(cat "$M/base")" = OEM ];exit $?;;
esac
R=$M/mnt/app/carplay-mu1367-wireless-native-v161t2
case "$A" in
 install)
  if [ "$(cat "$R/STATE" 2>/dev/null)" = installed ];then echo ADOPT_FIXTURE;exit 0;fi
  mkdir -p "$R"
  cp "$P/control.sh" "$R/control.sh"
  echo fixture-build > "$R/VERSION"
  echo installed > "$R/STATE"
  echo retained > "$R/snapshot"
  echo wireless > "$M/target";;
 uninstall|recover) echo removed > "$P/STATE";echo original > "$M/target";echo CHILD_ACTION=$A;;
esac
'''
compat=(release/'compatibility.sh').read_text()
for data in json.loads((build/'manifest.json').read_text())['migration_roots'].values():compat=compat.replace(data['controller_sha256'],sha(child.encode()))
compat+=r'''
KEYS=probe
baseline_ok(){ [ "$(cat "$M/base")" = 154 ]; }
target(){ echo "$M/target"; }
before_ok(){ [ "$(cat "$2")" = original ]; }
legacy_keys(){ echo probe; }
legacy_target(){ echo "$M/target"; }
'''
files={'release-control.sh':control,'compatibility.sh':compat,'child-control.sh':child}
checks='CUSTOM_CHECK=${P%/*}\n'
for name,relative in [('release-control.sh','carplay_mu1367_release/control.sh'),('compatibility.sh','carplay_mu1367_release/compatibility.sh'),('child-control.sh','carplay_mu1367_wireless_native/control.sh')]:
 checks+='"$P/verify" "$CUSTOM_CHECK/'+relative+'" '+sha(files[name].encode())+' || return 1\n'
files['payload-check.sh']=checks
for n,t in files.items():(inputs/n).write_text(t)
spec=importlib.util.spec_from_file_location('fixture',HERE.parent/'tests/receiver-alt-gate.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
fixture.SOURCE='int flow_fixture_no_receiver_main;\n'
fixture.EXTRA_FILES={name:inputs/name for name in files}
fixture.EXTRA_FILES.update({'diag.sh':sd/'Toolbox/scripts/cpmap_diag.sh','wireless-collect.sh':sd/'Toolbox/scripts/cpmap_wireless_collect_data.sh'})
fixture.IFS_EXTRA='[type=file]\n'+'\n'.join(fixture.EXTRA_FILES)+'\n'
fixture.RUN_SCRIPT=r'''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
export CPMAP_TEST_ROOT=/ramdisk/unit
M=$CPMAP_TEST_ROOT
C=/ramdisk/sd/Custom
P=$C/carplay_mu1367_release
mkdir -p "$M/mnt/app" "$M/mnt/persist/wcp" "$M/ramdisk" "$M/ifs" "$M/fs/sda0" "$M/dev/shmem" "$P" "$C/carplay_mu1367_guidance_v3" "$C/carplay_mu1367_wireless_native" "$C/carplay_mu1367_oem_reset"
echo 'flow JXE fixture' > "$M/ifs/lsd.jxe"
cp /proc/boot/release-control.sh "$P/control.sh"
cp /proc/boot/compatibility.sh "$P/compatibility.sh"
cp /proc/boot/payload-check.sh "$P/payload-check.sh"
cp /proc/boot/verify "$P/verify"
for L in carplay_mu1367_guidance_v3 carplay_mu1367_wireless_native carplay_mu1367_oem_reset;do cp /proc/boot/child-control.sh "$C/$L/control.sh";done
cp /proc/boot/child-control.sh "$C/carplay_mu1367_guidance_v3/actions.sh"
echo 153 > "$M/base"
echo original > "$M/target"
run(){ /bin/ksh "$P/control.sh" "$1" "$P"; }
boot(){ rm -f "$M/ramdisk/.cpmap-release-v161-reboot"; }
run install
grep '^previous$' "$M/base"
if run install;then exit 81;fi
boot
run install
grep '^154$' "$M/base"
boot
run install
grep '^wireless$' "$M/target"
if run install;then exit 82;fi
boot
run install
R=$M/mnt/app/carplay-mu1367-wireless-native-v161t2
grep '^retained$' "$R/snapshot"
run restore-oem
grep '^removed$' "$R/STATE"
if run restore-oem;then exit 83;fi
boot
mkdir "$M/mnt/app/carplay-mu1367-oem-reset"
echo complete > "$M/mnt/app/carplay-mu1367-oem-reset/STATE"
cp /proc/boot/child-control.sh "$M/mnt/app/carplay-mu1367-oem-reset/control.sh"
run restore-oem
grep '^OEM$' "$M/base"
for F in "$M/mnt/app"/carplay-mu1367-oem-reset.complete-*;do test -f "$F/STATE";done
boot
echo installed > "$R/STATE"
echo changed >> "$R/control.sh"
if run install;then exit 84;fi
test ! -e "$M/ramdisk/.cpmap-release-v161-reboot"
cp /proc/boot/child-control.sh "$R/control.sh"
run recover
grep '^removed$' "$R/STATE"
boot
echo prepared > "$R/STATE"
mkdir -p "$R/backup"
cp "$M/target" "$R/backup/probe"
H=$("$P/verify" "$R/backup/probe")
echo "probe $H" > "$R/backup.index"
"$P/verify" "$R/backup.index" > "$R/backup.index.sha256"
: > "$R/BACKUPS_READY"
run recover
test ! -e "$R"
for F in "$M/mnt/app"/carplay-mu1367-wireless-native-v161t2.prepared-*;do test -f "$F/backup.index";done
grep '^original$' "$M/target"
boot
mkdir -p "$M/ramdisk/wcp-rg" /ramdisk/scripts
cp /proc/boot/diag.sh /ramdisk/scripts/cpmap_diag.sh
cp /proc/boot/wireless-collect.sh /ramdisk/scripts/cpmap_wireless_collect_data.sh
echo bounded-mailbox > "$M/ramdisk/wcp-rg/latest.bin"
echo cadence > "$M/ramdisk/wcp-rg/idr.state"
echo timing > "$M/ramdisk/wcp-video-timing.bin"
echo SECRET_PAIRING_SENTINEL > "$M/mnt/persist/wcp/pairing.key"
export CPMAP_TEST_MEDIA=$M/fs/sda0
/bin/ksh /ramdisk/scripts/cpmap_diag.sh
for D in "$M/fs/sda0/Log"/cpmap-diag-*;do
 grep bounded-mailbox "$D/wireless/state/wcp-rg-latest.bin"
 grep cadence "$D/wireless/state/wcp-rg-idr.state"
 grep timing "$D/wireless/state/wcp-video-timing.bin"
 test ! -e "$D/wireless/pairing.key"
done
echo STABLE_FLOW_QNX_PASS
'''
fixture.PASS_MARKER='STABLE_FLOW_QNX_PASS'
fixture.EVIDENCE=dict(production_release_controller_sha256=sha((HERE/'control.sh').read_bytes()),production_diagnostics_sha256={n:sha((sd/n).read_bytes()) for n in ('Toolbox/scripts/cpmap_diag.sh','Toolbox/scripts/cpmap_wireless_collect_data.sh')},scope='Factory-ksh orchestration, reboot boundary, old OEM snapshot retention and real combined collector; child base/wireless transactions are stand-ins here, separately tested as actual controllers on host.',receiver_main_executed=False)
fixture.main()
