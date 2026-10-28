# Lane protocol and exact MU1367 integration

Protocol reference: Anton Perk's
[mst2-cluster-nav lane documentation](https://github.com/perkthefox/mst2-cluster-nav/blob/7d836690077e438e3e7dd86b1263ed49aa25fe95/docs/LANES.md),
reviewed at commit `7d836690077e438e3e7dd86b1263ed49aa25fe95`.
That project is CC BY-NC-SA 4.0. Its implementation is neither copied nor
vendored into this GPL project. `LaneData.java` is an independent decoder
of the documented wire fields, integrated against the user's exact MHI2
firmware interfaces. No MST2 binary or firmware patch is used.

## Data mapping

| iAP2 field | Meaning | MHI2 handling |
| --- | --- | --- |
| 0x5204 / 1 | Lane instruction index | Independent six-instruction cache |
| 0x5204 / repeated 2 / 0 | Lane position, u16 | Sort left to right; unknown/duplicate position hides instruction |
| 0x5204 / repeated 2 / 1 | Recommendation 0 / 1 / 2 | Not recommended / allowed / best |
| 0x5204 / repeated 2 / repeated 2 | Plain signed exit angles | Preserve other exits as raw BAP side-direction bytes |
| 0x5204 / repeated 2 / 3 | Separate highlighted signed angle | Main lane direction, even when absent from plain angles |
| 0x5201 / 16 | Current lane instruction | Select independently of maneuver order |
| 0x5201 / 18 | Show lanes | Hide immediately when false |

Angles use negative left and positive right. Native BAP direction is
0 ahead, 64 left, 128 back and 192 right. The decoder rounds valid angles
to 16 sectors. Values outside ±180 (including ±1000 unknown) are not
invented as straight. With no valid highlight, one distinct plain direction
can supply the main direction; ambiguous branches remain unhighlighted.
Lane type is unspecified, description unsupported and markings absent,
because these fields are not supplied by the phone message.

Cache and message bounds are six instructions, sixteen lanes and sixteen
plain angles per lane. Missing components on 0x5204 broadcast to our
component; repeated component TLVs are validated. Unknown components cannot
replace our lanes. Invalid nested lane content clears only that lane
instruction. Invalid outer framing retains the existing fail-closed decoder
behavior. Session reset, gaps, rerouting and arrival clear cached lanes.
Lane visibility expires after five seconds without an accepted route-status
update, independently of fresh maneuver events. It does not require a
nonempty maneuver list.

## Exact MHI2 contract

The existing MU1367 native reader already forwards 0x5204, and the existing
start request advertises a lane cache. No driver/capture changes are needed.
The former Java decoder validated then discarded this geometry; the former
lane adapter always cleared its array.

The new `LaneData` implements the firmware's actual
`NavigationLaneGuidanceElement` interface. The patch replaces just the
navigation-service getters inside the stock
`LaneGuidance.computeFullLaneGuidanceList` method. Its stock six-lane
selection, omitted-left/right markers, array comparisons, one-second
processing and blocking-request tracker remain unchanged. The OEM
`isSetupLaneGuidanceActive()` setting is respected. OEM navigation ownership
restores the original service data source.

Exact `/ifs/lsd.jxe` SHA256:
`09167f1d0ae5340e992821bf92a56bcc5d45965b1dc24af3e4cc9d096a07507a`.
The converted factory JAR content identity is
`37bb839fb026bd1d5c0cb5066d189bd58bbde93f5d355eac8473809799f10a48`.
Build scripts stage counted changes over existing sources; the published
v1.3.0 sources/payloads are retained intact.

## Remaining vehicle evidence

Existing private captures contained no 0x5204 geometry. Offline fixtures
cover the documented protocol and actual factory array builder, but cannot
prove that a particular iPhone/app supplies the messages or that the cluster
renders every branch correctly. Compare phone lane hints and cluster output
on a familiar route. A missing lane bar may mean the phone supplied no lane
data or the OEM lane setting is disabled. Status records lane count/timestamp,
without logging road names or accumulating lane traces.

This work does not establish a fix for all long-run guidance interruptions.
The v1.3.0 bounded logging remains in place; the existing reader still fails
closed on output failure. Extended vehicle endurance remains necessary.
