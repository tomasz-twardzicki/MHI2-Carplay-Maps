# D1 live runtime and HMI adapter

> Development reference. Some sections describe retired manual test tools. Use [INSTALL.md](./INSTALL.md) for the release and [README.md](./README.md) for maintained sources. Historical tooling is available in [Git history](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/tree/838dd535c23cb8214b170216066e60f8690d2074/MU1427/route-guidance).

Implemented after the C4-2 replay and host mapping contract. See
[INSTALL.md](./INSTALL.md) for the full automatic package;
[TEST-D3.md](./TEST-D3.md) retains the accepted manual-test procedure.
**Original D1 failed cluster startup and is withdrawn.** Its major-49
replacements were rejected by the firmware J9. D1-r2 targets 46 throughout
and passes the actual firmware-runtime regression. See [D1-RESULTS.md](./D1-RESULTS.md).
The r2 package passed unit startup/shadow verification with normal OEM and
CarPlay navigation/reconnection; see [D1-r2-RESULTS.md](./D1-r2-RESULTS.md).
D2 demonstrated native arrows on AID/HUD, disconnect clearing and normal
OEM/reconnection behavior. D3 corrects the factor-of-ten distance error and
adds route distance/remaining duration; see [D2-RESULTS.md](./D2-RESULTS.md).
D3 unit photos now demonstrate native distance/route totals with no issues
reported; both exports remain usable after removal. See [D3-RESULTS.md](./D3-RESULTS.md).

## Runtime path

```text
B4 bounded rgi-events publication
  -> unchanged, supervised C4 native recorder (manual, 300 seconds, RAM)
  -> compact append-only regular RAM journal
  -> Java background JournalReader / LiveModel (bounded validation + cache)
  -> immutable in-memory Frame
  -> factory MQBAB2 timer on the ASL event thread (250 ms)
  -> six narrowly patched stock stages and their stock BAP transport
```

No file/device reads or logging occur in the HMI output callbacks. Only C4's
supervised worker opens/reads/closes the virtual driver file; its supervisor
keeps the already-tested 1,500 ms deadline. The Java thread reads regular
RAM files, never Qnet, the virtual device or the SD. Its journal limit is
8 MiB, batch limit 64 records, and payload/window limits match B4/C4. It
accepts partial appended records only after the complete record is present.
The recorder binary and B4 driver/config/install/restore helpers are byte
identical to the tested C4 package.

Java validates the full compact window and every message before applying
any event. It validates all known field widths, duplicates, component lists,
bounded lists, UTF-8/control characters and nested lane envelopes even when
the corresponding text/geometry is not projected. It checks monotonic
sequences and immutable overlapping records. The cache has 32 entries and
protects the selected head; unknown geometry/type yields an empty descriptor.
Private text is validated and only source/destination comparison bytes are
retained in memory. Status contains counters/context, never navigation text,
coordinates or distances.

Source freshness requires subsequent accepted component progress after the
first publication baseline. Pre-existing journal bytes are bootstrap-only;
starting a reader against an old capture cannot emit it as live guidance.
Allocation/session/gap changes, unavailable/stale/end records and new manual
run IDs invalidate cached state. A missing recorder heartbeat expires after
1,500 ms; accepted component data expires after 5,000 ms. Identical reads,
foreign traffic and replayed retained records cannot renew this lease.
Distance binds to a cached head plus cache generation, and needs an actual
new meter update for that head. Zero is valid; unsigned overflow is invalid.

## Exact factory integration

The build checks the exact factory JXE fingerprint and the pinned converted
stock JAR, plus individual SHA-256 fingerprints of all six overridden
classes. The patcher preserves the original class/method bodies and adds
narrow conditional hooks. It does not replace APIFactory or subclass its
final navigation getter.

| Stock MQBAB2 stage | D1 hook |
| --- | --- |
| `ManeuverDescriptor`, FctID 23 | Full three-slot replacement in the fill method; a single route-state read in its compute method allows this fill while OEM navigation is idle |
| `DistanceToNextManeuver`, FctID 18 | Factory metric/imperial formatter and fixed-point scaling, explicit validity, bargraph off |
| `RGStatus`, FctID 17 | Active/inactive status while D1 owns the guidance |
| `DistanceToDestination`, FctID 21 | Factory destination-distance formatter; distance/type and separate validity hooks |
| `TimeToDestination`, FctID 22 | Remaining duration from accepted route seconds, rounded up to minutes; type 0, valid hour/minute, no date |
| `LaneGuidance`, FctID 24 | Empty lane array and lane guidance off while owned/clearing; original array diff/transport still handles delivery |

The factory service remains the authority for OEM guidance. D1 reads
`NavigationService.getNavigationStatus()==0`, `getRouteGuidanceState()==0`
and `SmartphoneIntegrationService` connection ordinal 2. Active/calculating
OEM routes, unknown/error context and other/disconnected phone types deny
takeover. Getters are rechecked at each output callback, including OEM route
changes between timer ticks. Context lease renewal alone cannot revive an
old proposal; fresh source progress is required.

