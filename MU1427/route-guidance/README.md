# MU1427: CarPlay turn-by-turn in the cockpit's own navigation display (research)

**Goal:** show Apple Maps guidance in the 791 cockpit's native navigation graphics: VW maneuver arrows, distance bar, street names and ETA. The current turn card is part of the CarPlay video drawn by the iPhone ([`../791_AID12.3/tuning/`](../791_AID12.3/tuning/)); this would replace or complement it with the cluster's own graphics.

**Current: the full automatic MU1427 guidance package is prepared.**
[INSTALL.md](./INSTALL.md) covers the separate native-guidance install/remove
options alongside the unchanged AUTO MU video installers. Research menu
entries are removed, author credits distinguish omonob and tomasz-twardzicki,
and narrow/wide turn cards move 16 pixels lower. The release uses a bounded
continuous RAM feed rather than manual capture journals. Its automatic
startup and revised card position still need a first check on the unit.

D3 unit testing accepted corrected maneuver distance, route distance and
travel duration, with native AID/HUD arrows and zero adapter errors. See
[D3-RESULTS.md](./D3-RESULTS.md). Both captures exported despite removal before
export; replay matches 676 observations. The bounded sixteen-slot publication
ring still has a known arbitrary-burst retention limit.

Original D1 remains withdrawn after its class-format startup failure.
D1-r2 corrected that and passed startup/shadow; see
[D1-RESULTS.md](./D1-RESULTS.md) and [D1-r2-RESULTS.md](./D1-r2-RESULTS.md).

Status: **C4-2 passes continuous-reader and maneuver-progression testing
(reviewed 2026-10-18): 240/240 published events retained across two
allocations, fresh current lists, advancing selected maneuvers and distances,
route-stop clearing and normal reconnection.** The user confirms outdoor
driving through ordinary turns with normal AID cards and route line. There
are no producer faults or B1-style link errors. See
[C4-2-RESULTS.md](./C4-2-RESULTS.md). The tested B4 driver and C4 recorder are
unchanged; no new installation is needed for this result.

The first garage run's sustained missing list is not reproduced. Its one
overwritten event still shows the sixteen-slot ring is not guaranteed
lossless for arbitrary bursts; see [C4-RESULTS.md](./C4-RESULTS.md). Host replay
reports unique coverage and per-message selection, with conservative clearing
preserved. [TEST-C4.md](./TEST-C4.md) retains the accepted test procedure and
[OBSERVER.md](./OBSERVER.md) describes the recorder.

**D3 is the accepted manual-test baseline; use INSTALL.md for the automatic release.**
[TEST-D3.md](./TEST-D3.md) gives installation, a mandatory fresh shadow gate,
the five-minute live test, export and HMI removal/reboot steps. D3 retains
verified/observed/pre-disable status before per-run counters reset.
[LIVE-BRIDGE.md](./LIVE-BRIDGE.md) describes the separate Java consumer,
factory ASL timer, narrow stock BAP-stage hooks and verification. B4 and the
C4 recorder binary are unchanged. Keep B4 installed; do not restore the
driver to factory for D3. Native output is disabled after every boot.

The preceding **native mapping and host bridge model** are also available.
[NATIVE-BRIDGE.md](./NATIVE-BRIDGE.md) documents the 54 maneuver cases,
replacement frames, independent ownership leases, distance association and
clear/handback behavior. The exact factory JXE supplies 22 verified interface
contracts; 37 mapping/bridge tests and 624 factory serializer / 39 pure
factory remapping cases pass. C4-2 replay produces left/right/roundabout
proposals, while unknown/conflicting geometry clears the symbol. The
live decoder matches 19,360 mapping vectors and both C4 journals. Host tests
exercise patched stock publishing, clearing, handback and delivery retries.
The corrected exact JAR now passes loading/hooks/registration checks using
factory ARM J9 under QNX, with verification on and off. Complete HMI startup,
ownership and shadow processing now pass on the unit. D2 native arrows and
disconnect clearing pass on AID/HUD. D3 photos now demonstrate corrected maneuver distance and native route totals;
no issues were reported. Exhaustive boundary/lifecycle coverage remains separate.

