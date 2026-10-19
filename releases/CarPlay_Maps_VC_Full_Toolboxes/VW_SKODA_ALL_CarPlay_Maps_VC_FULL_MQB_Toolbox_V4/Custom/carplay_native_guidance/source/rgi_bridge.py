#!/usr/bin/env python3
"""Offline replacement-frame model for a future MU1427 native adapter.

SPDX-License-Identifier: GPL-3.0-or-later
No device, PPS, Java, BAP or HMI writes. Runtime ownership must be independently
observed; the CLI's optional ownership simulation is explicitly an assumption.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

from rgi_decode import DecodeError
from rgi_maneuver import empty_descriptor, map_maneuver
import rgi_observer

STALE_MS = 5000
CONTEXT_MS = 1500


def native_context(connection_type, navigation_status, route_state):
    """Interpret the factory service getters, not iAP2 state or DSI bitmasks.

    The active-connection ASL property uses ordinal 2 for CarPlay. Native
    route state 2 means calculating and already prevents CarPlay takeover.
    Navigation errors and unknown values cannot establish inactivity.
    """
    carplay = connection_type == 2 if type(connection_type) is int and connection_type in (0, 1, 2, 3) else None
    native = route_state != 0 if (type(navigation_status) is int and navigation_status == 0
                                  and type(route_state) is int and route_state in (0, 1, 2)) else None
    return carplay, native


class Bridge:
    def __init__(self):
        self.context = (None, None, None)
        self.stamp = None
        self.changed = None
        self.accepted_identity = None
        self.data = None
        self.distance_key = None
        self.distance = None
        self.trip_key = None
        self.trip = {}
        self.owned = False
        self.now = 0

    def set_context(self, carplay_active, native_guidance_active, observed_ms):
        for value in (carplay_active, native_guidance_active):
            if value is not None and type(value) is not bool:
                raise ValueError('ownership flags must be boolean or unknown')
        if type(observed_ms) is not int or observed_ms < self.now:
            raise ValueError('ownership context time regressed')
        old_observed = self.context[2]
        if old_observed is not None and observed_ms < old_observed:
            raise ValueError('ownership context time regressed')
        if (carplay_active is not True or native_guidance_active is not False
                or old_observed is not None and observed_ms - old_observed >= CONTEXT_MS):
            self.data = None
            self.changed = None
            self.accepted_identity = None
            self.distance_key = None
            self.distance = None
        self.context = (carplay_active, native_guidance_active, observed_ms)

    def _guard(self, now):
        carplay, native, observed = self.context
        if observed is None or observed > now or now - observed >= CONTEXT_MS:
            return 'ownership_unknown_or_stale'
        if carplay is not True: return 'carplay_not_active'
        if native is not False: return 'native_guidance_active_or_unknown'
        return None

    @staticmethod
    def _key(message):
        state = message['state']
        if state['current_maneuver'] is None: return None
        return (tuple(message['instance']), message['session'],
                state['session'], state['generation'], state['current_index'])

    def note_message(self, message):
        """Record distance provenance, but never publish intermediate states.

        Wire distance deltas are usable only after a selected cached head is
        known, in the same reader session/generation. Changing heads cannot
        reuse the previous head's distance. Zero is a real received value.
        """
        state = message['state']
        trip_key = (tuple(message['instance']), message['session'], state['session'], state['generation'])
        if trip_key != self.trip_key or state['phase'] not in ('guiding', 'proceed_to_route'):
            self.trip_key = trip_key
            self.trip = {}
        key = self._key(message)
        if key != self.distance_key:
            self.distance_key = key
            self.distance = None
        identity = (tuple(message['instance']), message['session'])
        # A first window can have sat in the ring for an unknown time. Treat
        # it as a baseline; freshness requires observed subsequent progress.
        new = self.stamp is not None and identity == self.stamp[:2] and message['sequence'] > self.stamp[2]
        if message['applied'] and new:
            self.changed = message['elapsed_ms']
            self.accepted_identity = identity
        if message['applied'] and new and state['phase'] in ('guiding', 'proceed_to_route'):
            for field, limit in (('remaining_meters', 0x7fffffff), ('remaining_seconds', 359940)):
                if field in message['present']:
                    value = state['route'].get(field)
                    self.trip[field] = value if type(value) is int and 0 <= value <= limit else None
        if key is not None and message['applied'] and new and 'maneuver_meters' in message['present']:
            value = message['state']['route'].get('maneuver_meters')
            self.distance = value if type(value) is int and 0 <= value <= 0x7fffffff else None

    @staticmethod
    def _empty_payload():
        return {'rg_status': 0, 'maneuver_state': 0,
                'maneuvers': [empty_descriptor() for _ in range(3)],
                'distance': {'valid': False, 'meters': None, 'bap_unit': 0, 'komo_unit': 1},
                'destination_distance': {'valid': False, 'meters': None},
                'remaining_time': {'valid': False, 'seconds': None},
                'bargraph': {'enabled': False, 'value': 0}, 'lanes': {'show': False, 'entries': []}}

    def observe(self, event, include_private=False):
        now = event['elapsed_ms']
        if type(now) is not int or now < self.now:
            raise ValueError('bridge observation time regressed')
        self.now = now
        kind = event['event']
        guard = self._guard(now)
        reason = guard
        if kind == 'snapshot':
            publication = event['publication']
            stamp = (tuple(publication['instance']), publication['session'], publication['sequence'])
            if self.stamp is not None and stamp[:2] == self.stamp[:2] and stamp[2] < self.stamp[2]:
                raise ValueError('bridge publication sequence regressed')
            progress = stamp != self.stamp
            self.stamp = stamp
            if publication['fault'] or not publication['enabled']:
                self.data = None
                self.changed = None
                self.accepted_identity = None
                reason = 'producer_fault_or_disabled'
            elif progress:
                self.data = deepcopy(publication) if stamp[2] and guard is None else None
                if self.data is None and guard is None: reason = 'no_published_events'
        elif kind in ('unavailable', 'stale', 'end'):
            self.data = None
            self.changed = None
            self.accepted_identity = None
            self.distance_key = None
            self.distance = None
            reason = kind
        elif kind != 'heartbeat':
            raise ValueError('unsupported bridge observation')
        if guard is not None:
            self.data = None
            self.changed = None
            self.accepted_identity = None
            self.distance_key = None
            self.distance = None
            reason = guard
        elif reason is None and (self.changed is None or now - self.changed >= STALE_MS
                                 or self.data is not None and self.accepted_identity != self.stamp[:2]):
            reason = 'awaiting_source_progress' if self.changed is None else 'stale'
            self.data = None
            self.changed = None
            self.accepted_identity = None
            self.distance_key = None
            self.distance = None
        if kind == 'snapshot' and (event['publication']['fault'] or not event['publication']['enabled']):
            self.distance_key = None
            self.distance = None

        state = self.data['state'] if self.data is not None else None
        active = state is not None and state['active'] and state['phase'] in ('guiding', 'proceed_to_route')
        if not active:
            self.trip_key = None
            self.trip = {}
            had_owner = self.owned
            self.owned = False
            # Never send a clearing frame over newly active OEM guidance.
            action = 'release_to_stock' if had_owner and guard else (
                'clear_and_release' if had_owner else 'pass_through')
            payload = self._empty_payload() if action == 'clear_and_release' else None
            return {'schema': 1, 'elapsed_ms': now, 'action': action, 'owns_guidance': False,
                    'reason': reason or (state['phase'] if state else 'awaiting_fresh_publication'),
                    'mapping': None, 'payload': payload}

        self.owned = True
        mapping = map_maneuver(state['current_maneuver'])
        payload = self._empty_payload()
        payload['rg_status'] = 1
        if mapping['descriptor'] is not None:
            payload['maneuvers'][0] = mapping['descriptor']
        key = (tuple(self.data['instance']), self.data['session'], state['session'],
               state['generation'], state['current_index'])
        if self.distance_key == key and self.distance is not None:
            payload['distance'].update(valid=True, meters=self.distance)
        trip_key = (tuple(self.data['instance']), self.data['session'], state['session'], state['generation'])
        if trip_key == self.trip_key:
            for field, payload_key, unit in (('remaining_meters','destination_distance','meters'), ('remaining_seconds','remaining_time','seconds')):
                value = self.trip.get(field)
                if value is not None: payload[payload_key].update(valid=True, **{unit: value})
        if not include_private:
            payload['destination_distance'].pop('meters')
            payload['remaining_time'].pop('seconds')
            # Keep validity and units, never private numeric route distances.
            payload['distance'].pop('meters')
        return {'schema': 1, 'elapsed_ms': now, 'action': 'publish', 'owns_guidance': True,
                'reason': state['current_maneuver_status'],
                'identity': {'instance': list(self.data['instance']), 'session': self.data['session'],
                             'sequence': self.data['sequence'], 'generation': state['generation'],
                             'current_index': state['current_index']},
                'mapping': mapping, 'payload': payload}


def replay(stream, *, simulate_owner=False, emit=None, include_private=False):
    bridge = Bridge()
    actions = Counter()
    mappings = Counter()
    symbols = Counter()
    distances = 0
    last = None

    def observation(event):
        nonlocal distances, last
        if simulate_owner:
            # This models supplied external signals; an RGI packet is not
            # evidence of real CarPlay ownership or inactive OEM navigation.
            bridge.set_context(True, False, event['elapsed_ms'])
        frame = bridge.observe(event, include_private)
        actions[frame['action']] += 1
        if frame['mapping'] is not None:
            mappings[frame['mapping']['reason']] += 1
        if frame['action'] == 'publish':
            descriptor = frame['payload']['maneuvers'][0]
            symbols[f"{descriptor['main_element']}:{descriptor['direction']}"] += 1
            distances += frame['payload']['distance']['valid']
        last = frame
        if emit is not None: emit(frame)

    source = rgi_observer.replay(stream, emit=observation,
                                 emit_message=bridge.note_message, include_private=True)
    return {'kind': 'bridge_summary', 'ownership': 'simulated_carplay' if simulate_owner else 'unknown',
            'actions': dict(actions), 'mapping_reasons': dict(mappings),
            'descriptor_states': dict(symbols), 'valid_distance_frames': distances,
            'coverage': source['coverage'], 'source_end_reason': source['end_reason'],
            'publishing_snapshots': source['publishing_snapshots'],
            'producer_fault_snapshots': source['producer_fault_snapshots'], 'final': last}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('journal', type=Path)
    parser.add_argument('--simulate-carplay-owner', action='store_true',
                        help='assume fresh CarPlay-active/OEM-guidance-inactive context for offline modelling')
    parser.add_argument('--frames', action='store_true')
    parser.add_argument('--include-private', action='store_true')
    args = parser.parse_args()
    try:
        with args.journal.open('rb') as stream:
            result = replay(stream, simulate_owner=args.simulate_carplay_owner,
                            include_private=args.include_private,
                            emit=(lambda frame: print(json.dumps(frame))) if args.frames else None)
    except (OSError, DecodeError, ValueError) as error:
        print(json.dumps({'error': 'bridge input read failed' if isinstance(error, OSError) else str(error)}))
        return 1
    print(json.dumps(result))
    return int(result['source_end_reason'] in (2, 3, 4) or result['producer_fault_snapshots'] > 0
               or not result['publishing_snapshots'])


if __name__ == '__main__':
    sys.exit(main())
