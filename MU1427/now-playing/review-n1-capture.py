#!/usr/bin/env python3
"""Review counter-only N1 exports without copying private capture files.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

COUNTERS = ('ticks', 'fills', 'accepted', 'rejected', 'failures',
            'attach_failures', 'tracks', 'covers', 'io_failures', 'writes')
FIELDS = {'format', 'build', 'text_output', 'epoch', 'connected', 'context', *COUNTERS}


def review(root, build):
    paths = sorted(root.glob('cpmap-audio-N1-*/status.txt'))
    if not paths:
        raise ValueError('no N1 snapshots found')
    snapshots, previous = [], None
    for path in paths:
        raw = path.read_bytes()
        if not 0 < len(raw) <= 8192:
            raise ValueError('export size bound')
        lines = raw.decode('ascii').splitlines()
        if lines[:2] != ['N1 native title/artist/album text; no cover artwork', build]:
            raise ValueError('unexpected installed build or export envelope')
        item = {'snapshot': path.parent.name, 'sha256': hashlib.sha256(raw).hexdigest()}
        if lines[2:] == ['N1_STATUS_NOT_AVAILABLE_YET']:
            item['runtime_status_available'] = False
            snapshots.append(item)
            continue
        if len(lines) != 3:
            raise ValueError('unexpected status record count')
        fields = {}
        for token in lines[2].split():
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
                if value < 0 and not (key == 'context' and value == -1):
                    raise ValueError('negative counter')
            fields[key] = value
        if (set(fields) != FIELDS or fields['format'] != 1 or fields['text_output'] != 1
                or fields['connected'] not in (0, 1) or fields['context'] not in (-1, 0, 1)):
            raise ValueError('status schema mismatch')
        # N1 counters are process-wide, unlike N0's per-attachment counters.
        if previous and (fields['epoch'] < previous['epoch']
                         or fields['writes'] <= previous['writes']
                         or any(fields[k] < previous[k] for k in COUNTERS)):
            raise ValueError('restart/regression or unordered snapshots; review separately')
        previous = fields
        item.update(runtime_status_available=True, fields=fields)
        snapshots.append(item)
    runtime = [s['fields'] for s in snapshots if s.get('runtime_status_available')]
    return {'installed_build': build, 'snapshots': snapshots,
            'observed_epochs': sorted({s['epoch'] for s in runtime}),
            'last_process_counters': {k: runtime[-1][k] for k in COUNTERS} if runtime else None,
            'reported_failure_counters_zero': all(
                s[k] == 0 for s in runtime for k in ('failures', 'attach_failures', 'io_failures')) if runtime else None,
            'cover_callback_observed': any(s['covers'] for s in runtime),
            'false_property_returns_observed': any(s['rejected'] for s in runtime),
            'limitations': [
                'N1 counters are process-wide and must not be summed across sampled snapshots.',
                'accepted/rejected count true/false PropertyListener returns, not cluster acknowledgments or transport errors.',
                'The factory cached listener can return false for unchanged property values.',
                'One snapshot cannot establish source transitions, disconnect/reconnect ordering or rejection recovery.',
                'Build markers do not independently fingerprint the installed JAR.',
                'No text values, app identities, images or exact timestamps are exported.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--build', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = review(args.capture, args.build)
    result['reviewer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('snapshots', 'limitations')}))


if __name__ == '__main__':
    main()
