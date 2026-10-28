# N0: observe CarPlay audio on MU1427 / AID 791

This test subscribes to the head unit's factory CarPlay audio callbacks.
**The cluster will still show its existing CarPlay label.** N0 counts valid
title/artist/album events, playback updates and cover locators. It does not
send text/artwork to the cluster or change the iAP2 driver.

Use the generated **full toolbox**
`CarPlay_Maps_VC_MU1427_Audio_N0_Test.zip` and its `SHA256SUMS.txt`.
Firmware: `MHI2_ER_VWG11_K3342_MU1427`; profile: `MU1427/791`.
The working base map/video patch must already be installed. Existing native
guidance can remain installed. Do not install N0 alongside another custom
JAR that replaces `de.vw.mib.asl.internal.carplay.target.HsmTarget`.
The package builder checks the supplied toolbox JARs for this conflict;
it cannot inspect unrelated JARs already on your unit.

Host and factory QNX/J9 checks precede this package. Full HMI startup and
notification delivery still need this first on-unit test. Work parked with
stable power. If startup or CarPlay behaves abnormally, remove N0 using the
saved recovery controller below and fully reboot.

## Installation

1. Preserve existing SD `Log` folders separately. Extract the full ZIP to
   the SD root and refresh the toolbox scripts/menus using the same method
   as the existing bundle. There is no separate overlay to merge.
2. Open **Customization → CarPlay Maps VC**. Confirm four entries containing
   **N0 audio observer** / **N0 audio snapshot** appear near the bottom.
   The ordinary map and native-guidance entries remain available.
3. Disconnect the iPhone. Select **Install N0 audio observer (MU1427
   research, reboot)**. Expect `CPMAP_AUDIO_N0_INSTALLED_REBOOT_REQUIRED`
   or `CPMAP_AUDIO_N0_ALREADY_INSTALLED`.
4. Fully reboot the head unit. Confirm normal HMI and OEM cluster operation
   before connecting the phone. No base-map or native-guidance reinstall
   is needed for this test.

Installation saves the original boot script for reference and its recovery
controller under `/mnt/app/carplay-now-playing-n0/`. It prepends a separate
`CarPlayNowPlayingObserverN0.jar` while preserving other JARs and boot entries.
Removal edits only that JAR reference; it does not restore an obsolete
complete boot script over later changes.

## Test and export

Use **Export N0 audio snapshot to SD** after each step. It creates the next
available folder `Log/cpmap-audio-N0-01` through `-16`, without overwriting
earlier exports. Note which folder corresponds to each step. A status file
may be absent until the CarPlay service initializes; this alone does not
establish a boot failure.

1. After reboot, before phone connection: export the initial baseline.
2. Connect the iPhone and play a track with title, artist and artwork visible
   on the phone/CarPlay screen, without running a route. Wait about 10 seconds,
   show N0 status, then export.
3. Change track twice, waiting about 10 seconds between changes, then export.
4. Pause, show status, export; resume, wait about 10 seconds, and export again.
5. If available, switch to another audio app. Play a track, wait and export.
6. Start a CarPlay route and keep music playing. Confirm the existing map
   and native-guidance behavior remains normal, then export. Let N0 remain
   installed/running for more than five minutes during this parked test.
7. Disconnect, wait, export; reconnect and play a different track, wait and
   export again. Also confirm ordinary radio/USB/SD/Bluetooth audio still
   behaves normally when selected; testing every source is unnecessary.

The usual run uses fewer than 16 exports. Move/preserve old export folders
before starting another run if the menu reports `EXPORT_SLOTS_FULL`.
Exports contain counters and installation state, without track text, image
paths, device identifiers or image bytes. Report the phone audio app and any
HMI/CarPlay/cluster issue alongside the ordered export folders.

Interpretation:

- `writes` increasing means the RAM status writer is running. It is not a
  phone-connection or freshness indicator.
- `attached=1` with `attach_failures=0` means the subscription call returned
  successfully. Valid callback counts establish whether data actually arrives.
- `valid_tracks`, `titles`, `artists` and `albums` count valid, nonempty
  fields. Compare snapshots around track changes; counters alone cannot
  verify the text content's accuracy.
- `cover_urls` or `cover_ids` increasing identifies a possible native artwork
  input. It does not prove that the image is readable or displayable.
- `playback_state=1` is playing, 2 paused, 0 stopped, and -1 unknown/invalid.
- `epoch` changes when the DSI service is attached again. It need not change
  on physical phone reconnection; N0 does not infer phone sessions from it.
- A subscription failure is retained as `attached=0` and
  `attach_failures>0`. Missing status after phone connection, persistent zero
  valid callbacks, or nonzero exception/failure counters are useful results;
  do not assume the text/artwork input works without those observations.

## Removal and recovery

Export before reboot: RAM status is lost on reboot. **Remove N0 audio
observer (reboot)** removes its JAR/boot entry and preserves the RAM status
so it can still be exported before the required full reboot. Its already
loaded Java code may continue until that reboot. Remove N0 before using
the toolbox's general **Restore factory files** action.

Without SD, run on MMX:

```sh
/bin/ksh /mnt/app/carplay-now-playing-n0/control.sh status
/bin/ksh /mnt/app/carplay-now-playing-n0/control.sh uninstall
```

From RCC, prefix each command with `on -f mmx`. Then fully reboot. This
removes only the audio observer; it preserves the map/video patch, native
guidance, its driver/config and unrelated HMI patches.

If removal cannot commit the edited boot script, it retains the JAR and
saved controller. Keep the error output, correct the reported filesystem
condition and retry `uninstall`; do not delete the JAR while its boot
reference remains. A stale installer lock is not removed automatically.
