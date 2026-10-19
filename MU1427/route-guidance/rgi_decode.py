#!/usr/bin/env python3
"""Offline MU1427 B2 guidance decoder, bounded state cache and log replay.

SPDX-License-Identifier: GPL-3.0-or-later
Protocol field layout/reference cache semantics adapted from
luka-dev/mib2q-carplay-rgi (dfafccf6637ad45457085f0977f18cd7f64ab3ed),
Copyright (c) 2026 LuKa (@LuKa_dev), GPL-3.0-or-later.
This host-side model does not run in the driver or write PPS/HMI objects.
"""
from __future__ import annotations

import argparse
from collections import Counter, OrderedDict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import BinaryIO

MAX_PAYLOAD = 65535 - 6
MAX_TLVS = 256
MAX_COMPONENTS = 8
MAX_ORDER = 16
MAX_ANGLES = 16
MAX_CACHE = 32
MAX_LOG_LINE = 256 * 1024
PHASES = {0: "stopped", 1: "guiding", 2: "arrived", 3: "loading",
          4: "locating", 5: "rerouting", 6: "proceed_to_route"}

# (name, encoding, maximum text bytes or list entries). Scalars require EXACT
# widths. Unknown fields remain opaque and cannot change known field values.
ROUTE = {
    0: ("components", "u16s", MAX_COMPONENTS),
    1: ("route_state", "u8", 0), 2: ("maneuver_state", "u8", 0),
    3: ("current_road", "text", 256), 4: ("destination", "text", 256),
    5: ("eta_seconds", "u64", 0), 6: ("remaining_seconds", "u64", 0),
    7: ("remaining_meters", "u32", 0), 8: ("remaining_display", "text", 64),
    9: ("remaining_units", "u8", 0), 10: ("maneuver_meters", "u32", 0),
    11: ("maneuver_display", "text", 64), 12: ("maneuver_units", "u8", 0),
    13: ("maneuver_order", "u16s", MAX_ORDER), 14: ("maneuver_count", "u16", 0),
    15: ("visible_in_app", "u8", 0), 16: ("lane_index", "u16", 0),
    17: ("lane_count", "u16", 0), 18: ("lane_showing", "u8", 0),
    19: ("source_name", "text", 64), 20: ("source_supports_guidance", "u8", 0),
}
MANEUVER = {
    0: ROUTE[0], 1: ("index", "u16", 0), 2: ("description", "text", 256),
    3: ("type", "u8", 0), 4: ("after_road", "text", 256),
    5: ("between_meters", "u32", 0), 6: ("between_display", "text", 64),
    7: ("between_units", "u8", 0), 8: ("driving_side", "u8", 0),
    9: ("junction_type", "u8", 0), 10: ("junction_angles", "i16s", MAX_ANGLES),
    11: ("exit_angle", "i16", 0), 12: ("linked_lane_index", "u16", 0),
    13: ("exit_info", "text", 256),
}
LANE = {
    0: ROUTE[0], 1: ("index", "u16", 0),
    # No on-unit 5204 sample yet: validate the nested TLV envelope, preserve
    # the information, and deliberately do not invent lane geometry.
    2: ("information", "nested", 0), 3: ("description", "text", 256),
}
SCHEMAS = {0x5201: ROUTE, 0x5202: MANEUVER, 0x5204: LANE}


class DecodeError(ValueError):
    """Messages contain structural facts only, never input strings/bytes."""


@dataclass(frozen=True)
class TLV:
    identifier: int
    value: bytes


@dataclass(frozen=True)
class Message:
    identifier: int
    fields: dict
    unknown: tuple[TLV, ...]


def tlvs(payload: bytes) -> tuple[TLV, ...]:
    if len(payload) > MAX_PAYLOAD:
        raise DecodeError("payload exceeds control-message limit")
    result = []
    pos = 0
    while pos < len(payload):
        if len(payload) - pos < 4:
            raise DecodeError("incomplete TLV header")
        size = int.from_bytes(payload[pos:pos + 2], "big")
        if size < 4 or size > len(payload) - pos:
            raise DecodeError("invalid TLV length")
        if len(result) == MAX_TLVS:
            raise DecodeError("too many TLVs")
        result.append(TLV(int.from_bytes(payload[pos + 2:pos + 4], "big"),
                          payload[pos + 4:pos + size]))
        pos += size
    return tuple(result)


