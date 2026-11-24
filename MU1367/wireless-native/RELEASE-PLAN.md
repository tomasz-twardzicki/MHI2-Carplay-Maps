# MU1367 v1.6.0-e wireless integration and acceptance

Reviewed November 17, 2026. Target: **K4525/P4521 MU1367 + AID 791**, retaining
v1.5.3 features. AID 790 is a separate port/acceptance target.

## Test1 implementation boundary

An additive `v1.6.0-e-test1` candidate is implemented for first connection/video
testing. Its [instructions](TEST-PACKAGE.md) are the current installation and
recovery contract. It packages the 15 phone classes separately, retains the
v1.5.3 DIO wrapper and bridge, extends the existing supervisor with an accepted
wireless-session predicate, merges the native configs/bootstrap, preserves
active NAT policy and adds a checked 35-target snapshot transaction. Green Menu
provides enable, remove, recovery and status controls; existing base-action
wrappers require wireless removal first. Older SD packages cannot enforce that
order. A direct OEM reset while wireless is installed remains unsupported.

P4521 variants 50/70 now match the checked K4525 JXE, btstack,
connectionmanager and production-config inputs; see
[the bounded comparison](P4521-COMPATIBILITY.json). This does not replace
P4521 library or vehicle acceptance. The candidate asks for wireless 30 fps and
keeps the saved wired settings; wireless FPS tuning is pending.

Wireless guidance/media/artwork events and the native settings switch remain
required for full feature parity. No real-phone wireless result is claimed.
The original implementation/acceptance checklist below describes the broader
release target; test1 completes only its connection/video slice.

## Receiver licence conclusion

