# MU1367 / AID 791 — v1.6.1-e-test2 experimental candidate

This full SD package contains the released **v1.5.4 stable base** and an optional
v1.6.1-e-test2 wireless layer. It carries the confirmed automatic AID activation,
forwards OEM driving-side coding, adds native wireless guidance, and provides
wireless stream tuning in GEM. Offline checks do not replace a vehicle test.

## Upgrade from the original v1.6.1-e

1. Keep the **original v1.6.1-e SD** available. Disconnect USB and wireless
   CarPlay. From its installed toolbox use **Remove wireless and restore
   v1.5.4**, then perform a full reboot. If interrupted, use that generation's
   saved recovery action first. Do not enable test2 over an installed old layer.
2. Extract this full test2 package to the SD and refresh its toolbox scripts/menu.
   The existing exact v1.5.4 base can remain installed; do not reinstall the base
   merely to switch wireless candidates.
3. Use **Wireless-CarPlay-Test → Enable v1.6.1-e-test2 wireless**, then reboot.
   Pair/select wireless CarPlay with USB disconnected and collect diagnostics
   while the AID map is active.

The old `carplay-mu1367-wireless-native-v161` snapshot remains untouched. Test2
uses `carplay-mu1367-wireless-native-v161t2`. Never delete `STATE` to bypass a
version guard. Removing test2 restores its v1.5.4 baseline; keep the old SD if you
need the original candidate's recovery controller.

## Upgrade from v1.6.0-e test1

1. With the **old test1 SD**, disconnect the phone and use **Wireless-CarPlay-Test
   → Remove wireless and restore v1.5.3**. Perform a full reboot with USB unplugged.
   Use its saved recovery action first if installation was interrupted.
2. Put this package on the SD. Run the normal base installer to install **v1.5.4**
   and complete its reboot steps. Follow `BASELINE_START_HERE.md`; do not copy
   individual runtime files over an installed layer.
3. With phones disconnected, open **GEM → carplay-maps-vc → Wireless-CarPlay-Test
   → Enable v1.6.1-e-test2 wireless**. Perform a full reboot.
4. Keep iPhone Bluetooth and Wi-Fi enabled, pair/select wireless CarPlay through
   the vehicle, and leave USB disconnected. Bluetooth initiates the wireless
   handoff; manually joining the hotspot is a diagnostic step, not the normal flow.
5. Open navigation and start a fresh route. Check the main display, AID map,
   native arrows, distance/arrival display, and available lane guidance.

The package refuses an installed test1 or original v1.6.1-e layer, or an unexpected base. It retains
old test1 snapshots and uses a separate `carplay-mu1367-wireless-native-v161t2`
recovery directory. Never delete or edit `STATE` to bypass an installer check.

## Included changes

- v1.5.4's OEM remaining-time/arrival-time selection and wired FPS/IDR controls.
- AID alternate-display activation at each verified receiver launch. The launcher
  does not create its RAM probe when `wcp_alt_off` is present.
- OEM driver-side coding: `1` LHD, `2` RHD. The receiver sees the matching
  `rightHandDrive` Boolean in a RAM-only copy of this unit's config. Other config
  properties and the persistent pairing/config store are preserved. Unknown
  coding uses the last known OEM value in `/mnt/persist/cpmap-driver-side.state`
  when available. Live RAM coding takes priority. Each `/info` construction
  refreshes late coding instead of retaining the startup value. If neither is
  known, the original setting is used; no driving side is guessed. On the first
  boot with no cache, let the HMI finish starting and reconnect CarPlay once if
  its initial connection negotiated the layout too early. Check another cold
  boot to confirm the persisted coding is available immediately.
- Real wireless iAP2 `0x5201`/`0x5202`/`0x5204` payloads reach the existing BAP
  adapter through an accepted-session mailbox. Wireless uses subscription
  component **1**; wired CarPlay and Android Auto retain **16**. The receiver
  already requests lane messages. OEM route priority and disconnect clearing remain.
- Default wireless request: **40 FPS**, an **IDR request every 8 video frames**,
  and **150 ms adaptive smoothing**. Both advertised display FPS values are set;
  the phone still decides its actual delivered cadence.
- Startup no longer waits for HMI coding before exec. The controller recognizes
  its own launcher during hash verification using the firmware-verified full
  process-name format, retaining the same PID receipt across exec.