def _value(raw: bytes, kind: str, limit: int):
    widths = {"u8": 1, "u16": 2, "i16": 2, "u32": 4, "u64": 8}
    if kind in widths:
        if len(raw) != widths[kind]:
            raise DecodeError("invalid scalar width")
        return int.from_bytes(raw, "big", signed=kind == "i16")
    if kind in ("u16s", "i16s"):
        if len(raw) % 2 or len(raw) // 2 > limit:
            raise DecodeError("invalid or oversized 16-bit list")
        return tuple(int.from_bytes(raw[i:i + 2], "big", signed=kind == "i16s")
                     for i in range(0, len(raw), 2))
    if kind == "nested":
        return tlvs(raw)
    if kind == "text":
        if len(raw) > limit:
            raise DecodeError("text exceeds declared bound")
        # Accept empty values and one trailing C terminator. Reject embedded
        # terminators, invalid UTF-8 and controls; preserve Unicode/newlines
        # without choosing the future HMI's display formatting.
        raw = raw[:-1] if raw.endswith(b"\0") else raw
        try:
            value = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise DecodeError("invalid UTF-8 text") from None
        if any(ord(c) < 32 and c not in "\r\n\t" or 127 <= ord(c) < 160 for c in value):
            raise DecodeError("invalid text control character")
        return value
    raise AssertionError("unknown schema encoding")


def decode_payload(identifier: int, payload: bytes) -> Message:
    """Decode a complete B2 hook payload atomically; lengths include TLV headers.

    Presence is membership in fields. Zero/empty remain real values. Repeated
    junction-angle and lane-information TLVs are ordered; all other known
    duplicate fields are ambiguous and rejected. Unknown extensions are kept.
    """
    if identifier not in SCHEMAS:
        raise DecodeError("unsupported guidance message ID")
    fields = {}
    unknown = []
    for item in tlvs(payload):
        spec = SCHEMAS[identifier].get(item.identifier)
        if spec is None:
            unknown.append(item)
            continue
        name, kind, limit = spec
        value = _value(item.value, kind, limit)
        repeated = name in ("junction_angles", "information")
        if name in fields and not repeated:
            raise DecodeError("duplicate known scalar/list field")
        if repeated:
            value = fields.get(name, ()) + value
            if len(value) > (MAX_ANGLES if name == "junction_angles" else MAX_TLVS):
                raise DecodeError("too many repeated field values")
        fields[name] = value
    components = fields.get("components", ())
    if not components or len(set(components)) != len(components):
        raise DecodeError("missing, empty or duplicate component identifiers")
    if identifier != 0x5201 and "index" not in fields:
        raise DecodeError("missing indexed-update identifier")
    return Message(identifier, fields, tuple(unknown))


def decode_frame(frame: bytes) -> Message:
    """Decode a semantic 4040 control frame (not an FF5A link packet)."""
    if len(frame) < 6 or frame[:2] != b"@@" or int.from_bytes(frame[2:4], "big") != len(frame):
        raise DecodeError("invalid semantic control frame")
    return decode_payload(int.from_bytes(frame[4:6], "big"), frame[6:])


def _json_value(value):
    if isinstance(value, TLV):
        return {"id": value.identifier, "hex": value.value.hex()}
    if isinstance(value, dict):
        return {k: _json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(v) for v in value]
    return value


