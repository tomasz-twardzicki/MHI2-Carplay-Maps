# MU1367 / AID 791 — v1.6.2-e-test1

Experimental wireless fixes on the exact published v1.6.1 stable base. Vehicle validation is pending. Read [START_HERE.md](START_HERE.md) before installation.

- Priority floor 14 for the pinned receiver's port-9997 alternate sender and the dedicated input adapter. Higher OEM priorities and scheduling policies are preserved.
- Wireless iAP2 NowPlaying metadata, playback state, position and completed artwork feed the factory CarPlay dispatcher, AID text and existing picture service. Accepted-session leases, track identities and complete-transfer checks prevent old covers from crossing sessions or tracks.
- `oemIconLabel=Volkswagen` in the RAM configuration and `/info` refresh, including when driver coding has not arrived yet.

Existing maps, native guidance, RHD/LHD forwarding, 40 FPS, IDR and smoothing controls are retained. The bridge, guidance JAR, tuning tool and supervisor are byte-identical to v1.6.1. This candidate replaces the audio JAR, receiver launcher, tap and input launch script, and adds a bounded artwork decoder. Its complete wireless transaction covers 41 targets and has a separate recovery generation.

Owned changes: GPL-3.0-or-later. Existing omonob receiver/library provenance and permissions remain in the bundled upstream notices. The unmodified stb_image retains its own notice.
