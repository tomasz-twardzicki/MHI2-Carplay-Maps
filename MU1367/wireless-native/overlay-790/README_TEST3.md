# MU1367 / 790 playback and call-handoff experiment

See [START_HERE.md](START_HERE.md) for upgrade, the optional call comparison,
capture and rollback. The published v1.6.3-e pre-release is unchanged.

The map runtime is retained from the user-confirmed working test 2. A separate
790 media observer uses byte-verified receiver metadata/file-transfer sites to
publish the existing now-playing/artwork protocol. Only `fprintf` and `memcpy`
are interposed with exact caller guards; there are no video, audio, display-info,
send or scheduling hooks. Existing metadata consumer and OEM touch JARs remain
unchanged. The receiver launcher pins all binaries before enabling the observer.

The optional call preference exposes the adapter's existing matched-phone
Bluetooth media/phone-profile release request. It stays off when no prior
preference exists. Unknown preference contents are preserved and refused; the
transaction restores the first-saved preference. A request is not an ACK or
proof of correct cellular-call audio/microphone routing.

The 790 guidance/timing/RHD/tuning extensions and the separate 791 mirror
renderer are not ported here. This remains an experimental candidate requiring
vehicle confirmation for the new playback and call behavior.
