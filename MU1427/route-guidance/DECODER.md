# Offline guidance decoder and state cache

Implemented on 2026-10-17 in [rgi_decode.py](./rgi_decode.py). It runs on the
computer with Python 3.10+ and the standard library. It reads B2's existing
captures; no new installation, phone test, QNX utility or driver patch is
required. This is the model for the next publication/consumer implementation,
not a service installed on the unit.

## Run

From the repository root, set `CAPTURE` to **one** C2 capture directory or
`iap2.log` path, then run:

```sh
python3 MU1427/route-guidance/test-rgi-decode.py
python3 MU1427/route-guidance/rgi_decode.py "$CAPTURE"
python3 MU1427/route-guidance/rgi_decode.py "$CAPTURE" --events > /tmp/rgi-events.jsonl
```

The default output contains counts and structural state only: no destination,
road names, source name, ETA, duration, distance values or opaque lane bytes.
`--events` emits one JSON object per decoded guidance message, followed by a
summary. Only B2 hook records count as guidance: the stock printer's duplicate
semantic dump is ignored. The hex reader handles the stock logger's missing
newline before `TID...`.

`--include-private` adds route text, numeric route values and cached records.
Keep that output outside git, just like the input captures. Raw unknown
extensions remain available through the decoder API; event summaries report
only their IDs. Errors report line numbers and structural reasons, without
echoing input data. Malformed messages are skipped and make the CLI exit 1;
failure to read the input exits 2. Foreign-component or inactive indexed
updates are counted separately from malformed input.

**Do not concatenate the two B2 logs.** The stopped capture includes the
complete active capture. Replay either separately, or just the later one.
End of file preserves the last observed route state; it does not mean the
phone disconnected or guidance stopped.

## Decoder contract

- `decode_frame(frame)` accepts a complete `40 40` semantic control message.
  Its declared length must match exactly. An `FF 5A` transport packet is not
  a semantic frame.
- `decode_payload(message_id, payload)` accepts B2's TLV bytes after the
  six-byte semantic header. Supported IDs are `0x5201`, `0x5202`, `0x5204`.
- A `Message` contains `identifier`, a `fields` dictionary and an ordered
  `unknown` TLV tuple. Dictionary membership records presence: absent, empty
  and zero are distinct. Construct messages through the decoder; do not
  mutate decoded fields before applying them to a cache.
- Integers are big-endian and exact-width: u8/u16/u32/u64, signed i16 angles,
  and ordered u16 index lists. Unknown enum values remain numeric; no enum
  guess silently becomes a valid turn. ETA/duration are retained as raw u64
  seconds without local time or display conversion.
- Text accepts UTF-8, optional trailing NUL and explicit empty strings.
  Embedded NUL, invalid UTF-8 and control characters other than tab/newline
  are rejected. Display newline formatting is left to the future consumer.
- Component IDs are required, nonempty, unique u16 values. Indexed messages
  require a u16 index. Duplicate known scalar/list fields are rejected;
  repeated junction angles and lane-information containers are accumulated
  in order. Unknown extensions remain opaque and cannot override known data.
- Every TLV boundary is checked before any state mutation. Known scalar
  widths and list/text bounds are checked as well. This is deliberately
  stricter than the reference parser's minimum-width checks; a new wire
  shape must be reviewed rather than silently taking its first byte/word.

Bounds: 65,529 payload bytes; 256 TLVs; 8 component IDs; 16 current maneuver
indices; 16 junction angles; 256 bytes per route/maneuver string and 64 per
display/source string (including any terminating NUL). Log lines are capped at
256 KiB and replay retains at most 16 detailed malformed-input reports.
Oversized input is rejected, not silently truncated.

## State and current-maneuver selection

`GuidanceCache(component=0x10, capacity=32)` holds one advertised component,
route fields and bounded ordered dictionaries for maneuver and lane records.
`apply(message)` returns false for a foreign component, an indexed record
outside a known live route episode, or a record that cannot fit while
protecting the current entry. Never use wire index, total count or maneuver
storage capacity as an allocation size.

`0x5201` is merged as a **route delta**. Missing fields retain their value;
an empty string/list or numeric zero replaces the previous value. The first
entry of `maneuver_order` selects the current maneuver. If it is not cached,
the current maneuver is unavailable; a later cached index must not substitute
for it. The most recently received maneuver is often lookahead.

Each indexed `0x5202` is a **replacement record**, following the reference
hook's slot-cache assignment. Omitted geometry stays absent rather than
inheriting an old angle or becoming a fabricated zero. The same rule applies
to indexed lane records. Route-delta and indexed-record semantics are distinct.

The snapshot exposes the following phases:

| Route state | Phase | Current maneuver exposed |
| ---: | --- | --- |
| 0 | Stopped | No; route-specific fields and caches cleared |
| 1 | Guiding | Ordered head, if cached |
| 2 | Arrived | No; caches cleared |
| 3 | Loading | No; new indexed data may be cached |
| 4 | Locating | No; new indexed data may be cached |
| 5 | Rerouting | No; new indexed data may be cached |
| 6 | Proceed to route | Ordered head, if cached |
| Absent/unknown | Unknown | No |

