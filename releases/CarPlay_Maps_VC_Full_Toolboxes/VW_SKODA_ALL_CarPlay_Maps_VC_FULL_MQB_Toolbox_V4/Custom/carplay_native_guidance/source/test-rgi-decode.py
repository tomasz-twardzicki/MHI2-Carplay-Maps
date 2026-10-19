#!/usr/bin/env python3
"""Synthetic protocol/state/lifecycle tests; no vehicle logs or route data."""
import io
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

import rgi_decode as rgi


def tlv(identifier, value):
    return (len(value) + 4).to_bytes(2, "big") + identifier.to_bytes(2, "big") + value


def number(identifier, value, width=1, signed=False):
    return tlv(identifier, value.to_bytes(width, "big", signed=signed))


def text(identifier, value):
    return tlv(identifier, value.encode() + b"\0")


def indices(identifier, *values):
    return tlv(identifier, b"".join(v.to_bytes(2, "big") for v in values))


def payload(*values, component=0x10):
    return number(0, component, 2) + b"".join(values)


def message(mid=0x5201, *values, component=0x10):
    return rgi.decode_payload(mid, payload(*values, component=component))


def hook(mid, data, tail=b"TID01 SEND(1): synthetic ACK\n"):
    return (f"CPMAP_RGI_RX B2 id=0x{mid:04x} len={len(data)} (TLVs follow)\n".encode()
            + data.hex(" ").upper().encode() + tail)


START = b"CPMAP_RGI_START B2 0x5200 rc=0 (0=queued)\n"


