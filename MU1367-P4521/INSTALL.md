# MU1367-P4521 / 791 installation and recovery

Use only on **MHI2_ER_VWG13_P4521_MU1367 with a 791 / 12.3-inch cluster**.
This is an experimental P4521 bundle based on MU1367 v1.4.0. Offline firmware
and installation checks do not establish vehicle compatibility.

1. Verify `CarPlay_Maps_VC_MU1367_P4521_791_v1.4.0_Experimental.zip` against
   `SHA256SUMS.txt`. Extract it to a clean SD root; refresh Toolbox menus
   **and scripts** from this bundle. Keep the SD and recovery instructions.
2. Park, maintain stable power and keep a working MMX shell. Disconnect the
   phone and fully reboot. Start from OEM files. If another bundle is
   installed, use its saved recovery controllers to restore OEM first,
   reboot, then archive/move removed recovery directories aside. Never
   delete active or interrupted recovery directories to bypass a refusal.
3. In the **MU1367 P4521 v1.4.0 experimental** Toolbox menu, select
   **1. Install MU1367 P4521 / 791 video**, then
   **2. Install MU1367 P4521 / 791 guidance + audio text**. Fully reboot.
   Step 1 checks exact OEM hashes before writing. A rejection requires
   inspecting the files; do not edit expected hashes or bypass the check.
4. With the phone disconnected, select **3. Add MU UI settings + map/mirror
   runtime (791)** and reboot. Then select **4. Add native lanes + default
   cards OFF (791)** and reboot. Stop on any failure.
5. Confirm the OEM HMI, cluster, audio and controls before reconnecting.
   App-Connect **Virtual Cockpit settings** provides the existing display,
   stream and Card ON/OFF choices. Fresh card preferences default OFF;
   an explicit saved Card ON stays ON. Retain your preferred 30 fps / IDR5.

The source entry point `MU1367-P4521/791_AID12.3/install.sh` is copied to
`Custom/carplay_mu1367_p4521/install.sh` when packaging. For shell installation
of **step 1 only**, run the bundled script with the bundled maps directory:

```sh
/bin/ksh /fs/sda0/Custom/carplay_mu1367_p4521/install.sh /fs/sda0/Custom/carplay_maps_vc
```

Use the appropriate SD mount path; from RCC use `/net/mmx/fs/sda0` if needed.
The remaining steps use the Toolbox menu and unchanged v1.4.0 controllers.
The inherited K4525 documents in the ZIP explain those controllers; the
P4521 instructions here define this bundle's supported firmware and scope.

## Recovery without SD or HMI

Disconnect the phone. On MMX (from RCC use `on -f mmx`), remove in this order,
stopping on failure:

```sh
/bin/ksh /mnt/app/carplay-mu1367-lanes/control.sh uninstall
/bin/ksh /mnt/app/carplay-mu1367-settings/control.sh uninstall
/bin/ksh /mnt/app/carplay-mu1367/control.sh uninstall
/bin/ksh /mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_restore_core.sh
```

For an interrupted layer, run its saved `control.sh recover` before removing
lower layers. Keep all backups. If a power interruption leaves the shared
`/ramdisk/.carplay-guidance-install-lock`, confirm no installer is running
before removing the empty lock directory. The **Restore factory video +
integration** menu action performs the same reverse order and stops on error.
Fully reboot and verify OEM operation before archiving recovery directories.

## P4521 vehicle acceptance still required

Check navigation arrows, ETA, lane count/order/highlights, route cancellation,
rerouting, reconnect, OEM navigation takeover, native audio text, steering
controls, map/mirror and Card ON/OFF. Enable OEM lane display. Check Apple
Maps, Google Maps and Waze independently on routes with lane instructions,
then complete a 90-minute run. Save the exact release ZIP hash, preferences,
app details and diagnostics before reboot. Report P4521 results separately
from the existing K4525 v1.4.0 vehicle report.