B4 publication and normal AID route-line/turn-card behavior passed the
earlier test; see [B4-RESULTS.md](./B4-RESULTS.md). B4 fixes B3's activation
ordering; [TEST-B4.md](./TEST-B4.md) retains installation/rollback instructions.
[PUBLICATION.md](./PUBLICATION.md) describes the handoff,
[B2-RESULTS.md](./B2-RESULTS.md) reception,
[B3-RESULTS.md](./B3-RESULTS.md) earlier lane/visual observations and
[DECODER.md](./DECODER.md) the offline model. Existing B4/C4 packages and the
tested D3 ZIP remains unchanged. The full release adds its own installer and
automatic feed; its source and proof are in `release/` and `build-release*`.
Do not rerun B1.

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
- **Resolved by B1/C1:** unknown guidance IDs are rejected by the native reply table before semantic dispatch; the positive error is mistaken for a retained packet, leaking its receive buffer. B2 handles the advertised guidance IDs before that gate. See the receive-path section below.

Some of the identification and iAP2 message details here come from reverse engineering and public references, not from Apple's (NDA) accessory specification. Treat them as hypotheses until confirmed on the unit.

## Phases

| Phase | Work | Risk to the car |
| --- | --- | --- |
| **A. On-unit recon** | Toolbox entry **Collect navigation research data to SD**: which process loads `ipod-drvr-iap2.so` and with which `config=`, where the driver and configs live, PPS iAP2 objects, logs | None, read-only |
| B. Source | Patch the driver to declare the route-guidance component and receive its messages; send the start command; log the raw messages to `/ramdisk` | Medium: a bad identification can stop CarPlay until rolled back; needs a rollback entry |
| C. Mapping | VW maneuver mapper and ownership/replacement bridge model implemented against exact MU1427 interfaces and C4-2; lane interpretation remains | None, offline |
| Publication | B4 handoff validated; C4-2 records all 240 events across reconnect with selected-maneuver/distance progression; arbitrary burst retention remains bounded | Medium: new filesystem hooks; same OEM rollback |
| D. Sink | D3 distance scaling and route totals accepted; zero adapter errors; manual bounded testing only | Medium: HMI JAR install/removal requires reboot; fresh shadow gate before bounded live output |

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

The host decoder and bounded state model are implemented in
[`rgi_decode.py`](./rgi_decode.py). [DECODER.md](./DECODER.md) documents the
contract and tests, including the distinction between partial route updates
and replacement maneuver records. B3 implements a bounded publication path
through the existing iAP2 virtual filesystem; see [PUBLICATION.md](./PUBLICATION.md).
The synchronous PPS helpers remain outside the receive hook. A continuous
consumer and native cockpit output are subsequent steps after the successful
B4 handoff test; see [B4-RESULTS.md](./B4-RESULTS.md).

## B1 implementation (historical, 2026-10-16)

Two on-unit install attempts stopped before modifying files because the scripts
required unavailable `tr`, then `cksum`. Installer **B1-install-r3** follows the
base map patch: `ls -ln` field 5 checks the firmware, OEM, payload and backup
sizes; `cp` and `mv` stage and activate files. It has no on-unit hash or system
`cmp` dependency. All install/restore tests run with only the base utilities in
PATH. The driver/config payloads are unchanged; see [TEST-B1.md](./TEST-B1.md)
for updating the toolbox before retrying.

The current source now builds B2. The B1 offsets below describe the failed
first test; its later receive hook was unreachable for unregistered guidance
messages. The C1 archive and corrected receive path are described after this
section.

The exact Phase A driver is SHA-256
`0ac13f43d3fb259eee328c272fa1211bb558b6e2cd97c6e38ef38e4e71469d51`
(739,925 bytes). `patch-driver.py` refuses any other input and builds the ARM
assembly in `driver-hooks.S` using clang's assembler. A QNX SDK is unnecessary:
the payload calls functions already present in this driver, without adding
imports or runtime absolute pointers.

| File offset / virtual address | Stock instruction / behavior | B1 |
| --- | --- | --- |
| `0xe138` in `ident_info_request` | `mov r0,r6`, after all 24 stock component builders | Append `0x001e` through `packet_addparam_blob`; use stock cleanup on failure, then resume at `0xe13c` |
| `0x63f0` in `iap2_start_features` | `mov r0,r5`, returning the stock feature-start result | If stock result is zero, submit a separate 24-byte `0x5200` semantic frame through `link_send_raw_message`; preserve the stock result |
| `0x13470` in `link_handle_iap2pkt` | `movw r2,#0x5702`, start of semantic control-message dispatch | Log IDs `0x5201`, `0x5202`, `0x5204` with the complete TLV payload; restore dispatch inputs |

