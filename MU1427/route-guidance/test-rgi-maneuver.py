#!/usr/bin/env python3
"""Synthetic mapping tests plus factory-ROM metadata checks; no private data."""
import json
from pathlib import Path
import unittest

from rgi_maneuver import Direction as D, Main, empty_descriptor, map_maneuver


def record(kind=2, **fields):
    return {'type': kind, 'junction_type': 0, 'driving_side': 0, **fields}


class MappingTests(unittest.TestCase):
    def pair(self, value):
        result = map_maneuver(value)
        self.assertEqual(result['status'], 'mapped')
        return result['descriptor']['main_element'], result['descriptor']['direction']

    def test_all_54_known_types_have_a_deliberate_mapping_with_complete_geometry(self):
        for kind in range(54):
            junction = 1 if kind in (7, 19) or 28 <= kind <= 46 else 0
            with self.subTest(kind=kind):
                result = map_maneuver(record(kind, junction_type=junction, exit_angle=90))
                self.assertEqual(result['status'], 'mapped')
                self.assertEqual(result['descriptor']['z_level'], 0)
                self.assertEqual(result['descriptor']['side_streets'], [])
                self.assertIn(result['descriptor']['main_element'], list(Main))

    def test_explicit_types_keep_left_right_slight_sharp_without_angles(self):
        for kind, direction in [(1, 64), (2, 192), (3, 0), (13, 32), (14, 224),
                                (47, 96), (48, 160), (49, 32), (50, 224),
                                (22, 32), (23, 224)]:
            with self.subTest(kind=kind): self.assertEqual(self.pair(record(kind)), (13, direction))

    def test_arrival_follow_ferry_and_lane_change_do_not_need_geometry(self):
        for kind, expected in [(0, (11, 0)), (5, (11, 0)), (15, (11, 0)), (17, (11, 0)),
                               (10, (3, 0)), (12, (3, 0)), (27, (3, 0)),
                               (52, (12, 64)), (53, (12, 192))]:
            with self.subTest(kind=kind): self.assertEqual(self.pair({'type': kind}), expected)
        self.assertEqual(self.pair(record(24)), (3, 64))
        self.assertEqual(self.pair(record(25)), (3, 192))

    def test_generic_missing_or_sentinel_angle_never_becomes_straight(self):
        for kind in (11, 16, 51):
            for fields in ({}, {'exit_angle': 1000}, {'exit_angle': -1000},
                           {'exit_angle': 181}, {'exit_angle': -32768}, {'exit_angle': True}):
                with self.subTest(kind=kind, fields=fields):
                    self.assertIsNone(map_maneuver(record(kind, **fields))['descriptor'])
        self.assertEqual(self.pair(record(11, exit_angle=0)), (13, 0))
        self.assertEqual(self.pair(record(11, exit_angle=-1)), (13, 0))

    def test_generic_quantization_boundaries(self):
        for angle, direction in [(22, 0), (23, 224), (67, 224), (68, 192),
                                 (112, 192), (113, 160), (-23, 32), (-68, 64), (-113, 96)]:
            self.assertEqual(self.pair(record(11, exit_angle=angle)), (13, direction))

    def test_uturn_prefers_signed_geometry_then_requires_known_traffic_side(self):
        for kind in (4, 18, 26):
            self.assertEqual(self.pair(record(kind, exit_angle=-1, driving_side=1)), (25, 64))
            self.assertEqual(self.pair(record(kind, exit_angle=90)), (25, 192))
            self.assertEqual(self.pair(record(kind)), (25, 64))
            self.assertEqual(self.pair(record(kind, driving_side=1)), (25, 192))
            self.assertIsNone(map_maneuver(record(kind, driving_side=255))['descriptor'])

    def test_roundabout_exit_number_does_not_invent_an_angle(self):
        result = map_maneuver(record(29, junction_type=1))
        self.assertEqual(result['exit_number'], 2)
        self.assertIsNone(result['descriptor'])
        self.assertEqual(self.pair(record(29, junction_type=1, exit_angle=0)), (21, 0))
        self.assertEqual(self.pair(record(46, junction_type=1, exit_angle=0)), (21, 0))
        self.assertEqual(self.pair(record(29, junction_type=1, exit_angle=-90, driving_side=1)), (22, 64))
        self.assertIsNone(map_maneuver(record(29, junction_type=0, exit_angle=0))['descriptor'])

    def test_roundabout_16_step_encoding_and_real_signed_angles(self):
        for angle, code in [(-180, 128), (-90, 64), (-12, 16), (-11, 0),
                            (0, 0), (11, 0), (12, 240), (90, 192), (180, 128)]:
            self.assertEqual(self.pair(record(28, junction_type=1, exit_angle=angle)), (21, code))
        for angle in (-1000, 1000, -181, 181):
            self.assertIsNone(map_maneuver(record(28, junction_type=1, exit_angle=angle))['descriptor'])

    def test_roundabout_exit_and_uturn_require_real_traffic_side(self):
        self.assertEqual(self.pair(record(7, junction_type=1)), (26, 192))
        self.assertEqual(self.pair(record(7, junction_type=1, driving_side=1)), (27, 64))
        self.assertEqual(self.pair(record(19, junction_type=1)), (21, 128))
        self.assertIsNone(map_maneuver(record(7, junction_type=1, driving_side=True))['descriptor'])

    def test_ambiguous_ramp_does_not_guess_side_from_traffic(self):
        for kind in (8, 9):
            for angle in (None, 0, 1000):
                fields = {} if angle is None else {'exit_angle': angle}
                self.assertIsNone(map_maneuver(record(kind, **fields))['descriptor'])
            self.assertEqual(self.pair(record(kind, exit_angle=-1)), (13, 32))
            self.assertEqual(self.pair(record(kind, exit_angle=1)), (13, 224))

    def test_end_of_road_direction_does_not_collapse_small_angle_to_straight(self):
        self.assertEqual(self.pair(record(20, exit_angle=-1)), (13, 32))
        self.assertEqual(self.pair(record(21, exit_angle=1)), (13, 224))
        self.assertEqual(self.pair(record(20, exit_angle=90)), (13, 64))
        self.assertEqual(self.pair(record(21, exit_angle=-90)), (13, 192))

    def test_unknown_types_and_junctions_cannot_reuse_a_previous_arrow(self):
        for kind in (None, True, -1, 54, 255, 'LEFT'):
            self.assertIsNone(map_maneuver(record(kind))['descriptor'])
        for junction in (None, True, 2, 255):
            self.assertIsNone(map_maneuver(record(1, junction_type=junction))['descriptor'])
        self.assertIsNone(map_maneuver(record(1, junction_type=1))['descriptor'])
        self.assertIsNone(map_maneuver(None)['descriptor'])

    def test_output_is_detached_and_contains_no_route_text(self):
        raw = record(1, description='PRIVATE', after_road='PRIVATE')
        first = map_maneuver(raw); first['descriptor']['side_streets'].append(90)
        self.assertEqual(map_maneuver(raw)['descriptor']['side_streets'], [])
        self.assertNotIn('PRIVATE', json.dumps(map_maneuver(raw)))
        self.assertEqual(empty_descriptor()['main_element'], 0)

    def test_native_constants_match_factory_rom_metadata(self):
        native = json.loads((Path(__file__).parent / 'MU1427-NATIVE-CONTRACT.json').read_text())
        fields = native['classes']['de/vw/mib/bap/mqbab2/generated/navsd/serializer/'
                                  'ManeuverDescriptor_Status$Maneuver_1']['fields']
        names = {'ROUNDABOUT_RIGHT': 'ROUNDABOUT_TRS_RIGHT', 'ROUNDABOUT_LEFT': 'ROUNDABOUT_TRS_LEFT',
                 'EXIT_ROUNDABOUT_RIGHT': 'EXIT_ROUNDABOUT_TRS_RIGHT',
                 'EXIT_ROUNDABOUT_LEFT': 'EXIT_ROUNDABOUT_TRS_LEFT'}
        for main in Main:
            self.assertEqual(fields['MAIN_ELEMENT_' + names.get(main.name, main.name)]['value'], int(main))
        pq = native['classes']['de/vw/mib/bap/mqbpq/navsd/functions/ManeuverDescriptor']['fields']
        self.assertEqual(pq['MANEUVER_DIRECTION_LEFT']['value'], int(D.LEFT))
        self.assertEqual(pq['MANEUVER_DIRECTION_RIGHT']['value'], int(D.RIGHT))


if __name__ == '__main__': unittest.main()