`APIFactory.getTimerService()` creates the same `TimerObj` used by stock
LaneGuidance. In this exact firmware, `TimerObj` constructs the MIB timer
with `ASLFrameworkFactory...getASLThreadSwitch()` as its invoker. The callback
therefore runs on the factory ASL event thread. The underlying factory timer
manager's `getSystemTimeMillis()` converts `TimerSPI.getSystemTime()` ticks;
D1 checks regression and deadlines using that clock, rather than wall time.
The timer samples one immutable frame and refreshes the existing stage
objects in descriptor/distance/RG/lane/destination-distance/time order. No background-thread BAP call
or independent PPS writer is used. BAP functions remain separate messages;
this is not a hardware-atomic multi-function transaction.

Init/uninitialize hooks retain/release the stock stage instances. Ownership
requires all five property stages to be present. On stop/disable/stale input
with known CarPlay/OEM-idle context, D1 explicitly clears owned output, then
refreshes the latest stock state on the next timer tick. OEM takeover goes
directly to stock, without a blank replacement over native guidance.
Ordinary OEM listeners remain subscribed and their cached source stays live.

The five property send paths report `statusProperty()` acceptance for
bridge-triggered refreshes. False/exception retains a retry bit; an unaccepted
clear is retained before stock handback. This is **factory queue acceptance,
not a cluster ACK**. Normal stock callbacks retain factory retry behavior.
Lane delivery uses the original array tracker and throttling. D2 demonstrates native AID/HUD glyphs and disconnect clearing. The new
D3 photos demonstrate the corrected distance and route totals. Broader
boundary/lifecycle testing and persistent operation remain separate.

All installed classes use version **46**, including the surgical stock
replacements. Leaving those at the converter's version 49 caused the original
D1 failure; the earlier claim that working NavActiveIgnore used 49 was wrong.
Helpers compile against the firmware CDC boot classes. The patcher rejects invokedynamic,
class literals, StringBuilder and java.nio calls in installed helpers.
Host harnesses/build tools using reflection, proxies or newer APIs are excluded
from the installed JAR. Full `-Xverify:all` runs exercise the patched factory
compute/fill/send paths, not only mock copies of serializers.

## Controls and recovery

`bridge/control.sh` supplies install, shadow, verify, live, disable, stop,
export, clear, status and uninstall. Menu output is disabled after every boot.
Starting shadow creates an atomic RAM request with a run ID. A matching-build,
matching-run status with actual eligible context, proposals, zero writes and
zero errors/failures is required before `verify` creates the live-start proof.
Proof is RAM-only and is removed by a new shadow run or reboot. The existing
live code retains its five-minute bounds. **D1-r2 blocks live start even with
proof**; the D2 package profile enables the live menu/action only after a
fresh successful shadow check. Both profiles start disabled after reboot.

D2 saves the exact verified shadow status, status-menu observations and
pre-disable status/request files. The unchanged Java adapter resets per-run
counters on disable, so the latest stopped status alone does not describe
the active run. Snapshot failure during export still disables output and
retains RAM for retry. The immediate disable action has no copy dependency.

Installation uses the base toolbox's size checks (`ls -ln`, fifth field),
existing `awk` bootclasspath merge and `cp -p`/rename staging. There are no
on-unit hash, tr, cksum, timeout or new shell utility dependencies. The saved
controller runs without SD; disable needs no driver/JAR validation. Uninstall
removes D1 surgically, preserving prepend jars installed before or after it.
It does not restore an obsolete complete boot script over later edits. A
failed script replacement leaves the JAR/recovery copy for retry, with the
RAM enable request already removed. Installing/removing the HMI JAR requires
a full reboot; manual enable/disable/export does not.

## Verification and rebuild

- Exact patched stock stages: publishing, zero distance, all slots cleared,
  lane suppression, ownership/lease loss, OEM priority, stock handback,
  rejected delivery/clear retries, off/shadow pass-through and stage removal.
- 19,360 mapping vectors match the prior Python mapper.
- Synthetic lifecycle and 600-message bounded-cache/delta stress match the
  Python bridge; incomplete append and malformed-window rejection are checked.
- Both private C4 journals match the Python bridge at all 368/303 observations;
  starting against either complete old journal produces no live proposal.
- Closed-PATH shell tests cover actual host C4 processes, firmware/payload
  refusal, idempotence, reinstall, existing/later jars, no-SD removal, failed
  install/restore commits, shadow gating, export retention and immediate disable.

