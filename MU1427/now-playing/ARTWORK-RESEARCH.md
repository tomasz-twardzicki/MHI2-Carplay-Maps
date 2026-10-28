# Artwork approach for MU1427 / AID 791

Researched 2026-10-20 on `feature/mu1427-aid791-carplay-now-playing`.
N1 text display has since passed the reported [A1 run](./A1-RESULTS.md).
The [N2 test](./TEST-N2.md) now implements the counter-only native observer
designed below, with [host/QNX verification](./N2-VERIFICATION.json).
The [N3 diagnostic](./TEST-N3.md) now implements owned image extraction and
isolated decoding with host/QNX checks; its first unit test is pending.
Track matching and cluster picture output remain unimplemented.
[A2](./A2-RESULTS.md) now confirms seven completed JPEG-signature transfers
in the native artwork buffers. The stock completion path is a demonstrated
input; a raw-stream fallback is not the first implementation choice.

LuKa's solution provides a useful artwork architecture. MU1427 already has
a native artwork receiver worth observing before porting its raw-stream
parser. The remaining work has two independent boundaries: getting an image
out of iAP2, and serving it with the identity the Volkswagen cluster expects.
[A0](./A0-RESULTS.md) demonstrated text input but observed **zero** CarPlay
cover callbacks. It did not observe the native transfer buffer.

## Reference and reproducibility

