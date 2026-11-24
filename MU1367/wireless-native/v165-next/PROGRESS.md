# v1.6.5 development — 2026-11-23

Isolated follow-up to sealed v1.6.4-e-test1, following `research/v164-drive-review/REVIEW.md`.

| Item | Candidate result | Remaining acceptance/work |
|---|---|---|
| BT guard attachment | Lazy/resolved/mixed slots, bounded retry, race rollback, known overwrite repair and stage status implemented; pinned native QNX paths tested | BT off with healthy wireless, Wi-Fi teardown, next ignition and phone selection on the car |
| GPS | Actual health/counters, claim diagnostics and bounded source/clock qualifications implemented | Raw wireless producer and UTC contract unresolved; DIO is absent in wireless-only drives. No synthetic NMEA or forced USB service |
| Dial road | Next/current/off and GEM choices implemented on the shared guidance path; exact head/epoch/freshness/prefetch/UTF-8 checks | App-specific exits/roundabouts, wired and wireless in car |
| Artwork | Picture-server replacement retries current image; publication/identity/transfer diagnostics added | Confirm stage/server/handle path and cover appearance independently on MU/AID; no blanket wrong-cover retention |
| Main startup freeze | Ownership and native launch clocks recorded | Root cause and presentation fix unresolved; do not infer from AID PTS gaps or force foreground |
| Established stream | 40/8/150, main demand 30, timing/IDR/audio/reverse/RHD behavior retained | Compare reconnection and reverse on car |
| Recovery/diagnostics | 45-target managed candidate; v1.6.4 recognized; GPS/probe/road-label metadata archived; new traces collected | Final gates recorded in package verification; vehicle install remains pending |
| Input self-test | Released control and candidate pass after fixture cleanup and firmware sync | Prior ENOSPC evidence retained; production input unchanged |

Pre-acceptance Wi-Fi-first/last-phone arbitration, bootstrap-start resends, track-skip delay and deeper SDK jitter/link metrics remain tracked. Keep GPS off for the first comparison. A sealed local ZIP and its SHA256SUMS are the deliverable; no public upload is authorized here.