The generated build's `runtime-verification.json` and package `manifest.json`
record exact code/JAR fingerprints and test counts. These are host checks;
Factory-J9 linking is now checked under QNX with the failed release as a
negative control. D3 extends the positive checks to thirteen under both
`-noverify` and `-verify`.
Full HMI startup, RAM recording, eligible ownership and healthy shadow
processing passed on the unit. The new r2 journal also matches the Python
model at all 214 observations. D2's 20 controller tests include retained
shadow/active evidence and snapshot-failure disable behavior. D2 subsequently demonstrated native AID/HUD arrows and disconnect clearing;
D3 subsequently demonstrated corrected distance and displayed route totals,
with zero failures/errors at the active status check and no issues reported.

D3 changes the Java JAR: all six stock replacements and helpers still target
major 46 and compile against factory CDC classes. There are 123 host factory
integration assertions, including real factory distance converters at metric/
imperial boundaries, zero/overflow behavior, route-value clearing and retries.
Java/Python parity covers D2's 208/573 and r2's 214 observations, plus trip
lifecycle vectors. All 13 factory ARM J9 checks pass with `-noverify` and
`-verify`; the original D1 remains a required failing control. The package
builder checks these exact fingerprints. The default package profile is D3;
historical r2/D2 artifacts remain unchanged.

Trip values require new accepted route fields after the publication baseline.
They are independent of selected maneuver heads, carry through omitted deltas,
and reset on route episodes/stop/loading, allocation changes or invalidation.
Unsigned out-of-range values are invalid; source zero is valid. Duration is
bounded to the factory formatter's 99h59m range. No absolute ETA is synthesized
from an assumed timestamp epoch/timezone. Private totals stay out of status.

```sh
python3 MU1427/route-guidance/build-live-bridge.py \
  --java-home "$RG_JAVA" --stock-jar "$RG_STOCK_JAR" --jxe "$RG_JXE" \
  --asm-dir "$RG_REFERENCE/toolchain/java" --output "$RG_HMI_BUILD"
python3 MU1427/route-guidance/test-live-bridge.py "$RG_HMI_BUILD" \
  --java-home "$RG_JAVA" --stock-jar "$RG_STOCK_JAR"
python3 MU1427/route-guidance/test-live-control.py
python3 MU1427/route-guidance/test-live-qnx.py "$RG_HMI_BUILD" \
  --stage2 "$RG_STAGE2_IFS" --firmware "$RG_FIRMWARE" \
  --java-home "$RG_JAVA" --stock-jar "$RG_STOCK_JAR" \
  --toolchain "$RG_QNX_TOOLCHAIN" --failed-jar "$RG_FAILED_D1_JAR" \
  --output "$RG_QNX_BUILD"
python3 MU1427/route-guidance/build-live-package.py "$RG_HMI_BUILD" \
  --qnx-result "$RG_QNX_BUILD/result.json" --profile D3
```

Use the already pinned jxe2jar/reference artifacts described in
[NATIVE-BRIDGE.md](./NATIVE-BRIDGE.md). Optional private environment variables
are `CPMAP_PRIVATE_C4_DIR` and `CPMAP_PRIVATE_C4_2_DIR`. Firmware-derived
classes/JARs and SD packages remain in ignored build directories. Mapping
and protocol adaptations remain GPL-3.0-or-later, with LuKa attribution in
the source/previous contract. No raw capture is copied into the package.

## Automatic release

The release build (`build-live-bridge.py --release`) keeps the tested mapping,
factory formatter, six stock hooks and ownership/clear/retry behavior. It adds
`MailboxReader.java` and an automatic background loop. The boot script starts
`release/reader.c` independently, before J9. All virtual-device operations
remain in the supervised worker with a 1,500 ms deadline and bounded shutdown.
The supervisor stops on a stuck worker; it does not accumulate replacements.

The native process atomically replaces a bounded `RGM1` RAM mailbox, retaining
the latest validated compact window across heartbeat writes. Invalid/stale/end
records replace that window. The Java thread validates the complete file,
producer instance and immutable serials, then feeds the same `LiveModel`.
Initial/restarted producer content is baseline-only; heartbeats and read
recovery cannot revive old guidance. There is no growing journal, SD access,
manual enable proof, five-minute deadline or diagnostic elapsed-time cap.
Maximum feed-file storage, including temporary files/status, is below 70 KiB;
this bound is separate from the processes' memory use.

The release status is under `/ramdisk/carplay-route-guidance`. A RAM `disabled`
marker releases output until reboot. The saved controller at
`/mnt/app/carplay-route-guidance/control.sh` can disable/uninstall without SD.
Uninstall removes both guidance boot entries/JAR and restores driver/config
from the preserved OEM backups, retaining unrelated HMI modifications.
`Restore factory files` removes this add-on before the base video restore.

The full-JAR regression and native reader/Java mailbox integration pass using
factory ARM J9/libc under QNX, including fresh post-baseline route totals.
Eleven shell lifecycle/rollback tests, six real-worker/mailbox tests and the
existing 123 stock-stage assertions pass. Automatic unit startup, extended
operation and the 16-pixel card shift still need the installation check.
