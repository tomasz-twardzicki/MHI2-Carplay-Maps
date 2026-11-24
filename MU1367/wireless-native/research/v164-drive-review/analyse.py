#!/usr/bin/env python3
"""Read-only review of four v1.6.4 exports; emit counts, never road/GPS/track text.

Minute summaries describe PTS steps and sampled buffer demand, not measured
end-to-end display latency. Rotated detail logs cover only their retained tail.
"""
import argparse, collections, hashlib, json, re, statistics, struct, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
WIRELESS=HERE.parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
def fields(text):
    return {k:int(v) if re.fullmatch(r'-?\d+',v) else v
            for k,v in re.findall(r'([a-zA-Z][a-zA-Z0-9_]*)=([^\s]+)',text)}
def files(path):
    with zipfile.ZipFile(path) as z:
        result={}
        for i in z.infolist():
            if i.is_dir():continue
            parts=Path(i.filename).parts
            assert not Path(i.filename).is_absolute() and '..' not in parts
            key=Path(*parts[1:]).as_posix();assert key not in result
            result[key]=z.read(i)
    return result
def read(fs,name):return fs.get(name,b'').decode('utf-8',errors='replace')
def median(items):return statistics.median(items) if items else None

def mailbox(b):
    assert b[:4]==b'RGM1' and struct.unpack_from('<I',b,8)[0]==len(b)
    if b[32:36]!=b'RGI1':return dict(maneuvers=0)
    count=struct.unpack_from('<I',b,56)[0];assert count<=16
    at=96;rows=[];ids=collections.Counter();sources=set()
    for _ in range(count):
        seq,kind,size,session,res=struct.unpack_from('<IHHII',b,at)
        p=b[at+16:at+16+size];assert len(p)==size;at+=16+size;x=0;params={}
        while x<len(p):
            n,key=struct.unpack_from('>HH',p,x);assert n>=4 and x+n<=len(p)
            assert key not in params or kind==0x5204 and key in (0,2)
            params[key]=p[x+4:x+n];x+=n
        ids[hex(kind)]+=1
        if kind==0x5201 and 19 in params:
            # Only recognized app names leave this parser; no destination text.
            name=params[19].rstrip(b'\0').decode('utf-8',errors='replace')
            for app in ['Apple','Google','Waze']:
                if app.lower() in name.lower():sources.add(app)
        if kind==0x5202:
            raw=params.get(4,b'').rstrip(b'\0');raw.decode('utf-8')
            rows.append(dict(index=int.from_bytes(params.get(1,b''),'big'),parameter_ids=sorted(params),after_road_nonempty=bool(raw),after_road_bytes=len(raw)))
    assert at==len(b)
    return dict(retained_events=count,event_kinds=dict(ids),maneuvers=len(rows),after_road_nonempty=sum(r['after_road_nonempty'] for r in rows),rows=rows,recognized_route_sources=sorted(sources))

def artwork(text):
    rows=[fields(line) for line in text.splitlines() if line.startswith('ARTWORK ')]
    gates=[r for r in rows if r.get('event')=='gate']
    return dict(events=dict(collections.Counter(r.get('event') for r in rows)),gates=len(gates),
        no_uid=sum(r.get('uid_nonzero')==0 for r in gates),metadata_absent=sum(r.get('metadata')==0 for r in gates),
        no_cover=sum(r.get('cover',0)==0 for r in gates),text_not_matching=sum(r.get('text_match')==0 for r in gates),
        keep_true=sum(r.get('keep')==1 for r in gates))