class DecodeTests(unittest.TestCase):
    def test_semantic_frame_big_endian_scalars_and_presence(self):
        body = payload(number(1, 1), number(5, 2**40 + 7, 8), number(6, 0, 8),
                       number(7, 123456, 4), indices(13, 300, 65535), number(14, 500, 2))
        frame = b"@@" + (len(body) + 6).to_bytes(2, "big") + b"\x52\x01" + body
        fields = rgi.decode_frame(frame).fields
        self.assertEqual(fields["eta_seconds"], 2**40 + 7)
        self.assertEqual(fields["remaining_seconds"], 0)
        self.assertEqual(fields["remaining_meters"], 123456)
        self.assertEqual(fields["maneuver_order"], (300, 65535))
        self.assertNotIn("current_road", fields)

    def test_utf8_empty_and_multiline_text_are_distinct_from_absence(self):
        fields = message(0x5201, text(3, ""), text(4, "Synthetic Łódź\nStop")).fields
        self.assertEqual(fields["current_road"], "")
        self.assertEqual(fields["destination"], "Synthetic Łódź\nStop")
        self.assertNotIn("source_name", fields)
        self.assertEqual(message(0x5201, tlv(3, b"")).fields["current_road"], "")

    def test_signed_repeated_angles_and_zero_preserved(self):
        man = message(0x5202, number(1, 7, 2), number(3, 30),
                      number(10, -90, 2, signed=True), number(10, 0, 2, signed=True),
                      number(11, -1, 2, signed=True)).fields
        self.assertEqual(man["junction_angles"], (-90, 0))
        self.assertEqual(man["exit_angle"], -1)
        self.assertNotIn("exit_angle", message(0x5202, number(1, 7, 2)).fields)

    def test_unknown_fields_are_opaque_and_do_not_override_known_fields(self):
        event = message(0x5201, number(1, 1), tlv(0x9999, b"future\x00value"))
        self.assertEqual(event.fields["route_state"], 1)
        self.assertEqual(event.unknown, (rgi.TLV(0x9999, b"future\x00value"),))

    def test_component_list_routes_multiple_receivers(self):
        event = rgi.decode_payload(0x5201, indices(0, 0x10, 0x20) + number(1, 1))
        self.assertEqual(event.fields["components"], (0x10, 0x20))

    def test_malformed_envelopes_and_short_scalar_rejected(self):
        cases = [b"\0", b"\0\x03\0\1", b"\0\x10\0\1\0",
                 payload(tlv(1, b"")), payload(tlv(5, b"\0" * 7)),
                 payload(tlv(7, b"\0" * 5)), payload(tlv(13, b"\0"))]
        for data in cases:
            with self.subTest(size=len(data)), self.assertRaises(rgi.DecodeError):
                rgi.decode_payload(0x5201, data)

    def test_invalid_semantic_header_or_id_rejected(self):
        for frame in (b"", b"FF5A00", b"@@\0\6\x52\x03", b"@@\0\7\x52\x01"):
            with self.subTest(frame=frame), self.assertRaises(rgi.DecodeError):
                rgi.decode_frame(frame)

    def test_missing_or_duplicate_component_or_index_rejected(self):
        for mid, data in [(0x5201, number(1, 1)), (0x5201, indices(0)),
                          (0x5201, indices(0, 16, 16)), (0x5202, payload(number(3, 1))),
                          (0x5204, payload()), (0x5201, payload(number(0, 16, 2)))]:
            with self.subTest(mid=mid), self.assertRaises(rgi.DecodeError):
                rgi.decode_payload(mid, data)

    def test_duplicate_known_scalar_and_order_rejected(self):
        for values in [(number(1, 0), number(1, 1)), (indices(13, 1), indices(13, 2))]:
            with self.subTest(values=values), self.assertRaises(rgi.DecodeError):
                message(0x5201, *values)

    def test_text_controls_utf8_and_overlong_strings_rejected(self):
        for raw in (b"\xff", b"a\0b", b"a\0\0", b"a\x1bb", b"x" * 257):
            with self.subTest(size=len(raw)), self.assertRaises(rgi.DecodeError):
                message(0x5201, tlv(4, raw))

    def test_message_and_list_bounds(self):
        for data in (b"x" * (rgi.MAX_PAYLOAD + 1), payload(indices(13, *range(17))),
                     payload(indices(0, *range(9))), payload(tlv(999, b"") * 256)):
            with self.subTest(size=len(data)), self.assertRaises(rgi.DecodeError):
                rgi.decode_payload(0x5201, data)
        with self.assertRaises(rgi.DecodeError):
            message(0x5202, number(1, 1, 2), *(number(10, 0, 2) for _ in range(17)))

    def test_lane_information_is_validated_but_kept_opaque(self):
        nested = number(0, 0, 2) + number(1, 1) + number(2, -90, 2, signed=True)
        event = message(0x5204, number(1, 100, 2), tlv(2, nested), text(3, "Synthetic lane"))
        self.assertEqual(event.fields["information"][2].value, b"\xff\xa6")
        with self.assertRaises(rgi.DecodeError):
            message(0x5204, number(1, 100, 2), tlv(2, b"\0\x03\0\x02"))


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.cache = rgi.GuidanceCache()

    def apply(self, mid=0x5201, *values, **kwargs):
        return self.cache.apply(message(mid, *values, **kwargs))

    def start(self, *values):
        self.apply(0x5201, number(1, 1), *values)

    def maneuver(self, index, kind=1, *values):
        return self.apply(0x5202, number(1, index, 2), number(3, kind), *values)

    def test_route_delta_preserves_missing_and_applies_empty_and_zero(self):
        self.start(text(4, "Synthetic destination"), number(10, 100, 4))
        self.apply(0x5201, number(10, 0, 4))
        self.assertEqual(self.cache.route["destination"], "Synthetic destination")
        self.assertEqual(self.cache.route["maneuver_meters"], 0)
        self.apply(0x5201, text(4, ""))
        self.assertEqual(self.cache.route["destination"], "")

    def test_visibility_zero_does_not_stop_guidance(self):
        self.start(indices(13, 2, 3), number(15, 0))
        self.maneuver(2)
        self.assertTrue(self.cache.snapshot()["active"])
        self.assertEqual(self.cache.current_maneuver["index"], 2)

    def test_selection_status_distinguishes_missing_empty_and_uncached_order(self):
        self.assertEqual(self.cache.snapshot()['current_maneuver_status'], 'inactive')
        self.start()
        self.maneuver(0)
        self.assertEqual(self.cache.snapshot()['current_maneuver_status'], 'order_absent')
        self.apply(0x5201, indices(13))
        self.assertEqual(self.cache.snapshot()['current_maneuver_status'], 'order_empty')
        self.apply(0x5201, indices(13, 1, 0))
        self.assertEqual(self.cache.snapshot()['current_maneuver_status'], 'head_not_cached')
        self.maneuver(1)
        self.assertEqual(self.cache.snapshot()['current_maneuver_status'], 'head_cached')
        self.apply(0x5201, number(1, 0))
        self.assertEqual(self.cache.snapshot()['current_maneuver_status'], 'inactive')

    def test_ordered_head_selected_instead_of_latest_update(self):
        self.start(indices(13, 2, 3))
        self.maneuver(2, 1)
        self.maneuver(3, 2)
        self.assertEqual(self.cache.current_maneuver["type"], 1)
        self.apply(0x5201, indices(13, 3, 2))
        self.assertEqual(self.cache.current_maneuver["type"], 2)

    def test_uncached_head_never_falls_back_to_another_maneuver(self):
        self.start(indices(13, 42, 3))
        self.maneuver(3)
        self.assertIsNone(self.cache.current_maneuver)
        self.maneuver(42, 2)
        self.assertEqual(self.cache.current_maneuver["type"], 2)

    def test_explicit_empty_order_hides_arrow_without_erasing_prefetch(self):
        self.start(indices(13, 1))
        self.maneuver(1)
        self.apply(0x5201, indices(13))
        self.assertIsNone(self.cache.current_maneuver)
        self.assertIn(1, self.cache.maneuvers)

    def test_state_only_stop_clears_route_maneuvers_and_lanes(self):
        self.start(indices(13, 0), text(4, "Synthetic destination"), text(19, "Synthetic app"))
        self.maneuver(0)
        self.apply(0x5204, number(1, 0, 2), tlv(2, number(0, 0, 2)))
        self.apply(0x5201, number(1, 0))
        self.assertEqual(self.cache.route, {"route_state": 0, "source_name": "Synthetic app"})
        self.assertFalse(self.cache.maneuvers)
        self.assertFalse(self.cache.lanes)
        self.assertIsNone(self.cache.current_maneuver)

    def test_stale_updates_cannot_revive_stopped_route(self):
        self.start(indices(13, 0))
        self.apply(0x5201, number(1, 0), text(4, "Synthetic stale destination"))
        self.assertFalse(self.maneuver(0))
        self.apply(0x5201, text(4, "Synthetic stale destination"), indices(13, 0))
        self.assertNotIn("destination", self.cache.route)
        self.assertFalse(self.cache.maneuvers)

    def test_loading_locating_rerouting_do_not_emit_current_arrow(self):
        for state in (3, 4, 5):
            self.apply(0x5201, number(1, state), indices(13, 1))
            self.assertTrue(self.maneuver(1))
            self.assertIsNone(self.cache.current_maneuver)
            self.apply(0x5201, number(1, 1))
            self.assertIsNotNone(self.cache.current_maneuver)

    def test_reroute_invalidates_old_index_but_keeps_new_prefetch(self):
        self.start(indices(13, 0))
        self.maneuver(0, 1)
        generation = self.cache.generation
        self.apply(0x5201, number(1, 5))
        self.assertGreater(self.cache.generation, generation)
        self.assertFalse(self.cache.maneuvers)
        self.maneuver(0, 2)
        self.apply(0x5201, number(1, 5))
        self.apply(0x5201, number(1, 1), indices(13, 0))
        self.assertEqual(self.cache.current_maneuver["type"], 2)

    def test_maneuver_record_replacement_drops_old_optional_angle(self):
        self.start(indices(13, 0))
        self.maneuver(0, 30, number(11, -90, 2, signed=True), text(4, "Synthetic road"))
        self.maneuver(0, 1)
        self.assertNotIn("exit_angle", self.cache.current_maneuver)
        self.assertNotIn("after_road", self.cache.current_maneuver)

    def test_explicit_zero_angle_is_not_missing(self):
        self.start(indices(13, 0))
        self.maneuver(0, 3, number(11, 0, 2))
        self.assertEqual(self.cache.current_maneuver["exit_angle"], 0)

    def test_foreign_component_never_changes_state(self):
        self.start(indices(13, 0))
        before = self.cache.snapshot(True)
        self.assertFalse(self.apply(0x5201, number(1, 0), component=0x20))
        self.assertFalse(self.apply(0x5202, number(1, 0, 2), component=0x20))
        self.assertEqual(self.cache.snapshot(True), before)

    def test_route_reset_and_session_reset_prevent_index_reuse(self):
        self.start(indices(13, 0))
        self.maneuver(0, 1)
        self.apply(0x5201, number(1, 0))
        self.start(indices(13, 0))
        self.assertIsNone(self.cache.current_maneuver)
        self.maneuver(0, 2)
        self.cache.reset_session()
        self.assertIsNone(self.cache.current_maneuver)
        self.assertEqual(self.cache.route, {})
        self.assertEqual(self.cache.session, 1)

    def test_source_or_destination_change_invalidates_reused_index(self):
        for field in (4, 19):
            self.start(indices(13, 0), text(field, "Synthetic A"))
            self.maneuver(0)
            self.apply(0x5201, text(field, "Synthetic B"))
            self.assertFalse(self.cache.maneuvers)
            self.assertIsNone(self.cache.current_maneuver)

    def test_source_change_does_not_inherit_old_app_capabilities(self):
        self.start(text(19, "Synthetic A"), number(20, 1))
        self.apply(0x5201, text(19, "Synthetic B"))
        self.assertEqual(self.cache.route["source_name"], "Synthetic B")
        self.assertNotIn("source_supports_guidance", self.cache.route)

    def test_arrival_and_unknown_states_hide_stale_arrow(self):
        for state in (2, 255):
            self.start(indices(13, 0))
            self.maneuver(0)
            self.apply(0x5201, number(1, state))
            self.assertIsNone(self.cache.current_maneuver)
            self.assertFalse(self.cache.maneuvers)
            self.assertFalse(self.maneuver(1))

    def test_large_wire_indices_and_counts_do_not_allocate_by_index(self):
        self.start(indices(13, 65535), number(14, 65535, 2))
        self.maneuver(65535)
        self.assertEqual(len(self.cache.maneuvers), 1)
        self.assertEqual(self.cache.current_maneuver["index"], 65535)

    def test_cache_pressure_preserves_head_and_prefers_active_lookahead(self):
        self.cache = rgi.GuidanceCache(capacity=3)
        self.start(indices(13, 0, 1))
        for index in (0, 1, 2, 3, 4): self.maneuver(index)
        self.assertEqual(set(self.cache.maneuvers), {0, 1, 4})
        for index in range(5, 1000): self.maneuver(index)
        self.assertEqual(len(self.cache.maneuvers), 3)
        self.assertIn(0, self.cache.maneuvers)
        self.assertIn(1, self.cache.maneuvers)

    def test_single_slot_never_evicts_head_and_can_fill_missing_head(self):
        self.cache = rgi.GuidanceCache(capacity=1)
        self.start(indices(13, 0, 1))
        self.maneuver(1)
        self.assertTrue(self.maneuver(0))
        self.assertFalse(self.maneuver(1))
        self.assertEqual(self.cache.current_maneuver["index"], 0)

    def test_lane_cache_bounded_and_showing_flag_does_not_create_geometry(self):
        self.cache = rgi.GuidanceCache(capacity=2)
        self.start(number(16, 0, 2), number(18, 1))
        self.assertFalse(self.cache.lanes)
        for index in range(10):
            self.apply(0x5204, number(1, index, 2), tlv(2, number(0, 0, 2)))
        self.assertEqual(len(self.cache.lanes), 2)
        self.assertIn(0, self.cache.lanes)

    def test_public_snapshot_omits_all_route_text_time_distance_and_opaque_bytes(self):
        self.start(text(4, "PRIVATE_DESTINATION"), text(19, "PRIVATE_SOURCE"),
                   number(5, 123456789, 8), number(7, 987654321, 4), indices(13, 0))
        self.maneuver(0, 2, text(2, "PRIVATE_MANEUVER"), text(4, "PRIVATE_ROAD"))
        public = json.dumps(self.cache.snapshot())
        for value in ("PRIVATE_", "123456789", "987654321"):
            self.assertNotIn(value, public)
        self.assertIn("PRIVATE_DESTINATION", json.dumps(self.cache.snapshot(True)))

    def test_invalid_capacity_rejected(self):
        for cap in (0, 33):
            with self.assertRaises(ValueError): rgi.GuidanceCache(capacity=cap)


