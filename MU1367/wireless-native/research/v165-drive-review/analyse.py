#!/usr/bin/env python3
"""Review five overlapping v165 exports without emitting route/track/paired-phone text."""
from pathlib import Path
import collections,hashlib,json,re,statistics,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
def fields(line):
 return {k:int(v) if re.fullmatch(r'-?\d+',v) else v for k,v in re.findall(r'([A-Za-z][A-Za-z0-9_]*)=([^\s]+)',line)}
def main():
 logs=Path('/Users/tomasz/Documents/github/personal/Logs/wireless/v1.6.5-e-test1')
 package=ROOT/'dist/v1.6.5-e-test1/CarPlay_Maps_VC_MU1367_791_v1.6.5-e-test1.zip'
 assert sha(package.read_bytes())=='af2ef5f8fb5b7a5d8805b6274aa6fa445d8268c41148eb7513842e6fc98e4eca'
 with zipfile.ZipFile(package) as z:component=json.loads(z.read('Custom/carplay_mu1367_wireless_native/manifest.json'))['components']
 exports=[];minute={};audio=set();reset=set();most=set();covers=set();native_launch=set();bt_stages=collections.Counter()
 for path in sorted(logs.glob('*.zip')):
  with zipfile.ZipFile(path) as z:
   fs={Path(*Path(n).parts[1:]).as_posix():z.read(n) for n in z.namelist() if not n.endswith('/')}
  prefix='wireless/' if path.name.startswith('cpmap-') else ''
  read=lambda name:fs.get(prefix+name,b'').decode('utf-8',errors='replace')
  summary=read('summary.txt');fp=dict(re.findall(r'^([^\n]+)\n([0-9a-f]{64})$',summary,re.M))
  for name in ('wireless-receiver-exec','libcpmap-wcp-tap.so','wireless-tune','altscreen-most-bridge','carplay-cluster-supervisor','libcpmap-bt-session.so'):assert fp[name]==component[name],(path.name,name)
  for line in read('logs/ramdisk-cpmap-wireless-summary.log').splitlines():
   row=fields(line)
   if 't_us' in row:minute[row['t_us']]=row
  for n,b in fs.items():
   if n.startswith(prefix+'logs/') and ('wcp.log' in n):
    for line in b.decode('utf-8',errors='replace').splitlines():
     q=re.search(r'\[cpmap\]\[audio\] t_us=(\d+).*type=102.*输出 (\d+) B.*MPL5 写入 (\d+) B 未激活 (\d+) 错 (\d+)',line)
     if q:audio.add(tuple(map(int,q.groups())))
   if n=='ramdisk/altscreen-most-bridge.log':
    for line in b.decode('utf-8',errors='replace').splitlines():
     if 'latency-reset sequence=' in line:reset.add(line)
     if 'MOST write failed:' in line or 'most-reclaim' in line:most.add(line)
  for line in read('logs/ramdisk-cpmap-native-launch.log').splitlines():native_launch.add(line)
  for line in read('logs/ramdisk-cpmap-artwork.log').splitlines():
   if 'event=decoded ' in line:covers.add(line)
  stages=read('logs/ramdisk-cpmap-bt-session.log');values=[fields(line) for line in stages.splitlines()]
  for row in values:
   if 'stage' in row:bt_stages[row['stage']]+=1
  bt=read('logs/btwcp.log')
  art=fields(fs.get('ramdisk/cpmap-artwork.status',b'').decode())
  exports.append(dict(archive=path.name,sha256=sha(path.read_bytes()),package_runtime_fingerprints_match=True,
   bt_status=fields(read('state/cpmap-bt-session.status')),artwork_status=art,
   bt_snapshot_counts=dict(carplay_start=bt.count('CarPlayStart'),forced_teardown=bt.count('通知接收端拆会话(WC bye)'),acl_failures=bt.count('ACL 建立失败'),oem_acl_reuses=bt.count('ACL 已在(原厂持有)'))))
 sessions={}
 for row in sorted(minute.values(),key=lambda r:r['t_us']):sessions.setdefault(row.get('session',0),[]).append(row)
 result=dict(review_date='2026-11-23',package_sha256=sha(package.read_bytes()),exports=exports,unique_summary_rows=len(minute),sessions=sessions,
  unique_native_launch_records=sorted(native_launch),unique_latency_reset_events=sorted(reset),unique_most_recovery_events=sorted(most),unique_cover_decodes=len(covers),
  audio=dict(retained_unique_samples=len(audio),output_matches_mpl5=all(r[1]==r[2] for r in audio),inactive_max=max((r[3] for r in audio),default=None),errors_max=max((r[4] for r in audio),default=None),from_us=min((r[0] for r in audio),default=None),to_us=max((r[0] for r in audio),default=None)),
  libc=dict(sha256='485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc',open_offset='0x1ae18',write_offset='0x1d1a4',captured_open='0x101ae18',captured_write='0x101d1a4',same_base='0x1000000',global_write_address_not_recorded=True),
  user_observations=dict(artwork_both_screens_every_test=True,covers_across_sessions=7,audio_continuous=True),
  limits=['Five exports overlap within one boot, not five drives. Do not sum repeated counters/logs.','PTS-step summaries are not direct wall-clock presentation measurements; delay_ms is smoothing demand, not end-to-end latency.','Retained audio logs cover their tail only; physical artwork/audio acceptance also uses the user report.','Exact identity of the different global write lookup is not in test1 logs. Test2 logs explicit/global/slot addresses and dladdr identities.'])
 (HERE/'EVIDENCE.json').write_text(json.dumps(result,indent=2)+'\n')
 for session,rows in sessions.items():print('SESSION',session,'rows',len(rows),'last',rows[-1])
 print('AUDIO',result['audio']);print('ARTWORK',[(r['archive'],r['artwork_status'].get('fetches'),r['artwork_status'].get('errors')) for r in exports])
if __name__=='__main__':main()
