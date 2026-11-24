#!/usr/bin/env python3
"""Factory-shell profile transactions; parent bytes are explicit verified seeds."""
import argparse,hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
for n in ('build','setup','toolchain','output'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--legacy-build',type=Path)
a=p.parse_args();sd=a.build.resolve()/'sd-card';mod=sd/'Custom/carplay_mu1367_input_profile';parent=sd/'Custom/carplay_mu1367_wireless_native'
inputs=a.output.resolve().with_name(a.output.name+'-inputs');inputs.mkdir(parents=True,exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
fake=b'profile transaction firmware fixture\n';(inputs/'jxe').write_bytes(fake)
wrapper='#!/bin/ksh\ncase "$1" in */ifs/lsd.jxe) /proc/boot/verify "$1" '+sha(fake)+' || exit 1\n [ "${2:-}" = 09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a ] && exit 0;;esac\nexec /proc/boot/verify "$@"\n'
(inputs/'fixture-verify').write_text(wrapper)
native=sha((parent/'verify').read_bytes());extra={'fixture-jxe':inputs/'jxe'};ifs='[type=file]\nfixture-jxe\n'
for f in sorted(mod.rglob('*')):
 if not f.is_file():continue
 source=f
 if f.name=='verify':source=inputs/'fixture-verify'
 if f.name=='payload-check.sh':
  source=inputs/('guard-'+f.parent.name);source.write_text(f.read_text().replace(native,sha(wrapper.encode())))
 name='profile-file-%03d'%len(extra);extra[name]=source;ifs+='/test/profile/'+f.relative_to(mod).as_posix()+'='+name+'\n'
profile=json.loads((mod/'manifest.json').read_text())['790'];rows=profile['rows']
base=json.loads((parent/'manifest.json').read_text());by_target={r['target']:r for r in base['rows']}
seeds={}
for r in rows:
 path=r['target']
 if r['before'] in ('optional','absent','callpref'):continue
 if path.endswith('/core.so'):data=(sd/'Custom/carplay_mu1367_guidance_v3/6/core.so').read_bytes()
 elif path.endswith('/PROFILE'):data=b'MU1367/791\n'
 else:data=(parent/'payload'/by_target[path]['source']).read_bytes()
 seeds[path]=data
seeds['/mnt/app/carplay-mu1367-wireless-native-v163t2/control.sh']=(parent/'control.sh').read_bytes()
seeds['/mnt/app/carplay-mu1367-wireless-native-v163t2/STATE']=b'installed\n'
script=r'''#!/bin/ksh
set -eu
export PATH=/ramdisk/tools:/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
export CPMAP_TEST_ROOT=/ramdisk/unit
M=$CPMAP_TEST_ROOT
P=/test/profile
mkdir -p /ramdisk/tools "$M/ifs" "$M/ramdisk" "$M/mnt/app" "$M/mnt/persist" "$M/mnt/ota" "$M/dev/shmem"
echo '#!/bin/ksh' > /ramdisk/tools/mount
echo 'exit 0' >> /ramdisk/tools/mount
chmod 755 /ramdisk/tools/mount
cp /proc/boot/fixture-jxe "$M/ifs/lsd.jxe"
'''
for i,(path,data) in enumerate(seeds.items()):
 source=inputs/('seed-%d'%i);source.write_bytes(data);extra[source.name]=source;ifs+=source.name+'\n'
 script+='mkdir -p "$M'+str(Path(path).parent)+'"\ncp /proc/boot/'+source.name+' "$M'+path+'"\n'
script+=r'''
run(){ /bin/ksh "$P/actions.sh" "$1" "$P"; }
boot(){ rm -f "$M/ramdisk/.cpmap-profile-test-reboot"; }
originals(){
'''
for path,data in seeds.items():script+=' /proc/boot/verify "$M'+path+'" '+sha(data)+' || exit 80\n'
for row in rows:
 if row['before'] in ('absent','callpref'):script+=' test ! -e "$M'+row['target']+'"\n'
script+=r'''
 test ! -e "$M/mnt/persist/altscreen.conf"
 test ! -e "$M/mnt/persist/altscreen.geom"
}
originals
run select-790
grep '^MU1367/790$' "$M/mnt/app/carplaymaps/PROFILE"
if run select-791;then exit 81;fi
boot
/bin/ksh "$P/tune.sh" set "$P/790" 220 20 600 330
grep '^safex=220$' "$M/mnt/persist/altscreen.conf"
if /bin/ksh "$P/tune.sh" set "$P/790" 900 20 600 330;then exit 82;fi
grep '^safex=220$' "$M/mnt/persist/altscreen.conf"
run select-791
originals
boot
run select-791
boot
run remove
originals
boot
if CPMAP_TEST_FAIL_AFTER_KEY=k04 /bin/ksh "$P/790/control.sh" install "$P/790";then exit 83;fi
originals
if CPMAP_TEST_INTERRUPT_AFTER_KEY=k11 /bin/ksh "$P/790/control.sh" install "$P/790";then exit 84;fi
/bin/ksh "$P/790/control.sh" recover "$P/790"
originals
R=$M/mnt/app/carplay-mu1367-profile-790-test
echo collecting > "$R/STATE"
rm "$R/BACKUPS_READY"
run remove
test ! -e "$R"
originals
boot
run select-790
boot
run remove
originals
echo PROFILE_790_FACTORY_SHELL_PASS
'''
script=script.replace('R=$M/mnt/app/carplay-mu1367-profile-790-test\n','R=$M/mnt/app/'+profile['recovery_root']+'\n')
if (mod/'calls.sh').is_file():
 calls=r'''
run calls-status
test ! -e "$M/mnt/persist/wcp_btaudio_release"
run calls-on
grep '^1$' "$M/mnt/persist/wcp_btaudio_release"
echo 1 > "$M/dev/shmem/wcp_cp_session"
if run calls-off;then exit 86;fi
rm "$M/dev/shmem/wcp_cp_session"
run calls-off
test ! -e "$M/mnt/persist/wcp_btaudio_release"
echo PROFILE_790_CALL_PREFERENCE_PASS
'''
 script=script.replace('/bin/ksh "$P/tune.sh" set "$P/790" 220 20 600 330',calls+'\n/bin/ksh "$P/tune.sh" set "$P/790" 220 20 600 330',1)
if a.legacy_build:
 legacy=a.legacy_build.resolve()/'sd-card/Custom/carplay_mu1367_input_profile/790'
 for f in sorted(legacy.rglob('*')):
  if not f.is_file():continue
  origin=f
  if f.name=='verify':origin=inputs/'fixture-verify'
  if f.name=='payload-check.sh':
   origin=inputs/'legacy-guard';origin.write_text(f.read_text().replace(native,sha(wrapper.encode())))
  name='legacy-profile-%03d'%len(extra);extra[name]=origin;ifs+='/test/legacy/'+f.relative_to(legacy).as_posix()+'='+name+'\n'
 upgrade=r'''
/bin/ksh /test/legacy/control.sh install /test/legacy
boot
R1=$M/mnt/app/carplay-mu1367-profile-790-test
/proc/boot/verify "$R1/backup.index" > /ramdisk/legacy-index
run select-790
originals
grep '^removed$' "$R1/STATE"
/proc/boot/verify "$R1/backup.index" "$(cat /ramdisk/legacy-index)"
if run select-790;then exit 85;fi
boot
run select-790
boot
run remove
originals
/proc/boot/verify "$R1/backup.index" "$(cat /ramdisk/legacy-index)"
boot
echo PROFILE_790_LEGACY_MIGRATION_PASS
'''
 legacy_profile=json.loads((legacy.parent/'manifest.json').read_text())['790']['recovery_root']
 upgrade=upgrade.replace('R1=$M/mnt/app/carplay-mu1367-profile-790-test\n','R1=$M/mnt/app/'+legacy_profile+'\n')
 script=script.replace('echo PROFILE_790_FACTORY_SHELL_PASS',upgrade+'\necho PROFILE_790_FACTORY_SHELL_PASS')
source=HERE.parents[1]/'tests/receiver-alt-gate.py'
code=source.read_text().replace("'120','qemu-system-arm'","'300','qemu-system-arm'").replace('time.monotonic()+100','time.monotonic()+260')
ns=dict(__file__=str(source),__name__='profile_qnx');exec(compile(code,str(source),'exec'),ns)
ns.update(SOURCE='int profile_fixture_no_receiver;\n',EXTRA_FILES=extra,IFS_EXTRA=ifs,RUN_SCRIPT=script,PASS_MARKER='PROFILE_790_FACTORY_SHELL_PASS',EVIDENCE=dict(scope='Actual profile controllers, selector, tuning, rollback, interruption and collecting-state recovery; verified installed-parent file seeds; JXE gate wrapped and mounts inert; no receiver/radio/MOST execution.',legacy_migration=bool(a.legacy_build),controllers=json.loads((mod/'manifest.json').read_text())))
sys.argv=[sys.argv[0],'--setup',str(a.setup),'--toolchain',str(a.toolchain),'--output',str(a.output)]
ns['main']()
