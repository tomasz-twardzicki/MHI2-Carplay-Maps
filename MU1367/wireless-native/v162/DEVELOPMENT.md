# Candidate development

The runtime is isolated from the published v161 sources. Build against the exact MU1367 stock archive and pinned local QNX toolchain; `FACTORY.json` and `FIRMWARE-MEDIA-VERIFICATION.json` record the contracts. No OEM libraries or SDK files are distributed by the new build.

```sh
python3 build-components.py --tools /path/to/tools --base-package /path/to/CarPlay_Maps_VC_MU1367_791_v1.6.1.zip --output /path/to/components
python3 assemble.py --baseline /path/to/CarPlay_Maps_VC_MU1367_791_v1.6.1.zip --components /path/to/components --output /path/to/stage
```

The assembler requires the exact published stable archive. It retains the v1.5.4 transaction preimage, recognizes the previous wireless recovery generations, and creates a separate v162 snapshot controller. The new generation has 41 targets: the previous 39 plus the audio JAR and supervised wireless decoder.

Current verification is split between the fresh firmware field-table audit, host sanitizers/decoder tests, actual pinned-receiver callbacks, the factory ARM J9 dispatcher and image-worker tests, real migration/OEM controller tests, and factory-QNX flow/transaction checks. `seal.py` binds their reports, exact components, shell logic and source hashes before making the ZIP. Consult `VERIFICATION.json` for the precise tested scope; retained v161 tests are historical unless listed there.

The receiver tap captures complete 0x5001 deltas and binds a cover at its native file-session declaration ACK. Undeclared native transfers bind at their first byte. Image bytes are copied before the receiver reuses them, then written on a worker. The HMI reads bounded snapshots off the event thread and uses the factory dispatcher on the existing ASL timer. Artwork shares the established picture service and RGB PNG normalization. Wired subscriptions and the wired fetch binary retain their original path.

The priority floor preserves each selected thread's policy and higher priorities. Receiver selection is restricted to the pinned alternate sender and port 9997; the dedicated input adapter promotes its main thread and newly created threads. The receiver's existing priority-60 screen threads are preserved.

Vehicle testing must establish visible MU/AID media behavior, OEM label refresh and whether the reverse-load freeze improves. Bench tests do not establish these results.
