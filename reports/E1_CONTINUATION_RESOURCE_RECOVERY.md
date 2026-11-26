# E1 continuation resource-recovery report

**Status:** Resource-stopped during chunk 6; E1 remains incomplete and exploratory.  
**Research decision:** `CONTINUE_BRANCH`, pending researcher review.  
**Scope:** Two continuation chunks completed; no E2–E4 or confirmation work.

## Integrity and preflight

The original stopped-run record, 20-task report, registrations, task commitments, configuration, model checkpoint, and four original checkpoints were preserved. The original evidence manifest and P0 report hashes verified. Strict parent validation reconfirmed 160 completed calls, 41,376 output tokens, 18,904 input tokens, 1,112.966 seconds, and completed chunks 0–3. The continuation received a separate immutable segment bound to the stopped parent. Its final checksum manifest verifies all segment files.

All 11 registered model files matched their hashes. The inference runtime was MLX 0.32.5, MLX Metal 0.32.5, MLX-LM 0.32.2, and tokenizers 0.23.3; Metal GPU was available. Both pinned environments passed `uv pip check`. The full automated suite reported **59 tests total: 48 passed and 11 environment-gated tests were skipped**. A no-generation load check validated all 40 registered development records, balanced 20/20 across HumanEval+ and MBPP+.

The first CLI attempt used the static eligibility audit where the runner required the registered qualified-reference artifact. It failed closed before segment creation or any model call. The supplied and registered digests were reconciled privately, the command was corrected, and the full pre-generation load check passed. This was a path-selection error, not evidence drift or a protocol change.

The offline generator received only registered prompts and seeds. Its macOS sandbox denied network access and reads from protected task/reference/evidence locations. Candidate execution continued in the pinned Linux/ARM64 restricted container. No generated code ran on the host, no output was retried, and no confirmation record or outcome was accessed.

## Continuation activity

| Scope | Tasks with complete panels | Calls started | Complete generation records | Output tokens | Input tokens | Runner elapsed at stop/checkpoint |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Preserved original run, chunks 0–3 | 20 | 160 | 160 | 41,376 | 18,904 | 1,112.966 s |
| Continuation chunk 4 | 5 | 40 | 40 | 10,005 | 5,272 | 241.531 s segment elapsed |
| Continuation chunk 5 | 5 | 40 | 40 | 11,905 | 5,952 | 560.608 s cumulative segment elapsed |
| Continuation chunk 6, partial | 0 | 14 | 13 | 6,926 | 2,347 | 732.233 s cumulative segment elapsed at stop |
| **Cumulative** | **30** | **254** | **253** | **70,212** | **32,475** | **1,845.199 s** |

The 14th chunk 6 call was interrupted and has no raw output artifact or completion record. It is retained as an unsuccessful infrastructure attempt and is not retried. Its partial input and output token consumption is unknown and excluded from the completed-record counters; generation remained bounded by the registered 768-token per-call setting. The 13 completed chunk 6 outputs are preserved, but that chunk did not reach bank freeze, selection, or evaluation. No selection or correctness result from chunk 6 is included.

Chunks 4 and 5 froze their banks, froze visible-evidence decisions before joining labels, and reached completed checkpoints. Across those two chunks, 80 candidate records were generated and 80 sealed label records were written for 10 tasks. Their correctness values were not used for adaptive selection or for this resource decision. The completed E1 scientific analyses were not recomputed because the registered 40-task population is incomplete.

## Evaluator work and model throughput

For chunks 4 and 5, the private execution artifacts contain 296 completed candidate-panel runs: 74 each for base-visible, D, full-plus, and H-only panels. They contain 53,858 case response frames across those runs. Chunk 6 has no evaluation-panel artifacts. The original report recorded 618 panel containers and 136,447 case requests; cumulative counts through the two completed continuation chunks are therefore 914 panel runs and 190,305 case responses. The 296 continuation panel runs have cleanup markers, and no registered candidate container remained after stop.

Across 93 complete continuation outputs, the median per-call generation wall time was 5.09 seconds (mean 5.61 seconds). Median prefill throughput was 997 tokens/second (range 447–1,363), and median decode throughput was 62.1 tokens/second (range 38.7–66.1). Recorded per-call peak MLX allocation reached 2.14 GB; peak model-process RSS reached 1.51 GB. The model reported GPU readiness on both completed chunks; load times were 3.64 and 15.19 seconds. Throughput slowed in the partial third chunk, but these observations do not establish the cause.

The runner's first-completed-chunk reforecast was 949.99 seconds for the remaining continuation work. After chunk 5 it was 1,131.72 seconds. Both forecasts fit the cumulative remaining wall budget; the later resource stop occurred before the registered workload was complete.

## Resource recovery and stop

The Mac was not restarted and applications were not closed, so the continuation used a new measured baseline in the same boot session. Before continuation, swap had already increased from the earlier 629.69 MiB idle samples to approximately 1.5 GiB. The runner-recorded segment baseline was pressure level 1 and 1,491.25 MiB swap. This value is retained separately from the earlier standalone preflight sample; the detailed private log records the correction.