- The input adapter suppresses its old every-five-frame request only after a
  fresh accepted receiver has actually installed a cadence marker. Missing,
  stale or unaccepted cadence restores the fallback. The bridge separately
  requests an IDR at most once per second while frames arrive without avcC.

NowPlaying text and artwork forwarding over wireless are not included.

## GEM tuning and A/B checks

The Wireless-CarPlay-Test page offers:

| Setting | Choices | Default |
| --- | --- | --- |
| Wireless FPS request | 20 / 25 / 30 / 40 | 40 |
| Wireless IDR request interval, frames | 5 / 7 / 8 / 10 / 15 | 8 |
| Wireless smoothing base | Off / 100 / 150 / 200 ms | 150 ms |

Disconnect and reconnect wireless CarPlay after changing a setting. A receiver
process restart is not required: FPS/IDR are refreshed for the next display
negotiation, and smoothing is read for the next accepted video session.
**Show wireless tuning** displays saved values; **Restore wireless tuning defaults**
also recovers a damaged preference file. These preferences survive layer removal.

For a useful comparison, keep the same route/zoom and change one value at a time.
Start with 40/8 and compare Off, 100, 150 and 200 ms. Then compare IDR 7/8/10.
Collect diagnostics while each configuration is active; record the selected
values and whether zoom, continuous scrolling and reconnect improved.

Smoothing retains the phone-derived presentation clock already mapped by AirPlay
into local monotonic time. It matches unchanged H.264 payloads across the existing
input adapter, holds frames before TS muxing, and preserves their cadence in PTS.
Late frames are released immediately; delay can rise to **250 ms** and decays
slowly after a quiet period. This is a buffer-delay cap, not an end-to-end latency
promise. Intentional holds do not enter the TS-backlog reset queue. Encoded
reference frames are skipped only through a newer queued IDR, preserving a
valid decode chain. If timestamp matching fails, smoothing is bypassed and
reported in the bridge log.

## Vehicle acceptance checklist

- Wired CarPlay still has maps, native guidance, OEM ETA/arrival selection, and
  the v1.5.4 wired tuning choices. Android Auto remains functional.
- Wireless main display uses the coded driving side; AID map starts without the
  former manual probe. Check a full cold boot and a phone reconnect.
- With wireless active, start/cancel/restart a route, pass several turns, reroute,
  and check lanes where the phone supplies them. Confirm OEM navigation can take
  priority and that disconnect does not leave a stale arrow or distance.
- A/B smoothing and FPS/IDR. Check image detail while zooming, frame pacing,
  audio/video responsiveness, and reconnect after changing a setting.
- Use **Collect wireless diagnostics to SD** while connected. It includes native
  guidance source/adapter status, driver-side coding, tuning preferences and
  bridge timing counters, the coding cache and receiver cadence receipt. Review logs for identifiers before sharing.
- In the collector, check that `wcp_receiver.pid` matches the owner PID,
  `wcp-rg-session.state` ends in `1` (accepted), the bridge reports `avcC ready`
  and increasing frames, and `wcp-rg-idr.state` is refreshed. The startup log
  must not report `启动失败`. Confirm the main display dock is on the RHD side.
- Test removal and a full reboot, then verify wired operation on the restored base.

## Rollback

**Remove wireless and restore v1.5.4** restores all 39 managed targets to their
saved bytes/modes or original absence. This includes the previous supervisor,
bridge and guidance JAR, OEM launch/config changes, and the added native files.
Use **Recover interrupted wireless install** for an interrupted transaction.
Unknown third-party edits or damaged backups are preserved and reported.

Perform a full reboot after removal. The RHD shadow config, timestamp/mailbox
files and activation probe are RAM-only. Pairing data, saved user tuning, the last-known OEM coding cache and
recovery snapshots remain available. Returning specifically to v1.5.3 is a
separate base downgrade after wireless removal and reboot; this layer's removal
returns to **v1.5.4**, its required base. Run the baseline OEM restore/reset only
after the wireless layer has been removed or recovered.

See `WIRELESS-VERIFICATION.json` for exact payload hashes, firmware gates and
verification scope. No v1.6.1-e-test2 on-vehicle result is claimed by the package.
