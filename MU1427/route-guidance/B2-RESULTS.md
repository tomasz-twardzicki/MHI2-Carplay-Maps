# B2 on-unit result (2026-10-17)

**B2 passed this MU1427 / 791 test:** guidance and maneuver messages reached
the new receive hook, traffic continued beyond B1's six rejected frames,
guidance stopped cleanly, and both C2 captures completed. The user reports
that CarPlay stayed usable and worked after reconnecting. This is one test
session, not a long-duration stability result. No native cockpit output is
implemented yet.

Private inputs under `Logs/B2/`:

| Capture | User-described phase | iAP2 log bytes | `0x5201` | `0x5202` | `0x5204` |
| --- | --- | ---: | ---: | ---: | ---: |
| `cpmap-navrecon-C2-3256392` | Navigation active | 189,657 | 104 | 20 | 0 |
| `cpmap-navrecon-C2-3764296` | After stopping guidance | 261,771 | 135 | 32 | 0 |

The second log starts with the **entire first log**. Counts are cumulative:
there are **167 distinct guidance frames**, not 291. The additional capture
contains 31 route updates and 12 maneuver updates.

Keep raw captures private: they contain GPS, destination/street names,
authentication material and device information. Only structural observations
and fingerprints are recorded here.

## Installed files and collector

Both captures contain the exact intended files:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| Active B2 driver | 741,944 | `0763b7aa448837651ca59ce8d3e219c0b157df05204c9a2037f895001b1655b6` |
| Active config | 6,006 | `67b867db8eb05e0dd20645727d3216ff18b86be75d21c9fb89a92dffbcafc9f7` |
| Original driver backup | 739,925 | `0ac13f43d3fb259eee328c272fa1211bb558b6e2cd97c6e38ef38e4e71469d51` |
| Original config backup | 5,905 | `ce05524385ccae1167966d45c52ff60ac0c70fe0f46ac98d77a75f109a6bfa6c` |

Both summaries report zero read failures and both progress files finish with
`CPMAP_RGI_CAPTURE_OK`. The `dd` record counts in `copy-errors.txt` are normal
copy statistics. The later log grew during collection but remained within the
collector's fixed read bound.

The selected OEM error archive is still **42**, byte-identical to the B1
archive recovered by C1 (SHA-256
`62dd70713146796d6fd61e73ea9ad40b03f66ed1d685957ccde7c75a67a1ec95`).
It is historical B1 evidence, not a newly generated B2 failure.

## Receive path and lifecycle

- One `IdentificationAccepted` and one
  `CPMAP_RGI_START B2 0x5200 rc=0 (0=queued)` appear in each cumulative log.
- Every native-printer `0x5201` / `0x5202` frame has a matching
  `CPMAP_RGI_RX B2` entry. All 167 hook payloads match the native semantic
  payload byte for byte. Declared payload lengths and every TLV boundary
  validate, with no truncated or malformed dump.
- Both logs contain **zero** `Invalid packet`, `Failed to send packet`,
  `No packets in receive list`, or `IdentificationRejected` messages.
- The first capture ends with route state **1**. The second ends guidance
  with three state **0** updates (markers at lines 2080, 2083 and 2086).
  Loading (**3**) and rerouting (**5**) also occur earlier in the session.
- After the final guidance update, the later capture records another **79**
  outgoing location messages and **78** incoming ACKs. The last send is at
  the capture boundary. There is no repeated-send failure sequence like B1.
- The user reports CarPlay remained working through route end and reconnect.
  The supplied iAP2 captures show one identification/start cycle, so a fresh
  subscription after that reconnect is not established by these logs.
- Eight native now-playing (`0x5001`) messages occur before the first guidance
  update. These captures do not establish music-metadata changes during or
  after guidance.

## Data available for the next phase

The source is **Google Maps** and every guidance message names component
**`0x0010`**. Field interpretation follows the existing LuKa reference pinned
in [README.md](./README.md#reference-luka-devmib2q-carplay-rgi); wire values and
presence below were checked directly in this capture.

`0x5201` supplies route state, destination, ETA (8 bytes), remaining time
(8 bytes), destination/maneuver distances (4 bytes), display strings/units,
the current maneuver-index list and total count. It also supplies source,
visibility and lane-summary fields. Current-road-name fields are present in
121 updates but contain only the string terminator; the capture supplies no
usable current-road text.

The 32 `0x5202` updates address indices **0–7** and contain descriptions,
maneuver type, driving side and junction type. After-maneuver road text is
present in 28 updates. Observed maneuver-type counts:

| Wire type | Reference interpretation | Updates |
| ---: | --- | ---: |
| 1 | Left turn | 5 |
| 2 | Right turn | 6 |
| 7 | Exit roundabout | 4 |
| 11 | Start route | 6 |
| 28 | Roundabout exit 1 | 3 |
| 30 | Roundabout exit 3 | 4 |
| 50 | Slight right turn | 4 |

Seven maneuver updates include signed 16-bit exit angles: **−90 / +90**.
The other 25 omit the field. Junction-angle arrays (`0x0a`), per-maneuver
distance fields (`0x05`–`0x07`), linked lanes and exit-info text are absent.
No `0x5204` arrives, even though lane-showing is briefly true in the route
summary. A summary flag does not establish reception of lane geometry.

Requirements for a decoder/state cache before publishing to PPS or the HMI:

1. Treat updates as partial: absent, explicitly empty, and zero-valued fields
   have different meanings. The final state-only stop updates must clear
   stale guidance, even without empty maneuver lists or destination fields.
2. Use route state for route activity. In **109** updates, state is **1** while
   `RouteGuidanceBeingShownInApp` is **0**; app visibility must not stop guidance.
   Loading and rerouting need explicit handling rather than treating only
   state 1 as meaningful.
3. Resolve the current maneuver through the received ordered index list
   (ending at `[2, 3]` here), not the most recently updated cache entry.
   Route changes reuse indices, and the total count reaches 10 despite an
   advertised storage capacity of 6; do not use either value as an unchecked
   array bound or assume the whole route is cached.
4. Preserve signed angles and field presence. An omitted angle must not become
   a fabricated zero-degree turn. Do not infer lanes from the showing flag.

The offline decoder/state cache is now implemented and validated against
synthetic fixtures and both captures; see [DECODER.md](./DECODER.md). It selects
index 2 (right turn) in the active capture and clears route-specific state and
both caches on stop. Route updates merge as deltas; indexed maneuver updates
replace the previous record, preserving omitted geometry as absent. B3's
bounded virtual-file publication path is now implemented and prepared for a
separate on-unit test; see [PUBLICATION.md](./PUBLICATION.md) and
[TEST-B3.md](./TEST-B3.md). B2 remains the working receive-only baseline.
An Apple Maps capture with the same B2/C2
package would extend app/lane coverage but is not required for this step.

## Capture integrity

SHA-256 of `iap2.log`:

- Active: `1f43dadb69d8f8fffd6c95b2121103b21368f755f410a43ed672a691e8dbb801`.
- Stopped: `3e3e815ac0e57bab6d0fca9c9f5efe589aae676cd2b3f17fd6b3279d154c81ae`.

Analysis used host-side SHA-256, exact prefix comparison, matching of native
semantic dumps to B2 hook dumps, and a big-endian TLV walk checking lengths
including the four-byte TLV header. The stock hexdump omits a terminating
newline, so the following `TID...` text can immediately follow the final hex
byte; it is log formatting, not payload corruption. No unit files were changed
and no private raw logs were added to the repository.
