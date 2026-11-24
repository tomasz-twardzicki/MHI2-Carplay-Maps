# Wireless main-screen driving side — November 18, 2026

The user reports that wired CarPlay puts the menu on the expected side in an
RHD vehicle, while wireless uses the LHD layout. This is a main-screen metadata
issue; the AID alternate-display probe remains a separate test.

## OEM contract and receiver support

Freshly audited MU1367 stock class
`de.vw.mib.asl.internal.carplay.target.ASLHandler.sendStartService()` reads
`ServiceManager.configManagerDiag.getDriverSide()`. It passes
`useRightHandDrive=true` in the OEM CarPlay `ServiceConfiguration` when that
value is **2**. Unknown coding must not be treated as a confirmed driving side.

The pinned wireless receiver reads its config from `WCP_DATA/airplay.conf`
(normally `/mnt/persist/wcp/airplay.conf`). Its `/info` builder first looks for
`rightHandDrive` in the parsed config dictionary and includes that value when
present. A canonical Boolean `true` represents RHD; `false` represents LHD.
Setting an unsupported `WCP_RHD` environment variable would not implement this.

`RHD-VERIFICATION.json` records passing QNX checks using the **unchanged exact
receiver's CF parser and dictionary lookup**: RHD true, LHD false and RHD with
an unrelated config property. The XML plist attempt was rejected by that parser;
the binary plist cases pass. The test exits before receiver main, without
starting radio, MFi, video or MOST services. No RHD vehicle result is claimed.

## Prepared config change

[`prepare-drive-side.py`](prepare-drive-side.py) prepares a binary plist on the
host. `--input` preserves other existing plist properties; `--new` is explicit
and must only be used for a confirmed absent config. Unknown formats or a
non-dictionary root are rejected. Existing output files are never overwritten.

```sh
python3 MU1367/wireless-native/prepare-drive-side.py \
  --driver-side 2 --new --output /path/to/new-rhd-airplay.conf
```

For an existing per-unit plist, replace `--new` with
`--input /path/to/this-units-airplay.conf`. Do not copy another unit's receiver
config or pairing data. Do not replace an existing config with the minimal
preview file.

This is prepared config generation, **not an installed automatic fix**. Before
shipping automatic application, the wireless integration must forward the OEM
coding, merge the unit's existing config, snapshot its previous bytes/mode or
absence, and cover it in removal/recovery. The receiver reads the config when
its server is created, so application also needs a controlled receiver restart.
The current AID-probe SD package is unchanged while that vehicle test proceeds.
