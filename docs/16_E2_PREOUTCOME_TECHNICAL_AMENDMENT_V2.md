# E2 pre-outcome technical amendment v2

**Registered:** 26 November 2026, before E2 selector inference and before any E2 correctness-label join
**Research status:** E1 remains closed as an incomplete exploratory stage. The program remains active. H1–H6 remain untested or unresolved.

## Purpose and chronology

The v1 E2 amendment acknowledged the E1-R aggregate findings before the E2 design was frozen. During implementation-only preflight, three code defects were found before selector inference: the split reader assumed a wrapper not present in the committed split file; the baseline adapter passed presentation fields to an identity-only helper; and technical eligibility treated valid cached parse and initialization failures as missing V/D records. The initial technical attempt and its error output remain in private diagnostics as `registration-v1.json`. It is superseded and is not an E2 sample or result.

This v2 amendment records the technical corrections before any selector response, E2 outcome, or correctness-label join. It does not alter the research question, candidate bank, task membership rules, sample size, model, registered sampling parameters, correctness endpoints, or resource caps. E1-R aggregate results were already observed; the amendment does not describe them as preregistered evidence. No confirmation task or record was opened.

## Technical evidence and eligibility

The eligible source remains the six validated completed E1 checkpoints only. A separate technical projection carries the 30 checkpointed task identities, generation records, and cached V evidence; it has no correctness-label field. The E2 preparation process does not open `sealed-labels.jsonl`. It retrieves only task prompts for those completed development indices and only the registered diagnostic D references needed to prepare D. It does not use full-suite or H labels, H inputs, confirmation records, or unstarted and partial E1 tasks.

The four first candidates remain in each pool regardless of parsing or execution success. Candidate source text cached by E1 is passed as quoted source text together with its explicit parse status, including for syntax-invalid, missing-entry, or truncated candidates. Such a candidate is not treated as missing merely because it did not execute.

The model-visible B evidence contains the registered visible pass count, registered base-panel case count, all-pass flag, and explicit status:

- `complete` means the cached V panel completed and its individual case results reconcile with the summary.
- `candidate_parse_failure` means E1 did not execute the extracted candidate; the prompt states zero passes out of the registered base-panel size and marks the non-execution status.
- `initialization_exception` or `invalid_program` means the cached panel initialization failed; it is represented as zero passes out of the registered panel and the corresponding status.
- Any infrastructure failure or malformed/incomplete V record makes that task technically unavailable; it is not converted into a model failure or a zero score.

For C and D, cached ordered D request/response frames remain the source. A candidate panel that failed during initialization can legitimately contain only the cached request header and no case inputs. In that case, the common D input panel is taken from another complete cached candidate panel in the same task; the failed candidate receives an explicit initialization status and non-comparable D results for every diagnostic case. No test input or reference is reconstructed. If no cached candidate panel supplies the registered D inputs, or if any required output/reference/comparator record is malformed, that task is technically unavailable. Tasks are not excluded for correctness, pool composition, or selector difficulty.

The trusted D preparation applies the approved EvalPlus-compatible `Comparator` to cached candidate outputs in panel order. It uses validated candidate-reported post-call arguments where the registered comparator requires them, and retains input-mutation flags privately. D prompts show the approved expected D outputs and actual comparator verdicts; they do not show `args_after` or the mutation flag. Mutation-sensitive oracles remain identified separately from oracle integrity; no endpoint, task, input, label, or correctness rule is changed.

## Final prompt, ordering, and call lock

The final prompt body and shared system instruction are implemented in `ciresearch.e2_prompts` and `ciresearch.e2`. The four conditions differ only by their registered evidence fields. Candidate code and execution values remain JSON-quoted untrusted evidence. The strict parser accepts one object with exactly one integer `choice` in `1..4`; all other output is invalid and never retried.

Final prompts are counted after the pinned tokenizer applies the actual Qwen chat template. The selected task and candidate orders remain label-blind SHA-256 orders from v1. Candidate IDs map privately to displayed indices and original E1 samples. For each call, the seed remains the first 32 bits of SHA-256 over `namespace\0generation-seed-v1\0task_id\0arm\0model_revision`. The immutable call ID is SHA-256 over `namespace\0call-v1\0task_id\0arm\0seed\0prompt_sha256`. Six batches retain two tasks per benchmark and balanced cyclic arm positions. No prompt is truncated; every arm must fit within 8,064 input tokens plus the 128-token output reserve.

The preflight artifact is private and create-only. It binds the validated checkpoint sources, model-file manifest, tokenizer files, dependency lock hash, protocol hash, exact prompt hashes and counts, candidate identity mapping, selection rules, seeds, call IDs, and complete schedule. The artifact contains no correctness labels. Exact task membership, prompt text, candidate bank, diagnostic traces, reference outputs, and file-level private pins remain local.

## Inference boundary and execution

The selector uses a separate offline MLX worker. It receives one frozen prompt, one registered seed, and the expected input-token count. It does not import the evaluator, load task data, read labels, receive candidate mappings, or execute candidate code. Its environment contains no credentials, network is denied by the macOS sandbox profile, and protected E1, continuation, dataset, and E2 evidence paths are denied to the child process. The host validates the worker token count against the frozen registration, bounds output and response frames, writes each raw response before parsing, and records every call start and completion. A malformed selector response is retained and counted as invalid; infrastructure failures stop the run without retry.

The runner refuses to overwrite or resume an existing run. It validates the balanced 24-task/96-call schedule, all prompt hashes and evidence schemas, candidate maps, seeds, call IDs, context and resource caps before model startup. The existing E1 code-generation worker is unchanged. Resource snapshots are checked before startup and every four-task batch, with monitoring during inference. The resource gate requires a boot later than the accepted E1 stop, only the designated research/operating applications, no stale model or evaluation process, Docker stopped when feasible, at least 15 GiB free storage, and non-critical pressure. A swap increase of at least 256 MiB in two consecutive observations stops E2. A stop preserves raw output and ledger state; no restart or rebaseline bypass is permitted.

## Analysis and decision scope

The v1 deterministic baselines, task-level paired bootstrap plan, missingness rules, D-versus-V+D comparison, evidence-sufficiency decomposition, and conditional retrospective analyses remain unchanged. Baselines and visible evidence decisions are frozen before labels. Correctness labels may be joined only after all selector responses and deterministic choices are frozen. An incomplete selector run is not assumed missing at random; infrastructure failure is not imputed as a model error. E2 is exploratory, not a confirmatory significance test.

This amendment authorizes no E3, E4, additional E2 variant, candidate generation, or confirmation. It makes no scientific claim and does not establish or reject any hypothesis.
