# MU1367 / 791 audio progress test

**Deferred, November 3:** the owner confirmed no native time display with OEM
Bluetooth/CD on this AID. Stop native-progress testing. The current
[artwork-only R3 candidate](ARTWORK-R3.md) removes the extra processing and focuses
on cover fetching, PNG size and pipeline timings. This document is historical.

**Vehicle result, November 2:** the first test received playback callbacks but
did not display native time, and artwork still took seconds over Ottocast in
both Apple Music and Spotify. Local send counters do not establish native
delivery. The [historical native-only R2 probe](AUDIO-NATIVE-R2.md) distinguishes DSI
handoff, native rejection and artwork pipeline timing. No metadata time fallback
is enabled. The sections below retain the original R1 procedure and scope.

The subsequent [LuKa Audi comparison](AUDIO-NATIVE-AUDI-COMPARISON.md) confirms
the same native function and time units, and records the framework and
unknown-time differences without claiming VW cluster compatibility.

This test adds elapsed time and track duration to the cluster's native AudioSD
progress function (0x34). Positions come from CarPlay's native callbacks and are
converted from milliseconds to seconds. Pause holds the last received position;
seeking follows the phone. A different track, stop, disconnect or invalid track
clears the old position. Unknown duration produces no progress. No estimated
clock runs when the phone stops delivering positions.

Artwork now checks for completed transfers every 200 ms, with short initial
retries. A newly ready cover bypasses the one-second retry throttle, so the
ASL timer can publish it on its next 200 ms tick. Unchanged images generate no
extra BAP output, diagnostic files still update once a second, and the existing
identity checks, decoder deadline and eight-image cache remain in use. Phone or
adapter transfer time and cluster image loading can still add delay; the polling
change is not a measured vehicle latency result.

## Install and restore

Exact **K4525 MU1367 + AID 791** with the working identity-bound artwork runtime
is required. This is a separate test, not a published release. The complete ZIP
contains the unchanged v1.4.1 runtime baseline plus the additional audio test actions.
Its three baseline preflight checkers are regenerated with the CarPlay-only scope;
optional Toolbox Demo/example files may be removed.
An existing later navigation test can remain installed if its audio JAR, artwork
driver and fetch worker still match the checked baseline.

1. Extract the complete audio test ZIP to the SD root, then refresh/install the
   Toolbox menus in the usual way. If metadata and artwork are already working,
   use the audio test action directly. A fresh OEM installation must first follow
   `START_HERE.md`, install the baseline integration and fully reboot.
2. Disconnect CarPlay and fully reboot before installation. In **CarPlay Maps
   VC**, select **Install audio progress test (reboot)**, then fully reboot again.
   The controller saves the previous JAR before replacing it. It changes only
   the audio JAR and creates `/mnt/app/carplay-mu1367-audio-progress` for recovery.
3. Play a track in Apple Music and Spotify. Compare elapsed time and duration to
   the phone; test pause/resume, seeking both ways, next/previous tracks, rapid
   skips, cable/wireless reconnect and radio handback. Check that navigation and
   existing metadata/artwork still work. Try an internet stream with no duration.
4. Export the normal Toolbox diagnostics after testing. **Audio progress /
   artwork status** also shows position callback, progress output and error
   counters. Callback counts distinguish absent input from missing cluster output.
5. To undo the test, select **Restore previous audio (reboot)** and fully reboot.
   Restore audio **before** changing/uninstalling the base integration, using
   another release or doing a general OEM restore. Existing layer controllers
   reject the changed JAR instead of silently overwriting it.

If an install is interrupted, use **Recover interrupted audio update (reboot)**.
The retained snapshot also works without SD from an MMX shell:

```sh
/bin/ksh /mnt/app/carplay-mu1367-audio-progress/control.sh recover
```

Recovery retains its directory and backups. Reinstalling over a removed or
incomplete snapshot is deliberately refused; keep that snapshot for diagnosis.

## Development and evidence

Maintained sources are `src/audio`, `tools/PatchProgress.java` and the existing
audio patchers. `tools/build-audio.py` builds this test independently; `RUNTIME.json`
and the v1.4.1 release proofs continue to describe the accepted release bytes.
Do not use the release packager to promote an unvalidated audio test.

```sh
python3 MU1367/integration/tools/build-audio.py --java-home "$JDK" \
  --stock-jar "$STOCK" --asm-dir "$ASM" --output "$AUDIO_BUILD"
python3 MU1367/integration/tests/test-audio.py --build "$AUDIO_BUILD" \
  --java-home "$JDK" --stock-jar "$STOCK" --output "$HOST_TESTS"
python3 MU1367/integration/tests/test-audio-qnx.py --build "$AUDIO_BUILD" \
  --java-home "$JDK" --stock-jar "$STOCK" --setup "$FACTORY_J9_SETUP" \
  --output "$QNX_TESTS"
python3 MU1367/integration/tools/package-audio.py --build "$AUDIO_BUILD" \
  --host "$HOST_TESTS/result.json" --qnx "$QNX_TESTS/result.json" \
  --base-archive "$V141_ZIP" --output "$AUDIO_PACKAGE"
python3 MU1367/integration/tests/test-audio-package-qnx.py \
  --package "$AUDIO_PACKAGE" --setup "$FACTORY_ACTIONS_SETUP" \
  --output "$TRANSACTION_TESTS"
python3 MU1367/integration/tests/test-audio-package.py \
  --package "$AUDIO_PACKAGE" --base-archive "$V141_ZIP" \
  --transactions "$TRANSACTION_TESTS/result.json" --output "$PACKAGE_PROOF"
```

Host tests exercise the actual patched pool registration, advertised capability,
factory progress serializer and marshaller, source/session handling, and text /
artwork regressions. The factory ARM J9 test runs with verification enabled and
disabled, rejects a deliberately incompatible class and exercises ten decoded
images through the bounded worker/cache. Emulator checks establish linking and
message generation, not physical AID rendering or live app/adapter timing.
The transaction checks use the matching firmware shell and captured utilities,
including invalid payload/runtime, shared lock/live feed, repeat install,
changed runtime, corrupt backup, saved recovery, retained backup and uninstall
cases. Storage remounts are mocked. See `AUDIO-PROGRESS-VERIFICATION.json` for
the tested artifact hashes and results.
