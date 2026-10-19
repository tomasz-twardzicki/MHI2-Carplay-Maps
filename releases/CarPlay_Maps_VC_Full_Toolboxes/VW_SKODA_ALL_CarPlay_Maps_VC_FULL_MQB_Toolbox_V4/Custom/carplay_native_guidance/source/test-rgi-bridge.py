#!/usr/bin/env python3
"""Bridge lifecycle/ownership/geometry tests. Private replay is opt-in."""
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import rgi_bridge as bridge
import rgi_observer as observer
from rgi_publication import Consumer

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('publication_fixtures', HERE / 'test-rgi-publication.py')
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)


def route(head=2, distance=None, state=1):
    value = f.tlv(0, b'\0\x10') + f.tlv(1, bytes([state])) + f.tlv(13, head.to_bytes(2, 'big'))
    return value + (f.tlv(10, distance.to_bytes(4, 'big')) if distance is not None else b'')


def maneuver(index=2, kind=2, angle=None):
    value = (f.tlv(0, b'\0\x10') + f.tlv(1, index.to_bytes(2, 'big'))
             + f.tlv(3, bytes([kind])) + f.tlv(9, b'\0') + f.tlv(8, b'\0'))
    return value + (f.tlv(11, angle.to_bytes(2, 'big', signed=True)) if angle is not None else b'')


def guiding():
    return [(1, 0x5201, route()), (2, 0x5202, maneuver()), (3, 0x5201, route(distance=100))]


def compact(blob):
    result = bytes(blob[:64])
    last, count = struct.unpack_from('<II', blob, 20)
    for seq in range(last - count + 1, last + 1):
        offset = 64 + ((seq - 1) & 15) * 2064
        length = struct.unpack_from('<H', blob, offset + 6)[0]
        result += bytes(blob[offset:offset + 16 + length])
    return result


def record(kind=1, at=0, payload=b'', detail=0):
    return struct.pack('<8I', kind, at, len(payload), detail, 0, 0, 0, 0) + payload


def journal(*records):
    return struct.pack('<4sIII', b'RGJ1', 1, 33088, 100) + b''.join(records)


