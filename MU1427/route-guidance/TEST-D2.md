# D2: first live native arrow/distance test

> Historical test procedure. Use [INSTALL.md](./INSTALL.md) for the released package. Obsolete test tools are retained in [Git history](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/tree/838dd535c23cb8214b170216066e60f8690d2074/MU1427/route-guidance).

**Completed:** native arrows on AID/HUD and clearing accepted; distances
need a conversion fix. See [D2-RESULTS.md](./D2-RESULTS.md) and the next
[D3 test](./TEST-D3.md). This page retains the completed D2 procedure.

Package: [MU1427-route-guidance-D2-toolbox.zip](./build-D2/MU1427-route-guidance-D2-toolbox.zip).
D1-r2 passed startup and shadow; see [D1-r2-RESULTS.md](./D1-r2-RESULTS.md).
D2 uses the **identical Java JAR**, B4 driver and C4 native reader. It adds
the live menu and preserves shadow/active status before disable resets it.
Native cluster rendering is the new, unverified part of this test.

## Install and reboot

1. **Keep B4 installed. Do not restore the driver to factory.** If D1-r2 is
   still installed, export anything needed, select its remove-adapter option
   and fully reboot. If you already removed it and rebooted, start there.
2. Extract D2 to the SD root and refresh the toolbox scripts/menus as before.
   The new entries must say **D2:**. Select **D2: install native guidance
   adapter (reboot)** with the phone disconnected, then **fully reboot**.
3. Check normal cluster navigation before connecting the phone, then normal
   CarPlay map/card behavior after connecting. Output starts disabled.

The payload version is `MU1427-RGI-D2-cbdd13d9`. Adapter status still begins
`D1 build=8a25954d4812cdf0`: that is expected because the Java binary is
unchanged from the successful r2 test. D2 uses the same installed JAR path
and saved recovery controller as r2.

## Fresh shadow check, then export

1. Outdoors, with OEM guidance stopped, select **D2: start 5-minute SHADOW
   test**, then start phone guidance in the same app as the accepted test.
2. After 20–30 seconds, while guidance is active, select **D2: adapter and
   recorder status**, then **D2: verify healthy shadow before live**. Expect
   `CPMAP_RGI_D1_SHADOW_VERIFIED`. This requires `mode=1 context=0`, nonzero
   proposals/ticks, and **`writes=0 failures=0 error=0`** for this build/run.
3. If verification fails, use disable/export and return the logs; do not
   proceed to live. D2 also refuses live start without the successful proof.
4. Stop phone guidance, select **D2: disable and export capture**, then
   **D2: clear RAM capture (export first)**. Expect `CPMAP_RGI_D1_EXPORT_OK`.
   **Do not reboot between shadow and live**; the proof is RAM-only.

The shadow export now includes `shadow-verification.txt`, plus available
pre-disable and observed status snapshots. A stopped `adapter-status.txt`
can still have reset counters; use the retained snapshots for active values.

## Live, at most five minutes

1. With OEM guidance stopped, select **D2: start 5-minute LIVE arrows and
   distance**. Start a new phone route **after** starting the recorder, so
   the adapter sees fresh progress rather than an old ring window.
2. Check the native AID guidance area for the current maneuver and distance.
   Observe an ordinary right and left turn if the route allows. Note whether
   the native arrow agrees with the phone, distance decreases, and a new turn
   replaces the preceding one. Missing/conflicting geometry may deliberately
   produce a blank native arrow. The phone map/video turn card should keep
   working normally. Street, ETA, phase and bargraph output are outside D2.
3. While native guidance is active, select **D2: adapter and recorder status**.
   Expect `mode=2 context=0`, proposals and writes increasing, and
   `failures=0 error=0`. This action saves a status snapshot for export.
4. Stop phone guidance and check that the native arrow/distance clear. Start
   another route, disconnect the cable during guidance, and check clearing.
   Reconnect and start guidance again; fresh updates should restore output.
5. With phone guidance stopped, briefly start/stop OEM navigation. Check that
   OEM guidance has priority and no old phone arrow remains over it.
6. With phone guidance active again, select **status** to save its counters,
   then **D2: disable native output NOW**. Check that native output releases
   within about two seconds and ordinary CarPlay continues. Select **disable
   and export capture** before rebooting.

If behavior is abnormal, disable and export immediately; skip remaining
live checks. The recorder ends after five minutes and its end record releases
the adapter. If it finishes before you reach a check, export and report what
was completed. Clear the old capture before any new run. Do not extend the
deadline or bypass the fresh shadow gate.

## Export and remove

Return both `Log/cpmap-rgi-D1-<number>` folders: shadow and live. Depending
on the actions performed, each contains:

| File | Meaning |
| --- | --- |
| `events.rgj`, `recorder-status.txt` | Guidance recording and native reader counters |
| `shadow-verification.txt` | Exact status that passed the shadow gate |
| `adapter-status-observed.txt`, `request-observed.txt` | Status/run saved by the status menu before manual disable |
| `adapter-status-before-disable.txt`, `request-before-disable.txt` | Status/run saved by export before it removes an existing enable request |
| `adapter-status.txt` | Most recent status; may already be stopped/reset |

After exporting, select **D2: remove HMI adapter (reboot)** and **fully
reboot**. Confirm normal OEM/CarPlay behavior and reconnect. Keep B4 installed.
Only JAR installation/removal needs a reboot; start, status, disable and export
do not. Reboot discards RAM captures and the shadow proof.

Without SD, the MMX recovery commands remain:

```sh
/bin/ksh /mnt/app/route-guidance-D1/control.sh disable
/bin/ksh /mnt/app/route-guidance-D1/control.sh uninstall
```

Then fully reboot. From RCC prefix each command with `on -f mmx`.
Disable remains independent of the payload and status-copy tools. Removal
preserves the other HMI JARs, B4 and OEM driver/config backups.
