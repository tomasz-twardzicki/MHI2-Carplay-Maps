# MU1427 native guidance mapping and bridge model

> Development reference. Some sections describe retired manual test tools. Use [INSTALL.md](./INSTALL.md) for the release and [README.md](./README.md) for maintained sources. Historical tooling is available in [Git history](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/tree/838dd535c23cb8214b170216066e60f8690d2074/MU1427/route-guidance).

Implemented 2026-10-18 after [C4-2](./C4-2-RESULTS.md). This is executable
**host-side mapping and a replacement-frame/ownership model**. It does not
install an HMI hook, write PPS/BAP, change boot startup or enable native arrows.
This work supplies the data and lifecycle contract for the subsequent
[D1 live adapter](./LIVE-BRIDGE.md). That separate implementation now has a
[current unit test package](./TEST-D3.md); the mapping/model described
on this page remains host-side. Keep the tested B4 driver installed.

| File | Purpose |
| --- | --- |
| [rgi_maneuver.py](./rgi_maneuver.py) | iAP2 maneuver -> verified native main element/direction, or an explicit unavailable reason |
| [rgi_bridge.py](./rgi_bridge.py) | Full replacement frames after complete validated windows, context/freshness gating, distance provenance and handback actions |
| [MU1427-NATIVE-CONTRACT.json](./MU1427-NATIVE-CONTRACT.json) | Selected constants, signatures, access flags and original ROM-method hashes from the exact factory JXE |
| [probe-native-contract.py](./probe-native-contract.py) | Re-extract and verify that metadata from the supplied firmware |
| [bridge/VerifyNativeContract.java](./bridge/VerifyNativeContract.java) | Host execution of the converted factory serializer and pure main-element remapper |
| [NATIVE-BRIDGE-VERIFICATION.json](./NATIVE-BRIDGE-VERIFICATION.json) | Reproducible input/code fingerprints and verification/replay results |

D2 unit testing corrected the original distance-value assumption: the model
keeps source metres, but the live BAP adapter must use the **factory numeric
formatter**, not copy raw metres into the serializer. D3 also projects route
remaining distance/duration, with explicit validity and episode resets.
See [D2-RESULTS.md](./D2-RESULTS.md) and [LIVE-BRIDGE.md](./LIVE-BRIDGE.md).

## Exact factory interfaces

The source is the provided `MHI2_ER_VWG11_K3342_MU1427` MMX stage2 package,
not an Audi or newer VW image. Its `ifs/lsd.jxe` is 52,751,492 bytes, SHA-256
`f46290b4a33b98d957170f6207073ad329316902a87cd4c27da4168548ad911a`.
The probe decompresses the actual LZOZ image, verifies this fingerprint, then
reads the ROM with `luka-dev/jxe2jar` pinned to
`9eeb45bbf14bf8afe3452c7be96a4d1f0206a286`. No proprietary class/firmware
bytes are committed; the metadata records selected interface facts and hashes.

The MQBAB2 path is:

`APIFactory.getNavigationService()` -> `NavigationService` -> stock
`navsd.functions.ManeuverDescriptor` / `DistanceToNextManeuver` / `RGStatus`
-> their generated serializers and factory BAP dispatch.

`APIFactory` lazily creates/caches `NavigationASLDataAdapter`. Its
`getRouteGuidanceState()` is **final**: replacing it with a subclass override
is not a valid integration. An eventual adapter must wrap the service
interface or use an equivalently verified narrow hook, while retaining the
original service as the authoritative OEM source. The factory MQBAB2 stages
read that interface; the Audi reference's `AppConnectorNavi` is not this seam.

