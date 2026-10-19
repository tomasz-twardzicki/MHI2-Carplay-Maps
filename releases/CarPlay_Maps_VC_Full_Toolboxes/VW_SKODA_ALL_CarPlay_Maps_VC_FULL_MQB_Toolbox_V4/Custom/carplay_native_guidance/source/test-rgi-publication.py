#!/usr/bin/env python3
"""Synthetic publication-reader tests. No firmware or private log dependency."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import rgi_publication as pub
from rgi_decode import DecodeError


def tlv(n, value):
    return struct.pack('>HH', len(value) + 4, n) + value


def route(state=1):
    return tlv(0, b'\0\x10') + tlv(1, bytes([state])) + tlv(13, b'\0\x02')


def maneuver():
    return tlv(0, b'\0\x10') + tlv(1, b'\0\x02') + tlv(3, b'\x02')


def snapshot(events=(), session=1, last=None, enabled=1, fault=0, birth=(123, 456789)):
    if last is None: last = len(events)
    b = bytearray(pub.SIZE)
    struct.pack_into('<16I', b, 0, int.from_bytes(b'RGI1', 'little'), 1, pub.SIZE,
                     2, session, last, len(events), fault, 0, enabled, *birth, 0, 0, 0, 0)
    for seq, mid, payload in events:
        at = 64 + ((seq - 1) & 15) * pub.STRIDE
        struct.pack_into('<IHHII', b, at, seq, mid, len(payload), session, 0)
        b[at + 16:at + 16 + len(payload)] = payload
    return b


class PublicationReaderTests(unittest.TestCase):
    def test_decode_ordered_events_even_when_ring_wraps(self):
        blob = snapshot([(n, 0x5201, route()) for n in range(10, 26)], last=25)
        self.assertEqual([n for n, _ in pub.decode_snapshot(blob).events], list(range(10, 26)))

    def test_polling_deduplicates_and_resolves_current_maneuver(self):
        c = pub.Consumer()
        blob = snapshot([(1, 0x5201, route()), (2, 0x5202, maneuver())])
        result = c.consume(blob)
        self.assertEqual(result['applied'], 2)
        self.assertEqual(result['state']['current_maneuver']['type'], 2)
        self.assertEqual(c.consume(blob)['applied'], 0)

    def test_message_trace_retains_transient_head_then_startup_reset(self):
        def state_only(state):
            return tlv(0, b'\0\x10') + tlv(1, bytes([state]))
        blob = snapshot([(1, 0x5201, route()), (2, 0x5202, maneuver()),
                         (3, 0x5201, state_only(0)), (4, 0x5201, state_only(3)),
                         (5, 0x5202, maneuver()), (6, 0x5201, state_only(1))])
        consumer = pub.Consumer(); events = []
        result = consumer.consume(blob, emit=events.append)
        self.assertEqual([e['sequence'] for e in events], list(range(1, 7)))
        self.assertEqual([e['state']['current_maneuver_status'] for e in events],
                         ['head_not_cached', 'head_cached', 'inactive', 'inactive',
                          'inactive', 'order_absent'])
        self.assertIsNone(result['state']['current_maneuver'])
        consumer.consume(blob, emit=events.append)
        self.assertEqual(len(events), 6)
        events[1]['state']['current_maneuver']['type'] = 99
        self.assertEqual(consumer.cache.maneuvers[2]['type'], 2)

    def test_message_trace_validates_entire_window_before_emitting(self):
        blob = snapshot([(1, 0x5201, route()), (2, 0x5202, maneuver())])
        blob[64 + pub.STRIDE + 16:64 + pub.STRIDE + 18] = b'\0\x03'
        events = []; consumer = pub.Consumer()
        with self.assertRaises(DecodeError): consumer.consume(blob, emit=events.append)
        self.assertEqual(events, [])
        self.assertFalse(consumer.cache.snapshot()['active'])

    def test_new_session_or_new_instance_clears_reused_indices(self):
        for kwargs in ({'session': 2}, {'birth': (124, 456789)}):
            c = pub.Consumer()
            c.consume(snapshot([(1, 0x5201, route()), (2, 0x5202, maneuver())]))
            result = c.consume(snapshot([(1, 0x5201, route())], **kwargs))
            self.assertIsNone(result['state']['current_maneuver'])

    def test_window_gap_invalidates_old_maneuver_and_reports_missing_events(self):
        c = pub.Consumer()
        c.consume(snapshot([(1, 0x5201, route()), (2, 0x5202, maneuver())]))
        result = c.consume(snapshot([(n, 0x5201, route()) for n in range(10, 26)], last=25))
        self.assertEqual(result['missing_before_window'], 7)
        self.assertIsNone(result['state']['current_maneuver'])

    def test_late_first_reader_does_not_pretend_full_history_received(self):
        result = pub.Consumer().consume(snapshot([(n, 0x5201, route()) for n in range(10, 26)], last=25))
        self.assertEqual(result['missing_before_window'], 9)

    def test_stop_disabled_fault_and_disconnect_clear_stale_data(self):
        for reason in ('stop', 'disabled', 'fault', 'disconnect'):
            c = pub.Consumer()
            c.consume(snapshot([(1, 0x5201, route()), (2, 0x5202, maneuver())]))
            if reason == 'stop':
                state = c.consume(snapshot([(1, 0x5201, route()), (2, 0x5202, maneuver()),
                                            (3, 0x5201, route(0))]))['state']
            elif reason == 'disabled': state = c.consume(snapshot(enabled=0))['state']
            elif reason == 'fault':
                state = c.consume(snapshot([(1, 0x5201, route()), (2, 0x5202, maneuver())], fault=1))['state']
            else:
                c.disconnected(); state = c.cache.snapshot()
            self.assertFalse(state['active'])
            self.assertIsNone(state['current_maneuver'])
            self.assertFalse(state['cached_indices'])

    def test_torn_unsupported_and_short_headers_rejected(self):
        for offset, value in ((0, 0), (4, 2), (8, 0), (12, 3), (24, 17), (32, 1),
                              (36, 2), (44, 1_000_000_000), (48, 1)):
            data = snapshot(); struct.pack_into('<I', data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(DecodeError): pub.decode_snapshot(data)
        for data in (b'', snapshot()[:-1], snapshot() + b'X'):
            with self.assertRaises(DecodeError): pub.decode_snapshot(data)

    def test_slot_sequence_session_size_id_and_tlv_corruption_rejected_atomically(self):
        c = pub.Consumer()
        c.consume(snapshot([(1, 0x5201, route()), (2, 0x5202, maneuver())]))
        for offset, fmt, value in ((64, '<I', 99), (72, '<I', 99), (70, '<H', 2049),
                                   (68, '<H', 0x5205), (80, '>H', 3)):
            blob = snapshot([(1, 0x5201, route())])
            struct.pack_into(fmt, blob, offset, value)
            with self.assertRaises(DecodeError): c.consume(blob)
            self.assertFalse(c.cache.snapshot()['active'])

    def test_sequence_regression_never_replays_old_route(self):
        c = pub.Consumer()
        c.consume(snapshot([(1, 0x5201, route()), (2, 0x5202, maneuver())]))
        with self.assertRaises(DecodeError): c.consume(snapshot([(1, 0x5201, route())]))
        self.assertFalse(c.cache.snapshot()['active'])

    def test_private_fields_omitted_by_default(self):
        body = route() + tlv(4, b'PRIVATE_DESTINATION\0')
        blob = snapshot([(1, 0x5201, body)])
        self.assertNotIn('PRIVATE', json.dumps(pub.Consumer().consume(blob)))
        self.assertIn('PRIVATE', json.dumps(pub.Consumer().consume(blob, include_private=True)))

    def test_cli_expect_publishing_rejects_b3_initialized_but_disabled_header(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / 'snapshot.bin'
            path.write_bytes(snapshot(enabled=0, session=0))
            cmd = [sys.executable, pub.__file__, str(path)]
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            result = subprocess.run(cmd + ['--expect-publishing'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('publication has not started', result.stdout)
            path.write_bytes(snapshot([(1, 0x5201, route())]))
            self.assertEqual(subprocess.run(cmd + ['--expect-publishing'], capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
