> **Current stable: [v1.6.1 installation/update/restore instructions](stable/START_HERE.md).** The stable SD supports v1.5.3/v1.5.4 and known wireless generations through saved layers and enforced reboots. This page retains historical v1.6.0-e test procedures.



# v1.6.0-e test1 — native wireless CarPlay

Experimental connection/video test for **MU1367 K4525/P4521 + AID 791**.
The base integration remains **v1.5.3**. Enable the additional wireless layer
only after that baseline is installed and working. No on-car wireless result
is claimed by this package.

## Scope

This candidate adds the verified wireless receiver, Bluetooth integration,
HMI/touch classes and wireless cluster input. The supervisor accepts a wireless
producer only when its live receiver, accepted-session grant and active feed
generation agree. There remains one cluster supervisor/bridge path.

The published v1.5.3 bridge, startup clip, priority 14, DIO wrapper, core, MU menu,
wired information modules and Android Auto payloads are retained. Wireless asks
for **30 fps / 800×480** on the 791 cluster; the saved wired **40 fps / IDR 5**
setting is retained. The existing bridge follows the incoming timestamps.
The MU UI's FPS selection does not change the wireless request in test1.

**Wireless guidance arrows/lanes/road names, music text and artwork are not
integrated yet.** They remain wired features. Wireless mirroring, calls, Siri,
audio, controls, transport changes and vehicle endurance require acceptance;
the first test should establish the connection and main-screen/cluster video.

Use the new **Green Menu** controls below. Test1 does not add a functioning
Wireless CarPlay switch to the native Virtual Cockpit settings page. The
existing Startup animation control remains unchanged.

## Prepare and enable

1. Verify the ZIP against its adjacent `SHA256SUMS.txt`. Extract the complete
   package to a clean FAT32 SD root. Use this package's menus and scripts.
2. Disconnect phones/adapters and fully reboot. Refresh Toolbox menus/scripts
   from this SD using the existing MMX command:

   ```sh
   /bin/ksh /fs/sda0/Toolbox/final/install_scripts.sh /fs/sda0
   ```

   Use `/fs/sdb0` consistently if appropriate. From RCC, enter MMX with
   `on -f mmx`. This is the same refresh procedure as the v1.5.3 package.
3. If v1.5.3 is not already installed, follow `BASELINE_START_HERE.md` and its
   complete two-stage/reboot upgrade instructions where applicable. The base
   success marker remains `MU1367_RELEASE_1_5_3_INSTALLED_FULL_REBOOT_REQUIRED`.
   Verify wired CarPlay/cluster operation first.

   **Existing v1.5.3-e:** follow the base guide's two-stage migration when
   requested: restore the previous main layer, fully reboot disconnected, then
   run the same base install action again before enabling wireless.

   **November 18 installer fix:** if an earlier test SD stopped at
   `MU1367_GUIDANCE_V3_SUITE_FAIL=RETAINED_SESSION_EXISTS`, the base installer
   found an existing removed-snapshot archive with the same process-ID suffix.
   QNX can reuse that ID after reboot. Use the updated complete ZIP, refresh
   Toolbox menus/scripts again and rerun the base install action. The fixed
   installer selects an unused numeric archive name and preserves all previous
   snapshots. Do not delete snapshots or change STATE/VERSION to bypass this
   error. Normal migration/reboot and final-success requirements still apply.
4. With phones still disconnected, open **MQB Coding → Customization →
   CarPlay Maps VC → Wireless-CarPlay-Test**. Select **Enable wireless test layer
   (reboot)**. Wait for:

   ```text
   MU1367_WIRELESS_V160E_TEST1_INSTALLED_FULL_REBOOT_REQUIRED
   ```

   An exact matching baseline is required. Unknown modifications, another
   wireless installation, a wrong profile or damaged recovery data stop the
   action. The installer preserves the original per-unit files and absence
   records before applying the layer. It does not replace `btstack` or
   `connectionmanager`, change hotspot credentials, or copy pairing identities.
5. Fully reboot. Leave USB disconnected and keep Bluetooth and Wi-Fi enabled
   on the iPhone. Confirm the head unit's native WLAN hotspot is enabled. Pair
   Bluetooth and accept any CarPlay approval prompts. Select that iPhone in
   App-Connect if necessary. **Test automatic Wi-Fi joining first:** the
   wireless CarPlay Bluetooth handshake should supply this unit's Wi-Fi
   credentials and initiate association; an ordinary Bluetooth audio connection
   alone does not establish that handshake. This automatic handoff remains
   unverified on our target hardware.

   If automatic joining fails, capture the logs before manually joining this
   head unit's hotspot with its own SSID/password as a diagnostic fallback.
   Record whether manual joining was needed; success after that fallback does
   not pass the automatic-handoff test. Do not enable the iPhone's Personal
   Hotspot for this step. A local hotspot's “No Internet” indication alone does
   not establish a failure.

## First vehicle test

Record the firmware train, phone model/iOS and the stage where behavior changes.
Begin with Startup animation **Off** to inspect the live-video handoff, then
test the normal Once per boot setting after a successful session.

1. Confirm Bluetooth pairing, automatic hotspot association and an accepted
   CarPlay session. Record any manual Wi-Fi fallback separately. After a
   successful session, also test automatic reconnection without opening the
   phone's Wi-Fi settings.
