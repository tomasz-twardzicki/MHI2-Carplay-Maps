#!/usr/bin/env python3
"""Decode B3's fixed-size rgi-events virtual-file snapshot on the computer.

SPDX-License-Identifier: GPL-3.0-or-later
No QNX dependency. This models the reader side of a bounded memory handoff;
it does not write PPS, run a background process or render cockpit graphics.
"""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import struct
import sys

from rgi_decode import DecodeError, GuidanceCache, Message, decode_payload

SIZE = 0x8140
SLOTS = 16
STRIDE = 2064
PAYLOAD_LIMIT = 2048


@dataclass(frozen=True)
class Snapshot:
    instance: tuple[int, int]
    session: int
    sequence: int
    enabled: bool
    fault: bool
    events: tuple[tuple[int, Message], ...]


def decode_snapshot(data: bytes) -> Snapshot:
    """Validate the entire snapshot before allowing any state changes."""
    if len(data) != SIZE:
        raise DecodeError("incorrect publication snapshot size")
    words = struct.unpack_from('<16I', data)
    magic, version, size, epoch, session, sequence, count, fault, lock, enabled, sec, nsec = words[:12]
    if magic != int.from_bytes(b'RGI1', 'little') or version != 1 or size != SIZE:
        raise DecodeError("unsupported publication header")
    if epoch & 1 or lock or count > SLOTS or enabled not in (0, 1) or fault not in (0, 1):
        raise DecodeError("inconsistent publication snapshot")
    if nsec >= 1_000_000_000 or any(words[12:]):
        raise DecodeError("invalid publication instance/reserved fields")
    if count != min(sequence, SLOTS) or (not enabled and (count or sequence)):
        raise DecodeError("invalid publication history bounds")
    if enabled and not session:
        raise DecodeError("enabled publication without a session")
    events = []
    for seq in range(sequence - count + 1, sequence + 1):
        at = 64 + ((seq - 1) & 15) * STRIDE
        stored_seq, mid, length, stored_session, reserved = struct.unpack_from('<IHHII', data, at)
        if stored_seq != seq or stored_session != session or length > PAYLOAD_LIMIT or reserved:
            raise DecodeError("inconsistent publication event")
        events.append((seq, decode_payload(mid, data[at + 16:at + 16 + length])))
    return Snapshot((sec, nsec), session, sequence, bool(enabled), bool(fault), tuple(events))


class Consumer:
    """A polling reader with sequence-gap, session and disconnect invalidation.

    A future runtime reader also needs an external monotonic stale-data deadline
    and transport-removal handling. There are no timestamps on individual events.
    """
    def __init__(self):
        self.cache = GuidanceCache()
        self.identity = None
        self.last_sequence = 0
        self.enabled = False

    def consume(self, data: bytes, include_private=False, *, emit=None):
        """Apply a validated window; optionally emit state after each new event.

        The whole window is decoded before any callback. Overlapping events
        are emitted only when applied again by this consumer (including after
        a reset); this is not a journal-wide unique-event iterator.
        """
        try:
            snapshot = decode_snapshot(data)
        except DecodeError:
            self.cache.reset_session()
            self.identity = None
            self.last_sequence = 0
            self.enabled = False
            raise
        identity = (snapshot.instance, snapshot.session)
        changed = identity != self.identity
        if changed:
            self.cache.reset_session()
            self.last_sequence = 0
        elif snapshot.enabled and snapshot.sequence < self.last_sequence:
            self.cache.reset_session()
            raise DecodeError("publication sequence regressed within a session")
        self.identity = identity
        first = snapshot.events[0][0] if snapshot.events else 0
        gap = max(0, first - self.last_sequence - 1) if first else 0
        if gap:
            self.cache.reset_session()
        applied = 0
        unapplied = 0
        if snapshot.fault or not snapshot.enabled:
            if self.enabled or changed:
                self.cache.reset_session()
        else:
            for seq, message in snapshot.events:
                if seq > self.last_sequence:
                    accepted = self.cache.apply(message)
                    if accepted: applied += 1
                    else: unapplied += 1
                    if emit is not None:
                        emit({"kind": "publication_message",
                              "instance": list(snapshot.instance),
                              "session": snapshot.session, "sequence": seq,
                              "id": f"0x{message.identifier:04x}",
                              "present": sorted(message.fields),
                              "unknown_ids": [item.identifier for item in message.unknown],
                              "applied": accepted,
                              "state": self.cache.snapshot(include_private)})
        self.last_sequence = snapshot.sequence
        self.enabled = snapshot.enabled and not snapshot.fault
        return {"kind": "publication", "instance": list(snapshot.instance),
                "session": snapshot.session, "sequence": snapshot.sequence,
                "enabled": snapshot.enabled, "fault": snapshot.fault,
                "retained": len(snapshot.events), "missing_before_window": gap,
                "applied": applied, "unapplied": unapplied,
                "state": self.cache.snapshot(include_private)}

    def disconnected(self):
        """Use when the device disappears, read fails, or a runtime deadline expires."""
        self.cache.reset_session()
        self.identity = None
        self.last_sequence = 0
        self.enabled = False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshots', type=Path, nargs='+', help='snapshot files in acquisition order')
    parser.add_argument('--include-private', action='store_true')
    parser.add_argument('--expect-publishing', action='store_true',
                        help='fail if the snapshot has no enabled session/events (use for active-route captures)')
    args = parser.parse_args()
    consumer = Consumer()
    failed = False
    for number, path in enumerate(args.snapshots, 1):
        try:
            # Bounded file read: an oversized or growing input is rejected.
            with path.open('rb') as f: data = f.read(SIZE + 1)
            result = consumer.consume(data, args.include_private)
        except (OSError, DecodeError) as error:
            consumer.disconnected()
            # Never echo raw paths, payload text or bytes in diagnostic output.
            print(json.dumps({"input": number, "error": str(error) if isinstance(error, DecodeError)
                              else "snapshot read failed"}))
            failed = True
            continue
        if args.expect_publishing and not (result['enabled'] and result['session'] > 0 and result['sequence'] > 0):
            result['expectation_error'] = 'publication has not started'
            failed = True
        print(json.dumps(result, ensure_ascii=False))
        failed |= result['fault']
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
