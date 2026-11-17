# MU1367 v1.5.4 — stable: arrival time on the AID, stream test

**Stable release** for **K4525 / P4521 MU1367 + AID 791**. It replaces v1.5.3 as the
recommended release. v1.5.4 is v1.5.3 plus two changes; the startup animation, the MU
menus, audio and reader are the v1.5.3 ones, byte for byte. The video bridges and the
Android Auto feeder are the v1.5.3 sources, rebuilt with a newer compiler (Apple clang 21
instead of 17), so their files differ; they pass the same host and QNX tests.

- **Arrival time on the AID.** The OEM navigation setup lets you choose between time to
  destination and arrival time for the cluster. CarPlay guidance used to send the remaining
  time in both cases. With **arrival time** selected, the AID now shows the unit's own
  clock plus the remaining time from the phone (same time zone and 12/24 h format as the
  unit's clock). With **time to destination** nothing changes. Until the unit's clock is
  valid after a start, the remaining time is shown. Only the time of day is sent, as the
  stock navigation does when it has no date.
- **Stream test** in Toolbox > CarPlay diagnostics: try any map rate from 20 to 40 fps and a
  key frame every 5 to 15 frames, beyond the three MU UI choices. The test values override
  the MU UI stream setting until **Stream test: off** and apply on the next phone
  connection. **Show current fps / IDR** prints what the core last asked of the phone. The
  default stays 40 fps / IDR 5.
- **Android Auto** stays included and is **not yet fully tested**.

Both changes are verified off the unit: on the host, with the factory Java VM and the
firmware shell in the QNX emulator, and through the full install and migration tests.
**They are not yet tested in a car.** v1.5.3 itself is vehicle-tested (as v1.5.3-e).

Updating from v1.5.3, v1.5.3-e or any earlier supported version goes through the two-stage
install: install → full reboot → install again. MU UI settings, including the Startup
animation choice, are kept. The final message is
`MU1367_RELEASE_1_5_4_INSTALLED_FULL_REBOOT_REQUIRED`.

# MU1367 v1.5.3 — stable: startup animation, higher bridge priority

**Stable release** for **K4525 / P4521 MU1367 + AID 791**, built from v1.5.3-e after
vehicle tests with good results. It replaces v1.5.2 as the recommended release. Both
MU menus, both `core.so` builds, guidance, audio and reader are the tested v1.5.3-e
ones, byte for byte. One fix in the CarPlay video bridge:

- **The live map always follows the startup clip.** At the end of the clip, the bridge
  skips the map frames that arrived meanwhile and asks the phone for a fresh key frame.
  It used to send that request before noting where to skip to. If the phone answered
  within that very short gap, the key frame was skipped too, and the AID stayed on the
  clip's last frame until the phone sent its next key frame. The bridge now notes the
  position first. The vehicle tests did not hit this; a test on a heavily loaded PC
  did.

- **Startup animation on the AID.** A 4.2 s App-Connect clip before the live CarPlay
  map. Choose when it plays under **App-Connect > Virtual Cockpit settings > Startup
  animation**: **Once per boot** (default), **Every connection** or **Off**. With
  Tuning, the setting takes the place of the **Wireless CarPlay (test)** row, which
  never had a function. Android Auto has no startup animation.
- **The video bridge gets CPU when the unit is busy.** The CarPlay and Android Auto
  bridges run at priority 14 (was 10, the same as the navigation renderer), for
  steadier maps while the reverse camera and the navigation load the unit.
- **Android Auto** stays included and is **not yet fully tested**.

Details of the startup animation and the priority change are in the v1.5.3-e notes below. Updating from v1.5.3-e,
v1.5.2 or any earlier supported version goes through the two-stage install: install →
full reboot → install again. A Startup animation choice saved under v1.5.3-e is kept.
The final message is `MU1367_RELEASE_1_5_3_INSTALLED_FULL_REBOOT_REQUIRED`.

## Thanks and sources

This release builds on the work and help of:

- **[omonob (汽车大玩家 / QCDWJ)](https://github.com/omonob)**: the original
  [CarPlay Maps VC](https://github.com/omonob/MHI2-Carplay-Maps) (map-video runtime,
  steering-wheel controls, installers and toolbox integration).
- **[luka-dev](https://github.com/luka-dev)**: CarPlay route guidance research
  ([mib2q-carplay-rgi](https://github.com/luka-dev/mib2q-carplay-rgi)); the protocol and
  maneuver adaptations keep LuKa's attribution in the source.
- **[chrzanowy](https://github.com/chrzanowy)**: the Android Auto cluster feeder and route
  translation ([mhi2-aid-carplay](https://github.com/chrzanowy/mhi2-aid-carplay)), car-tested on MU1161 / AID 791.
- **[MacsInSpace](https://github.com/MacsInSpace)**: the `gal` cluster-map hook used for
  Android Auto ([mib-cluster-map](https://github.com/MacsInSpace/mib-cluster-map)) and other MIB projects.
- **[Mr-MIBonk](https://github.com/Mr-MIBonk)**: M.I.B. (More Incredible Bash), the MIB2 toolbox.
- **Jille & Olli**: the [MIB2 Toolbox](https://github.com/jilleb/mib2-toolbox) whose GEM
  menus and scripts this SD is built on.
- **[Karan](https://t.me/karanldn)**: valuable road tests and feedback.
- Research references: [perkthefox/mst2-cluster-nav](https://github.com/perkthefox/mst2-cluster-nav),
  [fifthBro/mh2p-cluster](https://github.com/fifthBro/mh2p-cluster) and
  [brisoleg/e-golf-mib2](https://github.com/brisoleg/e-golf-mib2).

Licenses and exact upstream revisions are in [NOTICE.md](NOTICE.md).

# Earlier: v1.5.3-e — experimental: startup animation, higher bridge priority

**EXPERIMENTAL — TO BE TESTED.** Update of stable v1.5.2 for **K4525 / P4521 MU1367 +
AID 791**. Use v1.5.2 for a stable installation. Two changes:

- **Startup animation on the AID.** When CarPlay takes the cluster map, the AID first
  plays a 4.2 s App-Connect clip, then switches to the live map. The clip is built into
  the CarPlay video bridge and sent to the AID as it is: nothing is decoded or
  re-encoded on the unit. After the clip the bridge drops the map frames that arrived
  meanwhile and asks the phone for a fresh key frame, so the map starts clean and
  current.
  Choose when it plays under **App-Connect > Virtual Cockpit settings > Startup
  animation**:
  - **Once per boot** (default): only on the first CarPlay connection after the unit
    starts. A reconnect or a handback mid-drive goes straight to the map.
  - **Every connection.**
  - **Off.** The map starts exactly as in v1.5.2.

  The change applies on the next phone connection. Without Tuning, the setting is a new
  fifth row. With Tuning, the page was already full, so the setting replaces the
  **Wireless CarPlay (test)** row. That row only saved a value that nothing used.
  Android Auto has no startup animation: an Android phone sends one key frame per
  connection and cannot answer the request that ends the clip.
- **The video bridge gets CPU when the unit is busy.** Drives with the reverse camera on
  showed the CPU at 98–100% for several seconds, then MOST writes of up to 3.7 s and
  ring overruns. The navigation map renderer threads run at priority 10, the same
  priority the bridge inherited, while the CarPlay receive threads that fill the ring
  run at 17–19. A ring overrun means the bridge's reader did not run for 64 frames in a
  row (1.6 s at 40 fps). The CarPlay and Android Auto bridges now raise their threads
  to priority 14. That is above every navigation thread in the heartbeat logs and below
  the MOST driver (16) and the CarPlay receivers. QNX drivers serve a request at the
  caller's priority, so the bridge's MOST writes also move up. The bridge log shows
  `bridge: priority thread=input before=10 target=14 status=0`.

Everything else is v1.5.2: guidance, audio, reader, both `core.so` builds, the safe
area, the 2048-packet backlog, the boot-time MOST reclaim and the defaults (40 fps / IDR
5). Only the two MU menus and the two bridge builds change. Updating from v1.5.2 (or
any earlier supported version) goes through the two-stage install: install → full
reboot → install again. The final message is
`MU1367_RELEASE_1_5_3_E_EXPERIMENTAL_INSTALLED_FULL_REBOOT_REQUIRED`.

**What to test:**
- Does the clip show on the AID after a cold start? Does the live map follow cleanly,
  without a grey or blocky picture?
- **Every connection** and **Off**: does a reconnect behave as chosen?
- Drives with reversing: are stalls shorter or gone? The bridge log keeps
  `write_us_max`, `drops` and `latency-reset`, so you can compare them with v1.5.2.

Export diagnostics after a drive.

# Earlier: v1.5.2 — stable: CarPlay and Android Auto on the AID

**Stable release** for **K4525 / P4521 MU1367 + AID 791**, built from v1.5.2-e after
vehicle tests with very good results. It replaces v1.4.6 as the recommended release.
The CarPlay map path is the tested v1.5.2-e one: the v1.2.2 safe area, the
2048-packet bridge backlog and the boot-time MOST reclaim. Changes from v1.5.2-e:

- **40 fps / IDR 5 is the default map stream.** The MU UI (**App-Connect > Virtual
  Cockpit settings > Map stream**) offers 40 fps (default), 30 fps and 25 fps, all with
  IDR 5. 20 and 27 fps are gone from the menu; a saved 20 or 27 fps choice now runs and
  shows as 40 fps. A saved 25 or 30 fps choice is kept. Before rolling back to v1.4.5 or
  older, select 30 or 40 fps again.
- **P4521 is no longer experimental.** It has been tested in vehicles. The installer
  reports `MU1367_FIRMWARE_TYPE=P4521` (was `P4521_EXPERIMENTAL`).
- **New: manage saved snapshots** under **Tuning > Saved snapshots of earlier
  installations**. Every update, rollback and OEM reset keeps copies of what it replaced
  on `/mnt/app`, and these add up. The four new entries list them with their sizes and
  remove them one at a time (**Select next snapshot**, then **Remove selected snapshot**)
  or all at once (**Remove all saved snapshots**). Only copies that nothing reads again
  are listed: removed or replaced layers (`*.removed-*`), stale artwork records, earlier
  and completed OEM resets, and archived MU UI settings. The installed layers keep their
  own snapshots, so **Remove latest update only**, **Recover** and **RESTORE OEM** keep
  working. A removed snapshot cannot be brought back; copy it off the unit first if you
  may need it.
- **Android Auto stays included but is not yet fully tested.** It is installed by the
  same install action, with the two **Android Auto cluster map: on / off** entries. CarPlay
  is the tested path; please report Android Auto results with a diagnostics export.

Guidance, audio, reader and both video bridges are byte-identical to v1.5.2-e. The base
and tuning core and the MU menu change only for the new default stream. Updating from
v1.4.6 or any v1.5.x goes through the two-stage install: install → full reboot → install
again. The final message is `MU1367_RELEASE_1_5_2_INSTALLED_FULL_REBOOT_REQUIRED`.

## What v1.5.2 brings over v1.4.6

- **v1.5.0-e:** Android Auto on the AID: the Google Maps picture and native VW arrows
  with distance from an Android phone.
- **v1.5.1-e:** the CarPlay map no longer drops out about 18 s after every boot (the
  bridge takes the MOST output back from the factory encoder); the Android Auto map no
  longer freezes after a stream hiccup.
- **v1.5.2-e:** the taller v1.2.2 safe area (160,20,480,440) for a closer, lighter map,
  and a 2048-packet bridge backlog (was 1024) so large frames no longer reset the stream.
- **v1.5.2:** 40 fps / IDR 5 default, P4521 supported, saved-snapshot management.

# Earlier: v1.5.2-e — experimental: lighter CarPlay map (v1.2.2 safe area, larger bridge buffer)

**EXPERIMENTAL — TO BE TESTED.** Update of v1.5.1-e for **K4525 / P4521 MU1367 + AID
791**. Use v1.4.6 for a stable CarPlay installation. Two changes aimed at the stutter
and blocky moments some drivers see with detailed Google Maps views at 27/5:

- **The map asks for the taller safe area of v1.2.2.** The safe area tells the phone's
  map app which part of the 800×480 cluster picture is clearly visible. The app keeps
  the car position and the route inside that box. v1.2.2 declared 160,20,480,440, a
  tall box almost the full height of the picture. Since v2.0 the map-only setting
  declared 200,96,400,364, smaller and lower between the dials. A comparison with v1.2.2
  pointed to this as the likely reason the map now looks wider and much more detailed
  (more roads and labels), with frames up to 145 KB, where v1.2.2 showed a closer,
  simpler map. v1.5.2-e goes back to the v1.2.2 box for the map-only view. The turn-card
  option keeps its own layouts. Possible side effect: parts of the map near the top
  edge or next to the dials may sit under the cluster graphics.
- **The video bridge allows twice the backlog before it resets.** When more than 1024
  TS packets (about 125 ms of video) were waiting for the MOST link, the bridge
  dropped them and waited for a fresh key frame. That is the brief lag, stutter and
  blocky picture. In a one-hour 27/5 drive the backlog peaked at 1377 packets, when
  a large key frame landed right after another large frame, while the MOST link
  itself was healthy (3 slow writes in 52 minutes). The limit is now 2048 packets
  (about 250 ms) for every stream setting. It only adds delay during such a burst. A
  real stall is still cut off, after about 250 ms instead of 125 ms. The bridge log now
  starts with `bridge: latency-limit packets=2048`.

Everything else is as in v1.5.1-e, including the boot-time MOST reclaim and Android
Auto on the AID. Updating from v1.5.1-e (or v1.5.0-e) goes through the two-stage
install: install → full reboot → install again. Stage 1 also removes the Android Auto
layer; stage 2 puts it back.

**What to test:** the same Google Maps routes and zoom levels as before, at 27/5 and
if possible 30 or 40 fps. Does the map look closer and simpler? Are there fewer
stutters? Is anything important hidden under the dials? Export diagnostics after a
drive: the bridge log shows `latency-reset` lines and `frame_max` sizes to compare.

The guidance, audio and menu payloads are byte-identical to v1.5.1-e. Only the map-only
core (safe area) and the CarPlay and Android Auto bridge builds (limit) change.

# Earlier: v1.5.1-e — experimental: CarPlay map survives boot, Android Auto map no longer freezes

**EXPERIMENTAL — TO BE TESTED.** Update of v1.5.0-e for **K4525 / P4521 MU1367 + AID
791**. Use v1.4.6 for a stable CarPlay installation. This rebuild of v1.5.1-e replaces
the first v1.5.1-e package published on 2026-11-10 (archive `444b4c2f…`).

- **The CarPlay map on the AID no longer drops out shortly after every boot.** In the
  v1.4.6-e test exports, the video bridge exited about 18 s after it started, on every
  boot, with `MOST write failed: Not enough memory`. The supervisor restarted it about
  4 s later. The unit's own log shows the cause. While the unit boots, the factory video
  encoder opens the same MOST output (`isoTX2`) about 15 s after the bridge has taken it,
  flushes its queue and keeps running until the cluster display is handed back to the
  map. The bridge's next write then fails. It is not low system memory (over 850 MB
  was free) and not the high boot CPU load. Now, in the first 3 minutes after boot,
  the bridge hands the cluster display back to the map itself (the supervisor's own
  `dmdt` release), reopens the output and asks the phone for a fresh key frame. The
  map should stay up or come back after a short hiccup, without the 4 s gap and the
  flash of the VW screen. It tries at most 3 times; after that, or later than 3 minutes
  after boot, the bridge exits and the supervisor restarts it as before. The
  diagnostics export shows each attempt as `bridge: most-reclaim attempt=…` in the
  bridge log.
- **The CarPlay bridge is now built from this repository's source.** Earlier releases
  used the upstream binary from the omonob toolbox v2.0.0 (GCC 4.9.4). That compiler
  is not available here, so the new bridge is built from the same reviewed source with
  the reclaim added, using the pinned QNX 6.5 SDK linker. The Android Auto feeder and
  bridge are built the same way. The main layer installs the new bridge and saves the
  upstream one in its snapshot; removal and recovery put the upstream bridge back.
- **The Android Auto map on the AID no longer freezes after a hiccup.** The first car
  test showed native guidance working but the cluster map freezing. The CarPlay map
  bridge, which v1.5.0-e also used for Android Auto, stops showing new frames after a
  gap in the stream or a short MOST backlog until the phone sends a new keyframe.
  CarPlay sends one on request; an Android phone sends only one per connection, so the
  map stayed frozen until a reconnect. Android Auto now runs its own build of the same
  bridge that keeps showing frames. It has the boot-time reclaim too, without the key
  frame request.
- **Diagnostics export** (Diagnostics > Export diagnostics to SD) now includes the
  Android Auto feeder, bridge and session summaries (`pmcp-aa-*`) and the Android Auto
  layer state.
- **Updating from v1.5.0-e or the first v1.5.1-e** goes through the usual two stages,
  because the main layer now also owns the CarPlay bridge. Stage 1 removes the Android
  Auto layer (the factory `gal` comes back from its snapshot) and the main layer, then
  asks for a full reboot. After the reboot, run the same install entry again to
  install everything. All earlier snapshots are kept.

The car log also showed USB errors (`CRC_ERR|STALL`) that disconnected the phone twice,
and the phone's main-screen Android Auto video ran at 13–17 fps. Use a short, good data
cable; a weak USB link can make the picture stutter on its own.

The six CarPlay runtime payloads (guidance, core, menu, audio, tuning) and compressed
artwork are byte-identical to v1.5.0-e.

# Earlier: v1.5.0-e — experimental Android Auto on the AID

**EXPERIMENTAL — TO BE TESTED.** Based on stable v1.4.6, for **K4525 / P4521 MU1367 +
AID 791**. P4521 installation remains experimental. This package has **no vehicle
result yet**, neither for Android Auto nor for the unchanged CarPlay features. Use
v1.4.6 for a stable CarPlay installation.

## Android Auto in the same installation

The same **Install / update CarPlay integration (reboot)** entry now installs
Android Auto support together with every CarPlay feature of v1.4.6. There is no
separate Android Auto install step. With an Android phone on the cable:

- **Google Maps picture on the AID**, over the head unit's own MOST video path, like
  the CarPlay map. The MU menu's cluster map switch applies to Android Auto too:
  with the map off, the AID keeps its VW content.
- **Native VW turn arrows with distance** and the countdown bar from Google Maps
  steps, through the same route guidance as CarPlay. A phone that stops navigating
  releases the arrow after 10 s; CarPlay keeps its 3-minute hold.

CarPlay is unchanged. Only the guidance JAR changes in the CarPlay runtime; the map
core, menu, audio, compressed artwork, reader and driver bytes match v1.4.6.

**How it works.** The factory Android Auto receiver (`gal`) is started through a
small wrapper that loads MacsInSpace's cluster-map hook. The hook offers the phone a
second 800 × 480 display and hands its H.264 video to a feeder, which writes it into
the ring the CarPlay map bridge already sends to the AID. The hook also turns Google
Maps' navigation messages into the mailbox format the CarPlay route guidance reads.
Both MU1367 trains carry the same factory `gal`, and it matches the hook's
car-tested P4521 profile exactly. Hook, feeder and route translation come from
[chrzanowy/mhi2-aid-carplay](https://github.com/chrzanowy/mhi2-aid-carplay) v1.5.0
(tested there on a Passat B8, MU1161 + AID 791). For MU1367 the feeder also respects
the MU menu map switch and holds the same video-cache lease as the CarPlay bridge.

**New menu entries:** **Android Auto cluster map: off / on** switch only the hook.
With it off, Android Auto runs exactly as from the factory from the next connection.

**Removal:** **Recovery > Remove latest update only** removes Android Auto first and
puts the factory `gal` back from its verified snapshot, then the CarPlay update. The
menu's **RESTORE OEM** removes Android Auto first as well.

## Known limits of Android Auto

- No vehicle result on MU1367 yet.
- The picture starts about 5 s after the phone connects. Now and then it starts dark
  until the phone's next key frame; reconnecting the phone helps.
- No VW arrow at the very first step of a route. Remaining distance and arrival time
  stay in the Google Maps picture. No VW lanes or road name from Android Auto.
- The MU menu's frame rate and turn-card settings apply to CarPlay only. The Android
  Auto stream is 30 fps.
- Track title and album art on the AID remain CarPlay-only.

# Earlier: v1.4.6 — stable: U-turn lanes, Apple Maps languages, 27 fps and compressed artwork

Stable release of the v1.4.6-e build for **K4525 / P4521 MU1367 + AID 791**. P4521
installation remains experimental. Everything in v1.4.6-e below is included, with two
new defaults:

- **27 fps / IDR 5 is the default map stream** (was 25 fps in v1.4.6-e). The MU menu
  still offers 20, 25, 27, 30 and 40 fps, all with IDR 5. A saved choice is kept; only
  units without a saved choice use the new default.
- **Compressed album artwork is installed by default.** It is lossless: the cover stays
  a 256 × 256 PNG with identical pixels, usually 1–100 KB instead of 197 KB. **Tuning >
  Disable compressed album artwork** switches it off, and later installs respect that.
  **Remove latest update only** and the menu's **RESTORE OEM** switch it off first.

Guidance, audio and reader are byte-identical to v1.4.6-e; only the map core and MU
menu change. An installed v1.4.6-e uses the checked removal, full reboot and install
sequence. Before rolling back to v1.4.5 or older, select **30 fps / IDR 5** or
**40 fps / IDR 5**: older menus do not recognize 27 fps.

# Earlier: v1.4.6-e — experimental U-turn lanes, Apple Maps languages and 25 fps default

**EXPERIMENTAL — TO BE TESTED.** Based on the stable v1.4.5 release, for
**K4525 / P4521 MU1367 + AID 791**. P4521 installation remains experimental. This
package has no vehicle result yet. Use v1.4.5 for a stable installation.

The guidance JAR, map core and MU menu change, in both the base and the optional
turn-card runtime. Audio, reader, driver and other runtime bytes match v1.4.5.

## U-turn lanes by driving side

A lane at exactly 180° carries no side, and was always drawn as the left U-turn
(byte 114). That is right for right-hand traffic but wrong in the UK and other
left-hand-traffic countries, where the main arrow was already correct. Such a lane now
follows the driving side the phone sends with each maneuver: the right U-turn (146) in
left-hand traffic, unchanged otherwise. A signed angle (for example −175°) keeps its own
side, and with no driving side known the previous behavior stays. The main arrow uses
the same rule for an exact ±180° angle.

## Apple Maps with any phone language

Some phones alternate between two names for Apple Maps within one session, for example
"Apple Maps" and "Mapy Apple". Each change was taken as a switch to another app and
cleared the stored maneuvers and lanes. Apple Maps does not resend them, so arrows and
lanes updated only from a later turn. Names containing the word "Apple" now count as the
same app. Switching to Google Maps or Waze, a new destination or a route end still
clears. `guidance-evidence.txt` adds `route_clears source=… destination=…` and a bounded
`source_flips` log (time, route state and what each message carried), with no road or
destination text.

## Map stream

**25 fps / IDR 5 is the default.** **App-Connect > Virtual Cockpit settings > Map
stream** offers 20, 25, 27, 30 and 40 fps, all with IDR 5. The IDR 20 choices are gone;
a saved 30 or 40 fps / IDR 20 choice runs at the same frame rate with IDR 5. Saved
30 fps / IDR 5 and other choices are kept. Reconnect after changing it.

**Before rolling back, select 30 fps / IDR 5 or 40 fps / IDR 5.** v1.4.5 and older
menus do not recognize 20 or 27 fps, and v1.4.4 and older also not 25 fps. If an older
menu refuses the saved settings, use **Reset saved MU UI settings (reboot)**.

## Optional compressed album artwork

**Tuning > Enable compressed album artwork (reboot)** replaces only the artwork helper.
The cover stays a lossless 256 × 256 PNG with identical pixels, compressed with the
factory zlib: usually 1–100 KB instead of 197 KB. It is off by default and keeps a
snapshot of the original helper. **Disable it before** a later update, removing the
integration or the OEM reset. This is the compression part of the earlier artwork R3
test only; cover polling is unchanged.

## Known issues

- **Wheel-arrow zoom over a wireless adapter also opens the factory cluster menu.**
  Not changed in this release; see KNOWN-ISSUES.md.
- Reroute handling from v1.4.5 and Waze still have no vehicle result.

# Earlier: v1.4.5-e — experimental reroute handling and 25 fps test option

**EXPERIMENTAL — TO BE TESTED.** Based on the stable v1.4.4 release, for
**K4525 / P4521 MU1367 + AID 791**. P4521 installation remains experimental. This
package has no vehicle result yet. Use v1.4.4 for a stable installation.

The guidance JAR, map core and MU menu change, in both the base and the optional
turn-card runtime. Audio, reader, driver and other runtime bytes match v1.4.4.

## Reroute handling

- **"Calculating route" during a reroute.** A reroute now shows the factory
  calculating symbol (`CALC_ROUTE`, main element 9) with its text in the car's
  language. Previously the output was released and came back with a placeholder.
- **The countdown no longer restarts.** In every reroute in the available captures,
  the phone sends states 1, 5, 0, 3, 1 within about half a second, then restarts
  its maneuver list at a start-route step reporting 0 m. That was treated as a new
  trip. It is now one episode: distance, progress bar, current road and arrival data
  keep their values until the phone reports a real distance again. See
  [the capture analysis](evidence/REROUTE-2026-11-05.md).
- **Bounds.** The wait ends after 20 s or 5 s of phone silence. A stop inside a
  reroute ends guidance within 1.5 s of the next phone message, or at that 5 s
  silence. A normal route end, a new destination, disconnect and OEM navigation still
  clear immediately.

## Placeholder arrow

With an active route and no maneuver yet, the cluster now shows the straight
`DIRECTION_TO_DESTINATION` arrow instead of a straight turn arrow. It always points
straight: iAP2 supplies no destination position or bearing, so the true direction
cannot be calculated.

## 25 fps test option

**App-Connect > Virtual Cockpit settings > Map stream** has a new choice,
**25 fps / IDR 5 (test)**. Reconnect after changing it. **30 fps / IDR 5 stays the
default**, and saved choices are preserved.

Captures show the phone delivering about 17–19 fps when 30 is requested, close to the
link's bandwidth at peaks. Requesting 25 may remove the occasional stutter. It may
also lower the delivered rate, because two captures requesting 40 fps reached about
27. Please compare the same app and route at both settings.

**Before rolling back to v1.4.4 or older, select another map stream.** Older menus
do not recognize this choice and can refuse the saved settings. If that happens, use
**Reset saved MU UI settings (reboot)**.

# Earlier: v1.4.4-e — experimental Apple Maps / Waze guidance handling

**EXPERIMENTAL — TO BE TESTED.** Based on the vehicle-confirmed v1.4.3-e release,
for **K4525 / P4521 MU1367 + AID 791**. P4521 installation remains experimental.
Only the guidance JAR and native reader change; audio, driver, menu and video
runtime bytes match v1.4.3-e.

## Native guidance

- **Quiet routes are held.** Apple Maps sends sparse deltas and can be silent for
  longer than 5 s while stopped or between distance steps. Previously the reader's
  5-second STALE record reset the whole route model and the bridge dropped output
  after 5 s; Apple Maps does not resend maneuvers it already sent, so the arrow
  and lanes stayed lost until the next maneuver. An active route is now held while
  the reader heartbeat, phone session and route state remain valid, for at most
  **3 minutes** of complete phone silence. Explicit route end, cancellation,
  invalidation, session change, disconnect and OEM navigation priority still
  clear immediately.
- **A malformed message is rejected alone.** Every captured MU1367 session's
  first route message failed validation. Because the 16-message window was
  validated as one unit, that message blocked all guidance until 16 newer
  messages arrived. Google Maps recovered within seconds; Waze, which sent only
  2–3 messages per session, never displayed anything. Envelope, ordering and
  overlap checks still reject a whole snapshot. An unreadable route update clears
  route state rather than being guessed.
- **Structural guidance evidence.** `guidance-evidence.txt` records message
  counts, route states, maneuver types, components, gaps between messages,
  rejected-message shapes (keys/sizes only) and the phone app's source name.
  It contains no road or destination text, is bounded to 4 KiB and is included
  in the normal diagnostics export and the Status action.

Waze's delivery remains unverified. The captured Waze sessions supplied only
2–3 iAP2 guidance messages in about 7 minutes, against hundreds for Google Maps.
If the new evidence shows that Waze sends no active route or maneuvers, its
native cluster guidance is not possible through this path.

## Reader recovery budget

v1.4.3-e allowed three worker replacements per reader lifetime (one boot).
After **10 minutes** of fault-free operation since the latest replacement, the
budget now returns to three attempts with the initial 1-second backoff. Rapid
faults still stop recovery after three replacements (1/2/4-second delays).
A lifetime ceiling of **64** replacements bounds a reader regardless. Status
adds `total_restarts` and `budget_resets`; the first-failure record is unchanged
apart from an appended `total_restarts` field.

## Installer output and reboot

The installer no longer shows a "reboot required" line after every internal
layer. It prints the planned step count, one numbered `[n/N]` line per completed
layer and a single reboot request at the end. A new **Reboot unit (after install
completes)** entry in the main menu refuses while an installation runs, then
uses the Toolbox's own reboot helper. Migration from an older integrated
revision still needs the existing reboot between its two stages.

## Install

Use the normal **Install / update CarPlay integration (reboot)** action.
v1.4.3-e is recognised by its exact saved controller and backups and uses the
established two-stage retirement/reboot/install path, preserving its snapshot.
All earlier supported revisions are unchanged. Expect
`MU1367_RELEASE_1_4_4_E_EXPERIMENTAL_INSTALLED_FULL_REBOOT_REQUIRED` in that package.

Test Apple Maps and Waze with active routes, including stops at lights, then
Google Maps for regression. Export diagnostics while guiding and record which
app each export belongs to (the evidence file now names it).

---

# MU1367 v1.4.3-e — experimental guidance-reader recovery

**EXPERIMENTAL FIX — TO BE TESTED.** Based on the published v1.4.3 release,
for **K4525 / P4521 MU1367 + AID 791**. P4521 installation remains experimental.

The new capture of disappearing native guidance ended with worker failure
(`reason=3`), a different path from the earlier RAM-output failure. This build
adds a bounded first-failure record and controlled native-worker recovery.
It does not establish that the original connection/resource interruption is
fixed or that long vehicle sessions now pass.

- At most three replacements per reader lifetime, after confirmed worker exit,
  with 1/2/4-second delays. Unconfirmed exit or exhausted budget stops recovery.
- Guidance stays inactive until a new mailbox baseline and fresh event arrive.
- The first worker failure retains numeric timing, phase, errno and child status.
- The normal release transaction installs/restores the reader alongside guidance;
  there is no separate reader-test installation step.
- Preserves the v1.4.3 P4521 gates, U-turn lane fix, runtime defaults and optional
  turn-card tuning. Java, audio, driver and video runtime bytes match v1.4.3.

Use the normal **Install / update CarPlay integration (reboot)** action.
Integrated v1.4.1, v1.4.2, v1.4.3 and known v3 revisions use the existing checked
retirement/reboot/install boundary, preserving original snapshots. If the older
standalone reader test was installed, restore it first using its saved controller
and reboot. Separate older P4521 bundles use the documented OEM reset first.

The user later confirmed v1.4.3-e working in a vehicle; a 2 h 30 min drive with
active guidance recorded two worker replacements.
