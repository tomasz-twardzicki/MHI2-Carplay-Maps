# MU1367 / AID 791: installation, test and recovery

This is a test package with [subsequent initial user results](../settings-v2/UNIT-RESULTS.md)
for the combined MU1367 integration/settings build. The original build-time
checks below are separate from that report.
Use only the supplied MU1367 firmware identity and 791 cluster. The 790 menu
is for the previously developed, still untested video experiment only.

## Prepare

1. Verify the ZIP against its adjacent `SHA256SUMS.txt`, then extract to a
   clean SD root and refresh the MQB Toolbox scripts/menus. The CarPlay menu
   must say **MU1367 test**. Preserve existing diagnostic exports separately.
2. Keep a working MMX shell connection and the recovery commands below before
   changing the HMI. Do this while parked with stable power and the phone
   disconnected. The scripts never reboot automatically.
3. Remove any generic `NavActiveIgnore.jar` with its own uninstaller and
   fully reboot first. The integration installs a MU1367-matched replacement.
   Old MU1427 adapter/recovery directories must not be used to restore files
   after a firmware upgrade. The new installer refuses old recovery markers
   and non-OEM driver/configuration. Inspect/archive old backups off-unit;
   do not overwrite MU1367 with old firmware files to satisfy a check.
4. Confirm the ordinary OEM HMI, cluster map and CarPlay work after the
   upgrade. Installation checks the complete MU1367 JXE hash, then exact
   OEM iAP2 driver/configuration and all payload hashes using its own small
   QNX verifier. An unexpected hash is a stop condition to investigate.

## Install and first check

1. Select **1. Install MU1367 / 791 video**. This uses the existing AUTO MU
   installer with the new narrow turn-card/30 fps core. Native/audio install
   requires the resulting `MU1367/791` profile.
2. Select **2. Install MU1367 / 791 guidance + audio text**. Expect
   `MU1367_INSTALLED_REBOOT_REQUIRED`. It also installs the matched navigation-active HMI adapter. It saves verified driver/configuration,
   boot script and JAR-presence backups under `/mnt/app/carplay-mu1367/backup`
   before committing. Its saved controller, verifier, reader and variants
   remain available without SD.
3. Fully reboot. Confirm OEM cluster/HMI operation with the phone absent,
   then connect and test a short route. Compare AID/HUD arrows, maneuver
   distance, remaining route distance and travel duration to the phone.
4. Check the turn card clears the native distance/time bar. Display options
   include narrow/wide, map-only and **stock-40fps**; every change needs a full
   reboot. The 790-only lower-card option is absent from the 791 payload and
   must refuse without changing the core.
5. Test Apple Music and Spotify title/artist/album changes, pause/resume,
   rapid track changes, OEM source switching, navigation coexistence and
   unplug/reconnect. The audio status `accepted`/`rejected` fields are N1
   property-listener true/false returns; false can mean cached-equal data,
   not a failed transmission. The existing N1 retry behavior is preserved.
6. Run beyond five minutes and repeat after a full reboot. Stop guidance,
   disconnect/reconnect, then start OEM guidance. Phone output must clear or
   yield to OEM navigation. Check failure/error counters and collect
   diagnostics **before** rebooting; RAM logs disappear at reboot.

Google/Apple Maps and Waze must be checked individually. Earlier MU1427 Waze
stutter/freezing remains unexplained; the 30 fps port does not establish a fix.
No unit result, app compatibility or elapsed-duration acceptance is inferred
from host/QEMU tests.

## Optional N3 artwork test

Do this only after the normal guidance/audio tests pass. Select
**Experimental N3 capture ON**, fully reboot, and test one app/track at a
time. This swaps only the driver; no Java decoder or cluster picture output
starts automatically. Use the saved manual worker from the MMX shell:

```sh
mkdir /fs/sda0/Log/mu1367-artwork-01
/mnt/app/carplay-mu1367/artwork-capture /dev/ipod0/rgi-events /ramdisk/.mu1367-artwork-reader-lock /fs/sda0/Log/mu1367-artwork-01
```

Use the actual mounted SD path and a new empty output directory each time;
ensure the SD is writable. The worker has a five-second deadline, bounded
reaping, a bounded owned image mailbox and decoder memory limits. If cleanup
cannot be confirmed it retains the RAM lock; reboot instead of repeatedly
starting workers. Exports can contain original embedded image metadata.
Artwork generation is not a verified track identity. Compare the exported
cover to the phone, including after fast changes/reconnect.

Select **Experimental N3 capture OFF** and fully reboot to return to B4.
The main uninstall also accepts N3 and restores the OEM driver/configuration.

## No-SD recovery

Run on **MMX**. From RCC, execute through `on -f mmx`.

```sh
/bin/ksh /mnt/app/carplay-mu1367/control.sh status
/bin/ksh /mnt/app/carplay-mu1367/control.sh disable
/bin/ksh /mnt/app/carplay-mu1367/control.sh uninstall
```

`disable` affects native guidance until reboot; audio stays installed.
`uninstall` removes all three HMI adapters and reader startup, restores the paired
MU1367 OEM driver/configuration, and retains the video profile and recovery
backups. It removes only its boot entries and preserves later unrelated
entries. **Fully reboot after removal.**

If installation lost power, a rename failed, or a transaction is incomplete,
use the saved snapshot recovery instead:

```sh
/bin/ksh /mnt/app/carplay-mu1367/control.sh recover
```

It verifies every backup before restoring any, restores the exact pre-add-on
snapshot (including the boot script), and keeps backups. This recovery can
discard boot changes made after that snapshot; normal removal preserves
them. Keep the phone disconnected and fully reboot afterward. If a lock
remains after power loss, confirm no install/remove process is running,
inspect it, then remove the empty
`/ramdisk/.carplay-guidance-install-lock` directory and retry recovery.
Do not delete backups or replace them with another firmware's files.

For an HMI startup failure where the controller cannot run, remove only
these three prepend JARs from MMX and fully reboot to let J9 use its stock HMI:

```sh
rm /mnt/app/eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar
rm /mnt/app/eso/hmi/lsd/jars/CarPlayMU1367Audio.jar
rm /mnt/app/eso/hmi/lsd/jars/CarPlayMU1367NavIgnore.jar
```

Missing prepend entries are skipped by the factory runtime. This emergency
step does not restore the native driver/configuration; run `recover` once
shell access works. Do not use normal `uninstall` after manually deleting
JARs, since its integrity checks will correctly refuse.

## Full return to OEM

Remove/recover the integration first and fully reboot. Then select **Restore
factory video + integration**, which calls the existing base video restore.
It restores the saved `dio_manager`, base boot script and original controls
JAR state, then removes the video directory. Fully reboot again and verify
OEM cluster map, audio and CarPlay. Without SD, the installed toolbox base
restore is `/bin/ksh /mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_restore_core.sh`.
Never restore the base alone while the
native/audio integration remains installed. Keep recovery backups until the
OEM check passes; archive them off-unit before a fresh installation.

Recovery reduces the consequences of failures; it cannot make power loss,
storage failure or untested in-car behavior risk-free. Extended endurance
and the individual acceptance steps remain unrecorded for MU1367.