`visible_in_app` never controls route activity. State zero clears immediately,
including a state-only stop with no destination/list fields. Later state-less
updates or indexed records cannot revive that stopped route. A new nonzero
state starts a fresh episode.

For conservative invalidation, a transition into loading/rerouting from a
different known nonzero state, an explicit source change, or a nonempty
destination change clears old route/cache data. Repeated loading/rerouting
updates retain newly prefetched data; transition from those phases to guiding
retains it too. A generation counter identifies invalidations. Cache pressure
protects the current head, prefers current lookahead, then evicts the oldest
other entry. Both maneuver and lane caches have a maximum of 32 records.

Call `reset_session()` on identification/start or disconnect; it clears all
route/source/cache state and advances the session/generation. Replay calls it
for each B2 start marker. A runtime port must also wire real disconnect and
staleness handling; the historical log does not reliably expose those events.
Session/generation values are process-local counters, not persistent IDs.

`snapshot()` returns a detached JSON-compatible structural snapshot.
`snapshot(include_private=True)` adds the full accumulated data. A resolved
record is protocol data: its presence does not establish that a VW icon can
already be generated from it.

`current_maneuver_status` explains selection without private data: `inactive`
outside guiding/proceed-to-route, `order_absent` when no list is known,
`order_empty` for an explicit empty list, `head_not_cached` when its first
index lacks a record, and `head_cached` when that record exists. This does
not alter stop/reset handling or infer a missing index or direction.

## Lane coverage and rendering limits

No B2 capture contains `0x5204`. The decoder checks its outer fields and the
nested lane-information TLV envelope, preserves that information and bounds
the cache. It does not interpret lane geometry or make lane arrows from the
`lane_showing` summary flag. Alternate field widths and nested lane semantics
remain unvalidated on this unit.

The wire layout and indexed-record semantics follow LuKa's GPL-3.0-or-later
`rgd_tlv.h` / `rgd_tlv.c` / `rgd_hook.c` at the pinned reference commit in
[README.md](./README.md#reference-luka-devmib2q-carplay-rgi). The model preserves
raw signed angles and absence, rather than the reference parser's injected
1000-degree sentinel. The separate [native mapper and bridge model](./NATIVE-BRIDGE.md)
now projects VW maneuver descriptors and models ownership. Timezone formatting,
live native arbitration and Java HMI changes remain outside this decoder.

State-zero resets occur within rerouting as well as at actual route end in
the real B2 log. Immediate invalidation is deliberate for this data model.
Before publishing visible HMI transitions, decide and test any presentation
grace period with timestamps, including a reliable final stop; the model
does not copy another platform's debounce or add a timer without evidence.

## Verification

**47 synthetic tests pass.** They cover malformed/truncated/duplicate TLVs,
Unicode, signed/absent/zero angles, unknown fields, wrong components, route
delta versus record replacement, ordered selection and missing heads, cache
pressure and large indices, stop/restart/reroute/session reset, lane bounds,
privacy, CLI error exits and 500 deterministic mutated payloads. The test suite
has no dependency on private captures, firmware or third-party packages.

Both real B2 captures were replayed separately:

| Input | Decoded route / maneuver | Malformed / unapplied | Final result |
| --- | --- | --- | --- |
| Active | 104 / 20 | 0 / 0 | Guiding; order `[2, 3]`; head index 2, right turn (type 2); visibility 0; no exit angle present |
| Stopped (cumulative) | 135 / 32 | 0 / 0 | Stopped; no selected maneuver, route-specific fields, or cached maneuvers/lanes |

This verifies the host model against the observed messages. It does not test
execution inside `mm-ipod`, PPS behavior, disconnect timing or an HMI consumer.
The B2 binary and tested ZIP remain unchanged.

B3 implemented the bounded event handoff through the native iAP2 virtual
filesystem; its on-unit capture exposed an activation-order defect, corrected
and validated on-unit by B4. See [PUBLICATION.md](./PUBLICATION.md),
[B3-RESULTS.md](./B3-RESULTS.md), [B4-RESULTS.md](./B4-RESULTS.md)
and [TEST-B4.md](./TEST-B4.md). The log decoder accepts B2/B3/B4 labels.
The B4 active snapshot illustrates missing maneuver history in a late read;
one interleaved text-log dump is also correctly rejected by strict replay.
The [C4 continuous diagnostic recorder](./OBSERVER.md) implements
disconnect/deadline handling, with semantic replay still on the host. Its
[first on-unit recording](./C4-RESULTS.md) retains all published maneuver
records, but current lists precede startup stop/loading resets and do not
reappear in sustained guidance. Clearing on state zero therefore leaves the
current index unknown. The [C4-2 follow-up](./C4-2-RESULTS.md) supplies fresh
lists later in each sustained episode, allowing selected maneuvers and
distances to advance without weakening stop invalidation. The user confirms
normal outdoor guidance/reconnect. Optional PPS publication outside iAP2 and
native cockpit output remain later steps. The host-side
[mapping/replacement model](./NATIVE-BRIDGE.md) uses these selected heads and
never forwards a transient state from the middle of a validated window.
