# MU1427 / AID 791 CarPlay now-playing research

Started 2026-10-19 on `feature/mu1427-aid791-carplay-now-playing`, after
reading [project status](../../PROJECT-STATUS.md) and its navigation release,
installation, results and implementation references.

The intended feature is **the current CarPlay title, artist and album cover
in the native AID 791 audio display**, including when CarPlay navigation is
not running. Album text is also available at the input. A custom overlay on
the map stream is a separate feature.

**Current output baseline: N1 native text test, accepted in A1.** It uses the input
demonstrated by N0 to fill title, artist and album in the factory audio BAP
stage. The user reports correct, immediate text updates, normal controls and
source switching, and normal Google Maps/HMI/native guidance. See
[A1 results](./A1-RESULTS.md) and [verification](./A1-VERIFICATION.json),
including the corrected interpretation of the `rejected` counter. Cluster cover
output remains unimplemented. Follow [N1 installation/test/recovery](./TEST-N1.md), including
**removing N0 and fully rebooting before N1 installation**.

The earlier [N0 observation procedure](./TEST-N0.md) and its package remain
historical evidence. Both test packages have install, status, bounded export
and saved no-SD removal. Published navigation payloads remain unchanged.

**N2 native artwork input confirmed in A2.** A separate full toolbox
adds native transfer/signature counters while retaining the accepted N1 JAR
and configuration. It replaces B4 with its observed extension and restores
B4 on removal; it does not yet display or export pictures. Follow
[N2 installation, export and recovery](./TEST-N2.md) and see
[N2 verification](./N2-VERIFICATION.json). [A2 results](./A2-RESULTS.md) show
seven completed JPEG-signature transfers across two native allocation
instances, with zero diagnostic faults. The user confirmed both
Apple Music and Spotify with no observed HMI, CarPlay text, maps or guidance
issues during A2. Individual exports are not mapped to apps or test steps.
Remove N2 before changing/removing native guidance or using general factory restore.

**Next unit test: N3 owned image capture and decoding.** The
[full N3 toolbox](./build-N3-unit-package/CarPlay_Maps_VC_MU1427_Audio_N3_Test.zip)
copies complete native artwork into bounded owned memory, then exports its
original bytes and a 256×256 PNG using one supervised child. It preserves the
accepted N1 text JAR and leaves cluster cover output for a subsequent stage.
See [N3 procedure and recovery](./TEST-N3.md),
[implementation](./n3/README.md) and [verification](./N3-VERIFICATION.json).
**Remove N2 and fully reboot before installing N3, then fully reboot again.**
Host ARM, sanitizer, installer/package and factory-libc QNX decoder checks
pass; N3 driver loading, live image usability and copy cost still need unit
testing. Exports now contain album images and original embedded metadata.
Track/text matching and Volkswagen picture-request identities remain open.

**A0 on-unit result:** Apple Music and Spotify were tested with no issues
reported. Valid native track/playback callbacks and reconnect subscription
were observed, with zero reported errors. No cover-art callbacks arrived.
See [A0 results](./A0-RESULTS.md) and [structural verification](./A0-VERIFICATION.json).
The native text input gate is satisfied for this run; artwork needs a
separate native-path investigation.

## Reported hardware baseline

On 2026-10-19 the user confirmed that this AID 791 shows only its label for
CarPlay, while another audio source shows title, artist and cover art. The
specific working source was not identified. This establishes an existing
native text/artwork display path on this car; enabling general cluster
artwork capability is not the first development task.

This is a user-reported OEM baseline, not an N0 test result. CarPlay callback
delivery, image availability and mapping to the active CarPlay source/handle
still need validation. Reuse the working native display path where possible.

## Findings from the exact factory firmware

Input: `MHI2_ER_VWG11_K3342_MU1427`, `ifs/lsd.jxe` = 52,751,492 bytes,
SHA-256 `f46290b4a33b98d957170f6207073ad329316902a87cd4c27da4168548ad911a`.
The [audio contract](./MU1427-AUDIO-CONTRACT.json) records 13 classes'
selected signatures, constants and ROM-method fingerprints. The probe
extracts the original firmware with the navigation project's existing
verified extractor and pinned jxe2jar parser. Firmware bytes remain private.
Semantic findings below also use disassembly of the fingerprinted converted
stock JAR; method hashes alone do not prove those interpretations.

