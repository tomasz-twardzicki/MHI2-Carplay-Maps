# MU1367 native progress compared with LuKa's Audi implementation

Reviewed November 2, 2026, after preparing the R2 diagnostic package. Reference:
[`luka-dev/mib2q-carplay-rgi`, `df73e061a29c4d996550716987f42a9243daa09a`](https://github.com/luka-dev/mib2q-carplay-rgi/tree/df73e061a29c4d996550716987f42a9243daa09a).
Earlier repository research covered LuKa's artwork architecture; it did not
establish a playback-progress comparison for the R1/R2 work.

## Progress path

LuKa's
[CarplayDSILifecycleController](https://github.com/luka-dev/mib2q-carplay-rgi/blob/df73e061a29c4d996550716987f42a9243daa09a/java_patch/de/audi/app/terminalmode/dsi/carplay/CarplayDSILifecycleController.java#L770)
receives the same `DSICarplay` callbacks used by our bridge. It divides both
position and duration by 1000, caches duration from now-playing metadata, and
suppresses unchanged position events. There is no estimated playback clock in
this path.

The
[terminal-mode listener](https://github.com/luka-dev/mib2q-carplay-rgi/blob/df73e061a29c4d996550716987f42a9243daa09a/java_patch/de/audi/app/terminalmode/combi/TerminalModeBapCombi.java#L321)
passes seconds to Audi's `CombiBAPServiceTerminalMode`. The
[audio connector](https://github.com/luka-dev/mib2q-carplay-rgi/blob/df73e061a29c4d996550716987f42a9243daa09a/java_patch/de/audi/app/combi/bap/app/audio/AppConnectorTerminalMode.java#L92)
checks terminal-mode audio focus, fills `PlayPosition_Status.timePosition`,
`totalPlayTime` and `attributes.variableBitRateActive`, and calls
`getBAPFunctionPropertyFSG(52).sendStatusIfChanged(...)`.

The upstream
[stock MU1316 connector decompilation](https://github.com/luka-dev/mib2q-carplay-rgi/blob/df73e061a29c4d996550716987f42a9243daa09a/docs/sources/research/mhi2-port/java/MU1316/de/audi/app/combi/bap/app/audio/AppConnectorTerminalMode.java#L66)
already contains those assignments and the function-52 send. This is an existing
Audi progress path, rather than an added progress renderer.

| Detail | Audi reference | MU1367 R1/R2 |
| --- | --- | --- |
| Input | Native position callback and metadata duration | Same callback and duration fields |
| Units | Milliseconds divided by 1000 | Same conversion |
| Function | AudioSD 52 / `0x34` | Same function |
| Valid track | Elapsed seconds and total seconds | Same two numeric quantities |
| Focus | Audi terminal-mode audio focus | CarPlay connection and VW audio component 6 |
| Registration | Stock Audi property/connector | Added stage and advertised capability; factory VW pool omits the stage |
| Unknown duration | Both time values `65535` / `0xFFFF` | Both zero; needs separate VW semantics investigation |
| Transport | Audi BAP FSG framework | VW `mqbab2` pool, serializer, marshaller and DSI proxy |

The field comparison does **not** establish identical Audi/VW wire serialization:
the Audi serializer implementation was not part of this comparison. MU1367's
factory serializer produces six bytes, verified in our host and factory J9
tests. R2 observes the numeric values at its actual DSI boundary.

The unknown-time difference cannot explain absent progress when both received
values are valid and nonzero. It should be resolved independently before claiming
correct unknown-duration rendering. No runtime change was made on that basis.

Audi's working display is a useful reference for native progress. It does not
establish function acceptance or rendering on VW AID 791. The remaining questions
are native acceptance, capability/source negotiation and cluster rendering.
R1's local counters do not distinguish those; R2 adds DSI payload and native
callback evidence. No metadata time fallback is proposed.

## Artwork relevance

LuKa's
[artwork pipeline](https://github.com/luka-dev/mib2q-carplay-rgi/blob/df73e061a29c4d996550716987f42a9243daa09a/docs/altscreen-and-video/COVER_ART_PIPELINE.md)
assembles raw transfers, decodes on a worker, then notifies Java over its bus.
Our implementation polls the captured native image through a supervised fetch
process. This is a concrete architectural difference to investigate if R2 shows
significant time between image availability and publication. The comparison
does not measure the delay on either vehicle or identify Ottocast as its cause.

The pinned
[Audi connector](https://github.com/luka-dev/mib2q-carplay-rgi/blob/df73e061a29c4d996550716987f42a9243daa09a/java_patch/de/audi/app/combi/bap/app/audio/AppConnectorTerminalMode.java#L64)
also pushes artwork proactively. Our existing bridge already does that after
accepting the current handle, so proactive publication is not a missing feature
that needs to be copied. Picture-source identifiers differ and must remain
specific to the matching firmware.

This comparison changes documentation only. The delivered R2 ZIP, its runtime
pin and verification evidence remain unchanged.
