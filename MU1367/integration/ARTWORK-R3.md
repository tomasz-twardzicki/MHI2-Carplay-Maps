# MU1367 / 791 artwork refresh R3 test

Native audio progress is deferred at the owner's request: OEM Bluetooth and CD
also show no progress on this AID. R3 removes the added progress stage,
advertised capability, DSI transport probes and position subscription. Playback
state remains necessary for clearing stopped tracks; metadata layout is unchanged.

## November 3 evidence

The R2 export `cpmap-diag-4100230` contains four completed covers:

| Cover | Text change to first usable PPS observation | Fetch process | Ready to picture push | Text change to picture push |
| --- | ---: | ---: | ---: | ---: |
| 1 | 52 ms | 199 ms | 112 ms | 364 ms |
| 2 | 799 ms | 194 ms | 35 ms | 1030 ms |
| 3 | 698 ms | 169 ms | 18 ms | 886 ms |
| 4 | 1131 ms | 176 ms | 97 ms | 1405 ms |

The first column is derived from `text_to_ready_ms - pps_to_ready_ms`.
It includes our observation interval and availability/validity of PPS identity,
artwork ID, size and matching track text. It is **not** a direct transfer-duration
measurement. Each successful cover needed one attempt for its observed metadata
identity; there were seven other short misses in the session. The export records
four proactive pushes and no HMI errors. Publication is not proof of when the AID
finished loading or visibly displayed an image.

The existing PNG writer always produced a 196947-byte 256x256 RGB PNG using
uncompressed DEFLATE, even for a small downloaded cover. R3 tries lossless PNG
compression (Sub filter and zlib level 1), keeping the same dimensions, pixels,
orientation handling and black contain padding. K4525 and P4521 contain the same
factory `/proc/boot/libz.so.2`; the installer checks its exact hash. No library
is installed. This removes unnecessary image bytes where compression helps;
its effect on visible vehicle latency is not yet established.

The existing passive driver, strict UID/transfer/session checks, five-second
supervisor, 200 ms polling and eight-image cache remain in use. R3 does not bypass
the wait for usable metadata or infer identity from a title alone. Numeric timing
rows now include `native_read_ms`, `decode_write_ms`, `native_recheck_ms`,
`png_bytes`, `input_bytes`, `input_width` and `input_height`.

## Install and test

Use the complete `CarPlay_Maps_VC_MU1367_791_Artwork_R3_Test.zip`. It uses the
current v1.4.3-e distribution as its package baseline, retaining both K4525 and
experimental P4521 support. **For an existing working installation, refresh the
Toolbox menus and use only the R3 action.** This does not require a base upgrade
or change navigation/reader recovery. Fresh installations must follow the base
installation instructions and reboot before installing this test.

Disconnect CarPlay and the adapter, fully reboot, then select **Install artwork
refresh R3 (reboot)** and fully reboot again. It accepts the original artwork
audio runtime or the exact R2 runtime `MU1367-audio-native-r2-1b29ead70598`.
An active R1 must be restored first. R2 upgrades verify the retained R2 controller
and backup; those files are not changed. Unknown runtimes are refused.

R3 replaces only the audio JAR and
`/mnt/app/carplay-mu1367-artwork/artwork-fetch`. Both previous files are saved in
the separate `/mnt/app/carplay-mu1367-artwork-r3/backup` snapshot.

Play a track, then skip three or four times, leaving each track long enough for
its cover to appear. Repeat with Apple Music and Spotify over Ottocast. Note
whether the old image remains or the picture area clears while waiting. Export
normal Toolbox diagnostics before rebooting. **Artwork R3 timings** shows the
status and the last eight numeric image timings. No titles or media UIDs are
added to those files.

## Restore

Select **Restore audio/artwork before R3 (reboot)** and fully reboot. This
restores both previous files, including R2 if R3 was installed over it. Restore
R3 before restoring R2 or changing/removing the base integration.

Saved MMX recovery without SD:

```sh
/bin/ksh /mnt/app/carplay-mu1367-artwork-r3/control.sh recover
```

If R3 restored R2 and you also want to remove that historical test, use its
saved `/mnt/app/carplay-mu1367-audio-progress-r2/control.sh uninstall` from an
MMX shell after the R3 restore/reboot, then fully reboot again. An R2 installed
over R1 restores R1, whose saved controller remains available as documented in
the original test.

Snapshots are retained and are never overwritten. The published releases and
R1/R2 ZIPs remain unchanged. This is a vehicle test candidate, not a released or
vehicle-validated fix for all artwork delay.
