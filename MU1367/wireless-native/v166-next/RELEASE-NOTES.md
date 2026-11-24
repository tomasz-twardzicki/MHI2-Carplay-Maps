> Development prototype: the text below was copied from sealed test2 as a baseline. It does not describe a new package. Current scope and evidence are in PROGRESS.md and CHECKPOINT.json.

# v1.6.5-e-test2

- Fix BT guard comparison against the wrong global write lookup. Use a named libc handle and the matching firmware open/write contract; retain exact-slot conflict protection and native call-through. Add global/libc/slot dladdr diagnostics.
- Add current-road publication through CurrentPositionInfo, NavSD function 19, separately from the selected TurnToInfo function 20 label. Handle independent refresh/retry and clear/OEM ownership. The cluster's visual field selection requires a car test.
- Recognize sealed v1.6.5-e-test1 for checked restore/reboot/migration into a distinct test2 recovery root. Preserve complete OEM restore and diagnostic export.
- Keep artwork/media/decoder, stream timing tap, MOST bridge, supervisor and main-screen support bytes unchanged. Test1 artwork is vehicle-confirmed on both displays. Retain 40/8/150 and native main demand 30.

Not claimed fixed: stale-phone paging before acceptance, long reconnect, startup/reconnect gaps, MU-only startup freeze or wireless vehicle GPS. The repeated queue reset evidence is retained for a separate timing investigation. Physical BT-off survival and the visible dial/middle label split remain acceptance tests.

The input fixture again exposed ENOSPC on its 32 MB RAM disk despite cleanup; test2 uses the transaction fixture's 64 MB capacity for the sequential 16.8 MB rings. Real control/candidate assertions and production input bytes are retained. Bench tests do not substitute for radio, MOST or physical display validation. This package is local and experimental; no public upload.
