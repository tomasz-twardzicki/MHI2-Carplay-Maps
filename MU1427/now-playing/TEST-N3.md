# N3: capture and decode CarPlay artwork on MU1427 / AID 791

Target: **MHI2_ER_VWG11_K3342_MU1427 / AID 791**. A2 proved native
JPEG-signature transfers. N3 copies a completed image into owned memory and
exports its original bytes plus a decoded **256 × 256 PNG**. **The cluster
still shows N1 text without a CarPlay album cover.** This stage establishes
image usability before track matching and the Volkswagen picture provider.

Use the full `CarPlay_Maps_VC_MU1427_Audio_N3_Test.zip` and its adjacent
`SHA256SUMS.txt`. The accepted N1 text JAR and B4 guidance configuration must
already be installed. No Java/boot/config changes are included. The N1
property-return cleanup remains deferred to the next Java revision.

Unlike N0–N2, **N3 exports actual album images**, including metadata embedded
in the original file. Keep these captures private unless you choose to share
them. It does not export track strings or device identifiers.

## Install

Work parked with stable power. Preserve old SD `Log` folders.

1. Disconnect the iPhone. **Remove N2 and fully reboot before installing N3.**
   Use its existing removal menu, or on MMX:

   ```sh
   /bin/ksh /mnt/app/carplay-artwork-n2/control.sh uninstall
   ```

   From RCC prefix with `on -f mmx`. This restores B4 and retains N1 and
   guidance. The N3 toolbox also includes **Remove installed N2 (then reboot
   before N3)** for convenience. Do not skip this full reboot.
2. Extract the full N3 ZIP to the SD root and refresh toolbox scripts/menus
   as usual. In **Customization → CarPlay Maps VC**, choose **Install N3
   artwork capture (MU1427, reboot)**. Expect
   `CPMAP_AUDIO_N3_INSTALLED_REBOOT_REQUIRED` or `CPMAP_AUDIO_N3_ALREADY_INSTALLED`.
3. Fully reboot again. Confirm normal HMI/OEM operation before connecting
   the phone. No N1, maps or guidance reinstall is needed.

N3 saves B4, its controller and helper under
`/mnt/app/carplay-artwork-n3/`. If startup, CarPlay, controls, maps or guidance
behave abnormally, remove N3 using the commands below and fully reboot.
Host ARM/sanitizer tests and actual factory-libc QNX decoder checks precede
this package. Full driver loading, copy cost and live decoding still require
this first on-unit test. Unit installation checks markers/sizes rather than
independently hashing installed files.

## Test and export

**Export N3 artwork image to SD** creates the next unused
`Log/cpmap-audio-N3-01` through `-16`. Leave the track playing while export
runs; allow about ten seconds after a track change. The helper has a five
second device/decode/write deadline with bounded child cleanup. No background
worker starts automatically.

Record the app and action for each export, and compare the exported
`cover.png` on a computer with the cover that was visible in CarPlay:

1. Export before phone connection. A missing device or an empty mailbox is
   useful baseline evidence.
2. In Apple Music, play a track with artwork, wait and export. Change to two
   tracks with different covers, waiting and exporting after each.
3. Repeat with Spotify. Include tracks from the same album if convenient;
   a repeated cover need not trigger another transfer. Note missing or
   incorrect covers rather than assuming every export is the latest track.
4. Change tracks rapidly, then settle on a different cover, wait and export.
   If convenient, also try an item with no artwork and record what appears.
5. Pause/resume, switch to an ordinary audio source and back, and test a
   Google Maps route with music. Confirm text, controls, HMI, map video,
   guidance and ordinary-source artwork remain normal. Run parked beyond
   five minutes, then export.
6. Disconnect and export; reconnect, play another track, wait and export.

Each folder contains `install.txt`, `native.txt` and optional N1 counters in
`n1.txt`. A nonempty successful capture also contains:

- `original.bin`: exact image bytes, JPEG for `kind=2` or PNG for `kind=1`.
- `cover.png`: decoded, EXIF-oriented, contained within a black 256 × 256
  canvas. This size is a research output, not an established AID requirement.

`snapshot_result=0` plus `bytes>0` and both image files means the worker
decoded and wrote that diagnostic capture. `bytes=0` is a successful empty
mailbox, without image files. `generation` identifies native mailbox changes;
compare it only within matching `instance_sec/instance_nsec` tokens. A read
does not consume the mailbox or move the factory artwork cursor.

`capture_session` is recorded when copying; `session` is the current B4
identification generation. Changed/disabled B4 sessions hide retained images.
These are not N1's DSI epoch or a verified phone/track identity.
`track_identity_verified=0` is deliberate: this test cannot establish that
an image belongs to the current typed text. An export may represent an
earlier completed transfer during rapid changes; report that result.

`copied` counts owned image copies and `rejected` counts bounded completion
rejections. `worker_ms` includes device read, decode and output writes; it
does not isolate time spent copying in the driver. `decoder_peak` is the
decoder allocator's high-water mark, excluding the 800128-byte input buffer
and ordinary process overhead. The decoder permits JPEG/PNG only, sides up
to 4096, at most 8 Mi pixels, and at most 64 MiB of decoder allocations.

Error exports are retained too. `CAPTURE_2` is device open, `CAPTURE_3` read,
`CAPTURE_4` close, `CAPTURE_5` frame/schema, `CAPTURE_7` original-file write,
and `CAPTURE_8` decode/PNG write failure. `errno` is meaningful only for the
reported I/O errors. Keep partial image files together with their error
status; their presence alone does not prove success.

`errno=11` on a read can indicate the native mailbox became unavailable
after contention. The driver never waits for a reader; mailbox contention
or generation wrap disables image reads for that allocation while stock
audio/guidance continue. Preserve the export, reconnect and retry; fully
reboot if it persists. If a child cannot be confirmed reaped, the helper
retains its RAM lock: preserve the error and reboot. Do not delete the lock
to launch another reader over an unconfirmed child.

## Remove and recover

Choose **Remove N3 artwork capture (restore B4, reboot)**, then fully reboot.
It restores only the saved B4 driver and preserves N1, guidance, boot script
and configuration. The currently loaded N3 code continues until reboot.

Without SD, on MMX:

```sh
/bin/ksh /mnt/app/carplay-artwork-n3/control.sh status
/bin/ksh /mnt/app/carplay-artwork-n3/control.sh uninstall
```

From RCC prefix with `on -f mmx`. Remove N3 and fully reboot before changing
or removing native guidance, another driver test, or general **Restore
factory files**. Recovery files remain for retry. If restoration cannot
commit, retain the error, correct the reported filesystem condition and
retry `uninstall`. Unknown later drivers and stale installer locks are
refused rather than overwritten or automatically removed.
