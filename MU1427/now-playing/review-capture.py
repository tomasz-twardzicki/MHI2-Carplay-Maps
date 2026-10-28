#!/usr/bin/env python3
"""Review bounded N0 status exports, without copying private captures into Git.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

COUNTERS = ('tracks', 'valid_tracks', 'titles', 'artists', 'albums', 'playback',
            'valid_playback', 'positions', 'valid_positions', 'covers', 'valid_covers',
            'cover_urls', 'cover_ids', 'exceptions', 'clear_failures', 'io_failures')
FIELDS = {'format', 'build', 'observer_only', 'epoch', 'attached', 'playback_state',
          'writes', 'attach_failures', *COUNTERS}


def review(root, build):
    paths = sorted(root.glob('cpmap-audio-N0-*/status.txt'))
    if not paths:
        raise ValueError('no N0 snapshots found')
    snapshots, epochs = [], {}
    last_writes = -1
    for path in paths:
        raw = path.read_bytes()
        if not 0 < len(raw) <= 8192:
            raise ValueError('export size bound')
        lines = raw.decode('ascii').splitlines()
        if lines[:2] != ['N0 observation only; no cluster text/artwork output', build]:
            raise ValueError('unexpected installed build or export envelope')
        item = {'snapshot': path.parent.name, 'sha256': hashlib.sha256(raw).hexdigest()}
        if lines[2:] == ['N0_STATUS_NOT_AVAILABLE_YET']:
            item['runtime_status_available'] = False
            snapshots.append(item)
            continue
        if len(lines) != 4:
            raise ValueError('unexpected status record count')
        fields = {}
        for token in ' '.join(lines[2:]).split():
            key, value = token.split('=', 1)
            if key not in FIELDS or key in fields:
                raise ValueError('unknown/duplicate status field')
            if key == 'build':
                if value != build:
                    raise ValueError('runtime build mismatch')
            else:
                if not re.fullmatch(r'-?\d+', value):
                    raise ValueError('non-integer status field')
                value = int(value)
                if value < 0 and not (key == 'playback_state' and value == -1):
                    raise ValueError('negative counter')
            fields[key] = value
        if set(fields) != FIELDS or fields['format'] != 1 or fields['observer_only'] != 1:
            raise ValueError('status schema mismatch')
        if fields['attached'] not in (0, 1) or fields['playback_state'] not in (-1, 0, 1, 2, 3, 4):
            raise ValueError('invalid state ordinal')
        if fields['writes'] <= last_writes:
            raise ValueError('writer restart or unordered snapshots; review separately')
        last_writes = fields['writes']
        epoch = fields['epoch']
        previous = epochs.get(epoch)
        if previous and any(fields[k] < previous[k] for k in COUNTERS):
            raise ValueError('same-epoch counter regression')
        epochs[epoch] = fields
        item.update(runtime_status_available=True, fields=fields)
        snapshots.append(item)
    totals = {key: sum(e[key] for e in epochs.values()) for key in COUNTERS}
    errors_zero = all(e[key] == 0 for e in epochs.values()
                      for key in ('exceptions', 'clear_failures', 'io_failures', 'attach_failures'))
    states = [s['fields']['playback_state'] for s in snapshots if s.get('runtime_status_available')]
    return {'installed_build': build, 'snapshots': snapshots, 'observed_epochs': sorted(epochs),
            'retained_epoch_totals': totals, 'reported_error_counters_zero': errors_zero,
            'pause_then_play_observed': any(a == 2 and b == 1 for a, b in zip(states, states[1:])),
            'detach_then_new_epoch_observed': any(
                a['attached'] == 0 and b['attached'] == 1 and b['epoch'] > a['epoch']
                for a, b in zip([s['fields'] for s in snapshots if s.get('runtime_status_available')],
                                [s['fields'] for s in snapshots if s.get('runtime_status_available')][1:])),
            'cover_callback_observed': totals['covers'] > 0,
            'limitations': ['Snapshots are sampled counters, not a lossless event trace.',
                            'Build markers do not independently fingerprint the installed JAR.',
                            'Snapshots do not identify which audio app was active.',
                            'No track strings, image bytes or exact timestamps are exported.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path)
    p.add_argument('--build', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = review(a.capture, a.build)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'snapshots'}))


if __name__ == '__main__':
    main()
