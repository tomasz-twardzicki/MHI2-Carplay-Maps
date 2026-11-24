#!/usr/bin/env python3
"""Audit eight overlapping exports without publishing device, road or track text."""
import argparse, hashlib, json, re, zipfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
def sha(data): return hashlib.sha256(data).hexdigest()
def fields(text):
    return {k: int(v) if re.fullmatch(r'-?\d+', v) else v
            for k, v in re.findall(r'([A-Za-z][A-Za-z0-9_]*)=([^\s]+)', text)}
GROUPS = {
    '16547957': 'connection-and-reconnect', '18190431': 'connection-and-reconnect',
    '19923039': 'connection-and-reconnect', '21626975': 'connection-and-reconnect',
    '17338463': 'drive-1', '19021919': 'drive-1',
    '16318548': 'drive-2-gps-probe', '18038868': 'drive-2-gps-probe',
}
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--logs', type=Path, required=True)
    a = p.parse_args()
    package = ROOT/'dist/v1.6.5-e-test2/CarPlay_Maps_VC_MU1367_791_v1.6.5-e-test2.zip'
    assert sha(package.read_bytes()) == 'e9b815eb0be0e1b9cf45564278e15b12ddbe4d0436553a40177e54324882fcae'
    with zipfile.ZipFile(package) as z:
        components = json.loads(z.read('Custom/carplay_mu1367_wireless_native/manifest.json'))['components']
    exports, summaries = [], {g: {} for g in set(GROUPS.values())}
    for path in sorted(a.logs.glob('*.zip')):
        identity = path.stem.split('-')[-1]
        assert identity in GROUPS, path.name
        with zipfile.ZipFile(path) as z:
            fs = {Path(*Path(n).parts[1:]).as_posix(): z.read(n) for n in z.namelist() if not n.endswith('/')}
        prefix = 'wireless/' if path.name.startswith('cpmap-') else ''
        def read(name): return fs.get(prefix+name, b'').decode('utf-8', 'replace')
        fingerprints = dict(re.findall(r'^([^\n]+)\n([0-9a-f]{64})$', read('summary.txt'), re.M))
        checked = ('wireless-receiver-exec', 'libcpmap-wcp-tap.so', 'wireless-tune',
                   'altscreen-most-bridge', 'carplay-cluster-supervisor', 'libcpmap-bt-session.so')
        for name in checked: assert fingerprints[name] == components[name], (path.name, name)
        rows = []
        for line in read('logs/ramdisk-cpmap-wireless-summary.log').splitlines():
            row = fields(line)
            if 't_us' in row:
                rows.append(row)
                summaries[GROUPS[identity]][(row['t_us'], row.get('bridge_pid'), row.get('session'))] = row
        bt = read('logs/btwcp.log')
        cp = read('logs/wcp_cp.log')
        receiver = read('logs/wcp.log')
        status = fields(read('state/cpmap-bt-session.status'))
        probe = fields(read('state/cpmap-gps-probe.txt').split('\n')[0])
        positions = [fields(line) for line in read('state/cpmap-gps-probe.txt').splitlines() if line.startswith('position ')]
        adapter = fields(read('state/wcp-rg-adapter-status.txt'))
        art = fields(fs.get('ramdisk/cpmap-artwork.status', b'').decode('utf-8', 'replace'))
        exports.append(dict(archive=path.name, sha256=sha(path.read_bytes()), group=GROUPS[identity],
            package_runtime_fingerprints_match=True, checked_components=list(checked),
            bt_status=status,
            bt_retained_log_counts=dict(acl_failures=bt.count('ACL 建立失败'),
                oem_acl_reuses=bt.count('ACL 已在(原厂持有)'),
                forced_wc_bye=bt.count('通知接收端拆会话(WC bye)'),
                preserved_events=read('logs/ramdisk-cpmap-bt-session.log').count('bt-close-preserve-live-wifi'),
                profile_release_kept=cp.count('bt audio | kept'),
                phone_disable_bluetooth=receiver.count('disableBluetooth ->')),
            road_adapter={k: adapter[k] for k in ('run','records','road_fields_seen','nonempty_roads_seen','road_index','next_road_at','mode') if k in adapter},
            road_output_trace_present=bool(read('logs/ramdisk-cpmap-road-output.log')),
            gps_probe={k: probe[k] for k in ('positions','clocks','boot_clocks','boot_sources','sources','failures') if k in probe},
            gps_retained_position_rows=len(positions),
            gps_retained_map_matched=sum(r.get('map_matched') == 1 for r in positions),
            gps_retained_raw_gnss_proven=sum(r.get('raw_gnss_proven') == 1 for r in positions),
            artwork={k: art[k] for k in ('fetches','errors','clears','attempts','decoded') if k in art},
            summary_rows=len(rows)))
    assert len(exports) == 8
    groups = {}
    for name, data in summaries.items():
        rows = sorted(data.values(), key=lambda r: r['t_us'])
        groups[name] = dict(unique_rows=len(rows), rows=rows,
            max_pts_step_ms=max((r.get('pts_step_max', 0)/90 for r in rows), default=None),
            warning='PTS interval, not measured wall-clock display cadence. Summary counters are cumulative within a bridge process.')
    result = dict(review_date='2026-11-24', package_sha256=sha(package.read_bytes()), exports=exports, groups=groups,
        findings=dict(native_oem_acl_prescan_exists=True,
            native_prescan_function='0x252bc', native_prescan_loop='0x254fc..0x25570',
            native_oem_acl_lookup='0x25068', required_native_acl_state=3,
            current_road_empty_is_not_omitted=True,
            timestamp_log_reason_is_correlation_reason=True,
            capture_repair_threshold_us=250000,
            gps_posposition_raw_gnss_and_utc_not_proven=True),
        limits=['Eight archives overlap across three reported boots; do not sum repeated counters.',
            'Last mailbox records and adapter status are snapshots, including route stop; they do not reconstruct the earlier road cache.',
            'Existing continuity logs lack clock-repair reason. BT-off and Wi-Fi-loss timing alone cannot attribute PTS rebases.',
            'An OEM-held ACL on a later attempt does not prove it existed or was visible to the native lookup on attempt one.',
            'Profile release is not equivalent to full ACL release or disabling the shared Bluetooth stack.'])
    (HERE/'EVIDENCE.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(exports=len(exports), groups={k: {'unique_rows': v['unique_rows'], 'max_pts_step_ms': v['max_pts_step_ms']} for k,v in groups.items()})))
if __name__ == '__main__': main()
