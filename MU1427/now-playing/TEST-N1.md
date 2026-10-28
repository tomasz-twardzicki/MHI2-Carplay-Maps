# N1: native CarPlay title and artist on MU1427 / AID 791

N1 uses the native track callbacks demonstrated by A0 to fill the stock
audio BAP title, artist and album fields. [A1 on-unit testing](./A1-RESULTS.md)
accepted correct, immediate text updates and normal controls, source
switching, Google Maps, HMI and native guidance for the reported run.
Album text visibility depends on the cluster view. **Cover art is not
implemented**: A0 received no native cover callbacks.

Use `CarPlay_Maps_VC_MU1427_Audio_N1_Test.zip`, a full toolbox, with its
adjacent `SHA256SUMS.txt`. Support remains MU1427 / 791 only. The base video
patch and existing native guidance can remain installed. N1 does not change
the iAP2 driver/config, maps, native guidance or audio-source selection.

## Replace N0 before installing N1

1. Export any remaining N0 evidence. Select **Remove N0 audio observer
   (reboot)** in the old menu, then **fully reboot**. Removal without reboot
   leaves its Java replacement loaded. If the old menu is unavailable, run
   `/bin/ksh /mnt/app/carplay-now-playing-n0/control.sh uninstall` on MMX
   (prefix with `on -f mmx` from RCC), then reboot.
2. Preserve old SD `Log` folders separately. Extract the complete N1 ZIP to
   the SD root and refresh the toolbox scripts/menus as before.
3. In **Customization → CarPlay Maps VC**, select **Install N1 audio text
   test (MU1427 research, reboot)** with the phone disconnected. Expect
   `CPMAP_AUDIO_N1_INSTALLED_REBOOT_REQUIRED` or `CPMAP_AUDIO_N1_ALREADY_INSTALLED`.
4. Fully reboot. Check normal HMI/OEM cluster startup before reconnecting.
   N1 refuses installation if the N0 JAR, boot reference or RAM status still
   exists. Follow the reported remove/reboot instruction rather than deleting
   the RAM status to bypass the check.

Both phases replace the factory CarPlay target, so they cannot be loaded
together. Also avoid another custom JAR replacing that target or
`de.vw.mib.bap.mqbab2.audiosd.functions.CurrentStationInfo`. The builder checks
the provided baseline JARs for conflicts; it cannot inspect other unit mods.

## Parked display test

Keep stable power. Use **Export N1 audio snapshot to SD** after each phase;
folders are `Log/cpmap-audio-N1-01` through `-16`. Note the folder/step mapping
and which app was active. Exports contain counters, never track strings.
Keep the test running for more than five minutes.

1. Connect the iPhone and play music without a navigation route. In the AID
   audio view, compare title and artist with Apple Music; check album text
   if the selected layout displays it. Change tracks several times, including
   a long or accented title if available. Confirm old artist/album fields
   disappear when the new content lacks those fields.
2. Pause and resume. Paused music should retain its current text. Stop or
   clear playback if the app supports it: explicit invalid/empty/stopped
   metadata should return to the generic CarPlay label and clear old details.
3. Repeat with Spotify and switch between the apps. A track can remain
   unchanged for minutes; it should not disappear on a five-second timeout.
4. With the phone connected, select ordinary radio/USB/SD/Bluetooth audio.
   Confirm normal source text and controls. Return to CarPlay music and check
   its current track. A connected phone must not overwrite another source.
5. Disconnect, wait, and export. Reconnect and play a different track; check
   that previous-phone text does not return before new metadata. Export.
6. Start/stop phone navigation while music plays and check the existing
   map/native-guidance behavior. If practical, briefly use Siri or a phone
   call and check normal audio/service recovery afterwards.

During eligible phone audio, expect `connected=1 context=1`, timer/fill
activity, property updates, and `failures=0 attach_failures=0`.
`context=0` is another source/connection; `-1` is unknown before sampling.
`accepted` and `rejected` count true/false factory property-listener returns,
**not cluster acknowledgments or transport errors**. A1 prompted inspection
of the exact factory cache: unchanged values can legitimately return false.
A growing `rejected` count alone does not establish a fault. Record missing,
wrong or stale text and any nonzero failure counters. See the
[A1 return-value correction](./A1-RESULTS.md#correction-rejected-does-not-mean-transport-failure).
Counters are process-wide; `epoch` changes on DSI attachment and does not
reset them. A single snapshot cannot establish transition/recovery order.

## Removal and recovery

Export before reboot, then select **Remove N1 audio text test (reboot)** and
fully reboot. The RAM status remains available for export until reboot.
The already loaded hook can continue until that reboot. Remove N1 before
the toolbox's general factory-restore action.

No-SD MMX recovery:

```sh
/bin/ksh /mnt/app/carplay-now-playing-n1/control.sh status
/bin/ksh /mnt/app/carplay-now-playing-n1/control.sh uninstall
```

From RCC prefix commands with `on -f mmx`; then fully reboot. Removal keeps
native guidance, its matched driver/config, base maps and unrelated JARs.
If boot-script replacement fails, the controller keeps the JAR and recovery
files for retry; do not manually delete a JAR still named by the boot script.
