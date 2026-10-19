"""Conservative iAP2 -> MU1427 MQBAB2 maneuver projection (host only).

SPDX-License-Identifier: GPL-3.0-or-later
Protocol/type families and angle quantization adapted from luka-dev/
mib2q-carplay-rgi, dfafccf6637ad45457085f0977f18cd7f64ab3ed,
Copyright (c) 2026 LuKa (@LuKa_dev). Native main elements are independently
checked against the factory MU1427 serializer; see NATIVE-BRIDGE.md.
"""
from enum import IntEnum


class Main(IntEnum):
    NO_SYMBOL = 0
    NO_INFO = 1
    ARRIVED = 3
    FOLLOW_STREET = 11
    CHANGE_LANE = 12
    TURN = 13
    ROUNDABOUT_RIGHT = 21
    ROUNDABOUT_LEFT = 22
    UTURN = 25
    EXIT_ROUNDABOUT_RIGHT = 26
    EXIT_ROUNDABOUT_LEFT = 27


class Direction(IntEnum):
    STRAIGHT = 0
    SLIGHT_LEFT = 32
    LEFT = 64
    SHARP_LEFT = 96
    UTURN = 128
    SHARP_RIGHT = 160
    RIGHT = 192
    SLIGHT_RIGHT = 224


def empty_descriptor():
    return {'main_element': 0, 'direction': 0, 'z_level': 0, 'side_streets': []}


def _angle_status(record):
    if 'exit_angle' not in record:
        return 'absent'
    angle = record['exit_angle']
    if type(angle) is not int or not -32768 <= angle <= 32767:
        return 'invalid'
    if angle in (-1000, 1000):
        return 'sentinel'
    return 'known' if -180 <= angle <= 180 else 'out_of_range'


def _turn_direction(angle):
    magnitude = abs(angle)
    if magnitude <= 22: return Direction.STRAIGHT
    if magnitude <= 67: return Direction.SLIGHT_LEFT if angle < 0 else Direction.SLIGHT_RIGHT
    if magnitude <= 112: return Direction.LEFT if angle < 0 else Direction.RIGHT
    return Direction.SHARP_LEFT if angle < 0 else Direction.SHARP_RIGHT


def _roundabout_direction(angle):
    # Integer nearest-bin selection, ties toward the higher angle. No clamping
    # of unknown/sentinel geometry; caller has already checked [-180, 180].
    index = ((angle + 180) * 4 + 45) // 90
    return (128, 112, 96, 80, 64, 48, 32, 16, 0,
            240, 224, 208, 192, 176, 160, 144, 128)[index]


