# MU1367 / 791 native audio R2 probe

**Deferred November 3:** native progress is no longer being pursued for this
AID. Use [artwork R3](ARTWORK-R3.md) for the current artwork test. The R2
procedure below is retained for interpreting existing logs and recovery.

The November 2 Ottocast test with Apple Music and Spotify did **not** show native
playback time, and artwork still took seconds. Its export contains 199 position
callbacks, 186 local progress updates, seven fetched covers and 30 fetch misses.
The first build did not record the real DSI handoff or native errors. Its
`progress_sends` count cannot establish bus delivery or cluster rendering.

R2 is a diagnostic build. It keeps native progress only and leaves the metadata
layout unchanged. It does not claim a working time display or faster artwork.

## Install

Use the complete R2 ZIP on the SD and refresh the Toolbox menus as usual. With
CarPlay disconnected, select **Install native audio R2 probe (reboot)**, then
fully reboot. It accepts either the original identity-bound artwork JAR or the
exact installed R1 `MU1367-audio-progress-86d70b62d256`. An R1 upgrade verifies
its controller and original backup before writing. No R1 removal is needed.

R2 replaces only `CarPlayMU1367Audio.jar`. Its separate saved controller and
backup live in `/mnt/app/carplay-mu1367-audio-progress-r2`. The R1 directory and
its original-audio snapshot remain intact. Other runtime changes are refused.

Play a track for around 20 seconds, pause/resume it, seek once, and skip two or
three tracks while watching the artwork. Export the normal Toolbox diagnostics
afterwards. The same short run in each app is sufficient; avoid rapid repeated
skips until the first covers have appeared so their timing can be distinguished.

**Native audio R2 / artwork timings** shows the new counters. The normal export
also includes `/ramdisk/cpmap-artwork-timing.status`, a bounded eight-cover
history containing numeric timings and handles, without titles or media IDs.

## Interpret the diagnostics

- `progress_sends`: local update attempts, retained for compatibility.
- `progress_native_calls` / `progress_native_returns`: factory DSI handoffs and
  synchronous method returns. A return is **not** an acknowledgement from AID.
- `progress_native_position_s` / `progress_native_total_s`: actual numeric DSI
  payload, rather than an inference from callback counts.
- `progress_native_acks` / `progress_native_ack_type`: native stack callbacks.
  These are still not proof of the cluster's rendered output.
- `progress_native_errors` / `progress_native_error_code`: native function errors.
  Stage errors are counted separately. Errors delay retries by one second.
  Error 66 can mean either not implemented or temporarily unavailable; it does
  not permanently disable progress or prove lack of cluster support.
- `progress_native_indications`: incoming native function indications. The type
  is retained so requests can be distinguished from other notifications.
- `bap_async_errors_global`: BAP asynchronous exceptions have no function identity;
  they are explicitly global and are never attributed to progress by assumption.
- Artwork timings separate first valid PPS metadata, text/metadata match, the
  fetch subprocess, ready image, accepted handle and proactive picture push.
  An unavailable endpoint has latency `-1`, not a fabricated zero.

`last_fetch_process_ms` includes process launch, device reads, decode and cleanup;
it does not measure decode in isolation. PPS-to-ready time cannot by itself be
called phone transfer time. R2 preserves the 200 ms polling, native fetch helper,
strict image identity checks, supervised deadline and eight-file cache.

## Restore

Select **Restore audio before R2 (reboot)** and fully reboot. If R2 was installed
over R1, this restores R1 exactly. To return all the way to original artwork,
restore R2 first and then run the retained R1 restore action/control before the
final reboot. Remove the audio test layers before changing the base integration.

Saved MMX-shell recovery without SD:

```sh
/bin/ksh /mnt/app/carplay-mu1367-audio-progress-r2/control.sh recover
```

After restoring R2, the retained R1 controller can restore original artwork:

```sh
/bin/ksh /mnt/app/carplay-mu1367-audio-progress/control.sh uninstall
```

Retained recovery snapshots are never overwritten. The archive has a distinct
R2 filename; the field-tested R1 artifact and its verification remain available.