| Factory entity | Verified contract |
| --- | --- |
| `ManeuverDescriptor_Status`, FctID 23 | Three complete maneuver slots; each has `mainElement`, `direction`, `zLevelGuidance`, `sidestreets` |
| `NavigationManeuverDescriptorElement` | `getMainelement()`, `getDirection()`, `getZLevelGuidance()`, `getSideStreets()`; spelling retained |
| Maneuver serializer | First three fields serialize as bytes, followed by the BAP side-street string |
| Maneuver main elements | TURN 13, FOLLOW_STREET 11, CHANGE_LANE 12, UTURN 25, roundabout R/L 21/22, exit roundabout R/L 26/27, ARRIVED 3, NO_SYMBOL 0 |
| Direction | Same-firmware PQ constants confirm left 64/right 192; MQBAB2 passes the direction through. Remaining quantization follows the pinned protocol reference and still needs glyph validation on the 791 |
| Stock main-element normalization | Input 32 -> 15 and 33 -> 16; other 0–38 inputs pass through. The model emits neither ramp alias |
| `DistanceToNextManeuver_Status`, FctID 18 | Signed Java `int` distance, unit byte, separate `distanceToNextManeuverValid` flag and bargraph data |
| Distance units | BAP meter is **0**; KOMO `DISTANCEUNIT_METERS` is **1**. Never copy unit numbers between these APIs |
| `RG_Status_Status`, FctID 17 | 0 inactive, 1 active, 2 suspended, 255 unsupported |
| `ManeuverState_Status`, FctID 55 | 0 unknown, 1 follow, 2 prepare, 3 distance, 4 call-for-action. No automatic offset from iAP2's differently defined state byte is implemented |

`DSIKOMONavInfo.setDistanceToNextManeuver(long,int,boolean)`, street setters
and trip setters exist, but are not a descriptor publisher. This model does
not call `setRgSelect`, change map mode, manufacture an exit view, or reuse
Audi-specific initialization/function-sync behavior. Those affect the
working map/video path and require separate integration evidence.

## Mapping policy

Protocol/type families and angle quantization are adapted under GPL-3.0-or-later
from LuKa's `ManeuverMapper.java` and `rgd_tlv.h` at the existing pinned
reference commit `dfafccf6637ad45457085f0977f18cd7f64ab3ed`.
Copyright (c) 2026 LuKa (@LuKa_dev); see the repository [license](../../LICENSE).
Native constants are independently checked against this MU1427 firmware.
The reference's permissive geometry fallbacks are not all adopted.

All 54 known type codes have deliberate mapping cases when their required
context is present. Unknown/255/missing types remain unavailable.

| Types | Projection / required evidence |
| --- | --- |
| 1/2/3, 13/14, 47–50 | TURN with explicit left/right/straight/slight/sharp direction; intersection junction metadata required, angle optional |
| 20/21 | Explicit end-of-road left/right; refine using consistent signed geometry, never turn a small received angle into straight |
| 0/5, 15/17 | FOLLOW_STREET; no invented ferry-only main element |
| 10/12/27, 24/25 | ARRIVED, with explicit side for 24/25 (intersection context required for those side-specific types) |
| 52/53 | CHANGE_LANE with explicit side |
| 11/16/51 | Generic turn: actual exit angle required; missing geometry cannot become straight |
| 4/18/26 | UTURN: prefer real signed nonzero angle, otherwise use known traffic side; unknown side cannot silently default to RHT |
| 6 | Roundabout approach using known traffic side and known junction type |
| 7/19 | Roundabout exit / U-turn, requiring roundabout junction and known traffic side |
| 28–46 | Roundabout with retained exit number, **plus a real exit angle** and traffic side. Exit number alone cannot establish physical exit geometry |
| 8/9 | Ramp with a real nonzero signed exit angle. No left/right guess from traffic side |
| 22/23 | Explicit highway-ramp side, represented by a slight TURN |

Absence, explicit zero and received −1 degree remain distinct. ±1000 sentinels,
invalid types and out-of-range geometry do not enter angle quantization.
An explicit directional type can still be mapped without using its bad or
absent optional geometry. Roundabouts use the reference's 16-sector encoding;
ordinary generic turns use 45-degree direction sectors. No side-street
geometry, lane arrows or z-level is synthesized.

Some C4-2 records have roundabout-exit types with intersection junction
metadata. The model reports `junction_conflict` and clears the proposed
symbol, rather than keeping the preceding turn or overriding the wire field.
This remaining mapping limitation needs a targeted review before live output.