class GuidanceCache:
    """One configured component; no buffer allocation using wire indices/counts.

    Route messages are deltas. Indexed maneuver/lane messages replace their
    previous record (as in the reference hook); an omitted angle stays absent.
    Explicit state zero clears immediately; presentation debounce is deferred.
    """

    def __init__(self, component: int = 0x10, capacity: int = MAX_CACHE):
        if not 0 <= component <= 65535 or not 1 <= capacity <= MAX_CACHE:
            raise ValueError("invalid component or cache capacity")
        self.component = component
        self.capacity = capacity
        self.session = 0
        self.generation = 0
        self.route = {}
        self.maneuvers = OrderedDict()
        self.lanes = OrderedDict()

    def reset_session(self):
        """Call on a new identification/start or transport disconnect."""
        self.session += 1
        self._invalidate(keep_source=False)

    def _invalidate(self, keep_source=True):
        source = {k: v for k, v in self.route.items()
                  if keep_source and k in ("source_name", "source_supports_guidance")}
        self.route = source
        self.maneuvers.clear()
        self.lanes.clear()
        self.generation += 1

    @property
    def current_index(self):
        order = self.route.get("maneuver_order", ())
        return order[0] if order else None

    @property
    def current_maneuver(self):
        # Never select an unrelated cached record when the head is missing.
        if self.route.get("route_state") not in (1, 6):
            return None
        return self.maneuvers.get(self.current_index)

    def _put(self, cache, index, record, head, preferred):
        if index not in cache and len(cache) == self.capacity:
            candidates = [key for key in cache if key != head]
            if not candidates:
                return False
            # Evict the oldest entry outside the active list first, then its
            # furthest lookahead. The currently selected index is protected.
            victim = next((key for key in candidates if key not in preferred), None)
            if victim is None:
                victim = max(candidates, key=lambda key: preferred.index(key))
            del cache[victim]
        cache[index] = dict(record)
        cache.move_to_end(index)
        return True

    def apply(self, message: Message) -> bool:
        """Apply an already validated message. False means foreign/inactive/full.

        Use decode_payload/decode_frame to construct Message; malformed input
        is rejected before this method and cannot partially mutate the cache.
        """
        fields = dict(message.fields)
        if self.component not in fields.pop("components"):
            return False
        if message.identifier != 0x5201:
            if self.route.get("route_state") not in (1, 3, 4, 5, 6):
                return False
            if message.identifier == 0x5202:
                order = self.route.get("maneuver_order", ())
                return self._put(self.maneuvers, fields["index"], fields,
                                 self.current_index, order)
            index = self.route.get("lane_index")
            return self._put(self.lanes, fields["index"], fields, index,
                             (index,) if index is not None else ())

        old_state = self.route.get("route_state")
        state = fields.get("route_state", old_state)
        source_changed = ("source_name" in fields and "source_name" in self.route
                          and fields["source_name"] != self.route["source_name"])
        destination_changed = (bool(fields.get("destination")) and bool(self.route.get("destination"))
                               and fields["destination"] != self.route["destination"])
        new_episode = state not in (None, 0) and old_state in (None, 0)
        restart = state in (3, 5) and old_state not in (None, 0, state)
        unknown_state = state is not None and state not in PHASES
        if (state == 0 and old_state != 0 or new_episode or restart
                or source_changed or destination_changed or unknown_state):
            self._invalidate(keep_source=not source_changed)
        if state == 0 or state is None or unknown_state:
            # Stop/reset frames can still carry stale route values. Accept
            # source metadata but do not let later state-less deltas revive it.
            fields = {k: v for k, v in fields.items()
                      if k in ("source_name", "source_supports_guidance")}
        if state is not None:
            self.route["route_state"] = state
        self.route.update(fields)
        if state == 2:
            self.maneuvers.clear()
            self.lanes.clear()
        return True

    def snapshot(self, include_private=False):
        state = self.route.get("route_state")
        public_route = {"route_state", "maneuver_state", "remaining_units", "maneuver_units",
                        "maneuver_order", "maneuver_count", "visible_in_app", "lane_index",
                        "lane_count", "lane_showing", "source_supports_guidance"}
        public_maneuver = {"index", "type", "driving_side", "junction_type", "junction_angles",
                           "exit_angle", "linked_lane_index", "between_units"}
        current = self.current_maneuver
        if state not in (1, 6):
            selection = "inactive"
        elif "maneuver_order" not in self.route:
            selection = "order_absent"
        elif not self.route["maneuver_order"]:
            selection = "order_empty"
        elif current is None:
            selection = "head_not_cached"
        else:
            selection = "head_cached"
        out = {"component": self.component, "session": self.session, "generation": self.generation,
               "phase": PHASES.get(state, "unknown"), "active": state in (1, 6),
               "route": {k: v for k, v in self.route.items() if include_private or k in public_route},
               "current_index": self.current_index,
               "current_maneuver_status": selection,
               "current_maneuver": None if current is None else {
                   k: v for k, v in current.items() if include_private or k in public_maneuver},
               "cached_indices": list(self.maneuvers), "cached_lane_indices": list(self.lanes)}
        if include_private:
            out["maneuvers"] = dict(self.maneuvers)
            out["lanes"] = dict(self.lanes)
        return _json_value(out)


START = re.compile(rb"CPMAP_RGI_START B[234] 0x5200 rc=(-?\d+) \(0=queued\)")
RX = re.compile(rb"CPMAP_RGI_RX B[234] id=0x(520[124]) len=(\d+) \(TLVs follow\)")
ERRORS = (b"Invalid packet", b"Failed to send packet", b"No packets in receive list",
          b"IdentificationRejected")