2. Check main-screen video and touch, then sound, microphone/calls and Siri.
3. Open navigation and check cluster video and steering-wheel controls. Do not
   interpret absent wireless arrows/media text/artwork as an installer failure;
   those event sources are outside test1.
4. Disconnect/reconnect, test reverse-camera takeover/return, then try USB and
   Android Auto transitions separately. Stop at a reproducible regression and
   retain its logs before repeating the same test.
5. Check CPU/RAM/log growth and ignition/sleep/wake before extending the test to
   endurance or other phone models. Offline/QNX results do not establish these.

Status/recovery is available in the same Green Menu page. For MMX diagnostics,
these are existing upstream runtime commands; optional tools may be unavailable:

```sh
/bin/ksh /mnt/app/carplay-mu1367-wireless-native/control.sh status
/bin/sh /mnt/ota/wcp_ctl.sh status
```

Relevant logs are `/dev/shmem/wcp_autostart.log`, `/dev/shmem/wcp.log`,
`/dev/shmem/wcp_video.log`, `/dev/shmem/omonob-phone.log`,
`/ramdisk/omonob-791-input.log`, `/ramdisk/carplay-cluster-supervisor.log` and
`/ramdisk/altscreen-most-bridge.log`. These are reset or changed by reboot;
capture a failure before reboot when possible. Review phone/vehicle identifiers
before sharing logs publicly; never share pairing stores or hotspot passwords.

The original **Collect diagnostics** action omits the wireless-specific logs
and accepted-session/feed state. This rebuilt package adds **Collect wireless
diagnostics to SD (no reboot)** under **MQB Coding → Customization → CarPlay
Maps VC → Wireless-CarPlay-Test**.

Extract the complete updated package to a clean SD and refresh Toolbox menus
and scripts using the command in step 2 above. If the wireless layer is already
installed, **only refresh the menus/scripts**; no base or wireless reinstall is
needed to use the collector. Leave this SD inserted. While wireless CarPlay is
working on the main screen and the AID map is missing, keep USB unplugged and
select the new diagnostic action. Wait for `WIRELESS_DIAG_OK=...`, then keep the
complete `Log/wireless-diag-<number>` directory from the SD.

The collector reads unit state and writes only to SD. It does not restart
services or require a reboot. This rebuild adds diagnostics; it does not claim
to fix the missing wireless AID map. As a shell alternative, run on MMX:

```sh
/bin/ksh /fs/sda0/collect-wireless.sh /fs/sda0
```

Use `/fs/sdb0` consistently if needed; enter MMX with `on -f mmx` from RCC.
The root `collect-wireless.sh` is included in this package too. The November 18
first-capture findings are in `VEHICLE-18808932.md` in the source workspace.

The follow-up capture identified a missing alternate-display activation
condition. The rebuilt **Wireless-CarPlay-Test** page also provides **Enable
AID display probe (until reboot)**. To test it on the installed test1 layer:

1. Refresh menus/scripts from this complete updated SD.
2. With USB unplugged, select **Enable AID display probe (until reboot)**.
   Expect `MU1367_WIRELESS_ALT_PROBE_ENABLED_UNTIL_FULL_REBOOT`.
3. Disconnect and reconnect wireless CarPlay; **do not reboot between enabling
   the probe and this test**. Open navigation and check the AID map.
4. Select **Collect wireless diagnostics to SD (no reboot)** and retain the
   complete output folder, whether the map appears or remains absent.

This action writes a RAM-only flag and checks the exact receiver hash. It
respects explicit wireless/alternate-display off flags and changes no installed
files or snapshots. A full reboot clears it. It is a diagnostic activation;
persistent automatic activation awaits the vehicle result. Detailed evidence
and the passing exact-receiver QNX gate checks are in `VEHICLE-30117947.md` and
`RECEIVER-ALT-GATE.json` in the source workspace.

## Remove or recover

Disconnect the phone/adapter; turn off the phone's Bluetooth/Wi-Fi if it keeps
reconnecting. Wait for the session to end. In **Wireless-CarPlay-Test**, choose
**Remove wireless and restore v1.5.3 (reboot)**, then fully reboot after:

```text
MU1367_WIRELESS_SNAPSHOT_RESTORED_FULL_REBOOT_REQUIRED
```

If an install was interrupted, choose **Recover interrupted wireless install**.
The saved MMX controller works without the SD:

```sh
/bin/ksh /mnt/app/carplay-mu1367-wireless-native/control.sh recover
```

Recovery verifies the snapshot before restoring it. Unknown changed targets or
damaged backups are preserved and reported; do not force version markers or
delete recovery directories. Keep `/mnt/app/carplay-mu1367-wireless-native`
after removal because it retains the first baseline snapshot. Pairing data
created by the receiver is retained; the installer never transfers another
unit's identity or erases that store.

**Remove/recover wireless and reboot before updating/removing the base, changing
the installed turn-card layer, or using OEM reset.** This package's base action
wrappers enforce that order. An older SD does not know about the wireless layer;
use the complete test SD for these actions. After wireless removal, the original
v1.5.3 installation/recovery procedure applies.

## Verification boundary

`WIRELESS-VERIFICATION.json` records the exact candidate's checks and their
scope. The transaction fixture uses factory QNX utilities and final installed
file bytes from the published v1.5.3 package. It does not rerun the historical
installer in the same fixture. No device, radio, decoder, MFi coprocessor or
real phone is simulated as a successful wireless connection.
