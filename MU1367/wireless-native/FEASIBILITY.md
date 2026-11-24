> **Stable v1.6.1:** [current release](stable/README.md) and [install/update/restore guide](stable/START_HERE.md). The test2 runtime was confirmed working by the maintainer on 2026-11-19 and is promoted unchanged. Earlier audit and experimental history remains below.



# MU1367 wireless CarPlay — offline feasibility

**November 17 follow-up:** the original V3.0 comparison below is historical.
The pinned V3.1 payload has now also been checked directly against the supplied
**K4525 MU1367 firmware**, including both hardware variants (50/70), rather than
relying on an upstream firmware label. The pinned 791 receiver already
omits its startup application-licence call; no licence generator is needed for
that exact binary. Its launcher and companion libraries must stay matched.
See [the receiver audit and release plan](RELEASE-PLAN.md) and
[`UPSTREAM.json`](UPSTREAM.json). This is an offline/emulated conclusion, not
an on-car connection result.

**Test candidate:** the additive `v1.6.0-e-test1` implementation now targets
connection and main-screen/cluster video over the exact v1.5.3 package. See
[test-package instructions](TEST-PACKAGE.md) and the [implementation status](README.md).
Wireless guidance/media/artwork and the native settings switch remain pending;
the original feasibility checklist below is not a claim that those features
have been implemented. Limited P4521 input checks are recorded separately in
[`P4521-COMPATIBILITY.json`](P4521-COMPATIBILITY.json).

## Direct V3.1 verification against K4525

Evidence: [`FIRMWARE-VERIFICATION.json`](FIRMWARE-VERIFICATION.json). Inputs came
from `/Users/tomasz/Documents/github/personal/MHI2_ER_VWG13_K4525_1_AIO_MU1367_20230318`,
not a different-MU firmware or an upstream acceptance claim.

- Freshly extracted JXE is size 55,840,541, SHA-256 `09167f1d…`, on both variants.
  The existing 26,291-class conversion was checked against the pinned MU1367
  entry-name/content digest `37bb839f…`; conversion itself was not rerun.
- Stock `btstack` is `dd80ce8f…`, and stock `connectionmanager` is `61069e02…`,
  on both variants. They match V3.1's exact MU1367 native-baseline entries.
  All **13** instruction-signature probes in `libbtwcp` profile `0x1c79` match
  this `btstack`. No connection-manager binary was replaced or patched.
- Across the four wireless JARs and 15 phone-support classes, all **23 classes**
  target Java major 46. All **36 unique OEM field/method references used by
  instructions** resolve through MU1367's hierarchy with exact descriptors.
  This counting method differs from the original constant-pool reference count.
- The V3.1 touch replacement still has MU1367's superclass/interfaces/access,
  10 matching fields and 19 matching methods. Seventeen method instruction
  bodies are identical; two preserve the complete stock body after their
  prepended hooks. Only synthetic access flags differ on three helper members.
- **12** selected wireless ELF payloads pass **559 strong-import checks** against
  the factory libraries and intended companion preloads, with no missing strong
  imports or required socket version names. All eight checked NvSS/KD decoder
  entry points exist in the firmware's libraries. This does not validate their
  hardware behavior or every private/native ABI assumption.
- Production configs were read through the F3S extent/directory structures,
  including variant 70's different alignment. Relevant config contents match
  between 50 and 70. In an isolated QNX ARM VM, the shipped config helper and
  launcher/bundle merger were run twice using the factory shell/awk/utilities:
  all **four transformations are idempotent**. The Bluetooth transform changes
  only the executable entry, preserving the same-named settings object. The
  stock SI transform is semantically unchanged; the bootstrap uses bundle 97.
- In that VM, the matched receiver launcher passes `--verify-only`, and the
  receiver's `--version` command loads successfully with K4525 libc/socket/math
  and the matched companion preloads. Factory J9, with `-verify` and the exact
  MU1367 JXE, loads all **23 classes** and reflects their declared members.

