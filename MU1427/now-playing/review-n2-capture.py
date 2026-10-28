#!/usr/bin/env python3
"""Review N2 counters and bounded diagnostic summaries; retain no media/text.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

N2_BUILD = 'MU1427-AUDIO-N2-06af3c0b1a79'
N1_BUILD = 'MU1427-AUDIO-N1-8bbacafe81af'
COUNTERS = ('associations', 'setups', 'data_calls', 'completed',
            'jpeg_signatures', 'png_signatures', 'oversize_setups',
            'setup_not_receiving', 'other_signatures')
NATIVE = {'format', 'observer', 'bytes', 'sequence', 'fault', 'last_size',
          'session', 'enabled', 'instance_sec', 'instance_nsec', *COUNTERS}
N1_COUNTERS = ('ticks', 'fills', 'accepted', 'rejected', 'failures',
               'attach_failures', 'tracks', 'covers', 'io_failures', 'writes')
N1_FIELDS = {'format', 'build', 'text_output', 'epoch', 'connected', 'context', *N1_COUNTERS}
ERRORS = {'ARGUMENTS', 'READER_LOCK_OR_STALE_CHILD_REBOOT',
          'CHILD_NOT_REAPED_LOCK_RETAINED_REBOOT',
          'DEVICE_TIMEOUT_OR_SHORT_WORKER_REPLY', 'DEVICE_IO_1', 'DEVICE_IO_2',
          'DEVICE_IO_3', 'SNAPSHOT_SCHEMA', 'LOCK_REMOVE'}


def bounded(path, limit=8192):
    data = path.read_bytes()
    if not 0 < len(data) <= limit:
        raise ValueError('capture size bound: ' + path.name)
    return data, data.decode('ascii').splitlines()


def fields(line, allowed, strings=None, signed=()):
    strings = strings or {}
    result = {}
    for token in line.split():
        key, value = token.split('=', 1)
        if key not in allowed or key in result:
            raise ValueError('unknown/duplicate field')
        if key in strings:
            if value != strings[key]:
                raise ValueError('unexpected string/build')
        else:
            if not re.fullmatch(r'-?\d+', value):
                raise ValueError('non-integer counter')
            value = int(value)
            if not (0 <= value <= 0xffffffff or key in signed and value == -1):
                raise ValueError('counter bound')
        result[key] = value
    if result.keys() != allowed:
        raise ValueError('missing fields')
    return result


def review(root):
    paths = sorted(root.glob('cpmap-audio-N2-*'))
    if not paths:
        raise ValueError('no N2 snapshots')
    snapshots, instances = [], {}
    prior_n1 = None
    for folder in paths:
        install_raw, install = bounded(folder / 'install.txt')
        if (len(install) != 4 or install[:2] != [
                'N2 artwork transfer observer; N1 text unchanged; no image output', N2_BUILD]
                or install[2] != 'driver_bytes=744248'
                or install[3] not in ('snapshot_result=0', 'snapshot_result=1')):
            raise ValueError('unexpected installation/build envelope')
        raw, lines = bounded(folder / 'native.txt')
        if len(lines) != 1:
            raise ValueError('native record count')
        item = {'snapshot': folder.name, 'hashes': {
            'install.txt': hashlib.sha256(install_raw).hexdigest(),
            'native.txt': hashlib.sha256(raw).hexdigest()}}
        if lines[0].startswith('N2_ERROR='):
            error = lines[0].split('=', 1)[1]
            if error not in ERRORS or install[3] != 'snapshot_result=1':
                raise ValueError('unknown/inconsistent native error')
            item['native_error'] = error
        else:
            if install[3] != 'snapshot_result=0':
                raise ValueError('successful frame paired with error result')
            native = fields(lines[0], NATIVE, {'observer': 'N2'})
            if (native['format'] != 1 or native['bytes'] != 128 or native['sequence'] & 1
                    or native['fault'] not in (0, 1) or native['enabled'] not in (0, 1)
                    or native['instance_nsec'] >= 1000000000):
                raise ValueError('native schema')
            if native['jpeg_signatures'] + native['png_signatures'] + native['other_signatures'] > native['completed']:
                raise ValueError('more classified images than completions')
            instance = (native['instance_sec'], native['instance_nsec'])
            prior = instances.get(instance)
            if prior and any(native[k] < prior[k] for k in COUNTERS):
                raise ValueError('same-instance counter regression')
            instances[instance] = native
            item['native'] = native
        n1 = folder / 'n1.txt'
        if n1.exists():
            n1raw, n1lines = bounded(n1, 4096)
            if len(n1lines) != 1:
                raise ValueError('N1 record count')
            text = fields(n1lines[0], N1_FIELDS, {'build': N1_BUILD}, ('context',))
            if (text['format'] != 1 or text['text_output'] != 1
                    or text['context'] not in (-1, 0, 1) or text['connected'] not in (0, 1)):
                raise ValueError('N1 schema')
            if prior_n1 and (text['epoch'] < prior_n1['epoch']
                            or any(text[k] < prior_n1[k] for k in N1_COUNTERS)):
                raise ValueError('N1 process restart/regression; split the run')
            prior_n1 = text
            item['n1'] = text
            item['hashes']['n1.txt'] = hashlib.sha256(n1raw).hexdigest()
        snapshots.append(item)
    totals = {k: sum(i[k] for i in instances.values()) for k in COUNTERS}
    valid = [s['native'] for s in snapshots if 'native' in s]
    n1s = [s['n1'] for s in snapshots if 'n1' in s]
    return {'build': N2_BUILD, 'snapshots': snapshots,
            'native_instances': [{'instance_sec': key[0], 'instance_nsec': key[1],
                                  'last_counters': value} for key, value in instances.items()],
            'retained_instance_totals': totals,
            'native_frame_count': len(valid),
            'native_error_snapshots': [
                {'snapshot': s['snapshot'], 'error': s['native_error']}
                for s in snapshots if 'native_error' in s],
            'native_frame_faults_zero': all(s['fault'] == 0 for s in valid) if valid else None,
            'sampled_last_sizes': [s['last_size'] for s in valid],
            'n1_failure_counters_zero': all(s[k] == 0 for s in n1s
                for k in ('failures', 'attach_failures', 'io_failures')) if n1s else None,
            'n1_cover_callbacks_observed': any(s['covers'] for s in n1s),
            'completed_image_input_observed': totals['completed'] > 0,
            'jpeg_signature_input_observed': totals['jpeg_signatures'] > 0,
            'independent_installed_driver_hash': False,
            'images_decoded_or_displayed': False,
            'limitations': [
                'Cumulative snapshots are counted once per native allocation instance.',
                'Last-size samples do not preserve the size of every completed transfer.',
                'New native allocation and DSI epoch do not independently identify a physical phone reconnect.',
                'Image headers establish input presence, not decoder validity, orientation, track matching or cluster display.',
                'Capture files do not identify audio apps or map every snapshot to a test step.',
                'No image bytes, track text or device identifiers are retained in this review.']}


def diagnostics(root):
    records = []
    for folder in sorted(root.glob('cpmap-diag-*')):
        record = {'capture': folder.name, 'hashes': {}}
        for name, keys in (
            ('ramdisk/carplay-route-guidance/status.txt',
             {'status', 'polls', 'valid', 'invalid', 'sequence', 'bytes', 'reason'}),
            ('ramdisk/carplay-route-guidance/adapter-status.txt',
             {'build', 'run', 'mode', 'context', 'ticks', 'proposals', 'writes', 'releases', 'failures', 'records', 'error'})):
            path = folder / name
            if not path.exists():
                continue
            raw, lines = bounded(path, 4096)
            if len(lines) != 1 or not lines[0].startswith('RG '):
                raise ValueError('guidance diagnostic record')
            values = dict(token.split('=', 1) for token in lines[0][3:].split())
            if values.keys() != keys:
                raise ValueError('guidance diagnostic keys')
            for key, value in list(values.items()):
                if key == 'status':
                    if value not in ('unavailable', 'stale', 'live', 'ended', 'disabled', 'starting'):
                        raise ValueError('guidance state')
                elif key == 'build':
                    if not re.fullmatch('[0-9a-f]{16}', value):
                        raise ValueError('guidance build')
                else:
                    if not re.fullmatch(r'\d+', value):
                        raise ValueError('guidance counter')
                    values[key] = int(value)
            record[Path(name).name] = values
            record['hashes'][name] = hashlib.sha256(raw).hexdigest()
        supervisor = folder / 'ramdisk/carplay-cluster-supervisor.log'
        if supervisor.exists():
            raw = supervisor.read_bytes()
            if len(raw) > 1024 * 1024:
                raise ValueError('supervisor log bound')
            # Export event names/counts only, never log values (which include PIDs).
            events = re.findall(rb'event=([a-z-]+) ', raw)
            counts = {}
            for event in ('stream-timeout-fallback', 'bridge-started', 'bridge-stopped',
                          'state-oem-active', 'state-carplay-active'):
                counts[event] = events.count(event.encode())
            record['supervisor_events'] = counts
            record['hashes']['ramdisk/carplay-cluster-supervisor.log'] = hashlib.sha256(raw).hexdigest()
        record['selected_crash_marker_counts'] = {}
        for name in ('sloginfo.txt', 'ramdisk/carplay-maps-session.log'):
            path = folder / name
            if not path.exists():
                continue
            raw = path.read_bytes()
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError('diagnostic log bound')
            record['hashes'][name] = hashlib.sha256(raw).hexdigest()
            record['selected_crash_marker_counts'][name] = {
                pattern: len(re.findall(re.escape(pattern.encode()), raw, re.I))
                for pattern in ('SIGSEGV', 'SIGILL', 'SIGBUS', 'segmentation fault',
                                'Unhandled exception', 'heap corruption')}
        summary = folder / 'summary.txt'
        if summary.exists():
            raw, _ = bounded(summary, 16384)
            record['hashes']['summary.txt'] = hashlib.sha256(raw).hexdigest()
            record['collector_date_command_unavailable'] = b'date: cannot execute' in raw
        records.append(record)
    return records


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = review(a.capture); result['diagnostics'] = diagnostics(a.capture)
    result['reviewer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ('snapshots', 'diagnostics', 'native_instances', 'limitations')}))