class ReplayTests(unittest.TestCase):
    def test_glued_tid_native_printer_not_double_counted_and_eof_keeps_active(self):
        body = payload(number(1, 1), indices(13, 2))
        log = START + b"TID01 --?-- [msgid=5201] CTRL[synthetic native dump]\n" + hook(0x5201, body)
        result = rgi.replay(io.BytesIO(log))
        self.assertEqual(result["decoded"], {"0x5201": 1})
        self.assertFalse(result["rejected"])
        self.assertTrue(result["final"]["active"])
        for revision in (b' B3 ', b' B4 '):
            self.assertEqual(rgi.replay(io.BytesIO(log.replace(b' B2 ', revision))), result)

    def test_stopped_session_full_lifecycle_and_reconnect(self):
        log = START + hook(0x5201, payload(number(1, 1), indices(13, 2)))
        log += hook(0x5202, payload(number(1, 2, 2), number(3, 2)))
        log += hook(0x5201, payload(number(1, 0)))
        log += START + hook(0x5201, payload(number(1, 1), indices(13, 2)))
        result = rgi.replay(io.BytesIO(log))
        self.assertEqual(result["start_attempts"], 2)
        self.assertEqual(result["final"]["session"], 2)
        self.assertIsNone(result["final"]["current_maneuver"])

    def test_truncated_and_interleaved_dump_does_not_mutate_state(self):
        for suffix in (b"", b"00 06 TID01 interleaved\n", b"zz\n"):
            cache = rgi.GuidanceCache()
            cache.apply(message(0x5201, number(1, 1), text(4, "Synthetic destination")))
            before = cache.snapshot(True)
            marker = b"CPMAP_RGI_RX B2 id=0x5201 len=11 (TLVs follow)\n"
            result = rgi.replay(io.BytesIO(marker + suffix), cache)
            self.assertEqual(result["rejected"]["malformed"], 1)
            self.assertEqual(cache.snapshot(True), before)

    def test_valid_prefix_then_malformed_tlv_is_atomic(self):
        cache = rgi.GuidanceCache()
        cache.apply(message(0x5201, number(1, 1)))
        before = cache.snapshot(True)
        bad = payload(number(1, 0), b"\0\xff\0\4")
        result = rgi.replay(io.BytesIO(hook(0x5201, bad)), cache)
        self.assertEqual(result["rejected"]["malformed"], 1)
        self.assertEqual(cache.snapshot(True), before)

    def test_missing_dump_does_not_swallow_new_start_marker(self):
        log = (b"CPMAP_RGI_RX B2 id=0x5201 len=11 (TLVs follow)\n" + START
               + hook(0x5201, payload(number(1, 1))))
        result = rgi.replay(io.BytesIO(log))
        self.assertEqual(result["rejected"]["malformed"], 1)
        self.assertEqual(result["start_attempts"], 1)
        self.assertEqual(result["decoded"], {"0x5201": 1})

    def test_oversized_lines_and_error_detail_storage_bounded(self):
        bad = hook(0x5201, payload(number(1, 1)), tail=b"BAD_SUFFIX\n")
        log = b"X" * (rgi.MAX_LOG_LINE + 5) + b"\n" + bad * 100
        result = rgi.replay(io.BytesIO(log))
        self.assertEqual(result["rejected"]["malformed"], 101)
        self.assertEqual(len(result["errors"]), 16)

    def test_no_newline_at_eof_after_complete_payload(self):
        result = rgi.replay(io.BytesIO(hook(0x5201, payload(number(1, 1)), tail=b"")))
        self.assertFalse(result["rejected"])

    def test_numeric_marker_lengths_bounded_before_integer_conversion(self):
        huge = b"9" * 5000
        log = (b"CPMAP_RGI_RX B2 id=0x5201 len=" + huge + b" (TLVs follow)\n"
               + b"CPMAP_RGI_START B2 0x5200 rc=" + huge + b" (0=queued)\n")
        result = rgi.replay(io.BytesIO(log))
        self.assertEqual(result["rejected"]["malformed"], 2)

    def test_failed_start_and_wire_error_counts(self):
        log = START.replace(b"rc=0", b"rc=-1") + b"Invalid packet\nFailed to send packet\n"
        result = rgi.replay(io.BytesIO(log))
        self.assertEqual(result["failed_starts"], 1)
        self.assertEqual(result["wire_errors"]["Invalid packet"], 1)

    def test_default_event_output_and_errors_do_not_expose_private_input(self):
        events = []
        body = payload(number(1, 1), text(4, "PRIVATE_DESTINATION"))
        bad = payload(tlv(4, b"PRIVATE_\xff"))
        result = rgi.replay(io.BytesIO(hook(0x5201, body) + hook(0x5201, bad)), emit=events.append)
        self.assertNotIn("PRIVATE", json.dumps([events, result]))
        self.assertEqual(events[0]["present"], ["components", "destination", "route_state"])

    def test_cli_exit_code_and_default_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "iap2.log"
            path.write_bytes(hook(0x5201, payload(number(1, 1), text(4, "PRIVATE_DESTINATION"))))
            script = str(Path(rgi.__file__))
            p = subprocess.run([sys.executable, script, tmp], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertNotIn("PRIVATE", p.stdout + p.stderr)
            p = subprocess.run([sys.executable, script, tmp, "--include-private"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("PRIVATE_DESTINATION", p.stdout)
            path.write_bytes(b"CPMAP_RGI_RX B2 id=0x5201 len=11 (TLVs follow)\n")
            p = subprocess.run([sys.executable, script, tmp], capture_output=True, text=True)
            self.assertEqual(p.returncode, 1)

    def test_deterministic_mutated_frames_never_partially_modify_cache(self):
        rng = random.Random(1427)
        original = payload(number(1, 1), text(4, "Synthetic destination"), indices(13, 2, 3))
        failures = 0
        for _ in range(500):
            body = bytearray(original)
            body[rng.randrange(len(body))] = rng.randrange(256)
            cache = rgi.GuidanceCache()
            before = cache.snapshot(True)
            try:
                event = rgi.decode_payload(0x5201, bytes(body))
            except rgi.DecodeError:
                failures += 1
                self.assertEqual(cache.snapshot(True), before)
            else:
                cache.apply(event)
                self.assertLessEqual(len(cache.maneuvers), rgi.MAX_CACHE)
        self.assertGreater(failures, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