## Replacement frame and ownership

The bridge processes **the final state of a complete validated window**.
`note_message` only tracks freshness and distance provenance. A transient
selected head followed by a stop in one window is never published. Unknown
heads, unmapped types or missing required geometry replace the symbol with
NO_SYMBOL; unused slots 2/3 are explicitly cleared. Lookahead is not a current
maneuver. Bargraph is off, lane output hidden and maneuver phase unknown in
this initial descriptor/distance contract. Street/trip/ETA transport remains
outside this implementation.

Ownership needs independent, fresh factory observations, not just RGI traffic:

- `SmartphoneIntegrationService.getSmarphoneIntegrationActiveConnectionType()`
  reads ASL property **2910004**, whose ordinal **2** means CarPlay. It is not
  the separate API's connection-method bitmask 4.
- Read the **underlying OEM** navigation service before any override. Native
  navigation status 0 means no error; native route state 0 is idle, 1 active,
  2 calculating. Both active and calculating prevent CarPlay takeover. Errors
  or unknown values cannot establish native inactivity.
- Context observations must be serialized and renewed within **1,500 ms**.
  A missed lease or denied/unknown ownership drops cached takeover. A later
  context renewal alone cannot revive old guidance; fresh producer progress
  is also required. `native_context()` implements the verified value decoding.

The CLI has no live factory observations. By default it produces only
`pass_through`. `--simulate-carplay-owner` supplies an explicitly **assumed**
fresh CarPlay-active/OEM-idle context for offline replay; this does not prove
that takeover was permissible at each moment in the capture.

| Action | Required eventual adapter behavior |
| --- | --- |
| `publish` | Commit one complete replacement while the ownership lease is valid; only its selected current slot may be populated |
| `clear_and_release` | Under still-known CarPlay ownership, clear all owned descriptors/distance/lanes and inactive RG status, then hand back to stock |
| `release_to_stock` | OEM guidance/context takes priority: restore/delegate to the latest stock state, **without sending a blank frame over it** |
| `pass_through` | Leave stock publishing in control; payload is absent |

A future adapter must keep stock state current while gated, process the
replacement on the HMI event queue and force stock refresh on handback.
Releasing cannot mean merely stopping CarPlay writes while its last arrow
remains visible. Sink writes/acknowledgements, bounded retry, transaction
ordering and the unit's FctSync behavior are not implemented by this model.
It must not be wired directly to `statusProperty` calls as a ready transport.
Reader session/generation counters are process-local. A live IPC format must
also identify writer restarts, validate a complete atomic frame and reject
old RAM output; the diagnostic JSON is not that transport protocol.

## Freshness and distance association

Five seconds without a **new accepted event for this component** invalidates
the proposal. Heartbeats, identical source reads, foreign-component sequence
increments and old retained events replayed after reset do not refresh it.
The first window in an allocation/session is only a baseline: its records
have no individual receive timestamps and may be old. A subsequent accepted
sequence advance is needed to establish fresh guidance, even with a valid
ownership context.
Disconnect, disabled publication, producer fault, stop, loading, locating,
reroute, arrival and recording end clear or release owned output. The source
consumer still invalidates on allocation/session change or history gap.

Distance is independent of icon availability, but requires a cached selected
head and a new `maneuver_meters` field received for that head's exact reader
session/generation. A new head cannot inherit the former head's distance.
Early distance before selection remains unavailable until another qualifying
update. Explicit zero is retained; values above signed-native-int range are
invalid, not wrapped. The contract uses raw meters and records both native
unit identifiers. The stock formatter may scale/round or suppress zero; its
eventual integration and actual cluster behavior remain to be tested.

`--frames` is diagnostic JSON, not a deployed IPC format. By default distance
values are redacted; `--include-private` exposes them deliberately. Input
journals remain private even when output is redacted. Frame counts include
heartbeat observations and must not be confused with unique wire messages.

## Run and verification