class BridgeTests(unittest.TestCase):
    def replay(self, *records, simulate=True, private=False, baseline=True):
        frames = []
        if baseline: records = (record(payload=compact(f.snapshot())),) + records
        result = bridge.replay(io.BytesIO(journal(*records)), simulate_owner=simulate,
                               include_private=private, emit=frames.append)
        return result, frames[1:] if baseline else frames

    def initial(self, model, at=0, events=None):
        if model.stamp is None:
            empty = Consumer().consume(f.snapshot(), include_private=True)
            model.observe({'event': 'snapshot', 'elapsed_ms': at, 'publication': empty})
        blob = f.snapshot(guiding() if events is None else events)
        p = Consumer().consume(blob, include_private=True,
                               emit=lambda m: model.note_message({**m, 'elapsed_ms': at}))
        return model.observe({'event': 'snapshot', 'elapsed_ms': at, 'publication': p}, True)

    def test_trip_values_survive_head_change_but_not_stop_or_new_episode(self):
        extra = f.tlv(7, (12345).to_bytes(4, 'big')) + f.tlv(6, (3661).to_bytes(8, 'big'))
        events = guiding(); events[0] = (1, 0x5201, events[0][2] + extra)
        records = [record(payload=compact(f.snapshot(events)))]
        for seq, payload in [(4, route(head=3, distance=100)), (5, route(state=0) + extra), (6, route(head=3))]:
            events.append((seq, 0x5201, payload)); records.append(record(at=seq*100, payload=compact(f.snapshot(events))))
        _, frames = self.replay(*records, record(5, 1000), private=True)
        for frame in frames[:2]:
            self.assertEqual(frame['payload']['destination_distance'], {'valid': True, 'meters': 12345})
            self.assertEqual(frame['payload']['remaining_time'], {'valid': True, 'seconds': 3661})
        self.assertFalse(frames[2]['payload']['destination_distance']['valid'])
        self.assertFalse(frames[3]['payload']['remaining_time']['valid'])

    def test_trip_overflow_zero_and_redaction(self):
        for remaining, seconds, valid in [(0,0,True), (0xffffffff,0xffffffffffffffff,False)]:
            extra = f.tlv(7, remaining.to_bytes(4,'big')) + f.tlv(6, seconds.to_bytes(8,'big'))
            events=guiding(); events.append((4,0x5201,route()+extra))
            _, frames=self.replay(record(payload=compact(f.snapshot(events))), record(5, 1000), private=True)
            self.assertEqual(frames[0]['payload']['destination_distance']['valid'],valid)
            self.assertEqual(frames[0]['payload']['remaining_time']['valid'],valid)
            _, redacted=self.replay(record(payload=compact(f.snapshot(events))), record(5, 1000))
            self.assertNotIn('meters',redacted[0]['payload']['destination_distance'])
            self.assertNotIn('seconds',redacted[0]['payload']['remaining_time'])

    def test_unknown_ownership_never_takes_over_from_stock(self):
        result, frames = self.replay(record(payload=compact(f.snapshot(guiding()))), record(5, 100), simulate=False)
        self.assertEqual(result['ownership'], 'unknown')
        self.assertEqual(result['actions'], {'pass_through': 3})
        self.assertTrue(all(frame['payload'] is None for frame in frames))

    def test_factory_connection_ordinal_and_oem_calculation_are_not_confused(self):
        self.assertEqual(bridge.native_context(2, 0, 0), (True, False))
        self.assertEqual(bridge.native_context(2, 0, 1), (True, True))
        self.assertEqual(bridge.native_context(2, 0, 2), (True, True))
        self.assertEqual(bridge.native_context(4, 0, 0), (None, False))
        self.assertEqual(bridge.native_context(3, 0, 0), (False, False))
        self.assertEqual(bridge.native_context(True, 0, 0), (None, False))
        self.assertEqual(bridge.native_context(2, 1, 0), (True, None))
        self.assertEqual(bridge.native_context(2, 0, 255), (True, None))
        metadata = json.loads((HERE / 'MU1427-NATIVE-CONTRACT.json').read_text())['classes']
        cp = metadata['generated/de/vw/mib/asl/internal/smartphoneintegration/'
                      'ASLSmartPhoneIntegrationPropertyManager']['fields']
        nav = metadata['generated/de/vw/mib/asl/internal/navigation/bap/ASLNavigationBapPropertyManager']['fields']
        self.assertEqual(cp['CURRENT_ACTIVE_CONNECTION_METHOD__C2_CARPLAY']['value'], 2)
        self.assertEqual(nav['ROUTE_GUIDANCE_STATE__C2_CALCULATING']['value'], 2)

    def test_complete_replacement_maps_head_and_clears_unused_slots(self):
        _, frames = self.replay(record(payload=compact(f.snapshot(guiding()))), record(5, 100))
        payload = frames[0]['payload']
        self.assertEqual(frames[0]['action'], 'publish')
        self.assertEqual(payload['rg_status'], 1)
        self.assertEqual((payload['maneuvers'][0]['main_element'], payload['maneuvers'][0]['direction']), (13, 192))
        self.assertEqual(payload['maneuvers'][1:], [bridge.empty_descriptor(), bridge.empty_descriptor()])
        self.assertFalse(payload['bargraph']['enabled'])
        self.assertFalse(payload['lanes']['show'])
        self.assertEqual(payload['maneuver_state'], 0)
        self.assertEqual(frames[-1]['action'], 'clear_and_release')
        self.assertEqual(frames[-1]['reason'], 'end')
        self.assertEqual(frames[-1]['payload']['rg_status'], 0)

    def test_context_lease_expiry_releases_without_blank_over_oem(self):
        model = bridge.Bridge(); model.set_context(True, False, 0)
        self.assertEqual(self.initial(model)['action'], 'publish')
        frame = model.observe({'event': 'heartbeat', 'elapsed_ms': 1500})
        self.assertEqual(frame['action'], 'release_to_stock')
        self.assertIsNone(frame['payload'])
        model.set_context(True, False, 1600)
        # Refreshing external context does not make an old producer frame fresh.
        self.assertNotEqual(self.initial(model, at=1600)['action'], 'publish')

    def test_native_guidance_or_carplay_exit_wins_without_clearing_its_payload(self):
        for context in [(True, True), (False, False), (True, None), (None, False)]:
            model = bridge.Bridge(); model.set_context(True, False, 0); self.initial(model)
            model.set_context(*context, 100)
            frame = model.observe({'event': 'heartbeat', 'elapsed_ms': 100})
            self.assertEqual(frame['action'], 'release_to_stock')
            self.assertIsNone(frame['payload'])

    def test_context_and_observation_times_are_checked(self):
        model = bridge.Bridge()
        with self.assertRaises(ValueError): model.set_context(1, False, 0)
        model.observe({'event': 'heartbeat', 'elapsed_ms': 100})
        with self.assertRaises(ValueError): model.set_context(True, False, 99)
        with self.assertRaises(ValueError): model.observe({'event': 'heartbeat', 'elapsed_ms': 99})
        model.set_context(True, False, 200)
        self.assertIsNotNone(model._guard(100))
        with self.assertRaises(ValueError): model.set_context(True, False, 150)

    def test_context_loss_or_late_renewal_cannot_revive_cached_ownership(self):
        for lost_and_restored in (True, False):
            model = bridge.Bridge(); model.set_context(True, False, 0)
            self.initial(model)
            if lost_and_restored:
                model.set_context(True, True, 100)
                model.set_context(True, False, 200)
                at = 200
            else:
                model.set_context(True, False, 1500)
                at = 1500
            frame = model.observe({'event': 'heartbeat', 'elapsed_ms': at})
            self.assertNotEqual(frame['action'], 'publish')
            self.assertFalse(frame['owns_guidance'])

    def test_loading_locating_reroute_arrival_and_fault_clear_all_owned_output(self):
        for state in (0, 2, 3, 4, 5):
            events = guiding() + [(4, 0x5201, route(state=state))]
            _, frames = self.replay(record(payload=compact(f.snapshot(guiding()))),
                                    record(at=100, payload=compact(f.snapshot(events))), record(5, 200))
            self.assertEqual(frames[1]['action'], 'clear_and_release')
            self.assertEqual(frames[1]['payload']['maneuvers'], [bridge.empty_descriptor() for _ in range(3)])
            self.assertFalse(frames[1]['payload']['distance']['valid'])
        for kwargs in ({'fault': 1}, {'enabled': 0}):
            blob = f.snapshot(guiding(), **kwargs) if 'fault' in kwargs else f.snapshot(**kwargs, session=2)
            _, frames = self.replay(record(payload=compact(f.snapshot(guiding()))),
                                    record(at=100, payload=compact(blob)), record(5, 200))
            self.assertEqual(frames[1]['action'], 'clear_and_release')
            self.assertEqual(frames[1]['reason'], 'producer_fault_or_disabled')

    def test_successful_identical_reads_do_not_extend_guidance_deadline(self):
        blob = compact(f.snapshot(guiding()))
        _, frames = self.replay(record(payload=blob),
                                *[record(4, at, detail=3) for at in (1000, 2000, 3000, 4000)],
                                record(at=4900, payload=blob),
                                record(4, 5000, detail=3), record(5, 5100))
        by_time = {frame['elapsed_ms']: frame for frame in frames}
        self.assertEqual(by_time[4900]['action'], 'publish')
        self.assertEqual(by_time[5000]['action'], 'clear_and_release')
        self.assertEqual(by_time[5000]['reason'], 'stale')

    def test_late_first_window_is_not_proof_of_fresh_guidance(self):
        old = guiding(); later = old + [(4, 0x5201, route(distance=50))]
        _, frames = self.replay(record(payload=compact(f.snapshot(old))),
                                record(at=100, payload=compact(f.snapshot(old))),
                                record(at=200, payload=compact(f.snapshot(later))),
                                record(5, 300), baseline=False)
        self.assertEqual(frames[0]['action'], 'pass_through')
        self.assertEqual(frames[0]['reason'], 'awaiting_source_progress')
        self.assertEqual(frames[1]['action'], 'pass_through')
        self.assertEqual(frames[2]['action'], 'publish')

    def test_read_failure_same_header_recovery_cannot_revive_old_guidance(self):
        blob = compact(f.snapshot(guiding()))
        _, frames = self.replay(record(payload=blob), record(2, 100, struct.pack('<I', 2), 1),
                                record(at=200, payload=blob), record(5, 300))
        self.assertEqual(frames[1]['action'], 'clear_and_release')
        self.assertEqual(frames[2]['action'], 'pass_through')

    def test_foreign_component_activity_cannot_keep_our_guidance_fresh(self):
        events = guiding(); records = [record(payload=compact(f.snapshot(events)))]
        foreign = f.tlv(0, b'\0\x20') + f.tlv(1, b'\1')
        for at in (1000, 2000, 3000, 4000, 5000):
            events = events + [(len(events) + 1, 0x5201, foreign)]
            records.append(record(at=at, payload=compact(f.snapshot(events))))
        _, frames = self.replay(*records, record(5, 5100))
        self.assertEqual(frames[-2]['action'], 'clear_and_release')
        self.assertEqual(frames[-2]['reason'], 'stale')

    def test_old_window_plus_fresh_foreign_tail_cannot_revive_stale_guidance(self):
        old = guiding()
        foreign = f.tlv(0, b'\0\x20') + f.tlv(1, b'\1')
        later = old + [(4, 0x5201, foreign)]
        _, frames = self.replay(record(payload=compact(f.snapshot(old))),
                                *[record(4, at, detail=3) for at in (1000, 2000, 3000, 4000)],
                                record(3, 5000, detail=5000),
                                record(at=5100, payload=compact(f.snapshot(later))), record(5, 5200))
        self.assertEqual(frames[-2]['action'], 'pass_through')
        self.assertFalse(frames[-2]['owns_guidance'])

    def test_new_allocation_cannot_reuse_old_maneuver_or_distance(self):
        new = f.snapshot([(1, 0x5201, route(distance=50))], birth=(999, 0))
        _, frames = self.replay(record(payload=compact(f.snapshot(guiding()))),
                                record(at=100, payload=compact(new)), record(5, 200), private=True)
        self.assertEqual(frames[1]['payload']['maneuvers'][0]['main_element'], 0)
        self.assertFalse(frames[1]['payload']['distance']['valid'])

    def test_gap_discards_old_arrow_even_when_route_remains_active(self):
        late = f.snapshot([(i, 0x5201, route(distance=25)) for i in range(10, 26)], last=25)
        _, frames = self.replay(record(payload=compact(f.snapshot(guiding()))),
                                record(at=100, payload=compact(late)), record(5, 200))
        self.assertEqual(frames[1]['payload']['maneuvers'][0]['main_element'], 0)
        self.assertFalse(frames[1]['payload']['distance']['valid'])

    def test_head_change_requires_new_distance_for_that_head_and_zero_is_valid(self):
        first = guiding()[:-1] + [(3, 0x5201, route(distance=0))]
        second = first + [(4, 0x5201, route(head=3)), (5, 0x5202, maneuver(index=3, kind=1))]
        third = second + [(6, 0x5201, route(head=3, distance=30))]
        _, frames = self.replay(record(payload=compact(f.snapshot(first))),
                                record(at=100, payload=compact(f.snapshot(second))),
                                record(at=200, payload=compact(f.snapshot(third))), record(5, 300), private=True)
        self.assertEqual(frames[0]['payload']['distance']['meters'], 0)
        self.assertTrue(frames[0]['payload']['distance']['valid'])
        self.assertEqual(frames[0]['payload']['distance']['bap_unit'], 0)
        self.assertEqual(frames[0]['payload']['distance']['komo_unit'], 1)
        self.assertFalse(frames[1]['payload']['distance']['valid'])
        self.assertEqual(frames[2]['payload']['distance']['meters'], 30)

    def test_unsigned_distance_over_signed_native_range_is_not_wrapped(self):
        events = guiding()[:-1] + [(3, 0x5201, route(distance=0xffffffff))]
        _, frames = self.replay(record(payload=compact(f.snapshot(events))), record(5, 100))
        self.assertFalse(frames[0]['payload']['distance']['valid'])

    def test_no_intermediate_publish_from_window_ending_in_stop(self):
        events = guiding() + [(4, 0x5201, route(state=0))]
        result, frames = self.replay(record(payload=compact(f.snapshot(events))), record(5, 100))
        self.assertNotIn('publish', result['actions'])
        self.assertTrue(all(frame['payload'] is None for frame in frames))

    def test_missing_geometry_clears_symbol_rather_than_keeps_previous_turn(self):
        events = guiding() + [(4, 0x5202, maneuver(kind=11))]
        _, frames = self.replay(record(payload=compact(f.snapshot(guiding()))),
                                record(at=100, payload=compact(f.snapshot(events))), record(5, 200))
        self.assertEqual(frames[1]['mapping']['reason'], 'exit_angle_absent')
        self.assertEqual(frames[1]['payload']['maneuvers'][0]['main_element'], 0)

    def test_distance_private_by_default_and_detached(self):
        events = guiding() + [(4, 0x5201, route(distance=12345) + f.tlv(4, b'PRIVATE DESTINATION\0'))]
        result, frames = self.replay(record(payload=compact(f.snapshot(events))), record(5, 100))
        output = json.dumps([result, frames])
        self.assertNotIn('PRIVATE', output)
        self.assertNotIn('12345', output)
        self.assertNotIn('meters', frames[0]['payload']['distance'])

    def test_cli_requires_explicit_simulation_and_preserves_privacy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.rgj'
            path.write_bytes(journal(record(payload=compact(f.snapshot())),
                                     record(payload=compact(f.snapshot(guiding()))), record(5, 100)))
            cmd = [sys.executable, str(HERE / 'rgi_bridge.py'), str(path)]
            no_owner = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.assertNotIn('publish', json.loads(no_owner.stdout)['actions'])
            simulated = subprocess.run(cmd + ['--simulate-carplay-owner', '--frames'],
                                       capture_output=True, text=True, check=True)
            lines = [json.loads(line) for line in simulated.stdout.splitlines()]
            self.assertEqual(lines[-1]['ownership'], 'simulated_carplay')
            self.assertEqual(lines[1]['action'], 'publish')
            self.assertNotIn('meters', lines[1]['payload']['distance'])

    @unittest.skipUnless(os.environ.get('CPMAP_PRIVATE_C4_2_DIR'), 'optional private C4-2 bridge replay')
    def test_private_c4_2_projection_and_terminal_release(self):
        path = Path(os.environ['CPMAP_PRIVATE_C4_2_DIR']) / 'cpmap-rgi-C4-4526211/events.rgj'
        frames = []
        with path.open('rb') as stream: result = bridge.replay(stream, simulate_owner=True, emit=frames.append)
        self.assertEqual(result['coverage']['unrecorded_events'], 0)
        self.assertGreater(result['valid_distance_frames'], 0)
        pairs = {(s['payload']['maneuvers'][0]['main_element'], s['payload']['maneuvers'][0]['direction'])
                 for s in frames if s['action'] == 'publish'}
        self.assertTrue({(13, 64), (13, 192), (21, 0)} <= pairs)
        self.assertFalse(result['final']['owns_guidance'])
        self.assertIsNone(result['final']['payload'])
        for frame in frames:
            if frame['action'] == 'publish':
                self.assertEqual(frame['payload']['maneuvers'][1:],
                                 [bridge.empty_descriptor(), bridge.empty_descriptor()])

    @unittest.skipUnless(os.environ.get('CPMAP_PRIVATE_C4_DIR'), 'optional original garage bridge replay')
    def test_private_garage_capture_does_not_invent_arrow_or_distance(self):
        path = Path(os.environ['CPMAP_PRIVATE_C4_DIR']) / 'cpmap-rgi-C4-5173328/events.rgj'
        with path.open('rb') as stream: result = bridge.replay(stream, simulate_owner=True)
        self.assertEqual(result['coverage']['unrecorded_events'], 1)
        self.assertEqual(set(result['descriptor_states']), {'0:0'})
        self.assertEqual(result['valid_distance_frames'], 0)
        self.assertFalse(result['final']['owns_guidance'])


if __name__ == '__main__': unittest.main()