The current public reference is pinned to
[`71b4ab1c9461d5383a7aa6d56d4dda34f567ade7`](https://github.com/luka-dev/mib2q-carplay-rgi/tree/71b4ab1c9461d5383a7aa6d56d4dda34f567ade7).
The earlier audio overview used `dfafccf`; these two revisions have identical
`hook/coverart/` sources and cover-pipeline documentation. The newer audio
documentation contains material updates, including an internal-amp car result.

[`research-artwork.py`](./research-artwork.py) reads pristine Git blobs at
the pinned revision, fingerprints the exact stock MU1427 ELF and builds the
upstream stream, image-safety and complete decoder/publication fixtures with
AddressSanitizer and UndefinedBehaviorSanitizer. Firmware bytes, reference
sources, synthetic images and executables remain outside version control.
See [verification](./ARTWORK-RESEARCH-VERIFICATION.json) for results and hashes.
These are host reference checks and static MU1427 inspection, not a QNX
port, proof of live artwork reception, or AID display acceptance.

```sh
python research-artwork.py --driver "$MU1427_STOCK_IAP2_DRIVER" \
  --reference "$LUKA_REFERENCE_CLONE" \
  --output ARTWORK-RESEARCH-VERIFICATION.json
```

Dependencies: pyelftools, capstone, Git and a C compiler with both sanitizers.
On this Mac the command additionally uses
`--cc /Library/Developer/CommandLineTools/usr/bin/clang --sysroot
/Library/Developer/CommandLineTools/SDKs/MacOSX27.0.sdk`. The newer CLT compiler
and runtime are needed: default Xcode clang 17 cannot link against the 27.0
SDK, and its ASan runtime hangs even on a minimal program with the older SDK.
The driver must match size 739925 and SHA-256
`0ac13f43d3fb259eee328c272fa1211bb558b6e2cd97c6e38ef38e4e71469d51`.
Already patched B1/B4 binaries are deliberately refused as probe inputs.

## What LuKa's implementation establishes

The [upstream pipeline](https://github.com/luka-dev/mib2q-carplay-rgi/blob/71b4ab1c9461d5383a7aa6d56d4dda34f567ade7/docs/altscreen-and-video/COVER_ART_PIPELINE.md)
describes the same high-level symptom on MHI2Q: the normal cover URL did not
deliver useful artwork. Its replacement taps `NmeTransport::Recv`, parses
iAP2 FF5A link frames, assembles file transfers and hands a complete image
to a worker. It does not discover JPEG boundaries by scanning for an end
marker; an embedded thumbnail may contain that marker.

The reusable pieces are:

- Negotiated file-transfer session IDs, checksums, sequence wrap/reordering,
  cancellation and reset handling. Setup can be eight-byte size-only or a
  typed extension; wire artwork type 2 is not mandatory in size-only Setup.
- Bounded files (800000 bytes), four active transfers and a bounded reorder
  queue. A single pending completed image is replaced by a newer image.
- PNG/JPEG-only decoding on one worker, maximum side 4096 and total pixels
  8 Mi, followed by a 256 by 256 contain resize and PNG publication. These
  are upstream limits and output size, not measured AID 791 requirements.
- Atomic file publication and an Identify-generation check before commit.
  QNX builds disable stb thread-local storage. Upstream applies only its
  observed EXIF orientation-4 correction, not all EXIF rotations.
- An image identity notification to Java, followed by a cluster refresh
  when an image arrives after the title. Its Audi Java/BAP classes and
  CRC-based IDs cannot be substituted directly into Volkswagen MQBAB2.

Retain LuKa's attribution and the upstream GPL notices if code is ported.
The upstream worker's session check does not by itself prove that an image
belongs to the latest track within a session; our adapter needs that check too.

## MU1427 already receives artwork at the driver layer

Static inspection of the exact stock driver found the following functions.
Addresses are ELF virtual addresses for this exact fingerprint.

| Boundary | Address | Finding |
| --- | --- | --- |
| `nowplay_start` | `0x1b860` | Constructs the native now-playing subscription |
| `nowplay_update_recv` | `0x1bb18` | Processes the artwork transfer identifier and initializes its file slot |
| `file_xfer_setup` | `0x89ac` | Sets expected length and allocates a transfer buffer |
| `file_xfer_data` | `0x86b0` | Copies received chunks and detects expected-length completion |
| `nowplay_getartwork` | `0x1ba3c` | Reads the current artwork buffer using a shared advancing cursor |
| `iap2_msg` | see verification | Calls that artwork reader from the native request interface |

The metadata table identifies `MediaItemArtworkFileTransferIdentifier` as
field **26 / 0x1a**. The already-deployed guidance `driver/iap2.cfg` requests
`ArtworkFileTransferIdentifier` in `[nowplaying]`. Increasing Java notification
coverage or adding that existing configuration option is therefore not an
established fix for the missing cover callback.

The stock receiver initializes artwork slots with its **internal kind 1**;
this differs from LuKa's **wire type 2**. At known-length completion,
`file_xfer_data` changes the slot state to 3, then publishes
`MediaItemArtworkFileTransferIdentifier` and `MediaItemArtworkSize` through
PPS. Setup also publishes these keys: seeing a size alone is not proof of
complete image bytes. A new native artwork identifier destroys the old
current slot before initializing its replacement.

The observed slot layout is `context + 48 * file_id`, with kind at `+0x120`,
state at `+0x121`, expected uint64 length at `+0x128`, data pointer at
`+0x130`, shared read cursor at `+0x138`, and received uint64 length at
`+0x140`. The current artwork file ID is at context `+0xbc`. These are
research observations, not sufficient patch/lifetime validation.

**First N2 producer:** a passive completion observer on the existing
receiver, initially counting artwork-ID, setup, completion and invalid-length
events only. It must preserve the B4 guidance hooks, stock packet recycling,
registers, locks, PPS updates, return values and transfer ownership. If it
proves live complete buffers, copy a bounded completed image into separately
owned storage and decode on a supervised worker. Never pass a stock pointer
to an asynchronous decoder or make a second consuming artwork-reader call.
Measure the completion-copy cost and drop on queue pressure; no decoding,
file I/O, waiting for a worker or new transport writes on reception.

N2's implemented hooks execute the full stock initialization/setup/data
functions, then count internal kind-1 artwork events. A receiving→complete
transition inspects at most eight signature bytes for bounded buffers. The
observer does not call `nowplay_getartwork` or move its cursor. An independent
128-byte counter area extends B4's existing allocation; its 33088-byte
guidance format, reserved fields and ring contents remain unchanged. Only a
128-byte request on the existing virtual file selects the diagnostic read.
Normal guidance reads tail-call B4. A separate helper supervises device I/O
with a deadline. A2 now demonstrates native hook execution and successful
diagnostic reads on the unit, including completed JPEG-signature buffers.
This does not establish decoded image validity or picture delivery.

**Fallback:** port LuKa's passive raw-stream reassembler if stock completion
does not provide useful images. First establish MU1427's actual transport
boundary and stream framing. The MHI2Q `NmeTransport::Recv` hook and offsets
have not been established here. A zero cover callback is insufficient reason
to replace the entire CarPlay stack.

## Volkswagen picture output still needs its own adapter

The [factory audio contract](./MU1427-AUDIO-CONTRACT.json) fingerprints the
stock `CoverArt`, `CurrentStationHandle`, `ActiveSource` and picture-service
interfaces. The stock `CoverArt` supports source types
6/7/8/10/11/15/16/18/19/20/21/22. `CurrentStationHandle` supplies invalid
handles for audio component 6, which is the smartphone audio path. Merely
making a PNG or changing the source-type allowlist will not establish a
valid CarPlay cover identity.

Use the stock `DSIKombiPictureServer.responseCoverArt` transport with a
CarPlay-only provider. Observe the actual active source and picture requests
on this unit before selecting handle values or changing source behavior.
Keep the regular media provider in charge when another source owns audio.
Calls into the picture service belong on the factory event thread; image
processing and mailbox reads belong on a worker.

The candidate design needs an explicit no-picture state and an identity
that changes when artwork changes, even if the file path repeats. Bound
immutable image files and their request lifetimes so a delayed cluster read
cannot receive a replacement image for an earlier handle. Drop or defer
when the bounded cache has no free slot.

Session generation, track generation and transfer ID must travel with the
image until publication. The generation must be captured when the transfer
is associated with a track, not when decoding finishes. The current typed
DSI text model and a native image observer do not yet share a verified track
identity; resolve that association before enabling output. Clear old art on
track/source/disconnect changes, reject late completions, and avoid a stale
image while waiting for the next cover. Artwork may precede or follow text,
and transfer IDs may be reused.

## Next acceptance steps

1. Keep the existing N1 package as the accepted text baseline. A1 also
   exposed a counter/retry interpretation issue: factory cached equality can
   return false. Resolve that distinction before a subsequent Java build.
2. The counter-only native completion observer against B4 passes ARM,
   installer and factory-libc QNX helper checks. A2 has now observed completed
   JPEG-signature transfers on the car. The user confirmed Apple Music and
   Spotify with no observed HMI, CarPlay text, maps or guidance issues.
   Individual exports are not mapped to apps or test steps.
3. Run the new [N3 image capture/decode test](./TEST-N3.md). It adds a bounded
   owned copy before stock completion notification, isolated JPEG/PNG decode
   and private original/256×256 PNG exports, retaining the accepted N1 JAR.
   ARM, sanitizer, installer/package and factory-libc QNX checks pass; live
   image usability and copy cost still require unit evidence. See
   [verification](./N3-VERIFICATION.json). It does not associate images with
   N1 text. Establish that track/session matching before output. Exercise
   missing covers, rapid track changes, cancelled/partial transfers,
   repeated covers, reconnect and source handback.
4. Observe AID source/handle/picture behavior, then implement and test the
   narrow Volkswagen picture provider. Verify late-image refresh, clearing
   and ordinary-source artwork before a combined package.

The user has already confirmed working OEM artwork from another source on
this AID. That avoids assuming cover support is disabled globally, but does
not establish CarPlay picture identities, dimensions or decoding behavior.
The user removed 5.1 audio from the scope; its earlier assessment is historical.