def map_maneuver(record):
    """Return a detached descriptor or an explicit unavailable reason.

    An exit number cannot establish a physical exit angle. Directional types
    can establish left/right without an angle; generic types cannot. All
    side-street/lane rendering and z-level inference are intentionally absent.
    """
    record = record if isinstance(record, dict) else {}
    kind = record.get('type')
    geometry = _angle_status(record)
    result = {'status': 'unavailable', 'reason': 'type_unknown',
              'wire_type': kind if type(kind) is int and 0 <= kind <= 255 else None,
              'angle_status': geometry, 'exit_number': None, 'descriptor': None}

    def unavailable(reason):
        return {**result, 'reason': reason}

    def mapped(main, direction, basis):
        return {**result, 'status': 'mapped', 'reason': basis,
                'descriptor': {**empty_descriptor(), 'main_element': int(main),
                               'direction': int(direction)}}

    if type(kind) is not int or not 0 <= kind <= 53:
        return result
    # These types carry their meaning independently of junction geometry.
    if kind in (0, 5, 15, 17):
        return mapped(Main.FOLLOW_STREET, Direction.STRAIGHT, 'explicit_type')
    if kind in (10, 12, 27):
        return mapped(Main.ARRIVED, Direction.STRAIGHT, 'explicit_type')
    if kind in (52, 53):
        return mapped(Main.CHANGE_LANE, Direction.LEFT if kind == 52 else Direction.RIGHT, 'explicit_type')
    if kind in (11, 16, 51):
        if geometry != 'known': return unavailable('exit_angle_' + geometry)
        return mapped(Main.TURN, _turn_direction(record['exit_angle']), 'exit_angle')

    junction = record.get('junction_type')
    if type(junction) is not int or junction not in (0, 1):
        return unavailable('junction_unknown')
    side = record.get('driving_side')
    side_known = type(side) is int and side in (0, 1)
    if kind == 6:
        if not side_known: return unavailable('driving_side_unknown')
        return mapped(Main.TURN, Direction.LEFT if side else Direction.RIGHT, 'traffic_side')
    if kind == 19 or kind == 7 or 28 <= kind <= 46:
        if junction != 1: return unavailable('junction_conflict')
        if not side_known: return unavailable('driving_side_unknown')
        if kind == 7:
            return mapped(Main.EXIT_ROUNDABOUT_LEFT if side else Main.EXIT_ROUNDABOUT_RIGHT,
                          Direction.LEFT if side else Direction.RIGHT, 'explicit_exit_and_traffic_side')
        main = Main.ROUNDABOUT_LEFT if side else Main.ROUNDABOUT_RIGHT
        if kind == 19: return mapped(main, Direction.UTURN, 'explicit_uturn_and_traffic_side')
        result['exit_number'] = kind - 27
        if geometry != 'known': return unavailable('exit_angle_' + geometry)
        return mapped(main, _roundabout_direction(record['exit_angle']), 'exit_angle_and_traffic_side')
    if junction != 0:
        return unavailable('junction_conflict')
    if kind in (24, 25):
        return mapped(Main.ARRIVED, Direction.LEFT if kind == 24 else Direction.RIGHT, 'explicit_type')

    fixed = {1: Direction.LEFT, 2: Direction.RIGHT, 3: Direction.STRAIGHT,
             13: Direction.SLIGHT_LEFT, 14: Direction.SLIGHT_RIGHT,
             20: Direction.LEFT, 21: Direction.RIGHT,
             22: Direction.SLIGHT_LEFT, 23: Direction.SLIGHT_RIGHT,
             47: Direction.SHARP_LEFT, 48: Direction.SHARP_RIGHT,
             49: Direction.SLIGHT_LEFT, 50: Direction.SLIGHT_RIGHT}
    if kind in fixed:
        direction = fixed[kind]
        # Refine end-of-road types only with consistent, real signed geometry.
        if kind in (20, 21) and geometry == 'known':
            angle = record['exit_angle']
            if kind == 20 and angle < 0 or kind == 21 and angle > 0:
                magnitude = abs(angle)
                if magnitude <= 67:
                    direction = Direction.SLIGHT_LEFT if kind == 20 else Direction.SLIGHT_RIGHT
                elif magnitude > 112:
                    direction = Direction.SHARP_LEFT if kind == 20 else Direction.SHARP_RIGHT
        return mapped(Main.TURN, direction, 'explicit_type')
    if kind in (4, 18, 26):
        if geometry == 'known' and record['exit_angle']:
            direction = Direction.LEFT if record['exit_angle'] < 0 else Direction.RIGHT
            return mapped(Main.UTURN, direction, 'exit_angle')
        if not side_known: return unavailable('driving_side_unknown')
        return mapped(Main.UTURN, Direction.RIGHT if side else Direction.LEFT, 'traffic_side')
    if kind in (8, 9):
        if geometry != 'known' or not record['exit_angle']:
            return unavailable('ramp_side_unknown')
        return mapped(Main.TURN, Direction.SLIGHT_LEFT if record['exit_angle'] < 0
                      else Direction.SLIGHT_RIGHT, 'exit_angle')
    return unavailable('type_unhandled')