The two callers of `iap2_start_features` (at `0x13628` and `0x13694`) check
`driver+0x5c & 3 == 3`: authentication succeeded **and** identification accepted,
regardless of their order. The new send occurs after the stock feature body,
using the existing send pool, transport, session ID and checksums. It does not
replace LocationInfo or any other stock message. There is one attempt per
successful feature initialization, with no retry or explicit stop hook yet.

The open receive question is resolved: `iap2_msg` handles **client commands**;
incoming phone control messages go through `link_handle_iap2pkt`. Its dispatch
has no `0x52xx` cases and falls through to `0x1401c`. B1 captures raw guidance
there before that fall-through. It does not yet decode fields or publish PPS.
The existing verbose packet printer can also dump unknown message groups, but
the explicit `CPMAP_RGI_RX` marker makes recognition independent of its schema.

The payload is appended at file offset and virtual address `0xb5000` in a new
RX `PT_LOAD`, replacing the program header for the non-allocated GNU build-id
note. The QNX note, original RX/RW mappings, BSS, dynamic tables and relocations
are preserved. **QNX loader acceptance of the added mapping is an on-unit test,
not something established by emulation.**

`build-test-package.py` adds the config IDs and B1 install/status/restore entries
to a private copy of the full toolbox. `rg-b1.sh` checks the firmware and known
OEM/payload sizes, retains original backups, preserves permissions and renames
staged files on their destination filesystems. Host SHA-256 checks remain in
the builder; runtime size checks do not detect same-size changes. Rollback
requires only valid-sized original backups, even if the active files are
missing or damaged. Its lock is in `/ramdisk`, so reboot clears an interrupted
operation's lock. It never restarts the
driver; install and restore require a full reboot. The original toolbox source
and released map-video payload are not modified by the package build.

Offline checks: `test-driver.py` runs the injected ARM instructions and actual
stock packet-building/send helpers under Unicorn at two load addresses, checks
TLV encoding, checksums, authentication/identification gates, register/stack
preservation, packet-space failure and send failure. `test-install.py` checks
install/repeat/status/local rollback using a closed PATH of base commands,
original bytes and permissions, missing/damaged active files, backup/staging/
rename failures, interrupted two-file installation, retry after a failed restore,
and MMX/RCC remount dispatch. See [TEST-B1.md](./TEST-B1.md) for reproduction commands.

Protocol layout adapted from LuKa's `rgd_tlv.c` / `rgd_tlv.h` at upstream commit
[`dfafccf6637ad45457085f0977f18cd7f64ab3ed`](https://github.com/luka-dev/mib2q-carplay-rgi/tree/dfafccf6637ad45457085f0977f18cd7f64ab3ed/hook/routeguidance),
Copyright (c) 2026 LuKa (@LuKa_dev), GPL-3.0-or-later. The assembly keeps this
notice, and the generated test ZIP includes corresponding source and license.

## B2: receive-buffer recycling fix

The C1 archive contains the missing iAP2 log. It proves that the component and
start request worked, but every incoming `0x5201` hit `link_handle_reply`'s
unknown-message table gate. That gate returns positive `EINVAL` (22). The
transport mistakes this for a retained reply packet and skips recycling its
receive buffer. Empty-pool waits and unanswered location retransmissions then
appear. The process snapshot also shows `mount` blocked sending to `mm-ipod`.

B2 moves the hook from `0x13470` to the stock **call at `0x133a0`**, before this
gate. Valid semantic IDs `0x5201`, `0x5202`, `0x5204` are logged and return zero
to the original dispatch/cleanup path. All other frames tail-call the stock
`link_handle_reply`. The existing ACK/sequence path, identification component,
start parameters and config IDs are unchanged. This is a targeted receive fix,
not a general change to unknown-message handling.

`test-driver.py` now executes the actual stock table gate and transport
return/recycle branch. It reproduces the B1 leak and verifies 1,000 guidance
frames without loss at each of two load addresses, followed by an original
now-playing update. Its OS/USB boundaries are mocked. The initial parked
on-unit test also passed; [B2-RESULTS.md](./B2-RESULTS.md) separates captured
evidence, user-observed reconnect stability and coverage still outstanding.

B2 uses the existing `route-guidance-b1` original backup directory; the installer
adopts a rolled-back OEM pair without replacing those backups. It refreshes the
saved local rollback script and includes the C2 focused collector, with no
plain mount listing or PPS reads. [B1-RESULTS.md](./B1-RESULTS.md) records the
redacted evidence and exact rejection/recycle addresses. Raw logs stay private.
