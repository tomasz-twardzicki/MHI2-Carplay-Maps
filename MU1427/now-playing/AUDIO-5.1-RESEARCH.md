# LuKa 5.1 audio assessment for MU1427

Historical research only. The user subsequently removed 5.1 audio from the
scope; no implementation or further investigation is planned.

Researched 2026-10-20. The user confirmed the car has the **standard sound
system**. No amplifier coding, audio routing, DSP image, codec, CarPlay
negotiation or sound payload has been changed. This is a separate possible
feature from cluster title/artist/artwork.

The reference is LuKa's MHI2Q project at
[`71b4ab1c9461d5383a7aa6d56d4dda34f567ade7`](https://github.com/luka-dev/mib2q-carplay-rgi/tree/71b4ab1c9461d5383a7aa6d56d4dda34f567ade7).
Source-document hashes are recorded in
[artwork research verification](./ARTWORK-RESEARCH-VERIFICATION.json).

## Two different capabilities

| Capability | Upstream implementation | Implication for this car |
| --- | --- | --- |
| Discrete multichannel input | A hook-owned type-103 buffered receiver; negotiation, RTSP controls, APAP framing/authentication, APAC/AAC decode and PCM routing | A substantial receiver/codec/transport port, not a channel-count configuration change |
| Stereo to surround | A scene upmixer synthesizes six output channels from stereo media, including realtime type-100 input | Does not make a stereo Spotify track a discrete 5.1 recording; still needs a working multichannel route to the speakers |

See upstream [buffered receiver](https://github.com/luka-dev/mib2q-carplay-rgi/blob/71b4ab1c9461d5383a7aa6d56d4dda34f567ade7/docs/audio/BUFFERED_AUDIO_PATH.md)
and [upmix pipeline](https://github.com/luka-dev/mib2q-carplay-rgi/blob/71b4ab1c9461d5383a7aa6d56d4dda34f567ade7/docs/audio/STEREO_TO_5_1_UPMIX.md).
The reference targets MHI2Q MU1316 AirPlay 210.81 in `dio_manager` and a
six-channel route to its external B&O amplifier. Its private hooks and
vehicle-specific channel matrix are not verified for MU1427. The current
upstream source explicitly fingerprints its private receiver boundary.

## Standard sound is the key limitation

The updated [internal-amp investigation](https://github.com/luka-dev/mib2q-carplay-rgi/blob/71b4ab1c9461d5383a7aa6d56d4dda34f567ade7/docs/audio/INTERNAL_AMP_PATH.md)
reports a real internal-amp Audi test on 2026-10-18: the stock route
transported front L/R only despite a six-channel MMX writer. Its installer
therefore disables spatial audio when amplifier coding is internal or
unreadable. Upstream's proposed internal-amp routing/DSP edits remain
unvalidated. Speaker count and the ability to open a six-channel PCM sink
do not establish end-to-end discrete-channel delivery.

This is evidence against treating the upstream package as suitable for the
user's standard sound system. It is **not** a measured MU1427 limitation or
proof that a Volkswagen internal-amp port is impossible. Conversely, the
Audi document's feasibility claim does not establish Volkswagen feasibility.
Changing coding to external would select a different hardware route; it
does not supply an external amplifier.

The useful next investigation, if pursued, is read-only mapping of the exact
MU1427 MMX/RCC audio stack, Volkswagen audio table, internal DSP input/output
channels, source/sink routing and channel order. Only after proving that
route should a receiver/upmixer port be scoped. Audi addresses, calibration,
B&O gains and amplifier-specific centre/LFE handling are not transferable
assumptions. Acceptance would need measured per-channel output, level and
clipping checks, calls/Siri/alerts priority, source handback, pause/seek,
reconnect and recovery on this hardware.

This assessment is retained as background. The user subsequently removed
5.1 audio from the scope; the active feature path is title/artist/artwork.
