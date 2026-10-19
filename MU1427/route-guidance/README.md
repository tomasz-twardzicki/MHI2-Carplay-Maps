# MU1427 native CarPlay guidance

The released add-on supplies native maneuver arrows and distance on AID/HUD,
plus remaining route distance and travel duration on AID. Phone guidance
controls output; OEM navigation retains priority. The phone-rendered map and
turn card remain available.

[Download and release notes](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/tag/mu1427-native-guidance)
· [Installation, upgrade and recovery](./INSTALL.md)
· [Release verification](./RELEASE-VERIFICATION.json).

The released maneuver mapping, distances and totals passed the D3 unit run.
Automatic startup, continuous operation beyond five minutes and the lowered
turn-card position still need the first full-package check on the unit.
See [D3 results](./D3-RESULTS.md).

## Runtime and recovery

```text
MU1427 iAP2 driver: bounded rgi-events publication
  -> supervised native reader
  -> atomic latest-state RAM mailbox
  -> Java MailboxReader / LiveModel
  -> factory ASL timer and six stock navigation hooks
  -> AID / HUD through stock BAP transport
```

`release/reader.c` keeps device open/read/close operations in a worker with a
1,500 ms deadline. A stuck worker stops the reader. Its RAM files remain
bounded below 70 KiB, with no growing journal, route archive or automatic SD
logging. Java reads the ordinary RAM mailbox, validates complete windows and
requires fresh guidance after attaching or reconnecting. Stop, disconnect,
stale input and ownership loss clear or release phone output.

`release/control.sh` installs the reader, HMI JAR and matched driver/config.
It uses the base toolbox's supported size checks, preserves OEM backups and
unrelated HMI JARs, and saves a controller for no-SD disable/removal. The
original driver-helper name and backup paths remain compatible with B4.
See [INSTALL.md](./INSTALL.md#disable-remove-or-restore) before removal.

## Maintained source and regression checks

| Files | Purpose |
| --- | --- |
| `patch-driver.py`, `patch-publication.py`, `patch-activation.py`, `*.S` | Reproduce and fingerprint the tested driver from exact factory input; the intermediate patches remain build dependencies |
| `bridge/*.java`, `build-live-bridge.py` | Firmware-matched Java adapter, class patcher, loading probes and integration checks |
| `release/reader.c`, `release/control.sh`, `build-observer.py` | Automatic native reader, installer/recovery and pinned QNX build support |
| `rgi_*.py` | Protocol decoder, publication parser and reference guidance models |
| `test-release-*.py`, `test-live-bridge.py`, `test-live-qnx.py` | Release installation/rollback, mailbox/lifecycle and factory Java regression checks |
| Other retained `test-*.py`, `observer/` | Driver/model regressions and native reader/QNX fixtures shared by the release checks |
| `build-release-package.py` | Assemble a new full toolbox after matching runtime, QNX and controller verification |

The committed toolbox is at
[`../../releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4/`](../../releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4/).
The package builder now uses its fingerprinted driver/config/helper directly;
it does not require an old B4 test ZIP. Package checks compare against these
committed files by default; `--baseline` optionally accepts an earlier ZIP.

From the repository root, check the actual committed installer/payload and a
downloaded release ZIP without any phase-package build directories:

```sh
python3 MU1427/route-guidance/test-release-control.py \
  --output /tmp/mu1427-release-controls.json
python3 MU1427/route-guidance/test-release-package.py "$RG_RELEASE_ZIP" \
  --output /tmp/mu1427-release-package.json
```

These checks require `/bin/ksh`; the installer tests deliberately limit PATH
to the base commands supported by the unit. Decoder/model checks use the
Python standard library. ARM patch execution tests also require Unicorn and
pyelftools. Java/QNX checks require the exact firmware inputs, converted
stock classes, Java/ASM tools and pinned QNX toolchain documented in
[LIVE-BRIDGE.md](./LIVE-BRIDGE.md) and [NATIVE-BRIDGE.md](./NATIVE-BRIDGE.md).
Use `build-live-bridge.py --release` for the automatic adapter and
`build-observer.py --source MU1427/route-guidance/release/reader.c --revision release`
for the native reader, with their other required arguments.

Generated builds and raw captures stay outside Git. `RELEASE-VERIFICATION.json`
and the deployed manifest describe the original published v1.0.0 artifact;
they are historical evidence, not a claim that modified tooling has the same
fingerprints. Rebuilds require new verification outputs. The published ZIP
and runtime binaries are unchanged by this source cleanup.

## Historical development

The B1–D3 results, verification records and `TEST-*.md` procedures are retained
as evidence of the firmware work. They are historical and must not replace
the current installation guide. Obsolete phase-package builders, manual
capture/export scripts, shadow/live controllers and their dedicated tests
have been removed from main and the current toolbox source snapshot.
Their original source remains in
[Git history](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/tree/838dd535c23cb8214b170216066e60f8690d2074/MU1427/route-guidance)
and the previously published source snapshot.

- [B1 failure and recovery](./B1-RESULTS.md), [B2 receive fix](./B2-RESULTS.md),
  [B3](./B3-RESULTS.md), [B4 publication](./B4-RESULTS.md).
- [C4 reader](./C4-RESULTS.md), [C4-2 progression/reconnect](./C4-2-RESULTS.md).
- [D1 class-format failure](./D1-RESULTS.md), [D1-r2 correction](./D1-r2-RESULTS.md),
  [D2 native arrows](./D2-RESULTS.md), [D3 distances/totals](./D3-RESULTS.md).
- [Decoder contract](./DECODER.md), [publication format](./PUBLICATION.md),
  [reader development](./OBSERVER.md), [mapping contract](./NATIVE-BRIDGE.md),
  [Java integration and automatic release](./LIVE-BRIDGE.md).

Baseline project: **omonob (QCDWJ)**. MU1427/native guidance:
**tomasz-twardzicki**. Protocol/maneuver adaptations retain LuKa's
GPL-3.0-or-later attribution in the source. Raw navigation captures remain private.
