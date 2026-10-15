# MU1427: CarPlay turn-by-turn in the cockpit's own navigation display (research)

**Goal:** show Apple Maps guidance in the 791 cockpit's native navigation graphics: VW maneuver arrows, distance bar, street names and ETA. The current turn card is part of the CarPlay video drawn by the iPhone ([`../791_AID12.3/tuning/`](../791_AID12.3/tuning/)); this would replace or complement it with the cluster's own graphics.

Status: **Phase A done** (two runs, see [Phase A results](#phase-a-results)); **Phase B designed** (see [Phase B design](#phase-b-design)). Nothing in this directory changes the car yet.

## Offline findings (factory package `MHI2_ER_VWG11_K3342_MU1427`)

### Sink: the cockpit already takes navigation data from the HMI

The Java HMI (`/ifs/lsd.jxe`, extracted with [`../NavActiveIgnore/extract/`](../NavActiveIgnore/extract/)) feeds the cluster on two paths, both driven today by the built-in navigation.

- **`DSIKOMONavInfo`** (`de/esolutions/fw/comm/dsi/komonavinfo`): text and values pushed to the cockpit. The method signatures come from `dsi.komonavinfo` in `app.img`:
  - `setCurrentStreet(currentStreet)`, `setCityName(city)`, `setTurnToStreet(turnToInfo, signPost)`
  - `setDistanceToNextManeuver(distance, unit, validity)`, `setDistanceToDestination(…)`
  - `setETA(timeFormat, day, hour, min, validity, timeInfo)`, `setRTT(hour, min, validity)`, `setTrafficOffset(…)`
  - `setRgSelect(rgMode)`, `setSemiDynRoute(alternativeRoute)`, `setCapabilities(suppNavType)`, `setMapScale(…)`
- **BAP NavSD** (`de/vw/mib/bap/mqbab2/generated/navsd`, `…/mqbpq/…`): the cluster's maneuver graphics.
  - `ManeuverDescriptor_Status`
  - `DistanceToNextManeuver_Status` (with a bar graph)
  - `LaneGuidance_StatusArray`
  - `RouteGuidance_Status_Status`
  - `TurnListElement`
  - On the DSI side: `BapManeuverDescriptor` in `de/esolutions/fw/comm/dsi/navigation`.

A Java hook loaded through `-Xbootclasspath/p:`, the same mechanism as `CarPlayClusterControls.jar`, could feed both paths from CarPlay data while CarPlay is guiding.

`exboxm` turned out to be an external audio/display box (Korea profile), not navigation. MU1427 has no "Exbox guidance" classes; newer firmware does.

### Source: getting Apple's route guidance over iAP2

- **CarPlay doesn't do iAP2 itself:** `dio_manager` is the CarPlay process (AirPlay, `DSICarplayImpl`). It has no iAP2 identification code and reads now-playing data from PPS (`CPPSNowPlayingMetadataObject`).
- **The iAP2 session runs in `ipod-drvr-iap2.so`.** It's the QNX iPod driver ("Media 1.0.61.1", built 2015-10-16) and isn't stripped.
  - It knows CarPlay transports (`carplay`, `iap2ncm`) and publishes to PPS under `/pps/services/multimedia/iap2/`.
  - Its config is `/etc/mm/iap2.cfg`, set by `config=` with that as the default. The factory copy is in `efs-system.img`.
  - The factory config enables `devaudio`, `nowplaying`, `location`, `eap` (`com.vwag.infotainment.carplay.exlap`), `power` and `telephony`.
- **What the driver can already do:**
  - `ident_info_sendmsgs` / `ident_info_recvmsgs` append extra message IDs from config to the identification ("Cannot add custom messages").
  - `link_send_raw_message` (client API `iap2_raw_msg_send`) sends arbitrary messages.
- **What it can't do:**
  - It has no builder for a route-guidance display component. Its identification builders are fixed: `ident_info_eap`, `…_gpscomp`, `…_hidcomp`, `…_power`, the transports and vehicle.
  - `packet_add_param_from_config` is only used by `power_start`, so config can't add arbitrary identification parameters.
  - Declaring route guidance therefore needs a **patch to the driver binary**.
- **Open:** how the driver handles received message IDs it doesn't know (`iap2_msg`, `packet_recvlist_*`, `transport_recv_pkt`). They might be dropped, queued for a client, or published to PPS.

Some of the identification and iAP2 message details here come from reverse engineering and public references, not from Apple's (NDA) accessory specification. Treat them as hypotheses until confirmed on the unit.

## Phases

| Phase | Work | Risk to the car |
| --- | --- | --- |
| **A. On-unit recon** | Toolbox entry **Collect navigation research data to SD**: which process loads `ipod-drvr-iap2.so` and with which `config=`, where the driver and configs live, PPS iAP2 objects, logs | None, read-only |
| B. Source | Patch the driver to declare the route-guidance component and receive its messages; send the start command; log the raw messages to `/ramdisk` | Medium: a bad identification can stop CarPlay until rolled back; needs a rollback entry |
| C. Mapping | Decode Apple maneuver data and map it to VW maneuver codes, units and lanes | None, offline |
| D. Sink | Java hook feeding `DSIKOMONavInfo` and BAP NavSD while CarPlay guides | Medium: the HMI must keep starting; same rollback approach as the steering-wheel jar |

## Phase A: how to run

1. Update the toolbox from a package that contains `cpmap_navrecon.sh`.
2. Connect the iPhone over USB, open CarPlay, and start a route in Apple Maps.
3. Open **Customization → CarPlay Maps VC → Collect navigation research data to SD**.
4. Wait for `CPMAP_NAVRECON_OK`. The output is in `Log/cpmap-navrecon-<time>/` on the card.

The script only reads from the unit. What it collects:

| File | Contents |
| --- | --- |
| `summary.txt` | firmware, CarPlay Maps VC profile and option, mounts |
| `proc-args.txt`, `proc-args-iap2.txt` | full command lines; look for the `config=` of the iPod driver host |
| `proc-mem.txt`, `proc-mem-iap2.txt` | mapped libraries; shows which process loads `ipod-drvr-iap2.so` |
| `files-found*.txt`, `files/` | paths of `*iap2*`, `*ipod*`, `mm-*`, `io-media*` and `mme*`, with copies of their configs and of the driver |
| `etc-mm-ls.txt` | `/etc/mm` and `efs-system/etc` listings |
| `pps-*.txt`, `pps/` | `/pps/services/multimedia` objects and any iAP2, CarPlay or navigation PPS objects |
| `sloginfo*.txt` | system log, full and filtered for iAP2 and CarPlay |

Phase A answers:
1. Is `ipod-drvr-iap2.so` the iAP2 stack used during CarPlay sessions?
2. Which config file does it really load, and is it writable (`efs-system` versus the read-only image)?
3. Is the driver on the unit byte-identical to the one carved from the factory `app.img` (offset `124347392`, `0xb4a55` bytes)?
4. What does it publish to PPS during CarPlay?

## Phase A results

### Run 1 (2026-10-15, MU1427/791, iPhone over USB, CarPlay active)

1. **`ipod-drvr-iap2.so` is the CarPlay iAP2 stack.**
   - It is loaded by `mm-ipod` (pid 3330128): `mm-ipod -d iap2,config=/etc/mm/iap2.cfg,probe,ppsdir=/ramdisk/pps/iap2 -a i2c,addr=0x11,path=/dev/i2c8,speed=50000 -t usbdevice,path=/dev/io-usb/otg_dev -l /dev/shmem/iap2.log -vvvvvv`.
   - USB runs in device mode through `io-usb-dcd -d devu-iap2ncm-tegra3-ci.so` (the CarPlay network link).
   - `dio_manager.real` loads `libiap2client.so.1`, so CarPlay is a client of this driver.
2. **The config is `/etc/mm/iap2.cfg`.** Its text matches the factory copy in `efs-system.img`.
   - `/etc` belongs to `/mnt/system`, which the stock scripts `activate_ipod_logging.sh` / `deactivate_ipod_logging.sh` remount read-write (`mount -uw /mnt/system`).
   - So the config can probably be edited in place, with a backup.
3. **The driver on the unit is byte-identical** to the copy carved from the factory `app.img`.
   - Path: `/mnt/app/armle/lib/dll/ipod-drvr-iap2.so`, on the writable app partition, like `mm-ipod` (`/mnt/app/armle/usr/sbin/mm-ipod`).
   - Offline disassembly of the carved file therefore applies to the car.
4. **PPS and the driver log weren't collected in run 1,** because the script looked under `/pps/services`, which doesn't exist on MMX.
   - The driver publishes to `/ramdisk/pps/iap2` and logs at maximum verbosity to `/dev/shmem/iap2.log`.
   - The script now collects both, plus the `/mnt/system` layout and whichever startup script launches `mm-ipod` (run 2).

Also found on the unit:
- `iap2cli` and `ipodcli` in `/mnt/app/armle/usr/bin`: stock iAP2 command-line clients, possibly useful for raw-message experiments.
- `libiap2client.so.1`: the client API that `dio_manager` uses.

### Run 2 (2026-10-15, route active in Apple Maps)

The full driver log and PPS were collected. **Don't commit raw logs:** they contain the car's GPS position (NMEA sentences) and the authentication certificate data.

- **The driver decodes every iAP2 packet in its log.**
  - The identification it sent: name `VOLKSWAGEN`, model `MIB2`, manufacturer `HARMAN`.
  - Messages sent by the car: `EA03 5000 5002 5003 AE00 AE02 AE03 FFFB 4154 4156 4157 4159`.
  - Messages accepted from the iPhone: `EA00 EA01 5001 AE01 FFFA FFFC 4155 4158 4E09 4E0A`.
  - Components: EAP `com.vwag.infotainment.carplay.exlap`, a USB host transport with `TransportSupportsCarPlay`, and Location.
  - The iPhone answered `IdentificationAccepted`.
- **There's no route-guidance traffic yet,** as expected. What does flow: now playing, power, telephony, location (sent by the car), device information and authentication.
- **`mm-ipod` is started by `/etc/usblauncher_otg.lua`.** `/etc` is `/mnt/system/etc`, which is writable after `mount -uw /mnt/system`.
- **`iap2cli` can't send raw messages.** It has no raw command, so `0x5200` must come from code inside the iAP2 path.
- **Config syntax for extra message IDs,** from disassembling `ident_info_recvmsgs` / `ident_info_sendmsgs`. Up to 64 IDs in total, comma-separated, hex allowed (`strtoul` base 0):

      [ident]
      sendmsgs=0x5200,0x5203
      recvmsgs=0x5201,0x5202,0x5204

## Reference: luka-dev/mib2q-carplay-rgi

[luka-dev/mib2q-carplay-rgi](https://github.com/luka-dev/mib2q-carplay-rgi) (GPL-3.0) implements exactly this feature on Audi MHI2Q (MU1316 and similar, same `libairplay.so` 210.81). On that platform iAP2 runs inside `dio_manager` through Cinemo's SDK, so its injection mechanics don't transfer. The protocol knowledge does:

- **Messages:**
  - `0x5200` StartRouteGuidanceUpdates (car → phone)
  - `0x5201` RouteGuidanceUpdate (phone → car)
  - `0x5202` RouteGuidanceManeuverUpdate (phone → car)
  - `0x5203` StopRouteGuidanceUpdates (car → phone)
  - `0x5204` LaneGuidanceInformation (phone → car)
- **Identification component `0x001E` (RouteGuidanceDisplayComponent):**
  - `0` Identifier, u16 (they use `0x0010`)
  - `1` Name, string
  - u16 limits `2`–`8`: current road name, destination name, after-maneuver road name and maneuver description lengths; maneuver storage capacity; lane-guidance description length and storage capacity. They use 256 for lengths and 6 for maneuver storage.
- **`0x5200` start parameters:** `0` component ID (u16), plus empty request flags `1` source name, `2` source supports route guidance, `3` exit info.
- **Field IDs and mapping:** the fields of `0x5201` and `0x5202`, the maneuver-type → BAP mapping and the BAP NavSD bridge are in their `docs/cluster-and-rgi/` (`IAP2_ROUTE_GUIDANCE_TLVS.md`, `MANEUVER_MAPPING.md`, `RGI_AND_BAP_BRIDGE.md`, `NAVSD_FCTID_MATRIX.md`).
- **Their lesson on timing:** send `0x5200` as an *extra* message after authentication and identification, never replacing a stock message. A badly timed start stalled the link without any `0x5201`.

Code adapted from that project must keep its GPL-3.0 notice and attribution.

## Phase B design

Goal of the first on-car test (**B1**): see `0x5201` / `0x5202` frames in `/dev/shmem/iap2.log`. Nothing reaches the cluster yet.

1. **Config** (`/mnt/system/etc/mm/iap2.cfg`, backed up): add the `[ident]` section above.
2. **Driver patch** (`/mnt/app/armle/lib/dll/ipod-drvr-iap2.so`, backed up):
   - append component `0x001E` to the identification;
   - send `0x5200` once after `IdentificationAccepted` and authentication, next to the stock feature starts;
   - stop with `0x5203` on teardown where possible.
3. **Rollback:** a toolbox entry restores both files. A rejected identification shows in the log as `IdentificationRejected`, listing the parameters it objects to.

Implementation options for step 2:
- **Hand-written ARM patch** in the driver: no toolchain needed, but hard to maintain.
- **C code** built with a QNX 6.5 ARM toolchain ([luka-dev/qnx65-armv7-toolchain](https://github.com/luka-dev/qnx65-armv7-toolchain), Docker). Internal calls in the driver are direct, not through the PLT, so a library loaded into `mm-ipod` would have to patch the code at runtime, or the driver file is patched to call into it.

For phases C and D, the driver already has PPS helpers (`pps_object_update_str` and others). A patched driver could publish the route-guidance fields to a PPS object under `/ramdisk/pps/iap2/`, and the Java hook would read that file.