| Layer | Verified static finding | Implication |
| --- | --- | --- |
| CarPlay DSI | `updateNowPlayingData(TrackData,int)`, `updatePlaybackState(PlaybackInfo,int)`, `updatePlayposition(int,int)`, `updateCoverArtUrl(ResourceLocator,int)` exist | Try the native callbacks before adding another iAP2 tap |
| Track data | `title`, `artist`, `album`, `duration`, `genre`, `composer` | Title and artist have a typed input; no raw TLV mapping is needed if delivery works |
| Validity | DSI flags: unknown 0, valid 1, invalid 2 | Non-null data alone cannot establish validity |
| Notification IDs | Now-playing 3, playback 4, play position 5, cover URL 6 | N0 registers these on a separate listener |
| CarPlay HMI | `HsmTarget` constructor sets `DSI_CARPLAY_ATTR` to `[8,7,8,2,9,12]`; none of 3–6 is included. It has no corresponding audio callback methods | Existing callback interfaces are not evidence of a working stock Java consumer |
| Native audio text | MQBAB2 `CurrentStationInfo`, FctID 21, sends literal `Apple CarPlay` for smartphone connection 2 in `setStationInfoForMirrorLink` | A narrow conditional replacement of this fill path is a candidate for text output |
| Audio ownership | `setStationInfoStatus` selects that path for audio component 6 | CarPlay connection alone is insufficient: radio/USB/BT may own audio |
| Text fields | `CurrentStationInfo_Status` has primary/secondary/tertiary BAP strings; stock media uses title 72, artist 73, album 74 | Preserve the stock serializer, encoding and dispatch |
| Cover delivery | `DSIKombiPictureServer.responseCoverArt(long,int,int,int,ResourceLocator)` exists | Cover delivery uses a picture service, independently of text BAP |
| Stock cover gate | `CoverArt._isActiveSourceSupportsCoverArt` accepts source types 6,7,8,10,11,15,16,18,19,20,21,22 | A CarPlay URI cannot simply be assigned to the media cover property |
| Picture identity | Stock `CoverArt` binds pictures to BAP active source and current-station handle; `CurrentStationHandle` (FctID 22) returns invalid handles for audio component 6 | The artwork implementation must establish a valid identity and refresh behavior for the CarPlay source |

