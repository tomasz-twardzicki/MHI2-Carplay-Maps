#!/usr/bin/env python3
"""Read the two drive exports and package fingerprints; never modify captures.

This reports retained log windows, not whole-drive latency statistics. No radio,
receiver, firmware or package is executed. Run from any directory with Python 3.
"""
import argparse
import hashlib
import json
import re
import statistics
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIRELESS = HERE.parents[1]
DEFAULT_LOGS = Path('/Users/tomasz/Documents/github/personal/Logs/wireless/v1.6.2e-test1')
PAIRS = [('wireless-diag-45396096', 'cpmap-diag-44699776'),
         ('wireless-diag-51548255', 'cpmap-diag-50896995')]
COMPONENTS = ['wireless-receiver-exec', 'libcpmap-wcp-tap.so']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fields(line):
    return {k: int(v) for k, v in re.findall(r'([a-zA-Z0-9_]+)=(\d+)', line)}


def package_fingerprints(version):
    candidates = sorted((WIRELESS / 'dist' / version).glob('*.zip'))
    if len(candidates) != 1:
        raise ValueError('Expected one package for ' + version)
    package = candidates[0]
    with zipfile.ZipFile(package) as archive:
        result = {name: digest(archive.read(
            'Custom/carplay_mu1367_wireless_native/payload/' + name))
                  for name in COMPONENTS}
    return dict(path=str(package.relative_to(WIRELESS)),
                sha256=digest(package.read_bytes()), components=result)