def bt_elf(b):
    assert b[:7]==b'\x7fELF\x01\x01\x01'
    off=struct.unpack_from('<I',b,28)[0];size,count=struct.unpack_from('<HH',b,42)
    ph=[struct.unpack_from('<8I',b,off+i*size) for i in range(count)]
    def mapped(va,n):
        for typ,offset,start,_,filesz,_,_,_ in ph:
            if typ==1 and start<=va and va+n<=start+filesz:return b[offset+va-start:offset+va-start+n]
        raise ValueError(hex(va))
    dyn=next(p for p in ph if p[0]==2);tags={}
    for p in range(dyn[1],dyn[1]+dyn[4],8):
        k,v=struct.unpack_from('<II',b,p)
        if not k:break
        tags[k]=v
    slots={}
    for at in range(0,tags[2],8):
        offset,info=struct.unpack('<II',mapped(tags[23]+at,8))
        if offset not in (0x47878,0x47860):continue
        sym=struct.unpack('<IIIBBH',mapped(tags[6]+(info>>8)*16,16))
        name=mapped(tags[5]+sym[0],16).split(b'\0')[0].decode()
        slots[name]=dict(offset=hex(offset),relocation=info&255,initial_word=hex(struct.unpack('<I',mapped(offset,4))[0]))
    contracts={hex(v):hex(struct.unpack('<I',mapped(v,4))[0]) for v in (0x13770,0x1c4c4,0x22e90,0x23c30)}
    return dict(sha256=sha(b),bind_now=(24 in tags or bool(tags.get(30,0)&8) or bool(tags.get(0x6ffffffb,0)&1)),slots=slots,contract_words=contracts,
        live_failure_stage_known=False,lazy_binding_explanation='Consistent with pinned ELF and current libc-only slot check; no live slot values were exported.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--logs',type=Path,default=Path('/Users/tomasz/Documents/github/personal/Logs/wireless/v1.6.4'))
    p.add_argument('--output',type=Path,default=HERE/'EVIDENCE.json');a=p.parse_args()
    package=WIRELESS/'dist/v1.6.4-e-test1/CarPlay_Maps_VC_MU1367_791_v1.6.4-e-test1.zip'
    assert sha(package.read_bytes())=='e2149b66f5dc7f6c26890d8b6ecad5961a99ec2da6b66096785f3a8d9e116dd4'
    with zipfile.ZipFile(package) as z:
        prefix='Custom/carplay_mu1367_wireless_native/'
        m=json.loads(z.read(prefix+'manifest.json'));native=bt_elf(z.read(prefix+'payload/libbtwcp.so'))
    result=dict(review_date='2026-11-23',package_sha256=sha(package.read_bytes()),bt_elf=native,drives=[],
        limits=['Only retained tail records are available for audio, main video and detailed bridge logs.',
                'Minute pts_step_max is a PTS interval, not proof of a wall-clock freeze; delay_ms is sampled smoothing demand, not end-to-end latency.',
                'Artwork responses=0 needs HMI publish/handle instrumentation; successful decode does not prove display.',
                'Position reliability is map-matched. Repeating its last value with invented UTC would not establish a new GNSS fix.'])
    for label,standard,wireless in [('gps_off','cpmap-diag-29999199','wireless-diag-31596639'),('gps_on','cpmap-diag-27807836','wireless-diag-29409375')]:
        sf=files(a.logs/(standard+'.zip'));wf=files(a.logs/(wireless+'.zip'))
        logs={n:data.decode('utf-8',errors='replace') for n,data in wf.items() if n.startswith('logs/')}
        summary=read(wf,'summary.txt');fp={name:pin for name,pin in re.findall(r'^([^\n]+)\n([0-9a-f]{64})$',summary,re.M)}
        for name in ['wireless-receiver-exec','libcpmap-wcp-tap.so','wireless-tune','altscreen-most-bridge','carplay-cluster-supervisor']:assert fp[name]==m['components'][name],name
        minute=[fields(l) for l in logs['logs/ramdisk-cpmap-wireless-summary.log'].splitlines() if 't_us=' in l]
        full=[r for r in minute if r.get('event')=='minute'];last=minute[-1]
        au=[];mainfps=[];altfps=[]
        for name in ['logs/wcp.log.1','logs/wcp.log']:
            text=logs.get(name,'')
            for line in text.splitlines():
                q=re.search(r'\[cpmap\]\[audio\] t_us=(\d+).*\[wcp\]\[audio\].*type=102.*输出 (\d+) B.*MPL5 写入 (\d+) B 未激活 (\d+) 错 (\d+)',line)
                if q:au.append(tuple(map(int,q.groups())))
                q=re.search(r'\[wcp\]\[(screen|alt-screen)\].*近\s*[0-9.]+\s*秒\s+([0-9.]+) fps',line)
                if q:(mainfps if q[1]=='screen' else altfps).append(float(q[2]))
        bt=logs['logs/btwcp.log'];cp=logs['logs/wcp_cp.log']
        cpwatch=re.search(r'cp_watch:CarPlay 会话已建立 dt=(\d+)ms 重发=(\d+)',bt)
        gate=artwork(logs['logs/ramdisk-cpmap-artwork.log'])
        probe=read(wf,'state/cpmap-gps-probe.txt');probe_rows=[fields(l) for l in probe.splitlines() if l.startswith('position ')]
        times=[int(re.match(r'(\d+) \|',l)[1]) for l in cp.splitlines() if re.match(r'\d+ \|',l) and '| canvas |' in l]
        row=dict(label=label,standard=standard,wireless=wireless,
            archives={n:sha((a.logs/(n+'.zip')).read_bytes()) for n in [standard,wireless]},
            package_runtime_fingerprints_match=True,
            stream=dict(summary_records=len(minute),last=last,first_minute_pts_step_ms=full[0]['pts_step_max']/90,
                        subsequent_max_pts_step_ms=max(r['pts_step_max'] for r in full[1:])/90,
                        smoothing_sample_median_ms=median([r['delay_ms'] for r in full]),smoothing_sample_max_ms=max(r['delay_ms'] for r in full),
                        retained_main_fps_median=median(mainfps),retained_alt_fps_median=median(altfps)),
            audio=dict(retained_samples=len(au),from_us=au[0][0] if au else None,to_us=au[-1][0] if au else None,
                       output_matches_mpl5=all(r[1]==r[2] for r in au),inactive_max=max((r[3] for r in au),default=None),errors_max=max((r[4] for r in au),default=None)),
            bt=dict(status=fields(read(wf,'state/cpmap-bt-session.status')),attach_log=read(wf,'logs/ramdisk-cpmap-bt-session.log').strip(),
                    carplay_start_count=bt.count('CarPlayStart'),cp_watch_established_ms=int(cpwatch[1]) if cpwatch else None,
                    resends=int(cpwatch[2]) if cpwatch else None,cold_acl_failure='ACL 建立失败' in bt,
                    oem_acl_reuse='ACL 已在(原厂持有)' in bt),
            gps=dict(enabled=wf.get('preferences/gps.enabled')==b'1\n',probe_enabled=wf.get('preferences/gps-probe.enabled')==b'1\n',
                     dio_seen='dio_manager.real' in summary[summary.index('=== MMX process'):],
                     attempt_present='state/cpmap-gps-dio-attempt.state' in wf,source_present='state/wcp-location-latest.bin' in wf,
                     receiver=fields(read(wf,'state/wcp-rg-location.status')),
                     probe=fields(probe.splitlines()[0]) if probe else {},retained_position_rows=len(probe_rows),
                     map_matched_rows=sum(bool(r.get('reliability_raw',0)&1024) for r in probe_rows),
                     reliability_histogram=dict(collections.Counter(r.get('reliability_raw') for r in probe_rows)),
                     position_states=sorted(set(r['state'] for r in probe_rows)),validities=sorted(set(r['validity'] for r in probe_rows))),
            artwork=dict(status=fields(read(sf,'ramdisk/cpmap-artwork.status')),trace=gate),
            media=fields(read(wf,'state/wcp-now-playing.status')),
            guidance=mailbox(wf['state/wcp-rg-latest.bin']),
            mu_canvas_events=[l for l in cp.splitlines() if '| canvas |' in l],
            snapshot_note='Artwork counters are from the standard export; event history is from the slightly later standalone export. Do not treat them as simultaneous.',
            file_fingerprints={n:dict(bytes=len(wf[n]),sha256=sha(wf[n])) for n in sorted(wf)})
        result['drives'].append(row)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    for r in result['drives']:
        print(json.dumps(dict(label=r['label'],timing_matches=r['stream']['last']['timing_matches'],timing_misses=r['stream']['last']['timing_misses'],pts_first_ms=r['stream']['first_minute_pts_step_ms'],pts_later_max_ms=r['stream']['subsequent_max_pts_step_ms'],smoothing_median_ms=r['stream']['smoothing_sample_median_ms'],audio_samples=r['audio']['retained_samples'],artwork_fetches=r['artwork']['status']['fetches'],artwork_errors=r['artwork']['status']['errors'],artwork_responses=r['artwork']['status']['responses'],maneuver_records=r['guidance']['maneuvers'],next_road_records=r['guidance']['after_road_nonempty'])))
if __name__=='__main__':main()
