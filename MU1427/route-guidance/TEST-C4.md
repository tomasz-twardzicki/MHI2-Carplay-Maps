# C4 continuous-reader test with the validated B4 driver

**Experimental; C4-2 passes the continuous-reader/progression test, retaining
240/240 events with normal outdoor guidance and reconnect confirmed.** See
[C4-2-RESULTS.md](./C4-2-RESULTS.md). The first garage run and its coverage
limit remain documented in [C4-RESULTS.md](./C4-RESULTS.md). C4 adds a
manual, five-minute recorder in RAM. Keep the working B4 driver installed;
**no factory restore, driver reinstall or reboot is needed for this step.**
No native cockpit/PPS/HMI output is enabled. See [OBSERVER.md](./OBSERVER.md)
for limits, format and host verification.

Prepared package:
[MU1427-route-guidance-C4-toolbox.zip](./build-C4/MU1427-route-guidance-C4-toolbox.zip).
The reader passed 22 host journal/process tests (including both private B4
replays), eight control/export tests and a QNX run using the exact factory
libc/pipe service. That run exercised 30 valid reads, background start and
explicit stop. All 41 required imports exist in the factory libc; the live
unit's polling load remains the purpose of this test.

## Prepare

1. Extract `MU1427-route-guidance-C4-toolbox.zip` to the SD root and update the
   toolbox again. Check for **C4: start 5-minute guidance recorder (RAM)** and
   **C4: stop and export guidance recording to SD** under CarPlay Maps VC.
2. Disconnect the iPhone. Select **C4: start 5-minute guidance recorder (RAM)**.
   Confirm `CPMAP_RGI_C4_STARTED`. The source file may be absent until the
   phone connects; this is expected and the recorder keeps checking.
3. Do not reinstall B4 from the menu. C4's package retains that exact tested
   driver/installer/rollback payload for recovery, with no driver changes.

## Test while parked, within five minutes

1. Connect the iPhone and start Google Maps guidance. Leave it active for
   20–30 seconds and check the AID route line and turn card.
2. Stop guidance and wait about five seconds. Start another route and leave
   it active for another 20–30 seconds.
3. Disconnect/reconnect the iPhone, start guidance again for 20–30 seconds,
   then stop it. Confirm CarPlay still works.
4. Select **C4: stop and export guidance recording to SD**. Confirm
   `CPMAP_RGI_C4_STOPPED` and `CPMAP_RGI_C4_EXPORT_OK`.
   Copy `Log/cpmap-rgi-C4-*` privately. This contains `events.rgj`, final status,
   the C4 build marker and the active driver/config for host verification.
5. Optionally run the existing C3 route-guidance capture after C4 stops to
   retain the final iAP2/error evidence too. Export **before rebooting**;
   reboot clears the RAM recording.

No need to capture isolated snapshots during this run: the purpose is to
measure continuous history coverage from before phone connection through
route stop and reconnect. The recorder automatically ends after five minutes
or 8 MiB; export still works afterwards. A capacity end is incomplete coverage
and is reported as such by host replay.

## Follow-up after the garage recording

This procedure produced the accepted [C4-2 result](./C4-2-RESULTS.md). No
further repeat is needed to establish this run's maneuver progression;
retain it for regression testing when the reader/driver changes.

Use this same package; keep B4 installed. Export and remove the previous RAM
recording before starting another. No reboot is needed.

The first recording's arrow matched the phone's Google Maps guidance, so
the follow-up targets current-maneuver selection rather than an established
AID rendering defect. Reconnect took three cable insertions in that run.
If available, use a cable known to reconnect reliably; note insertion attempts
and approximate recognition delay separately from navigation behavior.

Repeat outdoors after Maps has a usable position. Choose a route with an
identifiable ordinary left/right turn after the initial route-start
instruction. While parked, let guidance settle for 30 seconds and note
whether the card still shows a start instruction or the ordinary turn, and
whether it has an arrow. Open the active Maps route screen on the main
display for about ten seconds, then return to the usual CarPlay view for
another ten seconds; note any card/route-line change. Do not assume an
initial `START_ROUTE` instruction must have a direction arrow.

