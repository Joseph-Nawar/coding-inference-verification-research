# E1 continuation resource-stop decision v1

**Decision date:** 26 November 2026  
**Decision:** Stop the continuation and return for researcher review  
**Research status:** `CONTINUE_BRANCH`; no scientific no-go  
**Scope:** Preserve completed evidence; do not start further E1 calls until separately reviewed.

## Decision basis

The researcher authorized completion of the remaining E1 development tasks subject to stable resources, the original total caps, and the original no-retry rule. The Mac was not restarted before this continuation. The runner recorded a same-boot baseline at pressure level 1 with 1,491.25 MiB swap. The prior stopped run and all of its evidence remain unchanged.

The first two continuation chunks completed and passed their checkpoint validation. During chunk 6, swap rose from 1,655.25 MiB at 11:41:33 UTC to 2,653.38 MiB at 11:42:39 UTC, an increase of about 998 MiB in 66 seconds. It remained at that elevated level at 11:43:54 UTC. At the stop sample it was 2,645.38 MiB, with pressure level 2. The runner was interrupted before a chunk 6 checkpoint; after cleanup, pressure returned to level 1 and 56% free memory, while swap remained elevated. No active candidate container or research inference process remained.

The formal chunk-boundary rule had not yet observed two consecutive boundary samples at least 256 MiB over the registered baseline: chunk 5 and chunk 6 started at 1,497.19 and 1,655.25 MiB, respectively. The decision to stop was the conservative response to the separately authorized condition to pause when swap growth becomes material and persistent; it was made before another chunk could begin. It does not reset the resource budget or erase the earlier stop.

The evidence does not identify the source of the swap growth. The spike occurred during the E1 continuation as the runner moved from chunk 5 evaluation into chunk 6 inference. At the sampled stop, no candidate container was active; measured Docker host-process RSS was small, but this does not measure the Docker VM's complete allocation. MLX, Docker's VM, trusted host allocations, accumulated system state, and unrelated applications cannot be causally distinguished from these observations.

## Preserved workload and unresolved call

Chunks 4 and 5 added 10 completed tasks and 80 completed candidate outputs. Chunk 6 had 14 call starts and 13 complete raw outputs before interruption; its bank and panels were not frozen or evaluated. The in-flight call has no raw output artifact and will not be retried. The segment is immutable and its terminal manifest verifies.

At stop, the original 160 calls plus 94 continuation starts consumed 254 of the 320-call cap. This leaves 66 unstarted registered call identities. One additional started identity has no output, so 67 registered identities lack complete raw outputs. Completing the remaining 10 tasks without retry would leave that one candidate unavailable; retrying it would exceed the unchanged call cap. The researcher must decide how to handle this before any future E1 continuation. This decision is separate from the scientific hypotheses.

The continuation did not produce a complete registered candidate bank or full-population analysis. No new H1–H6 conclusion, E2 feasibility analysis, selector response, or E2–E4 intervention is reported. Confirmation records remain untouched. The next authorized work is a resource and continuation-protocol review, not an automatic restart or rebaseline.

## Record correction

The pinned test log reports 59 tests total, of which 48 passed and 11 environment-gated tests were skipped. An earlier pre-generation amendment described this as 59 passed plus 11 skipped; that historical record is retained, and this decision corrects the count.

## Limits and status

The cumulative run remained under the authorized 60-minute, 245,760-output-token, 320-call, one-stream, one-evaluator, and storage limits. The stop is a technical resource result, not evidence that a scientific hypothesis failed and not a termination of the research program. The historical E1 report remains the partial report it was when accepted; this decision records the later continuation separately.

## Publication-only amendment v2

**Recorded:** 26 November 2026, after the resource stop and before publication of this continuation milestone.

The first publication audit found five local integrity pins embedded in the continuation source: the stopped-parent ledger, parent evidence manifest, parent registration, reference-build tree, and checker digests. The published `PUBLICATION_SCOPE.md` says private split commitments are omitted. To conform the source to that scope, the publication copy now reads these five SHA-256 values from required local environment variables (`CIRESEARCH_E1_PARENT_LEDGER_SHA256`, `CIRESEARCH_E1_PARENT_MANIFEST_SHA256`, `CIRESEARCH_E1_PARENT_REGISTRATION_SHA256`, `CIRESEARCH_E1_REFERENCE_BUILD_SHA256`, and `CIRESEARCH_E1_CHECKER_SHA256`) and rejects missing or malformed values. No private digest value is included in the publication copy.

This is a post-run, publication-only source refactor. It changes where strict validation pins are supplied; it does not alter task data, prompts, model calls, generation parameters, evaluator behavior, candidate outputs, selection, scoring, or any result. The exact source used for the stopped run and its source identity remain in private evidence. The public source is not asserted to be the byte-identical run source. Synthetic tests cover the new local-pin loading and validation behavior; no inference or evaluation was rerun.

The safe publication history is constructed as a new commit directly on the independently verified public `main` commit. The local research branch contains earlier private parent-pin values in its ancestry; that branch and its ancestry are retained locally and are not part of the public history. The public commit's parent and complete tree are checked before advancing `main`.

The post-refactor full suite ran in the pinned scorer environment: **62 tests total, 51 passed, 11 skipped**. The first run had one fixture failure because the existing runner-gate test did not supply the newly required synthetic pins; the test fixture was updated and the full rerun passed. A separate attempted full-suite command using `uv run` selected the bare default interpreter, which lacked NumPy and failed during imports; the captured failure is retained privately, and the pinned scorer-environment command is the valid suite result. No test was silently dropped.

This amendment supersedes the prospective publication language in the earlier continuation report section that proposed publishing the embedded pin values. That earlier text remains preserved as part of the chronology; the values themselves are not published.
