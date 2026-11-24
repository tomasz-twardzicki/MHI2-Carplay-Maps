#!/usr/bin/env python3
"""Package a guarded, reversible native-reader test over exact v1.4.1."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
from payload_checks import write_payload_checks
HERE=Path(__file__).resolve().parent.parent
REPO=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','host','qnx','base-archive','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();b=json.loads((a.build/'manifest.json').read_text());h=json.loads(a.host.read_text());q=json.loads(a.qnx.read_text())
 binary=a.build/'rgi-observer';digest=sha(binary)
 assert b['passed'] and h['passed'] and q['passed']
 assert digest==b['sha256']==q['reader_sha256']
 assert sha(HERE/'src/reader/reader.c')==b['source_sha256']==h['reader_source_sha256']
 assert q['native_timeout_and_recovery'] and q['factory_libc_sha256']==b['factory_libc_sha256']
 assert sha(a.base_archive)==json.loads((REPO/'releases/MU1367/v1.4.1/manifest.json').read_text())['archive_sha256']
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);sd=out/'sd-card';sd.mkdir()
 with zipfile.ZipFile(a.base_archive) as z:
  for n in z.namelist():
   dest=sd/n;assert dest.resolve().is_relative_to(sd)
   if n.endswith('/'):dest.mkdir(parents=True,exist_ok=True);continue
   dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(n));dest.chmod((z.getinfo(n).external_attr>>16)&0o777 or 0o644)
 custom='carplay_mu1367_reader_recovery';live='carplay-mu1367-reader-recovery'
 root=sd/'Custom'/custom;root.mkdir()
 baseline=sd/'Custom/carplay_mu1367/rgi-observer';old_sha=sha(baseline)
 assert old_sha=='b683cef78828bfab2b8cdf43e4ea82e5d7c16d0d47730936d936e82af6ee08ac'
 guidance_sha=sha(sd/'Custom/carplay_mu1367_guidance_v3/6/CarPlayMU1367Guidance.jar');assert guidance_sha==h['guidance_sha256']
 parents={}
 for variant in ('6','6-road','7','7-road'):
  d=sd/'Custom/carplay_mu1367_guidance_v3'/variant;parents[(d/'VERSION').read_text().strip()]=sha(d/'control.sh')
 guard='''# Remove the reader test before changing the guidance parent.
case "${1:-status}" in install|uninstall|recover)
 G=${CPMAP_TEST_ROOT:-}
 if [ -z "$G" ] && [ ! -s /ifs/lsd.jxe ];then G=/net/mmx;fi
 G=$G/mnt/app/carplay-mu1367-reader-recovery
 if [ -d "$G" ];then
  [ -f "$G/STATE" ] && [ ! -L "$G/STATE" ] && [ "$(cat "$G/STATE")" = removed ] || { echo MU1367_READER_REMOVE_TEST_FIRST;exit 1; }
 fi;;esac
'''
 build='MU1367-reader-recovery-'+digest[:12]
 ctrl=(HERE/'tools/transaction.sh').read_text().replace('carplay-mu1367-lanes',live).replace('MU1367_LANES','MU1367_READER').replace('.lanes-new','.reader-new').replace('for K in parent settings;do','for K in $GUARDS;do')
 ctrl=ctrl.replace('  echo "Cards: App-Connect > Virtual Cockpit settings > navigation card ON/OFF; reconnect after changing"','  for F in status.txt reader-failure-first.txt;do if regular "$M/ramdisk/carplay-route-guidance/$F";then cat "$M/ramdisk/carplay-route-guidance/$F";fi;done')
 marker=' [ "$(cat "$P/VERSION" 2>/dev/null)" = "$BUILD" ] || fail PAYLOAD_VERSION'
 gates=' [ "$(cat "$APP/carplay-mu1367-guidance-v3/STATE" 2>/dev/null)" = installed ] || fail GUIDANCE_PARENT_REQUIRED\n'
 gates+=' check "$APP/eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar" '+guidance_sha+' || fail GUIDANCE_RUNTIME_CHANGED\n'
 gates+=' before parent >/dev/null || fail RECOGNIZED_V141_PARENT_REQUIRED\n'
 assert ctrl.count(marker)==1;ctrl=ctrl.replace(marker,gates+marker)
 table="KEYS='reader parent'\nFILES='reader'\nGUARDS='parent'\nGUARD_SHA="+hashlib.sha256(guard.encode()).hexdigest()+'\n'
 for var,name in [('PARENT_BUILD','carplay_mu1367'),('SETTINGS_BUILD','carplay_mu1367_settings')]:table+=var+'='+(sd/'Custom'/name/'VERSION').read_text().strip()+'\n'
 table+='target(){ case "$1" in reader) echo "$APP/carplay-mu1367/rgi-observer";; parent) echo "$APP/carplay-mu1367-guidance-v3/control.sh";; *) return 1;; esac; }\n'
 table+='payload(){ case "$1" in reader) echo rgi-observer;; *) return 1;; esac; }\n'
 table+='expected(){ case "$1" in reader) echo '+digest+';; *) return 1;; esac; }\n'
 table+='before(){ case "$1" in reader) echo '+old_sha+';; parent) case "$(cat "$APP/carplay-mu1367-guidance-v3/VERSION" 2>/dev/null)" in\n'
 for version,parent_sha in parents.items():table+=' '+version+') echo '+parent_sha+';;\n'
 table+=' *) return 1;;esac;; *) return 1;; esac; }\n'
 (root/'control.sh').write_text(ctrl.replace('@BUILD@',build).replace('@TABLE@',table));(root/'VERSION').write_text(build+'\n');(root/'guard').write_text(guard)
 shutil.copy2(binary,root/'rgi-observer');shutil.copy2(sd/'Custom/carplay_mu1367/verify',root/'verify')
 for action in ('install','uninstall','recover','status'):
  wrapper=(sd/'Toolbox/scripts/cpmap_suite_install.sh').read_text().replace('carplay_mu1367_guidance_v3/actions.sh',custom+'/control.sh').replace('carplay_mu1367_guidance_v3;',custom+';').replace('"$P/actions.sh" install','"$P/control.sh" '+action).replace('MU1367_OEM_RESET_','MU1367_READER_')
  (sd/'Toolbox/scripts'/('cpmap_reader_'+action+'.sh')).write_text(wrapper)
 with (sd/'Toolbox/GEM/carplay-maps-vc.esd').open('a') as f:
  for action,label in [('install','Install guidance reader recovery test (reboot)'),('uninstall','Restore previous guidance reader (reboot)'),('recover','Recover guidance reader update (reboot)'),('status','Guidance reader recovery / first failure')]:f.write('\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_reader_'+action+'.sh"\n    label "'+label+'"\n')
 shutil.copy2(HERE/'READER-RECOVERY.md',sd/'READER-RECOVERY.md')
 (sd/'README.md').write_text('# MU1367 / 791 guidance reader recovery test\n\nRead [READER-RECOVERY.md](READER-RECOVERY.md) for installation, behavior and rollback.\n')
 write_payload_checks(sd/'Custom')
 for f in [root/'control.sh',*(sd/'Toolbox/scripts').glob('cpmap_reader_*.sh')]:subprocess.run(['/bin/ksh','-n',str(f)],check=True);f.chmod(0o755)
 inv={str(f.relative_to(sd)):sha(f) for f in sorted(sd.rglob('*')) if f.is_file() and f.name!='FILES_SHA256.json'}
 (sd/'FILES_SHA256.json').write_text(json.dumps(inv,indent=2)+'\n')
 name='CarPlay_Maps_VC_MU1367_791_Reader_Recovery_Test.zip';archive=out/name
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for f in sorted(sd.rglob('*')):
   if f.is_file():z.write(f,f.relative_to(sd))
 r={'passed':True,'test_build':True,'build_id':build,'reader_sha256':digest,'base_reader_sha256':old_sha,'custom_layer':custom,'live_layer':live,'parent_controllers':parents,'guidance_sha256':guidance_sha,'archive_name':name,'archive_sha256':sha(archive),'base_archive_sha256':sha(a.base_archive),'host':h,'qnx':q,'build':b,'runtime_changes':['native reader','saved guidance controller removal guard'],'on_unit_validated':False}
 (out/'manifest.json').write_text(json.dumps(r,indent=2)+'\n');(out/'SHA256SUMS.txt').write_text(r['archive_sha256']+'  '+name+'\n');print(json.dumps({'archive':str(archive),'sha256':r['archive_sha256']}))
if __name__=='__main__':main()
