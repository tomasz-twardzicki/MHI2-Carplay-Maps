# MU1427: CarPlay turn-by-turn in the cockpit's own navigation display (research)

**Goal:** show Apple Maps guidance in the 791 cockpit's native navigation graphics: VW maneuver arrows, distance bar, street names and ETA. The current turn card is part of the CarPlay video drawn by the iPhone ([`../791_AID12.3/tuning/`](../791_AID12.3/tuning/)); this would replace or complement it with the cluster's own graphics.

Status: **Phase A (on-unit recon)**. Nothing in this directory changes the car yet.

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