def drive(logs, wireless_name, standard_name, packages):
    root, standard = logs / wireless_name, logs / standard_name
    used = {}

    def read(base, name):
        path = base / name
        if not path.is_file():
            return None
        data = path.read_bytes()
        used[str(path.relative_to(logs))] = dict(bytes=len(data), sha256=digest(data))
        return data.decode('utf-8', errors='replace')

    summary = read(root, 'summary.txt')
    fingerprints = {}
    lines = summary.splitlines()
    for name in COMPONENTS:
        index = lines.index(name)
        value = lines[index + 1]
        if not re.fullmatch('[0-9a-f]{64}', value):
            raise ValueError('Invalid fingerprint for ' + name)
        fingerprints[name] = value
    matching = [v for v, package in packages.items()
                if fingerprints == package['components']]
    bridge = read(root, 'logs/ramdisk-altscreen-most-bridge.log')
    metrics = [fields(line) for line in bridge.splitlines() if 'bridge: metrics ' in line]
    blocks = [fields(line) for line in bridge.splitlines() if 'bridge: blocks=' in line]
    clocks = [fields(line) for line in bridge.splitlines() if 'bridge: clock ' in line]
    timing = [fields(line) for line in bridge.splitlines() if 'bridge: wireless timing ' in line]
    # Ninety-kHz PTS steps are frame timestamp intervals, not a direct measure
    # of displayed freezes or of end-to-end latency.
    steps = [m['pts_step_max'] for m in metrics]
    tail = dict(metrics_samples=len(metrics),
                pts_step_max_ms=max(steps) / 90,
                pts_step_max_median_ms=statistics.median(steps) / 90,
                samples_with_pts_step_at_least_200_ms=sum(s >= 18000 for s in steps),
                samples_with_pts_step_at_least_200_ms_percent=100 * sum(s >= 18000 for s in steps) / len(steps),
                frame_max_bytes=max(m['frame_max'] for m in metrics),
                queue_hi_max=max(m['queue_hi'] for m in metrics),
                queue_hi_total_max=max(m['queue_hi_total'] for m in metrics),
                fps_median=statistics.median(m['fps_milli'] for m in metrics) / 1000,
                fps_max_short_window=max(m['fps_milli'] for m in metrics) / 1000,
                first_cumulative=blocks[0], last_cumulative=blocks[-1],
                first_clock=clocks[0], last_clock=clocks[-1],
                clock_span_seconds=(clocks[-1]['ntp'] - clocks[0]['ntp']) / 2**32,
                cumulative_frames_per_idr=blocks[-1]['frames'] / blocks[-1]['keys'],
                timing_log_lines=len(timing), last_timing=timing[-1] if timing else None)
    wcp = read(root, 'logs/wcp.log')
    auto = read(root, 'logs/wcp_autostart.log')
    video = read(root, 'logs/wcp_video.log')
    rotations = re.findall(r'第\s*(\d+)\s*次', wcp)
    status = {}
    for name in ['session.state', 'source-status.txt', 'adapter-status.txt', 'idr.state']:
        status[name] = read(root, 'state/wcp-rg-' + name) if name != 'idr.state' else read(root, 'state/wcp-rg-idr.state')
    audio = read(standard, 'ramdisk/carplay-now-playing-n1.status')
    card = read(standard, 'preferences/navigation-card.state')
    display = read(standard, 'preferences/display.state')
    supervisor = read(root, 'logs/ramdisk-carplay-cluster-supervisor.log')
    read(root, 'logs/ramdisk-omonob-791-input.log')
    read(root, 'logs/omonob-phone.log')
    return dict(wireless_export=wireless_name, standard_export=standard_name,
                runtime_fingerprints=fingerprints, matches_package_components=matching,
                managed_layer_lines=lines[1:15], retained_bridge_window=tail,
                state=status, now_playing_status=audio, navigation_card=card,
                display_preferences=display,
                wcp_rotation_count_reported=int(rotations[-1]) if rotations else None,
                retained_now_playing_5001_occurrences=len(re.findall(r'CSM msgid=0x5001\b', wcp)),
                audio_jitter_counter_lines=[line for line in wcp.splitlines()
                    if re.search(r'Late|Missing|Gaps|Rebuffer|underrun', line, re.I)],
                main_video_final_stats=video.splitlines()[-1],
                pf_empty_nat_observed="NAT 接口 '',''" in auto,
                pf_macro_error_observed="macro 'wlan_if' not defined" in auto,
                false_video_failure_observed='wcp_video 启动失败' in auto,
                channel_lines=[line for line in auto.splitlines() if 'settled on' in line or 'moved' in line],
                supervisor_lifecycle_lines=[line for line in supervisor.splitlines()
                    if any(word in line for word in ['video-owner-stop', 'bridge-started', 'ring-mapped', 'stopped', 'oem-most-restore'])],
                evidence_files=used)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--logs', type=Path, default=DEFAULT_LOGS)
    parser.add_argument('--output', type=Path, default=HERE / 'EVIDENCE.json')
    args = parser.parse_args()
    packages = {version: package_fingerprints(version)
                for version in ['v1.6.1', 'v1.6.2-e-test1']}
    source_names = ['v161/src/native/wcp_tap.c', 'v162/src/native/wcp_tap.c',
                    'v162/src/native/wcp_priority.h', 'v162/tests/receiver-tap.py',
                    'v162/src/runtime/wcp_ctl.sh',
                    'v162/src/runtime/vc-runtime/runtime/altscreen_most_bridge.c',
                    'stable/diagnostics.py', 'collect-wireless.sh']
    sources = {name: digest((WIRELESS / name).read_bytes()) for name in source_names}
    result = dict(schema=1, scope='offline analysis; no fixes or package built',
                  logs=str(args.logs), packages=packages,
                  user_clarification=dict(date='2026-11-19',
                      recorded_before_installing_v162=True,
                      interpretation='v1.6.1 baseline captures; not evidence of v1.6.2 installation failure'),
                  reviewed_source_sha256=sources,
                  limits=['Bridge metrics cover retained tails, not entire drives.',
                          'PTS intervals are not directly measured display freezes.',
                          'An advertised FPS maximum is not a guaranteed delivered FPS.',
                          'Package matches cover the two named native components only; HMI is corroborated by its status.'],
                  drives=[drive(args.logs, *pair, packages) for pair in PAIRS])
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    for item in result['drives']:
        t = item['retained_bridge_window']
        print(item['wireless_export'], 'native match=' + ','.join(item['matches_package_components']),
              'retained clock span=%.1fs' % t['clock_span_seconds'],
              'metrics=%d' % t['metrics_samples'], 'queue_hi=%d' % t['queue_hi_max'])


if __name__ == '__main__':
    main()
