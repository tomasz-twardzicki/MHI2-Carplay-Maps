# A1: N1 text display accepted on MU1427 / AID 791

On 2026-10-20 the user reported that the AID shows the correct text and
updates immediately, all controls and source switching work, and Google
Maps, the HMI and native guidance remain normal. This accepts the N1 text
display and reported coexistence for this run. The audio apps and individual
test-step mapping were not specified for A1; A0's app list is not reused as
A1 evidence.

The single private export `Logs/A1/cpmap-audio-N1-01/status.txt` matches
`MU1427-AUDIO-N1-8bbacafe81af`. [Structural verification](./A1-VERIFICATION.json)
records its hash and counters without copying the private export. The tested
N1 JAR and full-toolbox ZIP remain unchanged.

## Snapshot

| Field | Value | Interpretation |
| --- | --- | --- |
| `epoch` | 2 | DSI attachment generation at sampling; not proof of a physical reconnect sequence |
| `connected` / `context` | 1 / 1 | CarPlay connected and eligible for text output at sampling |
| `tracks` | 21 | Track callbacks counted; N1 does not separately count valid/nonempty fields |
| `ticks` / `fills` | 3531 / 735 | Factory timer activity / eligible CarPlay status fills |
| `accepted` / `rejected` | 16 / 1040 | True / false property-listener returns; see the correction below |
| `failures` / `attach_failures` / `io_failures` | 0 / 0 / 0 | No reported bridge, subscription or status-writer failures |
| `covers` | 0 | No cover callback observed; artwork remains unimplemented |
| `writes` | 672 | RAM status-writer iterations, consistent with operation beyond five minutes at its nominal one-second sleep |

N1 counters are process-wide, including across DSI attachment changes. Do
not interpret them as N0's per-epoch counters or add sampled cumulative rows.
The export contains no actual strings, exact timestamps or cluster receipts.
Display correctness and immediate updates are the user's visual observation.
Album visibility, special/missing text, Siri/call behavior, disconnect
clearing and exact startup sequences were not individually described.
The single snapshot cannot reconstruct those checks or source transitions.
The build marker does not independently fingerprint the installed JAR.

## Correction: `rejected` does not mean transport failure

The original N1 procedure described the boolean from `statusProperty` as
queue acceptance/backpressure. Exact factory inspection shows that this
interpretation was too strong:

- `AbstractBAPDataPool.getPropertyListener` selects the cached
  `SendbufferFunctionRegistryListenerAdapter`.
- Its `statusProperty` returns the result of
  `AbstractBAPDataPool.updateValueAdapterWithNewValue`. For a cached property,
  that method returns **false when the value equals the current/last valid
  value**, while a changed value updates the cache and returns true.
- The underlying `FunctionRegistryListenerAdapter.statusProperty` forwards
  to `BAPDispatcher.transmitData` and returns false even after forwarding.
  Neither boolean is a physical cluster acknowledgment.

The [host semantics probe](./test-property-semantics.py) executes the exact
converted factory classes. Its [six checks](./PROPERTY-SEMANTICS-VERIFICATION.json)
confirm equal-content suppression, changed/forced updates and a false return
after dispatch. It uses synthetic text and a dispatcher stub; it does not
exercise real transport or change the N1 payload.

Consequently, `rejected=1040` cannot be reported as 1040 failed transmissions.
Unchanged-value suppression is a verified explanation for false returns in
this factory path. This one aggregate snapshot does not classify every
return or establish their order.

There is a follow-up efficiency issue: N1 advances its remembered revision
only on true returns, so unchanged rendered text after a model revision or
source transition can cause repeated processing of an already-cached value.
Before the next Java revision, distinguish cached equality from an actual
dispatch problem and name the counters accordingly. Add integration coverage
using the factory cache behavior; the original listener mock's arbitrary
true/false responses did not establish that behavior. Do not silently replace
the accepted N1 artifact or treat every false return as successful delivery.

## Next development boundary

Keep N1 as the on-unit text baseline. Artwork still needs a native completion
observer against B4, followed by bounded image extraction and a Volkswagen
picture-provider/identity adapter. See [artwork research](./ARTWORK-RESEARCH.md).
The N1 display gate no longer blocks that work. The user has removed 5.1
audio from the scope.
The [N2 observer package](./TEST-N2.md) is now ready for that input test,
retaining the exact N1 Java baseline.

This result does not close unrelated navigation-release checks for automatic
startup or the lowered turn-card geometry. It reports normal Google Maps,
HMI and native-guidance coexistence during this audio run.

Reproduce the structural review from the repository root:

```sh
python3 MU1427/now-playing/review-n1-capture.py "$A1_CAPTURE" \
  --build MU1427-AUDIO-N1-8bbacafe81af --output /tmp/audio-A1-review.json
python3 MU1427/now-playing/test-property-semantics.py \
  --java-home "$RG_JAVA" --stock-jar "$RG_STOCK_JAR" \
  --output /tmp/audio-property-semantics.json
```
