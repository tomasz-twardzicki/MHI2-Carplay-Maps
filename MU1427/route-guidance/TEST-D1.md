# D1: first live native arrows and distance test

**WITHDRAWN after the unit test: D1 prevented cluster navigation startup.**
Removal/reboot restored it. Do not reinstall the original ZIP or repeat this
procedure. Use the corrected **shadow-only [D1-r2 test](./TEST-D1-r2.md)**.
See [D1-RESULTS.md](./D1-RESULTS.md). The procedure below is historical.

D1 adds a firmware-matched Java HMI adapter to the tested **B4 driver** and
uses the **unchanged C4 recorder binary** as its supervised device reader.
Keep B4 installed. **Do not restore the driver to factory before D1.**

Package: [MU1427-route-guidance-D1-toolbox.zip](./build-D1/MU1427-route-guidance-D1-toolbox.zip).
Extract its contents to the SD root, replacing the previous toolbox files.
Refresh/install the toolbox menus through the same procedure used for C4.
The new entries are appended to **CarPlay Maps VC** and start with `D1:`.

This is an experimental first HMI/cluster test. Host checks pass; embedded
J9 loading, actual ownership values, glyphs and cluster delivery still need
this test. Shadow mode checks loading and ownership before native output is
enabled. The live start refuses to proceed without a healthy shadow result
from the same build and boot.

## 1. Install once, then reboot

1. Stop any C4 recorder that is still running; export its capture if needed.
2. Disconnect the iPhone. Select **D1: install native guidance adapter (reboot)**.
3. Expect `CPMAP_RGI_D1_INSTALLED_REBOOT_REQUIRED`. **Fully reboot the unit.**
4. Reconnect the iPhone and confirm CarPlay, the AID route line and video turn
   card work as before. Installing D1 does not enable native output.

Installation changes the HMI bootclasspath and adds
`/mnt/app/eso/hmi/lsd/jars/CarPlayRouteGuidanceD1.jar`. It preserves existing
NavActiveIgnore/control jars, B4, configuration and their OEM backups.

## 2. Shadow run, with no native output

Do this outdoors with a usable GPS fix. Use the same phone navigation app
as C4-2. Do not start OEM navigation at the same time.

1. Select **D1: start 5-minute SHADOW test**.
2. Start phone guidance. Let guidance and distance updates run for 20–30 seconds.
3. While guidance is still active, select **D1: adapter and recorder status**.
   Expect `mode=1 context=0`, increasing `ticks`, `proposals>0`, `writes=0`,
   `failures=0 error=0`. `context=0` is the actual factory CarPlay-connected /
   OEM-navigation-idle observation. Context 1 means another/no phone connection,
   2 native state unknown/error, 3 OEM guidance active/calculating.
4. Select **D1: verify healthy shadow before live**. Expect
   `CPMAP_RGI_D1_SHADOW_VERIFIED`. If it fails, **export and send the logs**;
   do not work around the gate or reinstall the driver.
5. Stop phone guidance. Select **D1: disable and export capture**. Expect
   `CPMAP_RGI_D1_EXPORT_OK`. The SD folder is `Log/cpmap-rgi-D1-<number>`.
6. Select **D1: clear RAM capture (export first)**. This retains the healthy
   shadow proof for the live run. **Do not reboot between shadow and live**:
   reboot clears that proof, so shadow must be repeated.

If CarPlay/video/guidance is abnormal in shadow, disable, export, remove D1
and reboot. Shadow must show zero adapter output writes.

## 3. Live run, at most five minutes

1. With OEM navigation stopped, select **D1: start 5-minute LIVE arrows and distance**.
2. Start a new phone route **after starting the test**. The adapter waits for
   new accepted guidance; it does not replay an old retained ring as live data.
3. Check the native AID guidance area for an ordinary left and right turn,
   decreasing distance and changing maneuvers. Record whether native arrows
   appear and whether their direction agrees with the phone. A roundabout is
   useful if naturally on the route; some conflicting/underspecified records
   deliberately produce no native arrow. The phone-rendered turn card and
   route line should continue behaving normally.
4. Stop phone guidance. Check that the native arrow/distance clear. Start one
   more route, then disconnect the cable during guidance. Check clearing and
   normal reconnection. A subsequent route should recover after fresh updates.
5. With phone guidance stopped, briefly start and stop OEM navigation. OEM
   guidance should retain priority. Note any stale native CarPlay arrow.
6. Select **D1: disable native output NOW** while phone guidance is active.
   Native output should release within about two seconds; regular CarPlay
   should keep working. Check **status**, then **disable and export capture**.

The recorder stops after five minutes, and its end record disables output.
Every manual run needs a new capture directory: export, then clear before
starting again. A live attempt is optional after shadow; exporting shadow and
sending it for review first is also supported.

Initial output covers the current native maneuver and raw meter distance,
with unused maneuver slots cleared, bargraph off and lane output hidden.
Street, ETA, maneuver phase and map/video selection are outside D1. Distance
formatting/glyph support on the actual cluster are part of this test.

## Disable, removal and reboot

**Disable** removes only the RAM enable request. It needs no phone or SD
payload and no reboot. The adapter remains loaded, passes through stock
output and can be used again. Reboot always starts D1 disabled.

After exporting the first live run, select **D1: remove HMI adapter (reboot)**,
then **fully reboot**. This removes only D1's bootclasspath entry/JAR and
keeps other HMI patches, B4 and OEM driver/config backups. It also works if
the SD payload is missing. Clear the RAM capture after a confirmed export if
you want to reclaim space; reboot also removes RAM captures.

If the HMI cannot reach the menu, the saved controller can be run from the
MMX shell without SD:

```sh
/bin/ksh /mnt/app/route-guidance-D1/control.sh disable
/bin/ksh /mnt/app/route-guidance-D1/control.sh uninstall
```

Then fully reboot. From RCC, use `on -f mmx` before those commands. If an
uninstall reports a script-structure/rename failure, it retains the JAR and
backup for recovery: keep D1 disabled, preserve the error and current
`lsd.sh`, and retry after fixing the reported filesystem/layout condition.
The saved `original-lsd.sh` is a recovery copy; normal removal is surgical
so later unrelated HMI changes are preserved.

For this test, D1 removal is enough. The separate B4 **restore OEM** option
is available if you want to remove driver guidance reception too; that
restores driver/config together and requires another full reboot.

Please return both D1 export folders and note native arrow/distance behavior,
stop/disconnect clearing, OEM priority, video/card continuity and reconnection.
Captures contain private navigation data; keep them local.
