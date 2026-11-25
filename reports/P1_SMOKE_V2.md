# P1 engineering smoke v2

25 November 2026. **COMPLETE.** The eight registered smoke tasks were run after the approved evaluator amendment, separate-scoring parity, containment checks, local artifact verification, and offline MLX preflight passed. This is an engineering validation on a small fixed population. The six scientific hypotheses remain untested.

## Exact activity and outcomes

| Measurement | Observed |
| --- | ---: |
| Registered smoke tasks | 8 |
| Ordinary generation calls | 16 |
| Live seed replay calls | 1 |
| Selector or repair calls | 0 |
| Total started and completed calls | 17 / 17 |
| Total actual input tokens | 2,013 |
| Total actual output tokens | 5,225 |
| Ordinary input / output tokens | 1,782 / 4,733 |
| Valid / syntax-invalid ordinary responses | 15 / 1 |
| Ordinary responses stopped at EOS / token cap | 16 / 0 |
| Full official-compatible passes | 14 of 16 |
| Tasks with a full pass | 8 of 8 |
| Candidate panel invocations / individual executions | 30 / 6,057 |
| Trusted reference panels / cases | 16 / 3,505 |
| Successful returns / ordinary candidate exceptions / case timeouts | 5,109 / 948 / 0 |
| Empirical infrastructure failures | 0 |
| E1–E4 / confirmation evaluations | 0 / 0 |

The two nonpassing ordinary candidates included one syntax-invalid response and one evaluated response whose cases raised exceptions. The unsuccessful outputs and scoring evidence remain local. The replay is separate from the 16 candidate results. Re-extracting the cached output returned the same extraction. A live replay of the first call matched its text and token IDs. This measures a single seed replay on this runtime.

## Provenance, isolation and resources

The local checkpoint revision was `3dd939c621c08e5753d5b89f35a2642cd83b98ca`. All 11 files matched the pinned tree, including the 1,736,293,090-byte safetensors file at SHA-256 `d448aef7ea541ec604ec05f6aef13b80a0017c6cc7acb9261a005e0358995db9`. The tokenizer and local Qwen2 4-bit config passed verification. MLX 0.32.5, MLX Metal 0.32.5 and MLX-LM 0.32.2 loaded on `Device(gpu, 0)` in the offline subprocess. Runtime preflight load took 9.20 seconds. The subsequent smoke run recorded a 3.05-second model load. An initial Metal wheel retrieval stalled and a segmented attempt received partial responses. The exact locked macOS ARM64 wheel was reconstructed from verified ranges, hashed and installed offline. There were no model or dependency substitutions.

| Resource | Observed |
| --- | ---: |
| P1 ledger wall / command wall including setup | 118.07 s / 122.35 s |
| All inference-call wall / ordinary generation wall | 91.90 s / 83.47 s |
| Median MLX prefill / decode throughput | 962.62 / 59.85 tokens/s |
| Evaluator wall inclusive of references | 22.49 s |
| Median candidate evaluation wall | 1.59 s |
| Peak MLX allocation | 2,140,972,312 bytes |
| Peak recorded model process RSS | 1,773,338,624 bytes |
| Free project storage at post-run check | 100,550,668 KiB |

MLX memory and process RSS are separate measures. macOS reported 513.19 MiB of swap use at sampled times during and after P1, with no observed growth across those samples, and reported warning-level memory pressure at the final snapshot. An earlier recovery snapshot showed zero swap. Attribution and continuous peak system swap were unmeasured. P1 ran with one inference stream and one evaluator worker. Model sampling was offline throughout.

All generation was frozen before scoring. The production audit checked that candidate requests had only the source/entry or current-case/timer envelope. It also checked that empirical reference requests carried zero candidate bodies and that all 46 candidate and reference containers recorded cleanup, with no remaining runner containers. No confirmation records were decoded or outputs inspected. Archive hash validation and a smoke-only raw-line scan were used for the allowlist. [Containment and parity](P0_RECOVERY_V2.md)

## Proposed E1 budget for researcher review

The proposed scope is 40 development tasks, eight candidate generations each, one inference stream and one evaluator worker. Scaling the 16 ordinary P1 samples to 320 gives about **35.3 minutes serial wall time** before contingency, comprising about 27.8 minutes for generation and 7.5 for scoring and reference overhead. The same scaling projects 35,640 input tokens and 94,660 output tokens. The estimate uses realized P1 lengths and includes the reference overhead observed at two candidates per task. Development test counts and output lengths can differ.

Propose **60 minutes wall time** with the existing hard limits of 320 calls, 245,760 output tokens and 768 output tokens per candidate. Use balanced five-task chunks, remeasure after the first chunk, and check macOS pressure and swap before each chunk. Retain the 15 GiB free-storage floor. If resources or parity fail, stop at the last audited partial ledger. Researcher authorization is required before E1. No E1–E4 activity started.