```sh
python3 MU1427/route-guidance/test-rgi-maneuver.py
CPMAP_PRIVATE_C4_DIR="$GARAGE_DIR" CPMAP_PRIVATE_C4_2_DIR="$FOLLOWUP_DIR" python3 MU1427/route-guidance/test-rgi-bridge.py
python3 MU1427/route-guidance/rgi_bridge.py "$CAPTURE/events.rgj"
python3 MU1427/route-guidance/rgi_bridge.py "$CAPTURE/events.rgj" --simulate-carplay-owner
python3 MU1427/route-guidance/rgi_bridge.py "$CAPTURE/events.rgj" --simulate-carplay-owner --frames > /tmp/native-proposals.jsonl
```

No private captures are required for the synthetic suite. Optional private
tests assert actual C4-2 left/right/roundabout projection and clearing, and
that the original garage run produces no fabricated arrow or distance.

To reproduce the firmware metadata with the already-used liblzo2 available:

```sh
git clone https://github.com/luka-dev/jxe2jar /tmp/mu1427-jxe2jar
git -C /tmp/mu1427-jxe2jar checkout 9eeb45bbf14bf8afe3452c7be96a4d1f0206a286
python3 MU1427/route-guidance/probe-native-contract.py "$RG_FIRMWARE" --jxe2jar /tmp/mu1427-jxe2jar --check MU1427/route-guidance/MU1427-NATIVE-CONTRACT.json --export-jxe /tmp/mu1427-verified-lsd.jxe
python3 /tmp/mu1427-jxe2jar/src/jxe2jar.py /tmp/mu1427-verified-lsd.jxe /tmp/mu1427-stock.jar > /tmp/mu1427-conversion.log
mkdir -p /tmp/mu1427-native-check
"$RG_JAVA/bin/javac" -d /tmp/mu1427-native-check MU1427/route-guidance/bridge/VerifyNativeContract.java
"$RG_JAVA/bin/java" -Xverify:all -cp /tmp/mu1427-stock.jar:/tmp/mu1427-native-check VerifyNativeContract
```

`RG_FIRMWARE` is the supplied firmware directory; `RG_JAVA` is the bundled
Zulu JDK 8 Home (on this Mac,
`/tmp/mu1427-jxe2jar/jvms/zulu8.78.0.19-ca-jdk8.0.412-macosx_aarch64/zulu-8.jdk/Contents/Home`).
The JXE export refuses to overwrite an existing file. Keep these firmware
artifacts outside version control. The execution check uses the converted
factory JAR, not a replacement class compiled from decompiler output.
All **624 descriptor vectors**, **39 pure stock main-remapping cases**, three
slots and FctIDs 17/18/23/55 pass. These are host-JVM checks of converted
factory code, not an embedded J9/HMI or on-cluster rendering test.

**14 mapping tests + 23 bridge tests pass** with both optional private
captures enabled. The metadata probe verifies 22 selected factory classes.
See [NATIVE-BRIDGE-VERIFICATION.json](./NATIVE-BRIDGE-VERIFICATION.json).

With simulated ownership, C4-2 produces 91 right-turn, 35 left-turn and four
roundabout descriptor observations, with 141 distance-valid observations.
Fifty-three active observations have a cleared symbol: 33 lack a selected
typed head, four lack the generic maneuver's angle and sixteen have a
junction/type conflict. These counts include heartbeat observations. There
are three clear/release transitions and final ownership is released. The
garage control produces only cleared symbols and no valid distance proposals.
Without simulated ownership, all 303 C4-2 observations pass through to stock.
None of these results is an on-unit output/ownership measurement.

## Next live stage

The subsequent [D1 implementation](./LIVE-BRIDGE.md) reuses the exact C4
supervised native recorder and adds a separate bounded Java consumer plus
factory ASL timer / stock BAP-stage hooks. Its [unit procedure](./TEST-D1.md)
requires a healthy read-only shadow run before allowing a manually enabled
descriptor/distance takeover. Driver and recorder bytes remain unchanged.
