# D3: corrected maneuver distances and route totals

**Unit result:** corrected maneuver distance and both route totals passed;
the user confirms approximate agreement with the phone and no observed issues.
See [D3-RESULTS.md](./D3-RESULTS.md). The procedure below remains the
manual, bounded test; it does not enable persistent output.

Package: [MU1427-route-guidance-D3-toolbox.zip](./build-D3/MU1427-route-guidance-D3-toolbox.zip).
[D2](./D2-RESULTS.md) demonstrated native arrows on AID/HUD and normal
reconnection/OEM behavior. D3 changes the Java adapter; **B4 and the C4 native
reader are unchanged**.

Changes to check:

- Maneuver distance uses the exact factory formatter, fixing the factor of
  ten and using OEM rounding/unit switching. For example, 30 source metres
  round to 40 displayed metres; 20 source metres display as 20, not 2.
- Remaining route distance uses the stock destination-distance BAP function.
- Remaining travel time uses the stock time-to-destination function, rounded
  up to whole minutes. This is a duration such as 12 minutes, **not clock-time
  arrival ETA**. Date/street/lane/bargraph output is outside this test.

## Install, then shadow

1. **Keep B4 installed; do not restore the driver to factory.** If D2 remains
   installed, export its captures, remove its HMI adapter and fully reboot.
   If it was already removed/rebooted, start from that state.
2. Extract D3 to the SD root and refresh the toolbox scripts/menus. Check the
   entries say **D3:**. Disconnect the phone, install the adapter and **fully
   reboot**. Confirm the OEM cluster map loads before connecting the phone,
   then normal CarPlay map/card behavior. Output starts disabled.
3. Outdoors, with OEM guidance stopped, select **D3: start 5-minute SHADOW
   test**, then start a new phone route using the same navigation app.
4. After 20–30 seconds, check **D3: adapter and recorder status**, then
   **D3: verify healthy shadow before live**. Expect
   `CPMAP_RGI_D1_SHADOW_VERIFIED`, `mode=1 context=0`, nonzero proposals/ticks,
   and `writes=0 failures=0 error=0`. If verification fails, export and stop
   here; do not bypass the gate.
5. Stop phone guidance, **disable and export capture**, then **clear RAM
   capture (export first)**. **Do not reboot between shadow and live**.

Expected payload version: `MU1427-RGI-D3-ea264694`.
Adapter status still begins `D1`, with `build=6fa06a5387d3757b`; the shared
paths/recovery commands retain the D1 family name. D3 installs six major-46
stock replacements, compared with four in D2. Factory J9 loading/registration
passes with verification enabled and disabled; actual display needs this test.

## Live, at most five minutes

1. With OEM guidance stopped, select **D3: start 5-minute LIVE guidance and
   route totals**, then start a new phone route **after** the recorder starts.
2. Compare native maneuver distance against the phone as you approach a turn.
   Check metre/kilometre transitions if naturally on the route. OEM rounding
   can differ from the phone; the factor-of-ten error should be gone.
3. Check remaining route distance and travel duration in the AID's native
   guidance view, where those fields are available. Compare approximately
   with the phone. Note whether the display labels the time as a duration.
   Check arrows on AID/HUD and normal phone map/video turn cards.
4. While output is active, check **status**: `mode=2 context=0`, increasing
   writes/proposals, `failures=0 error=0`. Status saves a snapshot for export.
5. Stop phone guidance and check **all added values clear**. Start another
   route and disconnect during guidance; check clearing and normal reconnect.
   Fresh guidance should recover the arrows and totals. With phone guidance
   stopped, briefly start/stop OEM guidance and check its priority.
6. With phone guidance active, check **status**, then **disable native output
   NOW**. Check native output releases within about two seconds while ordinary
   CarPlay keeps working. **Disable and export capture** before rebooting.

If anything is abnormal, disable/export immediately and skip remaining checks.
The recorder stops after five minutes and its end record releases output.
Export what was completed; do not extend the deadline. A new run requires
export/clear first. Missing/invalid source values are blank rather than zero;
received zero remains valid. Totals reset on route changes, stop and reconnect.

## Export, remove and reboot

Return both `Log/cpmap-rgi-D1-<number>` folders and your observations of
distance scaling, route totals/time, AID/HUD arrows, clearing and OEM priority.
Exports include verified/observed/pre-disable status as in D2. Captures are
private navigation data; keep them local.

After export, **remove the D3 HMI adapter and fully reboot**. Confirm OEM and
CarPlay still work. Keep B4 installed. Only installation/removal needs a reboot;
reboot discards RAM captures and the shadow proof.

If you accidentally remove the adapter before exporting, **export before
rebooting or clearing**. Removal stops the recorder but keeps its RAM capture
and saved status snapshots. Both can still be exported with the menu. The
active status-menu snapshot is useful when removal has already reset counters.

Without SD, the saved MMX controller still supports:

```sh
/bin/ksh /mnt/app/route-guidance-D1/control.sh disable
/bin/ksh /mnt/app/route-guidance-D1/control.sh uninstall
```

Then fully reboot. From RCC prefix each command with `on -f mmx`.
Removal preserves other HMI JARs, B4 and OEM driver/config backups. If removal
reports a script/rename failure, keep output disabled and preserve the error,
current boot script and recovery backup for retry.
