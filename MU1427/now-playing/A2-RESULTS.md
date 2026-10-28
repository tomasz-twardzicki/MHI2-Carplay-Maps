# A2: completed JPEG artwork reaches the MU1427 driver

The eight N2 exports in private `Logs/A2` match build marker
`MU1427-AUDIO-N2-06af3c0b1a79` and on-disk driver size 744248. Seven contain
valid native diagnostic frames. Together they establish **seven completed
native artwork transfers with JPEG headers**, across two driver allocation
instances. This satisfies N2's native artwork-input observation gate.

All successful frames have `fault=0`. Oversize setups, setup-not-receiving
and other-signature counters remain zero. N1 reports zero bridge,
subscription and I/O failures, but still **zero cover callbacks**. The typed
cover callback cannot be the only input for this firmware's artwork adapter.
There is no need to port a raw Cinemo transport tap merely to establish
image input: the existing native completion boundary now has on-unit evidence.

The result does **not** establish successful decoding, orientation, matching
to the current track, or AID picture delivery. N2 deliberately copied no
image bytes. See [structural verification](./A2-VERIFICATION.json).

## Observations

| Export | Native instance | Associations / setups / data calls | Completed / JPEG | Latest declared/completed bytes | N1 epoch / connected / eligible |
| --- | --- | --- | --- | --- | --- |
| 01 | No native frame | — | — | — | 1 / 0 / 0 |
| 02 | A | 2 / 1 / 26 | 1 / 1 | 102882 | 2 / 1 / 1 |
| 03 | A | 3 / 2 / 57 | 2 / 2 | 125131 | 2 / 1 / 1 |
| 04 | A | 4 / 3 / 63 | 3 / 3 | 20602 | 2 / 1 / 1 |
| 05 | A | 5 / 4 / 89 | 4 / 4 | 102382 | 2 / 1 / 1 |
| 06 | A | 7 / 6 / 107 | 6 / 6 | 52065 | 2 / 1 / 1 |
| 07 | A | 7 / 6 / 107 | 6 / 6 | 52065 | 2 / 1 / 0 |
| 08 | B | 2 / 1 / 6 | 1 / 1 | 21193 | 3 / 1 / 1 |

Instances A and B have different allocation-clock pairs. Both report B4
`session=1`; that session number can restart on a new allocation. Do not
interpret the unchanged session number as the same instance. Native
allocation and DSI epoch changes establish service lifecycle activity,
without independently proving which physical reconnect action occurred.

Count each instance's last retained counters once: **9 associations,
7 setups, 113 data calls, 7 completions and 7 JPEG signatures**. PNG
signatures remain zero. Do not add every table row. Associations are not
one-to-one track counts; the extra association calls do not establish two
missing covers. The six distinct sampled latest-size values range from
20602 to 125131 bytes. One intermediate completed transfer's size is not
retained, so this is not a size range for all seven images.

Export 01 has `N2_ERROR=DEVICE_IO_1` / `snapshot_result=1`: the helper could
not open the device while N1 reported no phone connection. Exports 02–08
then succeed. This is consistent with the filesystem not being available
yet, but the helper did not export the exact open errno. It is not a JPEG
decode failure, timeout, retained-child lock or diagnostic schema failure.

N1's process-wide counters increase without restarting: the last audio
snapshot has 14 track callbacks, 25 true and 759 false property returns,
400 eligible fills and 401 writer iterations. At export 07, the connected
phone is not the eligible audio source; export 08 is eligible again. These
sampled states support source/lifecycle observation, not visual correctness
of every transition. The false-return interpretation remains the factory
cached-equality correction from [A1](./A1-RESULTS.md).

## Accompanying diagnostics

Two general diagnostic captures accompany the eight N2 exports. Their
guidance adapters report `failures=0 error=0`. The later capture records
3342 valid reader polls, 29 guidance proposals and 813 output writes.
The sampled reader states are `unavailable` then `stale`; these are not
independent evidence of broken guidance or of a continuously active route.

The later video supervisor's cumulative log contains two
`stream-timeout-fallback` events, OEM handbacks and subsequent CarPlay
activations. These can accompany disconnect tests, but the provided files
do not map them to user actions or establish their cause. Selected crash
markers (SIGSEGV/SIGILL/SIGBUS, segmentation fault, unhandled exception,
heap corruption) were not found in the supplied slog/session logs. This
bounded search is not a guarantee that no service issue occurred.

Both general summaries also report an unavailable `date` command in the
existing diagnostic collector. That is separate from N2's snapshot helper.
N2 uses monotonic allocation tokens; no wall-clock or exact test-duration
claim is made from these exports.

The user subsequently confirmed testing both Apple Music and Spotify with
no observed HMI, CarPlay text, maps or guidance issues during N2. Individual
exports have not been mapped to apps or test steps, so the video fallback
events cannot be assigned to particular user actions. Raw diagnostic logs
remain private. The capture-only review retains hashes, fixed event counts and structured
status counters, without track strings, phone identifiers or image bytes.

## Development consequence

Proceed from native counters to **bounded image extraction and decoding on
a worker**, keeping the stock artwork cursor untouched. Associate the owned
image buffer with its native allocation/session and track/transfer generation
before asynchronous work; reject superseded completions. Do not read the
stock consuming artwork API alongside its existing consumer.

Next prove decode success, dimensions/orientation and clearing on missing
covers, track changes and reconnect. A Volkswagen-specific picture provider,
valid handles/source identity and late-image refresh are still required
after that. Keep raw-stream reassembly as a fallback only if the established
native buffer cannot meet those remaining requirements.

The tested N1/N2 JAR, driver, helper and ZIP are unchanged by this review.
N2 removal still restores B4 and requires a full reboot. Remove N2 before
changing/removing guidance or using general factory restore.

Reproduce the counter review:

```sh
python3 MU1427/now-playing/review-n2-capture.py "$A2_CAPTURE" \
  --output /tmp/audio-A2-review.json
```