The earlier V3.0 notes overstate the remaining licence problem for the current
public payload. Reviewed upstream revision:
[`76ed060794b2f5ded1d5fb148b7c99980bcd4045`](https://github.com/omonob/VW-MHI2-Wireless-Carplay-Maps/tree/76ed060794b2f5ded1d5fb148b7c99980bcd4045),
labelled V3.1 experimental. Findings apply to its **AID12.3** receiver only.

- `wcp_receiver` SHA-256: `f195665b0e9fb8a592618e64b7201ddfc536a9b082c6dd35db214b99d5e01de1`.
- Its former startup licence-call site at virtual address `0xe1ca8` contains
  `mov r0, #0`, followed by the existing error-check sequence. It supplies
  success instead of invoking the retained checker.
- The old licence-wait/check helper at `0xec348` remains, as do
  `CPM-LICENSE 1`, `CPM_LICENSE_FILE`, `CPM_FAZIT_OVERRIDE`,
  `/mnt/persist/carplay_mirror.lic` and failure strings. The audit finds no
  direct ARM B/BL branches to that helper in executable LOAD segments.
  This is a bounded static check, not proof of all possible indirect execution.
- The retained wait helper explicitly clears licence/identity overrides before
  checking. Environment-variable spoofing is not a solution for older gated
  binaries. Do not transfer assumptions to another receiver hash.
- The shipped [`btstack_wrap.sh`](https://github.com/omonob/VW-MHI2-Wireless-Carplay-Maps/blob/76ed060794b2f5ded1d5fb148b7c99980bcd4045/standalone/SD_ROOT/carplay/payload/wireless/common/ota/btstack_wrap.sh)
  and `wcp_autostart.sh` also describe application binding as omitted.

**Follow upstream by using this reviewed receiver and its matched loader/library
set.** There is no additional per-car licence-generation task for this startup
path. Do not infer that successful loading, Apple authentication or a wireless
session has been demonstrated.

`wireless-receiver-exec` embeds and checks the hashes of:

1. `/dev/shmem/wcp_receiver`;
2. `/mnt/app/carplaymaps/libomonob-wireless-maps.so`;
3. `/mnt/app/carplaymaps/libv75-transport.so`.

The controller must stage the receiver in the first location before launcher
verification. The receiver imports `v75gen`, supplied by the companion maps
library; copying the receiver alone is insufficient. The launcher checks its
inputs, rejects a nonempty inherited preload on its normal execution path,
creates a scoped runtime directory and supplies the intended preloads itself.
Changing a binary, library or installation path requires revisiting this
contract. The shipped `--verify-only` path can check installed inputs without
starting the receiver; it does not establish authentication or playback.

Application licence handling and **MFi authentication are separate**. The
receiver and Bluetooth shim still reference `/dev/i2c8`. Confirm the actual
coprocessor transaction, certificate/challenge response and phone acceptance.
Device-node existence alone is insufficient; `nomfi` bench mode cannot establish
real-phone acceptance. Reuse and attribution permission recorded in
`FEASIBILITY.md` remains distinct from those runtime mechanisms.

## Establish the right baseline

This checkout's integration README still identifies v1.4.3-e. The actual stable
v1.5.3 source is in sibling `MHI2-Carplay-Maps-aa`, commit `1006274`.
The published ZIP's SHA-256 is
`011d37a7206739d77843f96e5446078d2175e4cbc12fc8702d1842c4035665d8`.
Use the v1.5.3 source/manifests for implementation; leave existing local work
and recovery artifacts intact when establishing the development branch.

Preserve K4525 and P4521 exact gates, the v1.5.3 intro-IDR race fix, bridge
priority 14, wired 40 fps / IDR 5, reader recovery, compressed artwork,
Android Auto and saved-snapshot behavior. Full wireless support includes the
existing cluster and information features, not just the main-screen session.

The repeatable [input/licence audit](audit-upstream.py) verifies 12 pinned upstream files,
the published ZIP, launcher hash references, the startup site and direct ARM
branches. It also scans all v1.5.3 JARs for wireless package collisions and
confirms the 15 `org/omonob/phone` classes in the selected upstream menu.
It does not itself compare target firmware. The subsequent direct K4525
[firmware verification](FIRMWARE-VERIFICATION.json) covers both hardware
variants, the 13 Bluetooth signatures, 559 native import checks, V3.1's HMI
member/touch contracts, and passing QNX configuration and receiver/J9 loading.
It establishes the recorded contracts, not private ABI semantics, hardware
behavior or a complete integrated release.

## Full-release implementation checklist

| Area | Required change or decision |
| --- | --- |
| HMI payload | K4525 member/touch comparisons and factory-J9 loading now pass. Package the 15 phone classes separately; retain our menu and guidance/audio patches. Confirm integrated bootstrap start order, touch behavior and no shadowing of unrelated classes. Recheck if payloads change. |
| Wireless switch | Add a functioning control to v1.5.3. Tuning now uses the former wireless row for Startup animation; preserve that row and its saved value. Translate the new setting to upstream's enable/off/autostart contract, including immediate disable and next-boot behavior. |
| Process startup | Extend the existing `dio_manager` wrapper with required hooks and use one supervisor/cluster writer. Keep preloads scoped to Bluetooth, receiver and video processes respectively. Do not replace the wrapper wholesale. |
| Native configuration | Merge the unique executable btstack entry while preserving the same-named settings object. Merge SI and bundles idempotently. V3.1 preserves stock MU1367 `connectionmanager`; test this before considering the old 20 MHz proposal. Independently fingerprint P4521's native binaries/configuration. |
| Network | Check actual AP channel versus advertised channel, DHCP and listeners. Handle connection-manager firewall reloads and preserve the active uplink/NAT policy. Upstream autostart unconditionally loads `pf.mlan0.conf`; justify or adapt that bench assumption before reuse. |
| Wireless cluster input | Connect accepted wireless session/video to our ring/ready/IDR protocol and transport ownership. Upstream uses alternate feed port 9997 and its own `wireless-entry`; resolve that contract against our bridge instead of running two cluster pipelines. |
| Display and performance | Upstream requests wireless 30 fps and 800×480 for 791, while v1.5.3 wired defaults to 40 fps. Make negotiation, bridge timing and settings truthful per transport. Preserve our safe-area, startup clip and fresh-IDR handoff. Confirm primary-screen geometry separately. |
| Guidance/audio/artwork | Port events from the wireless receiver/session into our existing readers/publishers. Current wired iAP2 hooks are not automatically a wireless source. Match session ownership, timestamps and expiry; reconnect subscriptions and reopen replaced inputs. |
| Recovery | Extend the existing checked transaction and OEM reset to all modified app/system/OTA/persist paths, bundles, wrappers and flags. Preserve first snapshots, file modes, missing-file receipts and per-unit pairing data. Wireless removal must restore working v1.5.3 wired operation. |
| Packaging | Generate a new manifest, source/provenance records and notices from the selected inputs. Upstream's standalone installer has different ownership/recovery rules and cannot be installed over v1.5.3 unchanged. |

## Offline and QNX checks before vehicle installation

The narrow receiver/input audit is recorded in `RECEIVER-AUDIT.json`.
`FIRMWARE-VERIFICATION.json` additionally records passing K4525 native/HMI
contracts, receiver `--verify-only`/version loading, four idempotent production
config/launcher/bundle transformations under factory QNX utilities, and loading
23 classes with factory J9 verification. The complete integrated checks below
remain pending; use these completed checks as the starting evidence. P4521 was
not included in that new run.

1. Reproduce v1.5.3 baseline payloads and run its existing tests, then run the
   new build/package and regression checks. Reject unknown firmware, binaries,
   conflicting classes, duplicate launch entries and wrong cluster profiles.
2. Audit every new command **and option** against matching firmware or captured
   live-unit availability. Upstream's transaction requires `rmdir`, absent on
   the documented v1.5.3 unit; do not import that installer as-is. Test using
   firmware-extracted QNX shell/utilities, including default aliases such as
   `hash`, real `ls`/`awk` output and production JSON. A Linux shell or augmented
   SDK image is insufficient evidence of target compatibility.
3. Resolve ELF imports/versions and loader/preload scope against MU1367 factory
   libraries. Exercise normal startup and `--verify-only`, missing or modified
   receiver/libraries, nonempty inherited preload, stale PID reuse, repeated
   autostart and disabled/missing AP. Confirm one receiver, video service,
   supervisor and intended watchers, with bounded waits and restored stock BT.
4. Test configuration transformations on actual K4525 and P4521 inputs twice.
   Check bundle slot allocation, exact launch-entry selection and unrelated
   settings preservation. Reject malformed/ambiguous input before writes.
5. Exercise real v1.5.3 install → wireless upgrade → repeat install → uninstall
   → reinstall → recovery/OEM reset. Also cover earlier supported upgrades,
   retained snapshots, insufficient space, symlink/unknown modifications and
   injected interruption at each commit step. Verify restored bytes, modes,
   absence markers and two-stage/reboot transitions.
6. Test the wireless input adapter with captured/synthetic session edges and
   video/data: accepted versus discovered phone, detach/reconnect, late packets,
   replaced ring/FIFO, IDR timing, clip completion, stale reader expiry, and
   mirrored/card/map transitions. Run the wired and Android Auto regressions.
   These tests establish adapter behavior, not radio/MFi acceptance.

## Vehicle acceptance, in order

Record firmware/native hashes, cluster, iPhone model/iOS, negotiated geometry
and fps, result and logs for each run. Begin with one phone, then extend the
matrix; do not assume upstream's retained 17 Pro Max profile covers all phones.

| Stage | Test and acceptance evidence |
| --- | --- |
| 1. Cold boot and disabled mode | Factory Bluetooth, calls, WLAN, wired CarPlay and Android Auto still work; no preload leakage or repeated service spawning. Wireless off remains off across boot. |
| 2. Receiver startup/authentication | Correct staged hashes; receiver listens without a per-car application licence; actual MFi challenge succeeds. A live PID or licence log alone is insufficient. |
| 3. First wireless connection | USB unplugged; enable wireless/hotspot, pair Bluetooth and approve CarPlay. Test automatic Wi-Fi association through the CarPlay credential exchange before any manual join. Observe association, DHCP, current channel and accepted session in order. Capture failed handoff logs; record manual joining only as a diagnostic fallback. Test with no external uplink as well as the normal uplink. |
| 4. Main-screen CarPlay | Stable video, touch and controls, audio, volume, calls/microphone and Siri; correct HMI entry/exit, reverse-camera takeover and return. No invisible menu touch-through after disconnect. |
| 5. Cluster and information | Map-only navigation and existing turn cards/lanes/road names, steering-wheel zoom, media text/artwork; mirroring → map returns on a fresh IDR. Check Startup animation Off/Once/Every and manual disconnect without automatic takeover. |
| 6. Transport and phone changes | Wireless → USB → wireless, wireless → Android Auto → wireless, Bluetooth-only use, second paired phone, out-of-range/re-entry and phone reboot. Exactly one accepted owner; no stale frames, data or MOST writer. |
| 7. Radio recovery | Hotspot toggle, delayed AP, channel movement and native firewall reload. Service recovers within a measured bound without modifying another network's credentials or requiring reinstallation. |
| 8. Endurance and vehicle lifecycle | Suggested minimum: 2-hour mixed route/media run, repeated reverse-camera use, at least 10 reconnect cycles and multiple genuine ignition/sleep/wake cycles. Record CPU/RAM/temperature, bounded logs and failure/recovery evidence. These are proposed release criteria, not completed results. |
| 9. Rollback | Remove wireless, full reboot, verify v1.5.3 wired features and factory BT/WLAN. Exercise OEM reset with the new files/flags covered and verify pairing-data policy. |

Upstream's [connection instructions](https://github.com/omonob/VW-MHI2-Wireless-Carplay-Maps/blob/76ed060794b2f5ded1d5fb148b7c99980bcd4045/docs/WIRELESS_CONNECTION.zh-CN_EN.md)
prescribe manual Bluetooth pairing and Wi-Fi joining for first use. However,
the pinned `btstack_wrap.sh` documents live credential exchange from
`/tmp/uaputl.cfg` in `0x4301`/`0x5703`, and autostart's channel watcher explicitly
aims to prevent failed phone association after that exchange. Our test therefore
tries automatic joining first and records manual joining as a diagnostic
fallback; automatic handoff and reconnection remain vehicle acceptance items. Its
[validation record](https://github.com/omonob/VW-MHI2-Wireless-Carplay-Maps/blob/76ed060794b2f5ded1d5fb148b7c99980bcd4045/docs/WIRELESS_VALIDATION.zh-CN.md)
still distinguishes MU1367 offline adaptation from hardware acceptance.

`v1.6.0-e` can remain explicitly experimental, but publish only after installer
recovery and a recorded end-to-end test on the stated target. Report untested
firmware/phone combinations and any missing wireless information features
explicitly. The initial review performed no release installation or vehicle
test. Subsequent local test-package work records its exact checks in each
candidate's `WIRELESS-VERIFICATION.json`; vehicle acceptance remains pending.