The emulator uses a virtual-machine kernel, not MU1367's Tegra kernel. The full
receiver service was not started. These results establish the checked K4525
binary/class/configuration contracts; they do **not** demonstrate MFi hardware,
radio association, decoding/display, audio/input, SI session acceptance, or
integration with v1.5.3's runtime and installers. P4521 remains a separate check.
The stock `check_auth_chip.sh` targets `/dev/i2c8` at address `0x11`, but the
coprocessor's presence and challenge response still require a car.

## Original V3.0 comparison

Reviewed November 16–17, 2026, against the full OEM firmware
`MHI2_ER_VWG13_K4525_1_AIO_MU1367_20230318` and the published
CarPlay Maps v1.5.3 release. Upstream reference:
[`omonob/VW-MHI2-Wireless-Carplay-Maps`](https://github.com/omonob/VW-MHI2-Wireless-Carplay-Maps)
(Wireless CarPlay Maps V3.0), whose native wireless path is documented upstream
as MU1102-only.

omonob agreed (2026-11-16) that we may reuse and modify their wireless
receiver and stack for an MU1367 port. This removed the redistribution blocker.
That permission alone did not establish how the receiver's licence path behaved.
The subsequent pinned-binary audit resolves the startup-site question as
described above; MFi hardware authentication still requires vehicle testing.

This document records what the offline comparison established. No firmware bytes,
extracted OEM files, or converted class archives are committed; the extraction
scripts stay outside Git the same way `MU1367/port` keeps them.

## Scope and method

The menu-software (`lsd.jxe`) side was compared class by class. MU1367's
`lsd.jxe` (size 55840541, sha `09167f1d…`, our build baseline) was converted to
a JAR with the pinned `jxe2jar` (`9eeb45bbf14bf8afe3452c7be96a4d1f0206a286`),
producing 26,291 classes (conversion rc=0). Each wireless class upstream ships
was then compared against the matching MU1367 class by parsed bytecode with exact
field/method descriptors. The receiver and Wi-Fi/Bluetooth plumbing were compared
at the binary level only (ELF `NEEDED`, instruction-signature probes, config
entries); their runtime behaviour cannot be verified offline.

## What the HMI side needs — and that it is portable

### TouchInputDeviceImpl (full class replacement)

Upstream fully replaces `system/input/TouchInputDeviceImpl`. Against MU1367 stock:

- same superclass (`AbstractInputDevice`), same interfaces, same access;
- same 10 fields and same 19 method descriptors;
- 17 of 19 methods are bytecode-identical;
- the 2 that differ only **prepend** a hook, then run MU1367's original body:
  - `createKeyPanelListener()` adds `CpWcpTouch.attach(this)`;
  - `updateTouchInput(IIIIIII)` adds `if (CpWcpTouch.onTouch(IIII)) return;`;
- the only other delta is `ACC_SYNTHETIC` on 3 helper members (a compiler
  artefact, no behavioural effect).

The MU1367 stock body is therefore compatible; the replacement is MU1367's own
class plus two prepended calls.

### Wireless JAR references all resolve

Across the 4 wireless JARs (CP, SI, Touch, Boot), all 38 external OEM member
references resolve through the MU1367 class hierarchy with exact descriptors and
0 missing.

### One extra package must ship separately

The JARs reference `org/omonob/phone/*`
(`PhoneConnectionRuntime`, `PhoneSelectionPolicy`, `TransportLease`,
`WirelessClusterGrant`, and others). These live in upstream's **MU1102**
`VCMenu.jar`, not in the wireless JARs, and MU1367 lacks them. Their closure is
15 classes (`OwnedDataNotice`+inner, `PhoneConnectionRuntime`+inner,
`PhoneConnectionSettings`+`$State`, `PhoneSelectionPolicy`, `QuietNoticeSelection`,
`TransportLease`, `WirelessClusterGrant`); all 32 of their OEM references resolve
against MU1367 with 0 missing, and they need nothing else from the MU1102 menu.
They must be shipped in a **separate** JAR for MU1367, so our `VCMenu.jar` is
unchanged.

### No collisions with v1.5.3

The pinned published v1.5.3 ZIP (checksum verified) was re-scanned by the
November 17 audit. None of its 43 JARs
define `org/omonob/phone/*`, `wcp*`, `org/omonob/cpmap/wireless/*`, or anything
under `system/input`.

### Launcher and bundle merge preconditions met

- Stock MU1367 `lsd.sh`: one `$J9` launch line, the form the merge expects; no
  `-Xbootclasspath/p:` line yet.
- `bundles.properties`: one `Bundle.Startup.Lateload` line (`61,62,95`); slot 97
  is free.
- With v1.5.3 installed, our installers use the same single
  `BOOTCLASSPATH="$BOOTCLASSPATH -Xbootclasspath/p:…"` convention. The upstream
  merge prepends its JARs and keeps ours in order, so the two are compatible. The
  appended `start-wireless-maps.sh` block after the `$J9` line is the one item
  our `control.sh` layout checks must be taught to allow.

## Binary-level findings (receiver / radio plumbing)

Compared at the binary level only; not runtime-verified:

- btstack matches the `libbtwcp` profile `0x1c79` on all 13 instruction-signature
  probes; the LD_PRELOAD wrap is structurally applicable.
- `connectionmanager` differs only by `HTCapInfo 0x116e → 0x12c` (20 MHz). Plan:
  originally patch MU1367's own binary rather than ship upstream's. **Superseded
  for the V3.1 starting point:** upstream now preserves MU1367's stock binary.
  Test the stock path first; a 20 MHz change needs separate evidence.
- `connectivity.json` and `smartphone_integrator.json` contain exactly the
  entries upstream's `config-patch` edits.
- `libnvss_video`, `libKD`, `libnvaudio`, `dmdt`, `pfctl`, `uaputl`, `wpa` are
  all present. Hotspot is 2.4 GHz, `ChanList=1,6,11`, on both platforms.

## Open blockers

1. **Matched receiver integration, not licence generation.** The pinned V3.1
   `wcp_receiver` retains FAZIT checker code/data but its former startup call
   supplies success. The launcher checks the receiver and two companion-library
   hashes. Package that reviewed set and verify loading/listening on QNX.
2. **On-car checks only a vehicle can confirm:** Apple authentication coprocessor
   usable on `/dev/i2c8`; hotspot and firewall reachable with stock MU1367
   `connectionmanager`; MU1367's `smartphone_integrator` accepting the wireless
   session (no MU1102 binary available to compare against offline).
3. **v1.5.3 integration conflicts:** both projects take over the `dio_manager`
   launch; `control.sh` layout checks vs. the appended `start-wireless-maps.sh`
   block; and our cluster / guidance / artwork features would not follow a
   wireless session without additional work.
4. **Actual v1.5.3 source baseline.** This worktree's integration is older;
   v1.5.3 is in the sibling `MHI2-Carplay-Maps-aa` worktree at `1006274`.
   Its tuning menu replaces the old wireless test row with Startup animation.
   Build from that baseline and preserve the setting, the 40 fps wired default,
   priority 14 bridges, compressed artwork and Android Auto layer. Re-run
   comparison checks when the selected inputs change. The direct K4525 checks
   above now cover the reviewed V3.1 inputs; integrated build/install/runtime
   tests and P4521 checks remain pending.

## Verdict

The HMI side is fully portable to MU1367: the touch replacement is MU1367's own
class plus two prepended hooks, every wireless JAR reference resolves, the extra
`org/omonob/phone/*` closure resolves cleanly as a separate JAR, there are no
collisions with v1.5.3, and the launcher/bundle merge preconditions hold.

## Attribution

Any MU1367 wireless release must credit omonob and the upstream provenance they
list, and retain the receiver/stack licences and notices, consistent with
`MU1367/integration/NOTICE.md`.
