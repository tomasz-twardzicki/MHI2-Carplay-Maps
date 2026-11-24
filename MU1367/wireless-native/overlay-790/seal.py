#!/usr/bin/env python3
"""Seal the local candidate only after input, firmware and recovery evidence."""
import argparse,hashlib,json,re,shutil,subprocess,tempfile,zipfile,os
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
for n in ('build','components','host-result','qnx-result','j9-result','native-result','output'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--mux-result',type=Path)
p.add_argument('--media-result',type=Path)
p.add_argument('--media-replay-result',type=Path)
p.add_argument('--call-j9-result',type=Path)
p.add_argument('--test2-archive',type=Path)
a=p.parse_args();sd=a.build.resolve()/'sd-card';custom=sd/'Custom';mod=custom/'carplay_mu1367_input_profile'
build_info=json.loads((a.build/'manifest.json').read_text())
generation=build_info.get('generation',2 if build_info.get('upstream_790_runtime',False) else 1)
test2=generation>=2
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
reports={n:json.loads(getattr(a,n+'_result').read_text()) for n in ('host','qnx','j9','native')}
assert all(r['passed'] for r in reports.values()) and reports['host']['tests']==(7 if generation==3 else 6 if test2 else 5)
if test2:
 assert reports['qnx']['legacy_migration']
 assert a.mux_result
 reports['mux']=json.loads(a.mux_result.read_text())
 assert reports['mux']['passed'] and reports['mux']['decoded_frames_byte_identical']
 research=HERE.parent/'research/sergey-v163e'
 comparison=json.loads((research/'UPSTREAM-790-COMPARISON.json').read_text())
 assert comparison['changed_map_runtime_components']==['core.so','altscreen-most-bridge','carplay-cluster-supervisor']
 assert reports['mux']['bridge_source_sha256']==comparison['shipped_bridge_source_sha256']
 for name in ('UPSTREAM-790-COMPARISON.md','UPSTREAM-790-COMPARISON.json')+(('TEST2-FOLLOWUP.md',) if generation==3 else ()):
  shutil.copy2(research/name,sd/name)
assert reports['j9']['factory_j9_verified'] and reports['j9']['class49_negative_rejected']
manifest=json.loads((mod/'manifest.json').read_text());assert manifest==reports['qnx']['controllers']
if generation==3:
 assert a.media_result and a.media_replay_result and a.call_j9_result and a.test2_archive
 for name,path in [('media790_receiver',a.media_result),('media790_capture_replay',a.media_replay_result),('call_handoff_contract',a.call_j9_result)]:
  reports[name]=json.loads(path.read_text());assert reports[name]['passed']
 assert reports['media790_receiver']['media790_actual_parser'] and reports['media790_receiver']['actual_native_file_transfer']
 assert reports['media790_receiver']['components']==build_info['media790']['files']
 assert reports['call_handoff_contract']['original_cp_sha256']==sha(a.components/'CarPlayWireless-CP-55915411.jar')
 assert sha(a.test2_archive)=='ec0c3ee5c2a4ac32df091d7612648e707b1fee9b587fe7f3a45e327a9d13e4cb'
 by_target={r['target']:r for r in manifest['790']['rows']}
 with zipfile.ZipFile(a.test2_archive) as z:
  old=json.loads(z.read('Custom/carplay_mu1367_input_profile/manifest.json'))['790']
  unchanged=[]
  for row in old['rows']:
   if row['source']=='wireless-receiver-exec':continue
   assert by_target[row['target']]['sha256']==row['sha256'],row['target']
   unchanged.append(row['target'])
 assert len(unchanged)==14
 reports['test2_runtime_preserved']=dict(passed=True,targets_unchanged=unchanged,
  exception='790 bootstrap adds only the media observer; separate opt-in data preference enables the existing Bluetooth release request.')
component=json.loads((a.components/'VERIFICATION.json').read_text());assert component['passed']
for name,pin in component['files'].items():
 assert sha(a.components/name)==pin==reports['j9']['components'][name]
for variant,m in manifest.items():
 assert sha(mod/variant/'control.sh')==m['controller_sha256']
 for row in m['rows']:assert sha(mod/variant/'payload'/row['source'])==row['sha256']
for firmware in reports['native']['profiles'].values():
 for name,proof in firmware['modules'].items():
  file=mod/'790/payload'/name
  if not file.is_file():file=custom/'carplay_mu1367_wireless_native/payload'/name
  assert sha(file)==proof['sha256'],name
# Selector/tuner bytes must equal the scripts actually mapped into the QNX IFS.
qnx=a.qnx_result.parent;mapping=(qnx/'test.build').read_text()
for name in ('actions.sh','tune.sh','790/geometry.sh')+(('calls.sh',) if generation==3 else ()):
 match=re.search(r'^/test/profile/'+re.escape(name)+r'=([^\n]+)$',mapping,re.M);assert match,name
 assert sha(qnx/match[1])==sha(mod/name),name
for path in ('collect-wireless.sh','Toolbox/scripts/cpmap_wireless_collect_data.sh'):
 f=sd/path;s=f.read_text()
 s=s.replace('wcp_cp.log omonob-phone.log;do','wcp_cp.log wcp_touch.log omonob-phone.log;do')
 s=s.replace('for F in omonob-791-input.log','for F in omonob-790-input.log omonob-791-input.log')
 s=s.replace('for F in wcp_receiver.pid wcp_video.pid wcp_cp_session wcp_alt_probe;do','for F in wcp_receiver.pid wcp_video.pid wcp_cp_session wcp_alt_probe wcp_cp_fg wcp_touch_fg wcp_cp_touch_owner;do')
 s=s.replace('sync\necho "WIRELESS_DIAG_OK=', '''copy_file "$M/ramdisk/cpmap-touch.status" "$OUT/state/cpmap-touch.status"
for L in carplay-mu1367-profile-790-test carplay-mu1367-profile-790-test2 carplay-mu1367-profile-790-test3 carplay-mu1367-overlay-touch-test;do
 mkdir -p "$OUT/state/$L" || exit 1
 for F in STATE VERSION installed.index installed.index.sha256 backup.index backup.index.sha256;do
  copy_file "$APP/$L/$F" "$OUT/state/$L/$F"
 done
done
{
 echo '=== HMI input adapter files (presence matters as well as classpath order)'
 for F in NavActiveIgnore.jar CarPlayMU1367NavIgnore.jar CarPlayWireless-CP-55915411.jar CarPlayWireless-Touch-55915411.jar;do
  ls -ln "$APP/eso/hmi/lsd/jars/$F" 2>&1
 done
} >> "$OUT/summary.txt"
sync
echo "WIRELESS_DIAG_OK=''')
 if generation==3:
  s=s.replace('wcp_touch_fg wcp_cp_touch_owner;do','wcp_touch_fg wcp_cp_touch_owner wcp_cp_audio wcp_bt_released;do')
  summary='\n'.join(['{',
   ' if [ -f "$M/mnt/persist/wcp_btaudio_release" ] && [ ! -L "$M/mnt/persist/wcp_btaudio_release" ];then',
   '  echo CALL_HANDOFF_PREFERENCE=request_carplay',
   ' else echo CALL_HANDOFF_PREFERENCE=keep_bluetooth;fi',
   ' echo CALL_HANDOFF_NOTE=preference_and_request_markers_do_not_prove_actual_call_route',
   '} >> "$OUT/summary.txt"'])
  s=s.replace('sync\necho "WIRELESS_DIAG_OK=',summary+'\nsync\necho "WIRELESS_DIAG_OK=')
 f.write_text(s)
# Execute the changed read-only collector with representative profile/input
# evidence and a pairing sentinel which must never enter the export.
with tempfile.TemporaryDirectory(prefix='profile-export-') as tmp:
 root=Path(tmp)
 for d in ('ifs','ramdisk','dev/shmem','mnt/app/carplay-mu1367-profile-790-test','mnt/persist/wcp','fs/sda0'):(root/d).mkdir(parents=True,exist_ok=True)
 (root/'ifs/lsd.jxe').write_bytes(b'fixture')
 (root/'ramdisk/cpmap-touch.status').write_text('ROUTED_TOUCH1 routed=2\n')
 (root/'mnt/app/carplay-mu1367-profile-790-test/STATE').write_text('installed\n')
 (root/'mnt/persist/wcp/key').write_bytes(b'PRIVATE_PAIRING_SENTINEL')
 if generation==3:
  (root/'mnt/persist/wcp_btaudio_release').write_bytes(b'1\n')
  (root/'dev/shmem/wcp_cp_audio').write_bytes(b'3')
  (root/'dev/shmem/wcp_bt_released').write_bytes(b'1')
  (root/'dev/shmem/wcp_bt_disable').write_bytes(b'PRIVATE_PHONE_ADDRESS_SENTINEL')
 result=subprocess.run(['/bin/ksh',str(sd/'collect-wireless.sh'),'/fs/sda0'],env=dict(os.environ,CPMAP_TEST_ROOT=str(root)),capture_output=True,text=True)
 assert result.returncode==0,result.stdout+result.stderr
 exports=list((root/'fs/sda0/Log').glob('wireless-diag-*'));assert len(exports)==1
 assert (exports[0]/'state/cpmap-touch.status').read_text()=='ROUTED_TOUCH1 routed=2\n'
 assert (exports[0]/'state/carplay-mu1367-profile-790-test/STATE').read_text()=='installed\n'
 assert not any(b'PRIVATE_PAIRING_SENTINEL' in f.read_bytes() for f in exports[0].rglob('*') if f.is_file())
 if generation==3:
  assert (exports[0]/'state/wcp_cp_audio').read_bytes()==b'3'
  assert (exports[0]/'state/wcp_bt_released').read_bytes()==b'1'
  assert 'CALL_HANDOFF_PREFERENCE=request_carplay' in (exports[0]/'summary.txt').read_text()
  assert not any(b'PRIVATE_PHONE_ADDRESS_SENTINEL' in f.read_bytes() for f in exports[0].rglob('*') if f.is_file())
for name in ('START_HERE.md','README.md'):(sd/name).write_bytes((HERE/(name.replace('.md','_TEST%d.md'%generation) if test2 else name)).read_bytes())
source=mod/'source';shutil.copytree(HERE,source,ignore=shutil.ignore_patterns('__pycache__','VERIFICATION*.json'))
version='1.6.3-e-overlay790-test'+str(generation);(sd/'WIRELESS_VERSION').write_text(version+'\n')
top=json.loads((sd/'MU1367_RELEASE_MANIFEST.json').read_text());top['local_experiment']=dict(version=version,published=False,profiles=manifest)
(sd/'MU1367_RELEASE_MANIFEST.json').write_text(json.dumps(top,indent=2)+'\n')
# Check the complete SD guards after adding the experiments, and all script syntax.
guard_count=0
for f in custom.rglob('payload-check.sh'):
 if 'source' in f.relative_to(custom).parts:continue
 refs=re.findall(r'(?:check "\$P/([^\"]+)"|"\$P/verify" "\$CUSTOM_CHECK/([^\"]+)") ([0-9a-f]{64})',f.read_text());assert refs,f
 for local,shared,pin in refs:
  assert sha(f.parent/local if local else custom/shared)==pin,(f,local,shared);guard_count+=1
for f in sd.rglob('*.sh'):
 if 'source' not in f.relative_to(sd).parts:
  r=subprocess.run(['/bin/ksh','-n',str(f)],capture_output=True);assert r.returncode==0,(f,r.stderr)
verification=dict(version=version,passed=True,published=False,experimental=True,on_unit_validated=False,
 reports=reports,input=component,profiles=manifest,collector_test_passed=True,pairing_exported=False,guard_references_verified=guard_count,
 limits=['New metadata delivery and opt-in call handoff still need vehicle acceptance; the unchanged Test-2 map path was user-confirmed working.','790 custom guidance/timing/RHD/tuning extensions remain absent.','Input candidate forwards single-contact touchscreen press/release only.','Call handoff observes the existing addressed request, not a Bluetooth disconnect ACK or a verified physical call route.'] if generation==3 else ['No physical input, radio, MOST, video-output or call-transport acceptance.','790 uses the exact upstream backend; custom 791 wireless guidance/media/timing/RHD/tuning extensions are absent.','Input candidate forwards single-contact touchscreen press/release only.'])
(sd/'VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n');(HERE/('VERIFICATION-TEST%d.json'%generation if test2 else 'VERIFICATION.json')).write_text(json.dumps(verification,indent=2)+'\n')
for name in ('FILES_SHA256.json','WIRELESS-FILES.sha256'):(sd/name).unlink(missing_ok=True)
assert not any(f.is_symlink() for f in sd.rglob('*'))
files={f.relative_to(sd).as_posix():sha(f) for f in sorted(sd.rglob('*')) if f.is_file()}
(sd/'FILES_SHA256.json').write_text(json.dumps(files,indent=2)+'\n');files['FILES_SHA256.json']=sha(sd/'FILES_SHA256.json')
(sd/'WIRELESS-FILES.sha256').write_text(''.join(h+'  '+n+'\n' for n,h in sorted(files.items())));files['WIRELESS-FILES.sha256']=sha(sd/'WIRELESS-FILES.sha256')
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);archive=out/('CarPlay_MU1367_Overlay_790_Experimental_Test'+str(generation)+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name in sorted(files):
  f=sd/name;i=zipfile.ZipInfo(name,(2026,11,23 if generation==3 else 22,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=(0o100000|(f.stat().st_mode&0o777))<<16;z.writestr(i,f.read_bytes())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==len(files)
 assert {n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}==files
(out/'SHA256SUMS.txt').write_text(sha(archive)+'  '+archive.name+'\n')
for name in ('README.md','START_HERE.md','VERIFICATION.json'):shutil.copy2(sd/name,out/name)
print(json.dumps(dict(passed=True,archive=str(archive),sha256=sha(archive),zip_entries=len(files),published=False)))