Existing [B2 evidence](../route-guidance/B2-RESULTS.md#receive-path-and-lifecycle)
contains eight native `0x5001` now-playing messages before guidance. It
does not establish live track changes, Java callback delivery, or cover-art
transfer. The route reader's `rgi-events` publication only carries guidance;
it is not an audio feed. Playing music must not require an active route.

## External references and limits

The [Audi MHI2Q project](https://github.com/luka-dev/mib2q-carplay-rgi)
includes a native artwork worker and a Java picture bridge. Its
[CoverArt helper](https://github.com/luka-dev/mib2q-carplay-rgi/blob/main/java_patch/com/luka/carplay/coverart/CoverArt.java)
consumes a bus event with a path and image identity. This establishes a
reference architecture, not VW compatibility.

The initial reference was pinned at
`dfafccf6637ad45457085f0977f18cd7f64ab3ed`. The newer
[artwork investigation](./ARTWORK-RESEARCH.md) checks
`71b4ab1c9461d5383a7aa6d56d4dda34f567ade7` and finds unchanged cover sources.
Its
`docs/altscreen-and-video/COVER_ART_PIPELINE.md` describes an MHI2Q unit
where the stock cover URL never delivered useful art. That implementation
reassembles raw iAP2 file transfers, decodes off the receive thread and
publishes an image atomically. This is a fallback to investigate only if
MU1427's native image path fails. Offsets, hooks and image transport from
that different platform cannot be copied directly. Exact MU1427 driver
inspection has since identified its existing artwork transfer buffer and
completion path; observe that before porting the raw-stream fallback.

The user confirmed the **standard sound system** and subsequently removed
5.1 audio from the scope. The [earlier assessment](./AUDIO-5.1-RESEARCH.md)
is historical background; development continues on text/artwork only.

[Audi AU37x MHI2](https://github.com/chefranov/mhi2-au37x-carplay)
also has an artwork implementation. Its README limits tested compatibility
to Audi firmware and states that cluster picture upload/download adaptation
is needed. It does not verify the same adaptation, renderer or cover layout
on a Volkswagen 791. No coding/adaptation change has been made here.

## Implementation sequence and acceptance gates

1. **N0: observe native input.** The recoverable installer and its 17
   host cases cover existing/later JARs, rollback, no-SD removal and exports.
   The factory-J9 checks pass. A0 has now passed on the unit for native text
   input and reported coexistence, but has no artwork callbacks. Run the test package with the existing
   navigation release. Record valid
   title/artist events, playback state and cover-URL/resource-ID availability
   across track changes, app changes and reconnection. N0's counters can
   establish presence but cannot establish the accuracy of the field values
   or readability of a returned image. A follow-up may need an explicitly
   bounded, local private inspection of artwork resources.
2. **N1: title and artist.** Native callbacks arrived in A0. The new test
   adapter adds a bounded in-memory model and a conditional
   `CurrentStationInfo` hook. Read
   both current audio ownership and smartphone connection on the factory ASL
   thread. Refresh the stock stage on accepted changes using the stock
   dispatch/retry path. Test radio/USB/BT handback, disconnect/reconnect,
   Unicode/long/missing text, pause/resume, phone calls and Siri. A paused
   track may retain its metadata while CarPlay owns audio; stopped/invalid
   data needs a defined clear policy. Do not impose navigation's five-second
   source timeout on track metadata: songs can have long gaps between updates.
   A1 accepted the reported text behavior and coexistence. Correct the
   cached-equality/retry distinction before a subsequent Java revision.
3. **N2: native artwork input.** A0 observed no typed cover callbacks.
   The counter-only driver and bounded snapshot helper pass host/QNX checks;
   A2 confirms seven native completed JPEG-signature transfers. Preserve B4
   packet ownership, buffer recycling and the accepted N1 text baseline.
4. **N3: owned image capture/decode.** Implemented with host/QNX checks;
   the first unit test is pending. Copy bounded complete native buffers into
   owned memory before stock completion notification, decode off reception
   and HMI threads, then inspect private original/PNG exports. The test does
   not associate images with N1 text or send them to the cluster.
5. **After N3: track matching and cluster pictures.** The user confirmed
   working OEM title/artist/cover display from another source. Determine the
   actual CarPlay BAP source type, current-station handle and picture-request
   behavior. Establish native-image/text correlation, then implement a narrow
   picture-provider/source gate with explicit no-picture clearing. If a
   native image never arrives, inspect MU1427's native iAP2 file-transfer
   path before designing a new producer; retain B4 packet ownership and
   buffer recycling. Any decoder must be off reception/HMI threads, with
   bounded dimensions, bytes, queue and cache. Reject late images from a
   previous track/session, clear old art on track changes, and use a fresh
   picture identity for refreshes even when a path is reused. The Volkswagen
   picture-provider path remains unimplemented.
6. **Combined release validation.** Verify factory J9 loading, install/remove/failed
   commit recovery, independent audio/navigation lifecycles, map/video and
   native guidance regressions, reboot/autostart and operation beyond five
   minutes on hardware. Only then update the full toolbox, its source
   snapshot and user-facing support claims.

Native text is the first output milestone. Artwork remains a required part
of the intended feature, with separate input and cluster-transport gates.
Neither is claimed accepted by N0. N1 text output passed the reported A1 run;
cluster artwork output remains unimplemented. N3 capture/decode awaits its
first on-unit result.
Playback control and track browsing are
outside the initial title/artist/cover scope.

## N1 text implementation

`n1/java/TextBridge.java` and `TextModel.java` are separate from the tested
N0 listener. An instance per DSI attachment rejects callbacks after detach
or replacement. The model keeps one immutable frame with at most 256 UTF-16
code units per field, rejects control/malformed text and oversized native
values, and clears on invalid/empty/stopped data or phone-connection loss.
Paused playback retains the track; there is no five-second metadata timeout.

The exact stock `CurrentStationInfo` class is fingerprinted, then patched
at its smartphone text fill, init/uninitialize, smartphone connection update
and property-listener return seams. All original stock methods remain.
A factory ASL timer polls at 200 ms and uses `stage.process(-1)` for stock
throttling and dispatch. The tested implementation retries after false
property returns and records the revision actually filled on true returns.
A1 established that cached equality also returns false; this can cause
redundant processing and needs a separate equality/retry decision in the
next revision. The diagnostic names are historical, not delivery guarantees.
The callback never performs BAP or filesystem work. A separate one-second
RAM status writer emits counters only, capped at 4 KiB per atomic file.

The fill hook rechecks both CarPlay connection ordinal 2 and current audio
component 6. Other sources retain stock behavior, and phone track changes
do not trigger refreshes while another audio source owns the display.
Connection loss and DSI teardown clear the frame; reconnect needs new native
text. An expired ASL lease uses the generic label and clears artist/album
until the timer resumes. Title/artist/album use the stock BAP strings and
type ordinals 72/73/74; empty secondary/tertiary fields use type 0.

The two overridden classes and every helper target major 46. N1 cannot
coexist with N0's CarPlay-target replacement. Its installer refuses an N0
JAR, boot reference, or retained RAM status requiring a reboot. The original
N0 ZIP is retained; modified shared packaging/test tooling requires fresh
verification and does not inherit N0's original tool fingerprints.

Build and verify N1 with the same firmware/Java/ASM/QNX inputs as N0:

```sh
python3 MU1427/now-playing/build-text.py \
  --java-home "$RG_JAVA" --stock-jar "$RG_STOCK_JAR" --jxe "$RG_JXE" \
  --asm-dir "$RG_REFERENCE/toolchain/java" \
  --output MU1427/now-playing/build-N1-hmi
python3 MU1427/now-playing/test-observer-qnx.py MU1427/now-playing/build-N1-hmi \
  --stage2 "$RG_STAGE2_IFS" --firmware "$RG_FIRMWARE" \
  --java-home "$RG_JAVA" --stock-jar "$RG_STOCK_JAR" \
  --toolchain "$RG_QNX_TOOLCHAIN" \
  --setup MU1427/route-guidance/build-C4-qnx-check \
  --output MU1427/now-playing/build-N1-qnx
python3 MU1427/now-playing/test-controls.py MU1427/now-playing/build-N1-hmi \
  --phase N1 --output MU1427/now-playing/build-N1-controls.json
python3 MU1427/now-playing/build-test-package.py --phase N1 \
  --hmi MU1427/now-playing/build-N1-hmi \
  --qnx-result MU1427/now-playing/build-N1-qnx/result.json \
  --controls-result MU1427/now-playing/build-N1-controls.json \
  --output MU1427/now-playing/build-N1-package
python3 MU1427/now-playing/test-package.py \
  MU1427/now-playing/build-N1-package/CarPlay_Maps_VC_MU1427_Audio_N1_Test.zip \
  --output MU1427/now-playing/build-N1-package/package-verification.json
```

See [N1 verification](./N1-VERIFICATION.json) for matching build/check records.
Factory J9 checks exercise loading and text mapping; A1 supplies the separate
on-unit text-display/coexistence result. Native artwork reception is the
next hardware boundary. Keep the tested N1 package unchanged as the baseline.

## N0 implementation and checks

`java/NowPlayingObserver.java` implements the exact factory listener. A
surgical patch attaches it at the end of `HsmTarget.initializeDSI()` and
detaches it at entry to `deInitializeDSI()`. The stock listener and its
notification list remain intact. Both injected hooks catch helper/linking
failures so they can return to the stock method. No audio BAP stage,
picture-server stage, iAP2 driver, media source, map or playback command is
changed by this prototype.

Diagnostics start before the subscription call, so a registration failure
can be reported as `attached=0 attach_failures>0` in the RAM status.
Callbacks count only validity and nonempty title/artist/album/cover fields.
They retain no text, image path, device identity or image bytes. Counters
reset on service attachment, **not necessarily on each physical phone
reconnection**; the ASL service may survive a reconnect. Late callbacks to a
detached observer are ignored. N1 must add explicit phone-session ownership.

One daemon thread writes `/ramdisk/carplay-now-playing-n0.status` once per
second through a regular `.new` file and rename. Each file is capped at
4,096 bytes, for at most 8 KiB combined, with no append log or automatic SD
capture. Callback locks are released before file I/O. `writes` shows writer
activity; it does not prove phone connection or metadata freshness.
`cover_urls` reports only nonempty locators, not that an image is readable.

The builder verifies the exact JXE and the full converted-JAR content hash,
compiles helpers against factory CDC classes and emits **major 46 for every
installed class**. Host tools/tests are excluded from the installed JAR.
It rejects invokedynamic, class-literal LDCs, StringBuilder and java.nio
calls in installed helpers. Host tests cover validity/null cases, empty
fields, paused/playing/invalid playback, privacy, bounded status,
idempotent attachment, replacement, late callbacks and registration/removal
failures. See [N0 verification](./N0-VERIFICATION.json) for recorded evidence.

Reproduce from the repository root (the Java/ASM inputs are the same pinned
tools used for native guidance):

```sh
python3 MU1427/now-playing/probe-factory.py "$RG_FIRMWARE" \
  --jxe2jar "$RG_JXE2JAR" \
  --check MU1427/now-playing/MU1427-AUDIO-CONTRACT.json
python3 MU1427/now-playing/build-observer.py \
  --java-home "$RG_JAVA" --stock-jar "$RG_STOCK_JAR" --jxe "$RG_JXE" \
  --asm-dir "$RG_REFERENCE/toolchain/java" \
  --output MU1427/now-playing/build-N0
python3 MU1427/now-playing/test-observer-qnx.py MU1427/now-playing/build-N0 \
  --stage2 "$RG_STAGE2_IFS" --firmware "$RG_FIRMWARE" \
  --java-home "$RG_JAVA" --stock-jar "$RG_STOCK_JAR" \
  --toolchain "$RG_QNX_TOOLCHAIN" \
  --setup MU1427/route-guidance/build-C4-qnx-check \
  --output MU1427/now-playing/build-N0-qnx
python3 MU1427/now-playing/test-controls.py MU1427/now-playing/build-N0 \
  --output MU1427/now-playing/build-N0-controls.json
python3 MU1427/now-playing/build-test-package.py \
  --hmi MU1427/now-playing/build-N0 \
  --qnx-result MU1427/now-playing/build-N0-qnx/result.json \
  --controls-result MU1427/now-playing/build-N0-controls.json \
  --output MU1427/now-playing/build-N0-package
```

Use new output directories for each run. The QNX output must be inside a
directory shared with the existing Docker VM; `/private/tmp` is not shared
by the current profile. The QNX check uses the exact factory J9/JXE/libc,
both `-noverify` and `-verify`, a deliberately major-49 negative control,
and actual atomic RAM status-file writes. This still does not execute full
HMI startup, target notification dispatch or physical cluster delivery.
The builder's manifest initially marks QNX unverified; the separate QNX
result must match its JAR hash before claiming that check passed.

The C4 VM fixture can be recreated with the retained native-reader/QNX
tooling described in [the observer reference](../route-guidance/OBSERVER.md).
Generated firmware/classes/builds and private captures remain ignored or
outside Git. The package builder requires matching current sources and
host/controller/QNX evidence, refuses class conflicts in the supplied base
toolbox, and checks every pre-existing bundle file except the appended menu
for byte identity. It writes only to its new output directory. The published
toolbox tree remains untouched. The resulting ZIP is a research test package;
on-unit HMI startup and text callback delivery passed the A0 run. A1 then
accepted the reported N1 text display and coexistence. A2 established native
artwork input; N3 capture/decode now has host/QNX verification with its first
unit result pending. Cluster artwork delivery remains unimplemented.

Baseline project: **omonob (QCDWJ)**. MU1427 feature research/implementation:
**tomasz-twardzicki**. Reference architecture: **LuKa** and the cited Audi
projects. New integration source is GPL-3.0-or-later; third-party firmware
is not relicensed or redistributed by these source files.
