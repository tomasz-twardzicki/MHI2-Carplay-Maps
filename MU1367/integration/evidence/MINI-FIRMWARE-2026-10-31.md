# Ottocast Mini firmware inspection — 31 October 2026

Input supplied by the user: `3072_CAR2_20250830.img`, from the `3072-PC burning`
directory. This is the Mini image, not an identified Mini Pico firmware dump.
It was parsed and disassembled offline; no vendor executable was run, no device
was accessed and no firmware/package was changed. Extracted vendor files remain
outside the repository in `/private/tmp/mu1367-ottocast-mini`.

The image is useful: it contains a complete alternate-display-capable CarPlay
stack and a concrete URL-replacement path. This is stronger evidence about
Ottocast-family implementation choices than the separate OMKE Smart Box example.
It is still not proof that the user's newer Mini Pico build has the same code.

## Identified image and files

Image SHA256:
`e9eb0489cf1f0ac3fc23ccffd0a3dea18e985d160e8da6e17548c1bbc960d67e`;
15,320,064 bytes. It is an Allwinner `IMAGEWTY` version 0x300 container with
36 entries. The two readable SquashFS v4/XZ filesystems are:

| Entry | Image offset | Stored length | SquashFS bytes used |
| --- | ---: | ---: | ---: |
| `rootfs.fex` | 6,682,624 | 4,198,400 | 4,197,154 |
| `customer.fex` | 11,014,144 | 4,304,896 | 4,303,872 |

Bounded container records were checked against image length. Both filesystems
were traversed with a read-only SquashFS parser, without creating image symlinks
or device nodes. The traversal found 492 entries, including 289 regular files.
Hashes and selected evidence are recorded in `MINI-FIRMWARE-2026-10-31.json`.

`customer/app/system.json` identifies app version **25083011.3072.2**.
The root release identifies Tina Linux/OpenWrt, target
**v851s-lybox_rtl8733/generic v2.1**, kernel module paths 4.9.191. The inspected
CarPlay application/library are **32-bit little-endian ARM EABI5**. This is a
different stack from OMKE's MIPS `sdDongle`.

The launch script starts `lylinkapp` and a separately packed `rcpservice` from
the `lylink` container. The packed server has not been unpacked or executed in
this review. That limits conclusions about the complete car-facing command
decoder and its acknowledgements.

## Actual alternate-display support

`libwcarplay_new.so` exports `ShowUI`, `RequestUI`, `RequestUIWithUrl`,
`UpdateViewArea`, `SendForceKeyFrame` and `SetScreenPlayerWithUuidIndex`.
Its strings explicitly describe `altScreen`, `viewAreas`, separate stream-1/2
dimensions, display UUIDs and `altScreenSuggestUIURLs` for map, instruction-card
and combined instrument-cluster scenes. This older image already contains
alternate-screen machinery; its support is not inferred merely from the brand.

These names do not alone establish end-to-end forwarding. The application
layer sitting above the library must preserve the requested parameters too.

## Concrete fixed-URL path in `lylinkapp`

Static ARM control-flow tracing identifies the application's internal command
**0x2027**, labelled **`COMMAD_SHOWUI_EVENT`** by its own command-name function:

1. Dispatcher comparison at VA `0x1ea80` selects the handler at `0x1ee7c`.
2. That handler reads the supplied payload into a local buffer, but does not
   pass that buffer to the subsequent display-activation call.
3. At `0x1ee90`–`0x1eea0`, it instead supplies the fixed string
   **`maps:/car/instrumentcluster`**, display index **1**, and show=true.
4. Wrapper `0x1b654` passes that index and fixed URL to the imported **`ShowUI`**
   function via its PLT entry at `0x145c8`. The relocation resolves to `ShowUI`.

This demonstrates URL replacement in this particular Mini application's show
path. It does not preserve a caller-supplied `/map?showETA=no&maneuverLayout=no`
selection through that path. It also does not prove that every possible command
path drops URLs: the library provides a separate `RequestUIWithUrl` entry point,
and the packed car-facing server remains unexamined.

**Relevance to Mini Pico is an inference:** a matching implementation could
acknowledge the MU request yet activate the combined instrument-cluster scene,
explaining a persistent video turn card. To establish causality we need the
Pico application/library or its phone-facing control trace. This is a 2025 Mini
snapshot; the user's Pico reports build 26101215.6071.
Model similarity is insufficient to transfer offsets, binaries or patches.

## A second lossy callback, with direction still to establish

Exported `_Z16ReceiveRequestUIPKcPv` (`ReceiveRequestUI(const char*, void*)`) is
at VA `0x1903c`, size 140. Its implementation does not use the incoming URL
argument. It obtains the command client and invokes `0x1efe0`, which sends a
fixed 12-byte **0x3002** notification without a URL body.

This is another concrete place where the application converts a rich request
into a simple event. Its direction/role must be traced through the packed
server before treating it as the path for the MU's outbound map request. It
could serve UI/focus signaling. It is not independently declared the card cause.

## What this changes for our investigation

The next productive comparison is between the Mini and Pico's `lylinkapp`,
`libwcarplay_new.so`, packed service, and actual firmware identity. Check whether
the Pico still has the 0x2027 fixed-URL behavior, which request path the MU
reaches, and whether the phone receives the full query string and correct
alternate UUID. The suggested-URL configuration in the library is another
lead to trace; its strings alone do not establish an available MU-side workaround.

This evidence makes blindly repeating OFF requests less promising. It does not
yet establish a safe fix on the MU or on the Pico. No Mini image should be
treated as a Pico update based on this comparison. The existing v3r3 ZIP and
its lane-type test are unchanged; no new target commands or firmware patch were
introduced. This display-transport inspection supplies no unused-lane encoding
change.
