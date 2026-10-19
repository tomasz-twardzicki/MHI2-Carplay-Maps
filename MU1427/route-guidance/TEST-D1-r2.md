# D1-r2: corrected class format, startup/shadow retest

> Historical test procedure. Use [INSTALL.md](./INSTALL.md) for the released package. Obsolete test tools are retained in [Git history](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/tree/838dd535c23cb8214b170216066e60f8690d2074/MU1427/route-guidance).

**Accepted on the unit:** see [D1-r2-RESULTS.md](./D1-r2-RESULTS.md).
The next test is [D2](./TEST-D2.md), reusing this exact Java JAR. This page
retains the completed shadow-only procedure.

Use [MU1427-route-guidance-D1-r2-toolbox.zip](./build-D1-r2/MU1427-route-guidance-D1-r2-toolbox.zip).
**Do not use the original D1 ZIP.** Its four stock replacements had a class
format rejected by this J9. [D1-RESULTS.md](./D1-RESULTS.md) records the cause
and the version-only reproduction on the actual firmware runtime.

D1-r2 emits **all classes as major 46**, matching the working MU1427
NavActiveIgnore replacements. It passes loading/registration checks using
the factory ARM J9 under QNX, including verification enabled. It still needs
this startup test in the actual HMI.

**This package permits shadow mode only.** There is no live-start menu, and
the controller also blocks live start. B4 and the C4 native reader are unchanged.
Keep B4 installed; no factory driver restore is needed.

1. Since D1 was removed and a full reboot restored the cluster, start from
   that recovered state. Extract the new ZIP to the SD root and refresh the
   toolbox scripts/menus as before. The new menu entries say **D1-r2:**.
2. Disconnect the phone. Select **D1-r2: install native guidance adapter (reboot)**.
   Expect `CPMAP_RGI_D1_INSTALLED_REBOOT_REQUIRED`, then **fully reboot**.
3. **Before connecting the phone**, check that cluster navigation finishes
   loading and shows the normal OEM map. Briefly start/stop OEM guidance and
   confirm the cluster follows it. If navigation stays at loading, remove
   D1-r2 and reboot; do not continue with shadow.
4. Connect the phone. Confirm normal CarPlay, the AID map/route line and phone
   turn card. Outdoors, with OEM guidance stopped, select **D1-r2: start
   5-minute SHADOW test**, then start phone guidance using the same app as C4-2.
5. After 20–30 seconds, while phone guidance is active, select **D1-r2: adapter
   and recorder status**. Expect `mode=1 context=0`, increasing `ticks`,
   `proposals>0`, **`writes=0 failures=0 error=0`**. Then select **D1-r2: verify
   shadow health** and note its result. This does not enable live output.
6. Select **D1-r2: disable and export capture** before rebooting. Expect
   `CPMAP_RGI_D1_EXPORT_OK`; send `Log/cpmap-rgi-D1-<number>` and the status
   result. Note OEM map startup, OEM guidance, CarPlay map/card behavior and
   reconnection. If the adapter still fails to report, export anyway.
7. Select **D1-r2: remove HMI adapter (reboot)** and **fully reboot** after
   exporting. Confirm the cluster and CarPlay still work. B4 remains installed.

Only installation/removal require a reboot. Starting, disabling and exporting
shadow do not. Do not reboot before export: captures are RAM-only.

Removal works without SD. The saved MMX shell recovery commands remain:

```sh
/bin/ksh /mnt/app/route-guidance-D1/control.sh disable
/bin/ksh /mnt/app/route-guidance-D1/control.sh uninstall
```

Then fully reboot. From RCC prefix each command with `on -f mmx`. Removal
preserves the other HMI JAR entries and B4; it removes only this adapter.
If the old D1 package/controller is accidentally used, it is not this retest:
check that the SD menu says **D1-r2**, not **D1**.
