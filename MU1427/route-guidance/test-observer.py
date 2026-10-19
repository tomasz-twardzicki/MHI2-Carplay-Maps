#!/usr/bin/env python3
"""C4 journal and real-process tests. Synthetic data only by default."""
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import unittest

import rgi_observer as observer
from rgi_decode import DecodeError
from rgi_publication import Consumer, decode_snapshot

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('publication_tests', HERE / 'test-rgi-publication.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def compact(blob):
    snap = decode_snapshot(blob)
    result = bytes(blob[:64])
    for seq, _ in snap.events:
        at = 64 + ((seq - 1) & 15) * 2064
        length = struct.unpack_from('<H', blob, at + 6)[0]
        result += bytes(blob[at:at + 16 + length])
    return result


def record(kind=1, at=0, payload=b'', detail=0):
    return struct.pack('<8I', kind, at, len(payload), detail, 0, 0, 0, 0) + payload


def journal(*records):
    return struct.pack('<4sIII', b'RGJ1', 1, 33088, 100) + b''.join(records)


def guiding():
    return fixtures.snapshot([(1, 0x5201, fixtures.route()),
                              (2, 0x5202, fixtures.maneuver())])


class JournalTests(unittest.TestCase):
    def replay(self, *records):
        events = []
        result = observer.replay(io.BytesIO(journal(*records)), emit=events.append)
        return result, events

    def test_round_trip_wrapped_snapshot(self):
        blob = fixtures.snapshot([(i, 0x5201, fixtures.route()) for i in range(10, 26)], last=25)
        self.assertEqual(decode_snapshot(observer.expand_snapshot(compact(blob))), decode_snapshot(blob))

    def test_maneuver_available_then_stop_clears_it(self):
        stopped = fixtures.snapshot([(1, 0x5201, fixtures.route()),
                                    (2, 0x5202, fixtures.maneuver()),
                                    (3, 0x5201, fixtures.route(0))])
        result, events = self.replay(record(payload=compact(guiding())),
                                     record(at=100, payload=compact(stopped)), record(5, 200))
        self.assertEqual(events[0]['publication']['state']['current_maneuver']['type'], 2)
        self.assertFalse(events[1]['publication']['state']['active'])
        self.assertEqual(result['messages']['applied'], 3)
        self.assertFalse(result['final']['active'])

    def test_gap_clears_maneuver(self):
        late = fixtures.snapshot([(i, 0x5201, fixtures.route()) for i in range(10, 26)], last=25)
        result, events = self.replay(record(payload=compact(guiding())),
                                     record(at=100, payload=compact(late)), record(5, 200))
        self.assertEqual(result['missing_before_windows'], 7)
        self.assertIsNone(events[1]['publication']['state']['current_maneuver'])

    def test_staleness_invalidates_without_reapplying_heartbeat(self):
        result, events = self.replay(record(payload=compact(guiding())),
                                     record(3, 5000, detail=5000), record(4, 5100, detail=2),
                                     record(5, 5200))
        self.assertEqual(result['stale_deadlines'], 1)
        self.assertFalse(events[1]['state']['active'])
        self.assertFalse(events[2]['state']['active'])

    def test_unique_coverage_survives_stale_replay_without_inventing_loss(self):
        first = fixtures.snapshot([(i, 0x5201, fixtures.route()) for i in range(5, 21)], last=20)
        later = fixtures.snapshot([(i, 0x5201, fixtures.route()) for i in range(10, 26)], last=25)
        result, _ = self.replay(record(payload=compact(first)), record(3, 5000, detail=5000),
                                record(at=5100, payload=compact(later)), record(5, 5200))
        self.assertEqual(result['missing_before_windows'], 13)
        self.assertEqual(result['messages']['applied'], 32)
        self.assertEqual(result['coverage'], {'publications': 1, 'published_events': 25,
                         'recorded_events': 21, 'unrecorded_events': 4, 'gap_windows': 1,
                         'recorded_by_id': {'0x5201': 21}})

    def test_unique_coverage_counts_new_allocation_and_session_separately(self):
        old = guiding()
        new_allocation = fixtures.snapshot([(1, 0x5201, fixtures.route())], birth=(999, 0))
        new_session = fixtures.snapshot([(1, 0x5201, fixtures.route())], session=2)
        result, _ = self.replay(record(payload=compact(old)),
                                record(at=100, payload=compact(new_allocation)),
                                record(at=200, payload=compact(new_session)), record(5, 300))
        self.assertEqual(result['coverage']['publications'], 3)
        self.assertEqual(result['coverage']['recorded_events'], 4)
        self.assertEqual(result['coverage']['unrecorded_events'], 0)

    def test_stale_reset_cannot_hide_sequence_regression_or_changed_overlap(self):
        regressed = fixtures.snapshot([(1, 0x5201, fixtures.route())])
        changed = fixtures.snapshot([(1, 0x5201, fixtures.route(0)),
                                    (2, 0x5202, fixtures.maneuver())])
        # Same decoded text, but different bytes at the same immutable identity.
        with_nul = fixtures.snapshot([(1, 0x5201, fixtures.route() + fixtures.tlv(4, b'A\0'))])
        no_nul = fixtures.snapshot([(1, 0x5201, fixtures.route() + fixtures.tlv(4, b'A'))])
        for first, later in ((guiding(), regressed), (guiding(), changed), (with_nul, no_nul)):
            with self.assertRaises(DecodeError):
                self.replay(record(payload=compact(first)), record(3, 5000, detail=5000),
                            record(at=5100, payload=compact(later)), record(5, 5200))

    def test_message_output_shows_intermediate_selection_and_hides_private_text(self):
        blob = fixtures.snapshot([(1, 0x5201, fixtures.route() + fixtures.tlv(4, b'PRIVATE\0')),
                                  (2, 0x5202, fixtures.maneuver()),
                                  (3, 0x5201, fixtures.route(0))])
        messages = []
        result = observer.replay(io.BytesIO(journal(record(at=100, payload=compact(blob)),
                                                   record(5, 200))), emit_message=messages.append)
        self.assertEqual(result['resolved_maneuver_snapshots'], 0)
        self.assertEqual(result['message_selection_states']['head_cached'], 1)
        self.assertEqual([m['elapsed_ms'] for m in messages], [100, 100, 100])
        self.assertEqual([m['sequence'] for m in messages], [1, 2, 3])
        self.assertEqual(messages[1]['state']['current_maneuver']['type'], 2)
        self.assertFalse(messages[2]['state']['active'])
        self.assertNotIn('PRIVATE', json.dumps([result, messages]))

    def test_cli_complete_coverage_option_and_message_output(self):
        late = fixtures.snapshot([(i, 0x5201, fixtures.route()) for i in range(2, 18)], last=17)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.rgj'
            path.write_bytes(journal(record(payload=compact(late)), record(5, 100)))
            cmd = [sys.executable, str(HERE / 'rgi_observer.py'), str(path), '--messages']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0)
            records = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(len(records), 17)
            self.assertEqual(records[0]['kind'], 'observer_message')
            self.assertEqual(records[-1]['coverage']['unrecorded_events'], 1)
            self.assertEqual(subprocess.run(cmd + ['--require-complete'], capture_output=True,
                                            timeout=5).returncode, 1)

    @unittest.skipUnless(os.environ.get('CPMAP_PRIVATE_C4_DIR'), 'optional private C4 journal replay')
    def test_private_c4_unique_coverage_and_startup_trace(self):
        captures = list(Path(os.environ['CPMAP_PRIVATE_C4_DIR']).glob('cpmap-rgi-C4-*/events.rgj'))
        self.assertEqual(len(captures), 1)
        messages = []
        with captures[0].open('rb') as stream:
            result = observer.replay(stream, emit_message=messages.append)
        self.assertEqual(result['coverage'], {'publications': 2, 'published_events': 237,
                         'recorded_events': 236, 'unrecorded_events': 1, 'gap_windows': 1,
                         'recorded_by_id': {'0x5201': 184, '0x5204': 12, '0x5202': 40}})
        self.assertEqual(result['end_reason'], 1)
        self.assertEqual(result['producer_fault_snapshots'], 0)
        initial = [m for m in messages if m['instance'] == [118, 714000000]
                   and 20 <= m['sequence'] <= 32 and m['elapsed_ms'] < 20000]
        self.assertEqual(initial[0]['state']['current_maneuver_status'], 'head_cached')
        self.assertEqual(initial[1]['state']['current_maneuver_status'], 'inactive')
        self.assertEqual(initial[-1]['state']['current_maneuver_status'], 'order_absent')

    @unittest.skipUnless(os.environ.get('CPMAP_PRIVATE_C4_2_DIR'), 'optional private C4-2 journal replay')
    def test_private_c4_2_complete_coverage_and_sustained_progression(self):
        # This directory also contains copies of the first test. Select only
        # the new journal; do not concatenate or recount the old recording.
        path = Path(os.environ['CPMAP_PRIVATE_C4_2_DIR']) / 'cpmap-rgi-C4-4526211/events.rgj'
        messages = []
        with path.open('rb') as stream:
            result = observer.replay(stream, emit_message=messages.append, include_private=True)
        self.assertEqual(result['coverage'], {'publications': 2, 'published_events': 240,
                         'recorded_events': 240, 'unrecorded_events': 0, 'gap_windows': 0,
                         'recorded_by_id': {'0x5201': 194, '0x5202': 46}})
        self.assertEqual(result['end_reason'], 1)
        self.assertEqual(result['producer_fault_snapshots'], 0)
        self.assertEqual(result['resolved_maneuver_snapshots'], 83)
        # A fresh list arrives after the startup stop, rather than retaining
        # the selected head from before that stop.
        initial = {m['sequence']: m for m in messages if m['instance'] == [129, 742000000]
                   and m['elapsed_ms'] < 60000}
        self.assertEqual(initial[28]['state']['current_maneuver_status'], 'order_absent')
        self.assertEqual(initial[37]['state']['current_maneuver_status'], 'head_cached')
        heads = []
        distances = []
        for m in messages:
            if m['instance'] != [129, 742000000] or not 35000 <= m['elapsed_ms'] < 55000:
                continue
            state = m['state']
            if state['current_maneuver'] is not None:
                index = state['current_index']
                if not heads or heads[-1] != index: heads.append(index)
                if index == 2 and 'maneuver_meters' in state['route']:
                    distances.append(state['route']['maneuver_meters'])
        self.assertEqual(heads, [0, 1, 2])
        self.assertTrue(any(later < earlier for earlier, later in zip(distances, distances[1:])))
        reconnected = [m for m in messages if m['instance'] == [255, 848000000]
                       and m['elapsed_ms'] >= 145844 and m['state']['current_maneuver'] is not None]
        self.assertTrue(reconnected)
        self.assertEqual(reconnected[0]['state']['current_index'], 2)
        self.assertEqual(result['last_observed']['phase'], 'stopped')
        self.assertIsNone(result['last_observed']['current_maneuver'])
        self.assertFalse(result['final']['active'])

    def test_read_failure_and_allocation_change_clear_old_maneuver(self):
        new = fixtures.snapshot([(1, 0x5201, fixtures.route())], birth=(99, 100))
        _, events = self.replay(record(payload=compact(guiding())),
                               record(2, 100, struct.pack('<I', 2), 1),
                               record(at=200, payload=compact(new)), record(5, 300))
        self.assertFalse(events[1]['state']['active'])
        self.assertIsNone(events[2]['publication']['state']['current_maneuver'])

    def test_end_clears_even_active_state(self):
        result, events = self.replay(record(payload=compact(guiding())), record(5, 100, detail=1))
        self.assertTrue(result['last_observed']['active'])
        self.assertFalse(result['final']['active'])
        self.assertFalse(events[-1]['state']['active'])

    def test_missing_end_truncation_extra_records_and_bad_metadata_rejected(self):
        valid = journal(record(payload=compact(guiding())), record(5, 100))
        cases = [b'', valid[:-1], valid[:16], valid + record(4, 101),
                 journal(record(99), record(5)),
                 journal(record(4, 100), record(5, 99)),
                 journal(record(3, 100, detail=0), record(5, 200)),
                 journal(record(5, 100, detail=99)),
                 journal(record(payload=compact(guiding()) + b'x'), record(5))]
        for blob in cases:
            with self.subTest(length=len(blob)), self.assertRaises(DecodeError):
                observer.replay(io.BytesIO(blob))

    def test_full_semantic_validation_of_compact_events(self):
        # Corrupt the TLV length, without relying on packer's own validation.
        data = bytearray(compact(guiding()))
        data[86:88] = b'\0\x04'
        with self.assertRaises(DecodeError):
            self.replay(record(payload=bytes(data)), record(5))

    def test_default_summary_has_no_private_strings(self):
        blob = fixtures.snapshot([(1, 0x5201, fixtures.route() + fixtures.tlv(4, b'PRIVATE DESTINATION\0'))])
        result, events = self.replay(record(payload=compact(blob)), record(5, 100))
        self.assertNotIn('PRIVATE DESTINATION', json.dumps([result, events]))

    def test_cli_rejects_disabled_only_capture_and_producer_fault(self):
        for blob in (fixtures.snapshot(enabled=0), fixtures.snapshot(
                [(1, 0x5201, fixtures.route())], fault=1)):
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / 'events.rgj'
                path.write_bytes(journal(record(payload=compact(blob)), record(5, 100)))
                r = subprocess.run([sys.executable, str(HERE / 'rgi_observer.py'), str(path)],
                                   capture_output=True, text=True, timeout=5)
                self.assertEqual(r.returncode, 1)
                self.assertFalse(json.loads(r.stdout)['final']['active'])

    @unittest.skipUnless(os.environ.get('CPMAP_PRIVATE_B4_DIR'), 'optional private B4 replay')
    def test_private_b4_snapshots_preserve_all_reader_states(self):
        blobs = [(p / 'rgi-events.bin').read_bytes() for p in sorted(Path(os.environ['CPMAP_PRIVATE_B4_DIR']).glob('cpmap-*'))]
        consumer = Consumer()
        expected = [consumer.consume(b) for b in blobs]
        _, events = self.replay(*[record(at=i*100, payload=compact(b)) for i, b in enumerate(blobs)],
                               record(5, len(blobs)*100))
        self.assertEqual([e['publication'] for e in events if e['event'] == 'snapshot'], expected)


class ProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory(prefix='rgi-observer-tests-')
        cls.root = Path(cls.work.name)
        cls.cc = [os.environ.get('CC', 'clang')]
        # Older local linkers cannot parse the newest macOS SDK's .tbd files.
        sdk = Path('/Library/Developer/CommandLineTools/SDKs/MacOSX14.4.sdk')
        if sys.platform == 'darwin' and sdk.exists(): cls.cc += ['-isysroot', str(sdk)]
        cls.flags = ['-std=c99', '-O2', '-Wall', '-Wextra', '-Werror']
        cls.binary = cls.root / 'observer'
        cls.build(cls.binary)

    @classmethod
    def build(cls, out, *extra):
        subprocess.run(cls.cc + cls.flags + list(extra) + [str(HERE / 'observer/observer.c'), '-o', str(out)], check=True)

    @classmethod
    def tearDownClass(cls): cls.work.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rgi-observer-case-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.source = self.path / 'source'
        self.out = self.path / 'out'

    def run_reader(self, seconds=1, binary=None):
        return subprocess.run([str(binary or self.binary), 'run', str(self.source), str(self.out), str(seconds)],
                              capture_output=True, timeout=seconds + 4)

    def read(self):
        events = []
        with (self.out / 'events.rgj').open('rb') as f:
            result = observer.replay(f, emit=events.append)
        return result, events

    def test_real_worker_round_trip_deduplicates_unchanged_reads(self):
        self.source.write_bytes(guiding())
        self.assertEqual(self.run_reader().returncode, 0)
        result, _ = self.read()
        self.assertEqual(result['snapshots'], 1)
        self.assertEqual(result['messages']['applied'], 2)
        self.assertIn('status=ended', (self.out / 'status.txt').read_text())

    def test_missing_source_is_bounded_and_does_not_fabricate_events(self):
        self.assertEqual(self.run_reader().returncode, 0)
        result, _ = self.read()
        self.assertEqual(result['snapshots'], 0)
        self.assertEqual(result['invalidations'], 1)

    def test_short_read_and_bad_header_invalidate(self):
        for name, blob in [('short', b'abc'), ('bad', b'x' * 33088)]:
            self.out = self.path / name
            self.source.write_bytes(blob)
            self.assertEqual(self.run_reader().returncode, 0)
            result, events = self.read()
            self.assertEqual(result['snapshots'], 0)
            self.assertEqual(events[0]['reason'], 3 if name == 'short' else 4)

    def test_read_recovery_without_progress_does_not_revive_old_guidance(self):
        self.source.write_bytes(guiding())
        process = subprocess.Popen([str(self.binary), 'run', str(self.source), str(self.out), '3'])
        try:
            time.sleep(.35)
            self.source.unlink()
            time.sleep(.35)
            self.source.write_bytes(guiding())
            self.assertEqual(process.wait(timeout=5), 0)
        finally:
            if process.poll() is None: process.kill(); process.wait()
        result, events = self.read()
        self.assertEqual(result['snapshots'], 1)
        unavailable = next(i for i, e in enumerate(events) if e['event'] == 'unavailable')
        self.assertTrue(all(not e.get('state', {}).get('active') for e in events[unavailable:]))

    def test_background_start_duplicate_protection_and_stop(self):
        self.source.write_bytes(guiding())
        cmd = [str(self.binary), 'start', str(self.source), str(self.out), '10']
        self.assertEqual(subprocess.run(cmd, capture_output=True, timeout=5).returncode, 0)
        try:
            self.assertNotEqual(subprocess.run(cmd, capture_output=True, timeout=5).returncode, 0)
        finally:
            r = subprocess.run([str(self.binary), 'stop', str(self.out)], capture_output=True, timeout=5)
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read()[0]['end_reason'], 1)

    def test_stale_deadline_is_recorded_once_and_unchanged_data_stays_stale(self):
        self.source.write_bytes(guiding())
        self.assertEqual(self.run_reader(seconds=6).returncode, 0)
        result, events = self.read()
        self.assertEqual(result['stale_deadlines'], 1)
        stale_at = next(i for i, e in enumerate(events) if e['event'] == 'stale')
        self.assertTrue(all(not e.get('state', {}).get('active') for e in events[stale_at:]))

    def test_journal_capacity_keeps_a_complete_end_record(self):
        binary = self.root / 'small'
        self.build(binary, '-DLIMIT=128u')
        self.source.write_bytes(guiding())
        self.assertEqual(self.run_reader(binary=binary).returncode, 0)
        self.assertLessEqual((self.out / 'events.rgj').stat().st_size, 128)
        self.assertEqual(self.read()[0]['end_reason'], 2)

    def test_blocked_worker_is_killed_by_supervisor_deadline(self):
        shim = self.path / 'blocked.c'
        shim.write_text('''#define _POSIX_C_SOURCE 200809L
#include <sys/stat.h>
#include <unistd.h>
#include <time.h>
ssize_t blocked_read(int fd, void *p, size_t n) {
    struct stat st; struct timespec t={5,0};
    if (!fstat(fd,&st) && S_ISREG(st.st_mode)) nanosleep(&t,0);
    return read(fd,p,n);
}
''')
        obj = self.path / 'observer.o'
        subprocess.run(self.cc + self.flags + ['-Dread=blocked_read', '-c', str(HERE / 'observer/observer.c'), '-o', str(obj)], check=True)
        binary = self.path / 'blocked'
        subprocess.run(self.cc + self.flags + [str(obj), str(shim), '-o', str(binary)], check=True)
        self.source.write_bytes(guiding())
        started = time.monotonic()
        self.assertEqual(self.run_reader(seconds=4, binary=binary).returncode, 1)
        self.assertLess(time.monotonic() - started, 3)
        result, events = self.read()
        self.assertEqual(result['end_reason'], 3)
        self.assertEqual(next(e for e in events if e['event'] == 'unavailable')['reason'], 5)

    def test_output_startup_delay_is_not_mistaken_for_blocked_device(self):
        shim = self.path / 'slow.c'
        shim.write_text('''#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <time.h>
int slow_rename(const char *a, const char *b) {
    static int once; struct timespec delay={2,0};
    if (!once++) nanosleep(&delay,0);
    return rename(a,b);
}
''')
        obj = self.path / 'observer.o'
        subprocess.run(self.cc + self.flags + ['-Drename=slow_rename', '-c', str(HERE / 'observer/observer.c'), '-o', str(obj)], check=True)
        binary = self.path / 'slow'
        subprocess.run(self.cc + self.flags + [str(obj), str(shim), '-o', str(binary)], check=True)
        self.source.write_bytes(guiding())
        self.assertEqual(self.run_reader(seconds=4, binary=binary).returncode, 0)
        result, _ = self.read()
        self.assertEqual(result['snapshots'], 1)
        self.assertEqual(result['end_reason'], 0)

    def test_nonblocking_read_progress_does_not_depend_on_readiness_notifications(self):
        shim = self.path / 'quiet.c'
        shim.write_text('''#define _POSIX_C_SOURCE 200809L
#include <sys/select.h>
#include <time.h>
int quiet_select(int n, fd_set *r, fd_set *w, fd_set *e, struct timeval *t) {
    struct timespec delay={0,100000000};
    (void)n; (void)r; (void)w; (void)e; (void)t;
    nanosleep(&delay,0); return 0;
}
''')
        obj = self.path / 'observer.o'
        subprocess.run(self.cc + self.flags + ['-Dselect=quiet_select', '-c', str(HERE / 'observer/observer.c'), '-o', str(obj)], check=True)
        binary = self.path / 'quiet'
        subprocess.run(self.cc + self.flags + [str(obj), str(shim), '-o', str(binary)], check=True)
        self.source.write_bytes(guiding())
        self.assertEqual(self.run_reader(binary=binary).returncode, 0)
        self.assertEqual(self.read()[0]['snapshots'], 1)

    @unittest.skipUnless(os.environ.get('CPMAP_PRIVATE_B4_DIR'), 'optional private B4 C packer replay')
    def test_private_b4_through_real_worker_and_c_packer(self):
        blobs = [(p / 'rgi-events.bin').read_bytes() for p in sorted(Path(os.environ['CPMAP_PRIVATE_B4_DIR']).glob('cpmap-*'))]
        self.assertEqual(len(blobs), 4)
        self.source.write_bytes(blobs[0])
        process = subprocess.Popen([str(self.binary), 'run', str(self.source), str(self.out), '2'])
        try:
            for blob in blobs[1:]:
                time.sleep(.25)
                stage = self.path / 'stage'; stage.write_bytes(blob); stage.replace(self.source)
            self.assertEqual(process.wait(timeout=5), 0)
        finally:
            if process.poll() is None: process.kill(); process.wait()
        _, events = self.read()
        consumer = Consumer()
        expected = [consumer.consume(b) for b in blobs]
        self.assertEqual([e['publication'] for e in events if e['event'] == 'snapshot'], expected)


if __name__ == '__main__':
    unittest.main()
