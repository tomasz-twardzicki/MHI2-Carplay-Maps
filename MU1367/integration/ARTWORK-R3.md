# Optional artwork refresh test (v1.4.5-e)

**Experimental. No vehicle result yet.** Covers on the AID should change sooner after
a track skip. This test isn't part of the normal install, and guidance, video and
the map stream don't change.

## What it changes

| | v1.4.5-e | With this test |
| --- | ---: | ---: |
| Checks for new artwork | every 1 s | every 200 ms |
| Retries a missed cover | after 1 s | after 200 ms (first 8 tries) |
| Sends the new cover to the cluster | up to 1 s after clearing the old one | immediately |
| Cover PNG size | always 197 KB | about 95 KB for a photo, much less for flat art |
| Timing diagnostics | none | last 8 covers |

Pictures are identical: the PNG stays 256 × 256 and lossless. It uses the factory
`/proc/boot/libz.so.2`, so nothing new is added to the unit's libraries.

The phone still has to send the artwork first. Earlier measurements with the same
polling show that wait at 0.7–1.1 s on most skips, and this test can't shorten it.

## Install

You need v1.4.5-e installed and working. Refresh the Toolbox menus from this SD card.

1. Disconnect the phone and adapter, then fully reboot.
2. Select **Tuning > Install artwork test: fast + compressed (reboot)**.
3. Fully reboot again.

It replaces two files, the audio JAR and `artwork-fetch`, and saves the originals in
`/mnt/app/carplay-mu1367-artwork-r3/backup`. If the old R2 artwork test is still
active, it upgrades from that and can restore it. Any other audio build is refused.

## What to test

Please do both parts on the same drive, with the same app.

**1. Is it faster overall?** Skip 5–6 tracks, leaving each one long enough for its
cover to appear. Roughly time each skip until the new cover shows. Compare this with
your memory of v1.4.5-e, or time it before installing. Note whether the old cover
stays or the picture area clears while waiting.

**2. Does compression help?** No reboot is needed to switch:

1. Select **Tuning > Artwork test: uncompressed PNG (A/B)** and skip 4–5 tracks.
2. Select **Tuning > Artwork test: compressed PNG (A/B)** and skip 4–5 tracks.

Each choice applies from the next new cover. A reboot always returns to compressed.

Try Apple Music and Spotify if you can, over cable and over the adapter. Then export
normal Toolbox diagnostics before rebooting, and tell us what you saw at the cluster.

## Reading the results

**Tuning > Artwork test timings** shows the current PNG mode and the last 8 covers.
The exported diagnostics contain the same file, `ramdisk/cpmap-artwork-timing.status`.
It holds numbers only, with no titles or media IDs.

| Field | Meaning |
| --- | --- |
| `png_bytes` | 196947 means uncompressed; a smaller value means compressed |
| `text_to_ready_ms` | Track text change until the cover file is ready |
| `pps_to_ready_ms` | Artwork metadata seen until the cover file is ready |
| `decode_write_ms` | Helper's decode, resize, compress and write time |
| `ready_to_push_ms` | Cover file ready until it's handed to the picture service |

These stop at the hand-off. **Nothing on the unit measures when the cluster actually
shows the picture**, so your timing at the cluster decides the compression question.
If compressed and uncompressed covers look the same, then file size isn't the delay.

## Remove

Select **Tuning > Remove artwork test (reboot)** and fully reboot. This restores
both files exactly as they were.

**Remove this test first** before you do any of these:

- **Install / update CarPlay integration** or **Install optional turn-card support**.
  While the test is active, these stop with `UNEXPECTED_UNCHANGED_RUNTIME` and change
  nothing.
- Removing the integration or restoring OEM. These can refuse to run, or leave this
  test's saved folder behind.

If an install is interrupted, use **Recover interrupted artwork test (reboot)**.
Without the SD card, run this from an MMX shell:

```sh
/bin/ksh /mnt/app/carplay-mu1367-artwork-r3/control.sh recover
```

If covers stop appearing, remove the test and include a diagnostics export in your report.