def _hook_bytes(line: bytes, count: int) -> bytes:
    if not 0 <= count <= MAX_PAYLOAD:
        raise DecodeError("invalid hook payload length")
    width = max(0, count * 3 - 1)
    hexpart = line[:width]
    if count and not re.fullmatch(rb"[0-9a-fA-F]{2}(?: [0-9a-fA-F]{2})*", hexpart):
        raise DecodeError("incomplete or interleaved hook dump")
    tail = line[width:].strip()
    # driver_hexdump emits no newline. A stock TID message is usually glued
    # directly to the last byte; extra hex or unexpected text is an error.
    if tail and not tail.startswith(b"TID"):
        raise DecodeError("unexpected hook dump suffix")
    data = bytes.fromhex(hexpart.decode("ascii"))
    if len(data) != count:
        raise DecodeError("incomplete hook dump")
    return data


def replay(stream: BinaryIO, cache=None, emit=None, include_private=False):
    """Replay ONE cumulative B2 log; EOF preserves the last observed state.

    emit receives snapshots, never raw input. Do not concatenate overlapping
    C2 captures. Malformed records are counted, skipped atomically, and cause
    the CLI to exit nonzero. Input lines and error-detail storage are bounded.
    """
    cache = cache if cache is not None else GuidanceCache()
    counts = Counter()
    rejected = Counter()
    wire_errors = Counter()
    details = []
    line_number = 0
    pending = None
    start_count = 0
    failed_starts = 0
    transitions = Counter()

    def reject(line, error):
        rejected["malformed"] += 1
        if len(details) < 16:
            details.append({"line": line, "error": str(error)})

    while True:
        line = stream.readline(MAX_LOG_LINE + 1)
        if not line:
            break
        line_number += 1
        if len(line) > MAX_LOG_LINE:
            reject(line_number, DecodeError("log line exceeds bound"))
            pending = None
            # Consume the rest of this line with the same fixed read bound.
            while line and not line.endswith(b"\n"):
                line = stream.readline(MAX_LOG_LINE + 1)
            continue
        for error in ERRORS:
            wire_errors[error.decode()] += line.count(error)
        if pending is not None:
            identifier, size, marker_line = pending
            pending = None
            try:
                message = decode_payload(identifier, _hook_bytes(line.rstrip(b"\r\n"), size))
                before = cache.route.get("route_state")
                accepted = cache.apply(message)
                counts[f"0x{identifier:04x}"] += 1
                if not accepted:
                    rejected["foreign_inactive_or_capacity"] += 1
                after = cache.route.get("route_state")
                if after != before:
                    transitions[f"{before}->{after}"] += 1
                if emit is not None:
                    emit({"kind": "guidance", "line": marker_line, "id": f"0x{identifier:04x}",
                          "applied": accepted, "present": sorted(message.fields),
                          "unknown_ids": [item.identifier for item in message.unknown],
                          "state": cache.snapshot(include_private)})
            except DecodeError as error:
                reject(marker_line, error)
                # Still inspect this line for a new marker; a missing dump
                # must not silently swallow the next identification/start.
        start = START.search(line)
        if start:
            if len(start[1]) > 11:
                reject(line_number, DecodeError("invalid start return code"))
            else:
                cache.reset_session()
                start_count += 1
                failed_starts += int(start[1]) != 0
        marker = RX.search(line)
        if marker:
            if len(marker[2]) > 5:
                reject(line_number, DecodeError("invalid hook payload length"))
            else:
                pending = (int(marker[1], 16), int(marker[2]), line_number)
    if pending is not None:
        reject(pending[2], DecodeError("missing hook dump at EOF"))
    return {"kind": "summary", "decoded": dict(counts), "start_attempts": start_count,
            "failed_starts": failed_starts, "rejected": dict(rejected), "errors": details,
            "wire_errors": dict(wire_errors), "state_transitions": dict(transitions),
            "final": cache.snapshot(include_private)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="one C2 directory or one iap2.log")
    parser.add_argument("--events", action="store_true", help="emit per-message JSON snapshots too")
    parser.add_argument("--include-private", action="store_true",
                        help="include private route text, distances, times and opaque lane bytes")
    args = parser.parse_args()
    path = args.capture / "iap2.log" if args.capture.is_dir() else args.capture
    try:
        with path.open("rb") as stream:
            result = replay(stream, emit=(lambda event: print(json.dumps(event, ensure_ascii=False)))
                            if args.events else None, include_private=args.include_private)
    except OSError:
        parser.exit(2, "Cannot read the requested capture file.\n")
    print(json.dumps(result, indent=None if args.events else 2, ensure_ascii=False))
    return 1 if result["rejected"].get("malformed") else 0


if __name__ == "__main__":
    sys.exit(main())