| Observation | Pressure level | Swap used | Free memory | Other state |
| --- | ---: | ---: | ---: | --- |
| Continuation baseline | 1 | 1,491.25 MiB | 53% in nearby sample | No active model or research container; 96 GiB disk free |
| Chunk 4 checkpoint | 1 | 1,497.19 MiB | — | Five tasks complete |
| Chunk 5 checkpoint / chunk 6 start | 1 | 1,655.25 MiB | — | Ten continuation tasks complete |
| During chunk 6 | 2 | 2,653.38 MiB | 37% | Increase of about 998 MiB in 66 seconds; no candidate container active at sample |
| Stop sample | 2 | 2,645.38 MiB | 41% | Swap total had expanded to 3,072 MiB; no active candidate container |
| After cleanup | 1 | 2,645.38 MiB | 56% | No model process, evaluator worker, or container; 96 GiB disk free |

The elevated swap remained near 2.65 GiB for at least 75 seconds. We stopped before the next chunk boundary rather than wait for another chunk to start. At the last two formal chunk starts, swap had not exceeded the registered +256 MiB threshold on two consecutive samples; the stop followed the researcher's broader instruction to stop on material, persistent swap growth. The runner was interrupted during one inference call, wrote its stopped ledger, and produced a verifiable segment manifest. Its ledger's `stopped.reason` is empty because `KeyboardInterrupt` has no message; the append-only private resource record documents the reason and timing.

The observed process and container snapshots cannot identify the swap source. Docker was configured with a 12 GiB VM ceiling, but that is not a measured VM allocation. At the stop sample, Docker host-process RSS was about 76 MiB and no candidate container was active. Ollama had no model loaded. Several unrelated user applications remained open; their activity was observed, but causality was not established. The model process, Docker VM, trusted scorer allocations, accumulated system state, and other applications remain possible contributors. No resource gate was disabled or changed.

## Remaining workload and scientific scope

The 254 call starts leave 66 unstarted registered calls under the 320-call cap. The output-token cap has 175,548 tokens remaining, but the remaining call slots can produce at most 50,688 tokens under the unchanged 768-token limit. The cumulative wall cap has 1,754.801 seconds remaining. Ten registered tasks remain without complete panels: the unfinished portion of chunk 6 and all of chunk 7.

One started identity has no output, while 66 identities remain unstarted. Completing all 320 raw outputs would require 67 additional starts; that exceeds the unchanged 66-call allowance and would retry an interrupted call, which is not authorized. Continuing without a retry would leave one candidate unavailable. The researcher must prospectively resolve this before any further E1 execution. No task, input, eligibility qualification, endpoint, split, or label was changed.

No complete 40-task aggregate, candidate-pool composition analysis, verification-quality analysis, E2 feasibility estimate, or updated H1–H6 assessment is reported. The recorded cumulative total of 70,212 output tokens excludes the interrupted call; actual use may be up to 768 tokens higher. The recorded 32,475 input tokens also exclude that call. The two completed continuation chunks do not authorize selecting E2 tasks from their labels. This resource result is not a scientific no-go and does not change the research direction.

## Review required

The continuation is stopped and its segment is immutable. Before any later E1 activity, the researcher should review the resource cause uncertainty, same-session condition, missing interrupted candidate, remaining call budget, and need for a versioned segment-chain mechanism. No automatic restart, retry, E1 resume, E2–E4 intervention, or confirmation evaluation is initiated here.

## Public-data boundary

The audited source and synthetic tests are being published with this report and the versioned stop decision. The source contains SHA-256 pins for the private parent ledger, evidence manifest, registration, and reference-build tree. These hashes are non-invertible integrity commitments; publishing them reveals no task identifiers, prompts, labels, expected outputs, or run contents. They are retained to preserve the exact strict validation behavior, and this is an explicit publication decision. The underlying manifests, task commitments, raw candidate bank, candidate traces, withheld labels, model files, caches, and local diagnostics remain private. The reviewed publication set contains no credentials, personal email, or machine-specific absolute paths; continuation tests use synthetic fixtures only. No dependency substitution or standalone reuse license was added. A complete combined aggregate is intentionally absent because E1 did not finish.

## Publication-only source amendment v2

Before this milestone was published, a final scope review compared the source with the repository's existing `PUBLICATION_SCOPE.md`, which excludes private split commitments. The publication copy was therefore refactored to load the five strict parent-validation pins from required local environment variables and to fail closed when any value is absent or malformed. The five variable names and behavior are documented in [the versioned stop decision](../docs/12_e1_continuation_stop.md); the private values are not published.

This amendment supersedes the preceding paragraph's prospective statement that the embedded pins would be published. That paragraph is retained to preserve the decision chronology; it does not describe the final published tree. The refactor occurred after the run and affects only how local integrity values enter validation. It does not change run behavior or any observed result. The executed source identity remains in private evidence, and the published source is not claimed to be byte-identical to that run source. No inference, candidate execution, label join, or analysis was rerun for this publication-only change. Synthetic tests exercise missing, malformed, and valid local pin values.

The public milestone is prepared directly as a new commit whose sole parent is the verified public `main` tip. The local source branch has earlier commits containing private parent commitments, so neither that branch nor its ancestry is pushed. The public tree is assembled from the verified base tree and the seven audited files, then checked before the ref update.

The post-refactor full suite completed in the pinned scorer environment with **62 tests: 51 passed and 11 environment-gated skips**. The first run exposed one test-fixture issue: the runner-gate test had not been updated to supply synthetic local pins. The fixture was corrected and the full suite passed on rerun. A separate attempt through the default `uv run` interpreter lacked NumPy and failed during imports; this was an environment-selection error, and that output is retained in local diagnostics. The full suite was not run with candidate-container environment gates enabled, so the 11 existing skips remain explicit.
