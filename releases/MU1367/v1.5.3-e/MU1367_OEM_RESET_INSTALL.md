# MU1367 / 791 independent OEM recovery

Use the v1.4.3 SD for a complete return to exact **K4525 or P4521 MU1367 + 791**, including
mixed or partially removed test installations. This reset does not call old
per-layer uninstallers or depend on their installed/removed markers.

The controller checks the complete factory `lsd.jxe` fingerprint, every OEM
payload and required command before writes. Its command inventory comes from
both matching factory IFS variants, not the SDK. Required reset tools are `cat`,
`cp`, `mv`, `rm`, `mkdir`, `chmod`, `sync` and `mount`; hashing uses the supplied
verifier. Optional `df`/`slay` are used only when available. No `rmdir` is needed.

## Restore

Keep a working MMX shell, park with stable power, disconnect phone/adapter and
fully reboot. Refresh both Toolbox menus and scripts from this release SD.
Use **Diagnostics > Check required commands**, then **Inspect OEM reset state**.
Inspection is read-only. Save its output on any failure.

Choose **Recovery > RESTORE OEM + retain all snapshots**. This remounts
`/mnt/app` and `/mnt/system`, checks actual writes, saves existing target files,
then restores the firmware-matched boot script, `dio_manager`, iAP2 driver and
configuration. It removes this suite's override JARs and archives all twelve
active runtime/recovery roots, including roots marked removed. Old staging
files are retained separately. Preferences and earlier `.removed-*` archives
are retained. Completed prior reset sessions are moved aside as `.completed-*`
before a subsequent reset; an interrupted session must be recovered instead.

Expect **`MU1367_OEM_RESET_COMPLETE_FULL_REBOOT_REQUIRED`**. Fully reboot with
the phone/adapter absent, then **Diagnostics > Verify restored OEM files**.
Expect `MU1367_OEM_RESET_VERIFIED_REBOOT_IF_NOT_ALREADY_DONE`. Check OEM HMI,
cluster, navigation/audio and ordinary cable CarPlay before installing again.
The same SD's single install/update action provides the complete fresh path.

Without menus, on MMX (from RCC enter MMX with `on -f mmx`):

```sh
/bin/ksh /fs/sda0/RUN_CHECK_TOOLS.sh
/bin/ksh /fs/sda0/RUN_INSPECT.sh
/bin/ksh /fs/sda0/RUN_RESTORE.sh
```

After reboot:

```sh
/bin/ksh /fs/sda0/RUN_VERIFY.sh
```

Use `/fs/sdb0` throughout if appropriate. Keep the SD and archive
`/mnt/app/carplay-mu1367-oem-reset`, its `pre-reset`, `archive` and `stale-files`,
and all `.removed-*` / `.completed-*` sessions off-unit. Never delete snapshots
to force an installation.

The full original HMI boot script is restored, so unrelated boot-script edits
are also removed after backup. Coding, FECs, pairing, OEM data and Toolbox stay
in place. Custom MU preferences stay unless the settings-reset action is used.

## Interrupted reset or failed write

Stop on failure and retain the exact output. Disconnect, fully reboot to clear
an abandoned RAM lock, then rerun `RUN_RESTORE.sh`. It resumes using its saved
OEM payload and immutable pre-reset snapshot. Partially archived directories
are handled without overwriting their saved originals. Success requires every
OEM file and the absence of all twelve active roots to verify.

Once `BACKUPS_READY` exists, forward recovery needs neither SD nor HMI. On MMX:

```sh
/bin/ksh /mnt/app/carplay-mu1367-oem-reset/control.sh restore
```

Do not run old layer removers during this recovery. A snapshot checksum failure,
symlink conflict, incomplete preparation or real remount/write failure stops
the controller. Keep the evidence for repair; do not force a marker or move an
incomplete session aside. The pre-reset snapshot may itself contain the broken
mixture, so reset does not automatically reinstall that mixture on failure.

After a physical storage failure, software restoration cannot make a partition
writable. The reported failed mount/write operation needs separate diagnosis.
