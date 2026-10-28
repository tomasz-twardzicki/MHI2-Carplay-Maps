# N3 native artwork capture and isolated decoder

N3 builds from the exact A2-tested N2 driver, which builds from B4 and the
fingerprinted stock MU1427 ELF. Existing N1/N2 packages remain immutable.
This is a manual image diagnostic; no daemon, Java change or cluster picture
provider is installed. See [unit procedure](../TEST-N3.md).

## Native lifetime and scope

Five four-byte instructions differ from N2: the pool allocation-size
instruction, stock `file_xfer_destroy` entry, N2 setup/read entry branches,
and the stock kind-1 completion seam at `0x879c`. The latter is after the
stock receiving→complete transition and before PPS notification. It copies
only the current native kind-1 slot, with equal expected/received uint64
lengths, a non-null pointer, a JPEG/PNG signature and 8..800000 bytes. It
replays the displaced instruction and preserves stock registers, return
values and packet/transfer ownership. Stock mutation serialization remains
the lifetime boundary; no pointer escapes to an asynchronous consumer.

The single zeroed allocation grows from N2's 33216 to 833344 bytes. B4's
33088-byte guidance format and N2's 128-byte diagnostics are unchanged. The
new mailbox is a 128-byte header plus 800000-byte owned buffer at offset
33216. Capture performs at most one bounded memcpy into that buffer, with
no allocator, decoder, I/O or wait. The stock artwork read cursor is untouched.

Destruction/setup of a kind-1 slot invalidates the mailbox before the stock
buffer can be replaced. Completion increments generation and replaces the
single owned image. A one-attempt exclusive lock protects this mailbox from
the diagnostic reader; receive processing never waits. Contention or counter
wrap sets a sticky fault and disables image reads for the allocation. The
reader copies into its own allocated reply, releases the lock before
`MsgReply`, and rejects a fault observed during its copy. This conservative
diagnostic policy favors an explicit failed capture over continuing with
unverified mailbox state.

The resource-manager read hook selects N3 only for **800128-byte** requests
on the existing `rgi-events` entry. Other requests use N2/B4 unchanged. The
reply contains exactly `128 + length` bytes, or a 128-byte empty frame. It
never exports unused bytes left after an older, larger image. Allocation
failure, read verification, EOF and return conventions follow the existing
driver boundary. Old B4 sessions or a disabled publication hide retained
payloads. A read neither consumes the image nor calls `nowplay_getartwork`.

Header fields are little-endian uint32 values:

| Offset | Value |
| --- | --- |
| 0 | `N3AR` |
| 4 / 8 | Version 1 / header size 128 |
| 12 | Native mailbox generation |
| 16 | Sticky fault; usable frames require 0 |
| 20 / 24 | Image bytes / kind: 0 empty, 1 PNG, 2 JPEG |
| 28 / 32 | Owned copies / rejected completions |
| 36 | B4 session captured with the image |
| 40..63 | Reserved zero |
| 64 / 68 | Current B4 session / enabled state |
| 72 / 76 | Monotonic native allocation token seconds / nanoseconds |
| 80..127 | Reserved zero in the wire reply; offset 80 is an internal lock |

Generation is an artwork-transfer identity, **not a verified media-track
identity**. An in-session title can change without an artwork association,
and a delayed transfer can outlive a title change. The manual export records
that limitation explicitly. No image is associated with N1 text or served
to AID. A future output adapter needs track correlation, session/source
clearing, late-result rejection and Volkswagen picture-request handles.

## Worker and recovery

`capture.c` forks one child for device open/read/close, decode and file
writes. Its parent enforces a 5000 ms monotonic deadline and up to 250 ms of
child-reaping attempts. An unconfirmed child retains the RAM lock; another
invocation cannot create a second worker. The small result packet fits a
pipe's atomic-write budget. Original data never travels through the pipe.

`image.c` uses the pinned unmodified stb header with TLS, HDR/linear formats,
stdio and all formats except JPEG/PNG disabled. It checks dimensions and an
8 Mi pixel budget before full decode. A 64 MiB custom allocator enforces a
separate decoder memory ceiling. Input bytes and ordinary process overhead
are outside that ceiling. Bounds-checked IFD0 parsing handles all eight EXIF
orientations. Integer contain resizing and a fixed-size PNG writer avoid
libm/zlib imports. Output is a 256×256 RGB PNG with black margins; PNG alpha
is discarded by the RGB conversion. Original files retain their bytes and
metadata. Files in failed/timed-out exports must be interpreted with status,
not treated as successful publications.

`control.sh` changes only the driver and saves B4/controller/helper under
`/mnt/app/carplay-artwork-n3`. Installation requires the accepted N1, B4
markers/sizes, profile MU1427/791 and N2 removal. Both transition reboots are
explicit in the unit procedure. The existing shared guidance installer lock,
staged rename/mode preservation and unknown-driver refusal remain in place.
Saved removal restores B4 without replacing boot scripts, JARs or config.

## Reproduction

Use the exact stock ELF described in `../ARTWORK-RESEARCH.md`, pyelftools,
capstone, Unicorn, clang and the pinned local QNX toolchain/reference clone.
Unicorn needs unsandboxed execution on this Mac. The worker builder and QNX
runner use the existing offline Docker context `colima-cpmap-rgi`.

```sh
python n3/build-driver.py "$STOCK_DRIVER" build-N3-driver/ipod-drvr-iap2.so
python n3/test-driver.py "$STOCK_DRIVER" build-N3-driver-tests.json
python n3/test-worker.py --reference "$LUKA_REFERENCE" --output build-N3-worker-tests.json
python n3/build-reader.py --toolchain "$QNX_TOOLCHAIN" --firmware "$MU1427_FIRMWARE" --output build-N3-reader-verified
python n3/test-controls.py build-N3-driver/ipod-drvr-iap2.so build-N3-reader-verified/rgi-observer build-N3-controls.json "$HOST_CAPTURE_WORKER"
python n3/test-qnx.py --toolchain "$QNX_TOOLCHAIN" --firmware "$MU1427_FIRMWARE" --reader build-N3-reader-verified --reference "$LUKA_REFERENCE" --output build-N3-qnx-final
python n3/build-package.py --n1-package "$ACCEPTED_N1_ZIP" --driver build-N3-driver/ipod-drvr-iap2.so --reader build-N3-reader-verified --driver-tests build-N3-driver-tests.json --worker-tests build-N3-worker-tests.json --controls build-N3-controls.json --qnx build-N3-qnx-final/result.json --output build-N3-unit-package
python n3/test-package.py build-N3-unit-package/CarPlay_Maps_VC_MU1427_Audio_N3_Test.zip --output build-N3-unit-package/package-check.json
```

Commands run from `MU1427/now-playing`. Build/package output directories must
be new. `$HOST_CAPTURE_WORKER` is a host build of `n3/capture.c`; the production
worker is ARM/QNX. The host worker test shows the sanitizer/compiler settings.
The package gates matching hashes across driver/worker/controller/QNX checks
and preserves every N1 base file/mode except appending menu entries. Source
packages include n2/n3 and maintained route-guidance dependencies with their
relative paths and GPL license. No private captures or original firmware
are used as source-package inputs.
