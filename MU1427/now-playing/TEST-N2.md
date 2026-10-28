# N2: observe native artwork transfers, keeping N1 text

[A2 results](./A2-RESULTS.md) now confirm native diagnostic delivery and seven
completed JPEG-signature transfers. This procedure is retained for repeat
testing and recovery. N2 itself does not decode or display artwork; the next
[N3 test](./TEST-N3.md) adds image capture/decoding without AID cover output.

Target: **MHI2_ER_VWG11_K3342_MU1427 / AID 791**. This test counts the
factory iAP2 driver's artwork associations, setup, completion and JPEG/PNG
signatures. **It does not display cover art, decode pictures or export image
bytes.** The accepted N1 JAR, boot script, driver configuration and ordinary
audio controls stay as tested in A1. The N1 diagnostic/retry cleanup is
deferred to the next Java revision.

Use the full `CarPlay_Maps_VC_MU1427_Audio_N2_Test.zip` and adjacent
`SHA256SUMS.txt`. The tested N1 text package and B4 native-guidance driver
must already be installed. N2 refuses other build markers/sizes. Host checks
use exact fingerprints; unit checks use markers/sizes, as in the existing
toolbox. They do not independently hash installed binaries.

N2 extends B4 with 128 bytes of independent counters and a special 128-byte
read of `/dev/ipod0/rgi-events`. Normal guidance reads still receive the
original 33088-byte snapshot with its reserved fields unchanged. Transfer
hooks perform no I/O, image copying, allocation or waits. One snapshot helper
contains device I/O in a child with a 1500 ms deadline and bounded cleanup.
The host ARM tests and factory-libc QNX helper checks precede this package;
full driver loading and live callback delivery still require this unit test.

## Install

Work parked with stable power. Preserve old SD `Log` folders, then extract
the full ZIP to the SD root and refresh toolbox scripts/menus as usual.

1. Leave N1 and native guidance installed. Disconnect the iPhone.
2. In **Customization → CarPlay Maps VC**, choose **Install N2 artwork
   observer (MU1427, reboot)**. Expect
   `CPMAP_AUDIO_N2_INSTALLED_REBOOT_REQUIRED` or `CPMAP_AUDIO_N2_ALREADY_INSTALLED`.
3. Fully reboot. Check normal HMI/OEM operation, then connect the phone.
   No N1, guidance or map reinstallation is needed.

N2 saves the B4 driver, controller and helper under
`/mnt/app/carplay-artwork-n2/`. If HMI/CarPlay/maps/guidance behave abnormally,
remove N2 using the recovery commands below and fully reboot.

## Test and export

**Export N2 artwork snapshot to SD** creates the next unused
`Log/cpmap-audio-N2-01` through `-16`. Each contains `install.txt`,
`native.txt` and, when available, N1's counter-only `n1.txt`. Record the
app and step corresponding to each export. Export retains device/schema
errors too; `snapshot_result=0` means the helper accepted a diagnostic frame.

1. Export a baseline before phone connection. A missing device at this point
   may mean the iAP2 filesystem has not initialized yet.
2. In Apple Music, play a track with visible artwork on CarPlay. Wait about
   ten seconds and export. Change to two tracks with different artwork,
   waiting and exporting after each.
3. Repeat with Spotify. Include a change between tracks on the same album
   if convenient; repeated artwork need not cause another transfer.
4. Pause/resume and switch to an ordinary audio source and back. Confirm N1
   text and controls remain normal, then export.
5. Play music with a Google Maps route. Confirm HMI, maps and native guidance
   remain normal. Keep the parked test running beyond five minutes and export.
6. Disconnect, export, reconnect and play another track, wait and export.

Interpretation:

- `associations` counts internal artwork-slot initialization; `setups` and
  `data_calls` count stock artwork transfer calls. None alone proves a
  complete image.
- `completed` counts receiving→complete transitions. `jpeg_signatures` and
  `png_signatures` count bounded header matches on completed 8..800000-byte
  buffers. A signature does not establish decoder validity or AID usability.
- `oversize_setups` counts declared lengths above the observer's image
  budget. N2 observes factory behavior; it does not change its allocation.
  `setup_not_receiving` means setup did not leave the stock slot in receiving
  state, including zero-length cases. `other_signatures` counts other headers.
- `last_size` is the low 32 bits of the most recently observed declared or
  completed artwork size; it is not an image identity or freshness signal.
- `fault=1` records diagnostic contention/loss; keep the export. This flag
  does not alter the guidance ring. Compare counters only while
  `instance_sec/instance_nsec` match. `session` belongs to B4 identification;
  it is not inferred from N1's DSI epoch.
- All-zero transfer counters after track/app changes are a useful negative
  result. Keep those exports; the raw-stream fallback may be needed.
- Persistent `N2_ERROR` after reconnect is useful evidence. If the helper
  reports a retained reader lock, preserve the output and reboot; do not
  delete the lock to spawn more readers over an unconfirmed child.

Exports include no track text, file paths from the phone, device identifiers
or image bytes. The instance clock is a monotonic allocation token.

## Remove and recover

**Remove N2 artwork observer (restore B4, reboot)** restores only its saved
B4 driver. Then fully reboot. N1 and native guidance remain installed. The
loaded N2 code may continue until reboot; exporting before reboot can still
capture its counters after the on-disk driver has been restored.

**Remove N2 before removing/reinstalling native guidance, changing its
driver or using general Restore factory files.** Do not restore a complete
boot script or an OEM driver to remove this observer.

Without SD, on MMX:

```sh
/bin/ksh /mnt/app/carplay-artwork-n2/control.sh status
/bin/ksh /mnt/app/carplay-artwork-n2/control.sh uninstall
```

From RCC prefix with `on -f mmx`. Fully reboot afterwards. Recovery files
remain for retry. If restoration cannot commit, retain the error and retry
`uninstall` after resolving the filesystem condition. An unrecognized later
driver is refused rather than overwritten. Stale installer locks are not
removed automatically.