For a stronger progression check, let the recorder run through an ordinary
turn on a short route; start the recording and export it while parked. Note
whether the card advances to the next instruction and its distance changes.
A parked capture tests route startup but cannot establish maneuver progression.
Stop guidance and export within five minutes, then collect C3 while still
connected. The companion log retains location-quality evidence as well as
the final publication; no coordinates need to go into the test notes.

Prior B2/B4 logs show that the startup reset can be followed by fresh current
lists later. C4's later-connection NMEA has GGA quality `0` throughout, while
RMC says `A`, so position conditions deserve a controlled comparison. This
does not prove the garage caused the absent list; see [C4-RESULTS.md](./C4-RESULTS.md).

Keep reconnect testing in a separate recording if needed to avoid using the
five-minute window on cable retries. Export/remove the first RAM capture,
start C4 again, then follow the original disconnect/reconnect steps. Record
insertion attempts, approximate recognition delay and any extra app/route
changes. Export C4 and collect C3 again. The same package handles both runs.

## Review and acceptance

```sh
python3 MU1427/route-guidance/rgi_observer.py "$CAPTURE/events.rgj"
python3 MU1427/route-guidance/rgi_observer.py "$CAPTURE/events.rgj" --events > /tmp/c4-events.jsonl
python3 MU1427/route-guidance/rgi_observer.py "$CAPTURE/events.rgj" --messages > /tmp/c4-messages.jsonl
python3 MU1427/route-guidance/rgi_observer.py "$CAPTURE/events.rgj" --require-complete
```

Look for publishing snapshots, increasing sequences, active guidance,
resolved current maneuvers where their records were received, state-zero
clearing and a new allocation/session after reconnect. Check missing-history
counts and producer faults. A 100 ms cadence is a test setting, not a
guarantee that every initial burst fits in sixteen slots. Gaps must be visible
and must invalidate previously selected maneuver data.

Use `coverage.recorded_events` / `published_events` / `unrecorded_events` to
assess unique capture coverage. `--require-complete` fails for a real sequence
gap even if the recorder ends normally. `missing_before_windows` also counts
history discarded by consumer resets after staleness. The first run reports
118 there but misses only one unique event. `--messages` shows intermediate
selection/reset events; resolved-snapshot counts describe only the state
after each window. These host-tool additions require no unit update.

Source absence during reconnect and staleness during quiet/idle periods can
be expected. Identical successful reads must not refresh old guidance. A
worker deadline, producer fault, malformed journal or nonzero end reason
other than manual stop means the capture needs investigation. Check that
CarPlay, route visuals and reconnect remain normal throughout.

## Stop, retry or remove

- **C4: guidance recorder status** shows `running`, `unavailable`, `stale` or
  `ended` with counters. This is recording status, not proof of active routing.
- **C4: stop guidance recorder** stops without exporting. Export can be retried;
  RAM data is retained even if SD is absent or copying fails.
- After successful export, **C4: remove RAM recorder/capture (export first)**
  deletes only C4's RAM files. Remove the previous recording before starting
  another, so it cannot be silently overwritten.

If the menu is unavailable, run locally on MMX:

```sh
/ramdisk/cpmap-rgi-observer-C4 stop /ramdisk/cpmap-rgi-C4
```

From RCC use `on -f mmx` with the same local MMX paths. If the RAM binary is
missing/corrupt or shutdown cannot be confirmed, a full reboot stops C4 and
clears its RAM files. B4 and its original backups remain installed. The saved
factory-driver restore helper is unchanged:

```sh
/bin/ksh /mnt/app/route-guidance-b1/rg-b1.sh restore
```

Use the normal full reboot after a factory-driver restore. Removing C4 alone
does not restore the driver; it removes only this diagnostic recorder.
