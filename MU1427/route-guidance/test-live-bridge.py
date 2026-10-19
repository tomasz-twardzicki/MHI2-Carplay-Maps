#!/usr/bin/env python3
"""D1 runtime vs Python oracle, malformed inputs and exact factory integration.
Private inputs opt in via the same C4/C4-2 environment variables; never printed.
"""
import argparse
import hashlib
import importlib.util
import io
import itertools
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import tempfile

import rgi_bridge
from rgi_maneuver import map_maneuver, empty_descriptor

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('bridge_fixtures', HERE / 'test-rgi-bridge.py')
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)


def sha(data): return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('build', type=Path)
    p.add_argument('--java-home', type=Path, required=True)
    p.add_argument('--stock-jar', type=Path, required=True)
    p.add_argument('--private-journal', type=Path, action='append', default=[])
    a = p.parse_args()
    manifest = json.loads((a.build / 'manifest.json').read_text())
    builder_spec = importlib.util.spec_from_file_location('live_builder', HERE / 'build-live-bridge.py')
    builder = importlib.util.module_from_spec(builder_spec); builder_spec.loader.exec_module(builder)
    assert builder.stock_content(a.stock_jar) == manifest['converted_content_sha256'], 'Wrong factory classes'
    jar = a.build / 'CarPlayRouteGuidanceD1.jar'
    assert sha(jar.read_bytes()) == manifest['jar_sha256']
    for n, digest in manifest['sources'].items(): assert sha((HERE / 'bridge' / n).read_bytes()) == digest, 'Rebuild changed source'
    command = [str(a.java_home / 'bin/java'), '-Xverify:all', '-cp', ':'.join(str(x.resolve()) for x in (a.build / 'tests', jar, a.stock_jar)), 'com.cpmap.rgi.TestLive']

    def java(*args, text=None, success=True):
        result = subprocess.run(command + list(args), input=text, capture_output=True, text=True)
        assert (result.returncode == 0) == success, 'Unexpected Java runtime result (input suppressed)'
        return result.stdout

    report = json.loads(java())
    vectors = list(itertools.product(range(55), [None, 0, 1, 2], [None, 0, 1, 2],
                                    [None, -1000, -181, -180, -113, -90, -68, -67, -23, -22, -1, 0, 1, 22, 23, 67, 68, 90, 113, 180, 181, 1000]))
    lines = java('vectors', text=''.join(','.join('x' if v is None else str(v) for v in row) + '\n' for row in vectors)).splitlines()
    for row, line in zip(vectors, lines, strict=True):
        record = {k: v for k, v in zip(('type', 'junction_type', 'driving_side', 'exit_angle'), row) if v is not None}
        d = map_maneuver(record)['descriptor'] or empty_descriptor()
        assert line == f"{d['main_element']},{d['direction']}", 'Mapping parity'
    report['mapping_vectors'] = len(vectors)
    with tempfile.TemporaryDirectory(prefix='rgi-d1-runtime-') as temp:
        path = Path(temp) / 'synthetic.rgj'

        def parity(data):
            frames = []
            rgi_bridge.replay(io.BytesIO(data), simulate_owner=True, include_private=True, emit=frames.append)
            path.write_bytes(data)
            rows = [list(map(int, line.split(','))) for line in java('replay', str(path)).splitlines()]
            for number, (frame, row) in enumerate(zip(frames, rows, strict=True)):
                active = frame['action'] == 'publish'
                assert active == bool(row[1]), f'Lifecycle parity at observation {number}'
                if active:
                    d = frame['payload']['maneuvers'][0]; distance = frame['payload']['distance']
                    assert row[2:4] == [d['main_element'], d['direction']], f'Descriptor parity at observation {number}'
                    assert row[4] == (distance['meters'] if distance['valid'] else -1), f'Distance parity at observation {number}'
                    for column, key, field in ((5,'destination_distance','meters'), (6,'remaining_time','seconds')):
                        metric = frame['payload'][key]
                        assert row[column] == (metric[field] if metric['valid'] else -1), f'Trip metric parity at observation {number}'
            # Attaching to an already-written journal must never replay it live.
            old = java('replay', str(path), 'bootstrap').splitlines()
            assert all(line.split(',')[1] == '0' for line in old), 'Old journal bootstrap must not publish'
            return len(rows)

        def snapshot(events, **kw): return f.record(payload=f.compact(f.f.snapshot(events, **kw)))
        events = f.guiding()
        first = f.f.snapshot(events)
        records = [snapshot([]), f.record(at=100, payload=f.compact(first))]
        for seq, payload in [(4, f.route(distance=0)), (5, f.route(head=9, distance=500)),
                             (6, f.route(state=0)), (7, f.route(state=1, distance=1))]:
            events.append((seq, 0x5201, payload)); records.append(f.record(at=seq*100, payload=f.compact(f.f.snapshot(events))))
        records.append(f.record(5, 1000))
        report['synthetic_lifecycle_observations'] = parity(f.journal(*records))
        # Trip values are independent of the maneuver head, require observed
        # post-baseline updates, and must not cross stop/reroute/new episodes.
        events = []; records = [snapshot([])]
        cases = [(1,1,12345,3661), (1,2,None,None), (1,2,0,0), (1,2,0xffffffff,0xffffffffffffffff),
                 (0,2,800,120), (1,3,None,None), (1,3,1000,359940), (3,3,2000,60), (1,4,None,None)]
        for seq,(state,head,remaining,seconds) in enumerate(cases,1):
            payload=f.route(head=head,state=state)
            if remaining is not None: payload += f.f.tlv(7,remaining.to_bytes(4,'big'))
            if seconds is not None: payload += f.f.tlv(6,seconds.to_bytes(8,'big'))
            events.append((seq,0x5201,payload)); records.append(snapshot(events, last=seq))
            # snapshot() defaults to at=0, so all deltas share a valid timestamp.
        records.append(f.record(5,100))
        report['trip_lifecycle_observations'] = parity(f.journal(*records))
        report['fragmented_append'] = json.loads(java('fragment', str(path), str(Path(temp) / 'growing.rgj')))
        # Deterministic delta/cache stress, wraparound, stops, loading, arrival,
        # foreign components, distance overflow and absent/generic geometry.
        rng = random.Random(1427); events = []; records = [snapshot([])]
        for seq in range(1, 601):
            head = rng.randrange(40)
            if seq % 3:
                payload = f.route(head=head, distance=rng.choice([None, 0, 1, 100, 0x80000000]), state=rng.choice([1, 1, 1, 0, 2, 3, 4, 5, 6]))
                if seq % 31 == 0: payload = payload.replace(b'\x00\x10', b'\x00\x20', 1)
                mid = 0x5201
            else:
                payload = f.maneuver(index=head, kind=rng.randrange(55), angle=rng.choice([None, 0, -1, 90, -90, 1000])); mid = 0x5202
            events.append((seq, mid, payload))
            records.append(f.record(at=seq*100, payload=f.compact(f.f.snapshot(events[-16:], last=seq))))
        records.append(f.record(5, 60100))
        report['delta_stress_observations'] = parity(f.journal(*records))
        # Malformed final events, scalar widths, duplicate/empty components,
        # text/UTF8, history changes, reserved fields and record bounds.
        component = f.f.tlv(0, b'\0\x10')
        invalid = [component + f.f.tlv(1, b'\0\1'), component + f.f.tlv(1, b'\1')*2,
                   f.f.tlv(0, b''), f.f.tlv(0, b'\0\x10\0\x10'), component + f.f.tlv(3, b'\xff'),
                   component + f.f.tlv(3, b'a\0b'), component + f.f.tlv(3, b'\xed\xa0\x80'),
                   component + f.f.tlv(13, b'\0'), b'\0\3\0\1']
        rejected = 0
        for payload in invalid:
            blob = f.f.snapshot([(1, 0x5201, f.route(state=0)), (2, 0x5201, payload)])
            path.write_bytes(f.journal(f.record(payload=f.compact(blob)), f.record(5, 100)))
            java('replay', str(path), success=False); rejected += 1
        changed = bytearray(first); changed[48] = 1
        bad_envelopes = [f.compact(changed), f.compact(first) + b'\0']
        for payload in bad_envelopes:
            path.write_bytes(f.journal(f.record(payload=payload), f.record(5, 100)))
            java('replay', str(path), success=False); rejected += 1
        changed = f.f.snapshot([(1, 0x5201, f.route()), (2, 0x5202, f.maneuver(kind=1)), (3, 0x5201, f.route(distance=100))])
        path.write_bytes(f.journal(f.record(payload=f.compact(first)), f.record(at=100, payload=f.compact(changed)), f.record(5, 200)))
        java('replay', str(path), success=False); rejected += 1
        report['malformed_inputs_rejected'] = rejected
        private = []
        for variable in ('CPMAP_PRIVATE_C4_DIR', 'CPMAP_PRIVATE_C4_2_DIR'):
            if not os.environ.get(variable): continue
            capture = Path(os.environ[variable]) / 'events.rgj'; data = capture.read_bytes()
            private.append({'input_sha256': sha(data), 'observations_matched': parity(data)})
        for capture in a.private_journal:
            data=capture.read_bytes()
            private.append({'input_sha256':sha(data), 'observations_matched':parity(data)})
        report['private_replays'] = private
    report.update(jar_sha256=manifest['jar_sha256'], source_id=manifest['source_id'], passed=True,
                  test_sha256=sha(Path(__file__).read_bytes()), builder_sha256=sha((HERE / 'build-live-bridge.py').read_bytes()))
    (a.build / 'runtime-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__': main()
