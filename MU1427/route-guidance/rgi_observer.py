#!/usr/bin/env python3
"""Replay a C4 compact diagnostic journal on the computer; no QNX dependency.

SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys

from rgi_decode import DecodeError
from rgi_publication import Consumer, SIZE, STRIDE, decode_snapshot

LIMIT = 8 * 1024 * 1024
SNAPSHOT, INVALIDATE, STALE, HEARTBEAT, END = range(1, 6)


def expand_snapshot(payload):
    if len(payload) < 64:
        raise DecodeError('short compact snapshot header')
    words = struct.unpack_from('<16I', payload)
    sequence, count = words[5:7]
    if count != min(sequence, 16):
        raise DecodeError('invalid compact snapshot history bounds')
    snapshot = bytearray(SIZE)
    snapshot[:64] = payload[:64]
    offset = 64
    for seq in range(sequence - count + 1, sequence + 1):
        if offset + 16 > len(payload):
            raise DecodeError('short compact event header')
        length = struct.unpack_from('<H', payload, offset + 6)[0]
        if length > 2048 or offset + 16 + length > len(payload):
            raise DecodeError('invalid compact event length')
        slot = 64 + ((seq - 1) & 15) * STRIDE
        snapshot[slot:slot + 16 + length] = payload[offset:offset + 16 + length]
        offset += 16 + length
    if offset != len(payload):
        raise DecodeError('unexpected compact snapshot suffix')
    return bytes(snapshot)


class Coverage:
    """Journal-wide sequence coverage independent of consumer cache resets.

    Keep only the last window per publication to check overlapping identities;
    never allocate a list using a sequence/count supplied by the producer.
    """
    def __init__(self):
        self.publications = {}
        self.recorded = Counter()
        self.gap_windows = 0

    def observe(self, data):
        snapshot = decode_snapshot(data)
        identity = (snapshot.instance, snapshot.session)
        previous, retained = self.publications.get(identity, (0, {}))
        if snapshot.sequence < previous:
            raise DecodeError('observer publication sequence regressed')
        window = {}
        for seq, message in snapshot.events:
            offset = 64 + ((seq - 1) & 15) * STRIDE
            length = struct.unpack_from('<H', data, offset + 6)[0]
            window[seq] = data[offset:offset + 16 + length]
            if seq in retained and retained[seq] != window[seq]:
                raise DecodeError('observer overlapping event changed')
        new = [(seq, message) for seq, message in snapshot.events if seq > previous]
        missing = snapshot.sequence - previous - len(new)
        self.gap_windows += missing > 0
        self.recorded.update(f'0x{message.identifier:04x}' for _, message in new)
        self.publications[identity] = (snapshot.sequence, window)

    def summary(self):
        published = sum(sequence for sequence, _ in self.publications.values())
        recorded = sum(self.recorded.values())
        return {'publications': len(self.publications), 'published_events': published,
                'recorded_events': recorded, 'unrecorded_events': published - recorded,
                'gap_windows': self.gap_windows, 'recorded_by_id': dict(self.recorded)}


def replay(stream, emit=None, include_private=False, *, emit_message=None):
    header = stream.read(16)
    if len(header) != 16:
        raise DecodeError('short observer journal header')
    magic, version, size, interval = struct.unpack('<4sIII', header)
    if (magic, version, size) != (b'RGJ1', 1, SIZE) or not 1 <= interval <= 1000:
        raise DecodeError('unsupported observer journal')
    consumer = Consumer()
    coverage = Coverage()
    selection = Counter()
    counts = Counter()
    messages = Counter()
    last_observed = None
    elapsed = 0
    total = 16
    missing = 0
    end_reason = None
    snapshots = 0
    publishing = faults = active = resolved = stopped = 0
    max_sequence = 0
    # Errors never echo file paths, private route strings or binary input.
    while True:
        record = stream.read(32)
        if not record:
            break
        if len(record) != 32:
            raise DecodeError('short observer record header')
        kind, at, length, detail, *reserved = struct.unpack('<8I', record)
        total += 32 + length
        if total > LIMIT or length > SIZE or any(reserved) or at < elapsed or at > 603000:
            raise DecodeError('invalid observer record bounds/time/reserved fields')
        if end_reason is not None:
            raise DecodeError('observer record after end')
        elapsed = at
        payload = stream.read(length)
        if len(payload) != length:
            raise DecodeError('short observer record payload')
        counts[kind] += 1
        event = {'kind': 'observer', 'elapsed_ms': at}
        if kind == SNAPSHOT:
            if detail:
                raise DecodeError('unexpected snapshot detail')
            blob = expand_snapshot(payload)
            coverage.observe(blob)

            def message_event(message):
                selection[message['state']['current_maneuver_status']] += 1
                if emit_message is not None:
                    emit_message({**message, 'kind': 'observer_message', 'elapsed_ms': at})

            result = consumer.consume(blob, include_private, emit=message_event)
            snapshots += 1
            publishing += bool(result['enabled'] and not result['fault'] and result['sequence'])
            faults += bool(result['fault'])
            active += bool(result['state']['active'])
            resolved += result['state']['current_maneuver'] is not None
            stopped += result['state']['route'].get('route_state') == 0
            max_sequence = max(max_sequence, result['sequence'])
            missing += result['missing_before_window']
            # Consumer validates every event before applying any state change.
            event.update(event='snapshot', publication=result)
            last_observed = result['state']
            messages['applied'] += result['applied']
            messages['unapplied'] += result['unapplied']
        elif kind == INVALIDATE:
            if detail not in range(1, 7) or length not in (0, 4):
                raise DecodeError('invalid observer invalidation')
            consumer.disconnected()
            event.update(event='unavailable', reason=detail,
                         source_errno=struct.unpack('<I', payload)[0] if payload else None)
        elif kind == STALE:
            if length or detail != 5000:
                raise DecodeError('invalid observer stale deadline')
            consumer.disconnected()
            event.update(event='stale', deadline_ms=detail)
        elif kind == HEARTBEAT:
            if length:
                raise DecodeError('unexpected heartbeat payload')
            event.update(event='heartbeat', sequence=detail)
        elif kind == END:
            if length or detail not in range(5):
                raise DecodeError('invalid observer termination')
            end_reason = detail
            consumer.disconnected()
            event.update(event='end', reason=detail)
        else:
            raise DecodeError('unknown observer record kind')
        if kind != SNAPSHOT:
            event['state'] = consumer.cache.snapshot(include_private)
        if emit is not None:
            emit(event)
    if end_reason is None:
        raise DecodeError('observer journal has no end record (incomplete capture)')
    return {'kind': 'summary', 'poll_interval_ms': interval,
            'elapsed_ms': elapsed, 'snapshots': snapshots,
            'publishing_snapshots': publishing, 'producer_fault_snapshots': faults,
            'active_snapshots': active, 'resolved_maneuver_snapshots': resolved,
            'stopped_snapshots': stopped, 'max_sequence': max_sequence,
            'invalidations': counts[INVALIDATE], 'stale_deadlines': counts[STALE],
            'heartbeats': counts[HEARTBEAT], 'missing_before_windows': missing,
            'coverage': coverage.summary(), 'message_selection_states': dict(selection),
            'messages': dict(messages), 'end_reason': end_reason,
            'last_observed': last_observed,
            'final': consumer.cache.snapshot(include_private)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('journal', type=Path)
    parser.add_argument('--events', action='store_true')
    parser.add_argument('--messages', action='store_true',
                        help='emit state after each consumer-applied event, including replay after resets')
    parser.add_argument('--require-complete', action='store_true',
                        help='also fail if any published sequence is absent from this journal')
    parser.add_argument('--include-private', action='store_true')
    args = parser.parse_args()
    try:
        with args.journal.open('rb') as f:
            result = replay(f, emit=(lambda e: print(json.dumps(e))) if args.events else None,
                            include_private=args.include_private,
                            emit_message=(lambda e: print(json.dumps(e))) if args.messages else None)
    except (OSError, DecodeError) as error:
        print(json.dumps({'error': str(error) if isinstance(error, DecodeError)
                          else 'observer journal read failed'}))
        return 1
    print(json.dumps(result))
    return int(result['end_reason'] in (2, 3, 4) or not result['publishing_snapshots']
               or result['producer_fault_snapshots'] > 0
               or args.require_complete and result['coverage']['unrecorded_events'] > 0)


if __name__ == '__main__':
    sys.exit(main())
