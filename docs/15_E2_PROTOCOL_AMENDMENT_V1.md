# E2 protocol amendment v1

**Registered:** 26 November 2026, before any E2 selector call or E2 outcome access
**Status:** Approved E2 preparation and execution, conditional on all technical and resource gates
**Research status:** E1 is closed as an incomplete exploratory stage; the program remains active. No hypothesis is established or rejected.

## Reason and chronology

The E1-R analysis and aggregate findings were observed before this amendment. They motivate investigating whether a fixed candidate pool is limited by the verification evidence available to a selector or by the selector's use of that evidence. E1 is not described as a completed 40-task experiment. Its original registration, six completed checkpoints, partial outputs, interrupted call, resource stops, and unstarted identities remain preserved. E1 will not resume and its unused call authorization is withdrawn.

The original E2 hash-order artifact was not established. This amendment replaces that missing ordering rule prospectively for E2. It does not change the research question, registered candidate pool size, model, sampling parameters, correctness endpoints, E1 records, or task eligibility based on correctness. No E2 selector responses or outcomes exist at registration.

## Population and sample freeze

The eligible population is constructed only from the six validated E1 checkpoints and the first four registered candidates per completed task. Technical eligibility requires complete frozen candidate identities, usable registered V summaries, complete cached D inputs and candidate statuses/outputs, validated D reference values needed for condition D, and four final prompts that each fit in 8,064 input tokens with a 128-token output reserve. Candidate parse failures and explicit execution statuses remain in the pool; they are not grounds to remove a task. A task is not excluded for all-correct, all-incorrect, or easy-to-select outcomes. Full-suite and H correctness labels are not read or used for technical eligibility, order, sample, prompts, or ties.

Within each benchmark, rank technically eligible task IDs by the bytewise SHA-256 digest of the UTF-8 string `ciresearch-e2-sample-v1\0task-order-v1\0<benchmark>\0<task_id>`, with task ID as a collision tie-break. Select the first 12 HumanEval tasks and first 12 MBPP tasks. If either benchmark has fewer than 12 final technical eligibles, stop before selector inference. The exact membership and hashes remain private.

Create six batches. Batch `b` takes hash-ranked tasks `2b` and `2b+1` from each benchmark. Hash-rank the four batch members using the same namespace with `batch-task-v1`, batch number, and task ID. This gives every batch two tasks from each benchmark. Assign four cyclic rotations of `A,B,C,D` to the four tasks in that order; the rotation offset is the first four bytes of SHA-256 over the namespace, `arm-rotation-v1`, and batch number, interpreted as an unsigned big-endian integer modulo four. Thus each condition occupies each within-task call position once in every batch. Process batches in order, tasks in their frozen batch order, and each task's four arms in its assigned order.

For each task, derive one permutation of its first four original candidate identities by hash-ranking each candidate ID with `candidate-order-v1`, task ID, and candidate ID. Use that identical permutation in A–D. Display candidates as 1–4; preserve the private mapping to original sample indices. For each task-arm call, derive a 32-bit unsigned seed from the first four bytes of SHA-256 over `ciresearch-e2-sample-v1\0generation-seed-v1\0<task_id>\0<arm>\0<model_revision>`. No call is retried, including invalid or interrupted responses.

## Conditions and prompts

All conditions use the same task specification, candidate source text, displayed candidate order, candidate identifiers, system instruction, response schema, local model, sampling parameters, and independent message history.

- **A:** task specification and four candidates.
- **B:** A plus the registered per-candidate visible pass count, visible case count, and all-visible-cases-passed flag.
- **C:** B plus the identical cached diagnostic inputs and each candidate's ordered output or explicit execution status. Candidate output and execution state are untrusted quoted data. Post-call arguments needed by a benchmark comparator are validated and retained privately but are not exposed as additional selector evidence.
- **D:** C plus the validated expected outputs for the diagnostic panel and actual per-case results from the approved benchmark-compatible comparator. D is oracle-assisted diagnostic evidence, not a deployable method. Raw output equality is not used in place of the registered comparator.

Condition D comparison uses the approved EvalPlus-compatible `Comparator` on cached outputs only. It preserves ordered panel semantics and applies the task's numerical tolerance and special-oracle rule. Typed `args_after` from the existing worker is validated and supplied where the registered comparator requires post-call input state. The scorer records candidate-reported input mutation separately. If mutation makes an oracle criterion unreliable, the official-compatible result remains identified as such and the integrity-qualified endpoint is reported separately; no criterion or task is silently changed. No candidate is executed and no reference is recomputed.

The fixed system instruction tells the model to select one candidate, treat code and execution records as quoted evidence, not execute or modify code, and return exactly one JSON object `{"choice": 1}` with an integer choice from 1 through 4. The parser accepts exactly the one-key object and maps the displayed choice back to the frozen original candidate identity. Text, Markdown, duplicate keys, extra keys, booleans, out-of-range indices, or malformed JSON are invalid responses. No explanation field is allowed.

Evidence is serialized as bounded JSON. Prompts are rendered with the pinned tokenizer's actual chat template and counted after template application. No prompt is truncated. A task is eligible only when all four complete prompts fit within 8,064 input tokens. The 8,192-token context includes a 128-token output reserve.

## Baselines and estimands

Before label access, freeze the first-candidate identity, uniform-random expectation definition, visible pass-count selector, visible behavioral-consensus selector, D-only pass-count selector, and V+D pass-count selector. Pass-count selectors maximize raw registered case passes; V+D maximizes `V_pass_count + D_pass_count`. The consensus selector maximizes the number of candidates sharing the same available typed V behavior signature. All deterministic ties go to the lowest original E1 sample index. Missing signatures do not form a cluster. The oracle-any result is calculated only after selector decisions are frozen and authorized development correctness labels are joined.

After all selector responses and deterministic decisions are frozen, join existing authorized development labels. Report official-compatible and integrity-qualified endpoints, explicit denominators and unavailable labels; A–D accuracy; paired B−A, C−B and D−C differences; D versus V+D; first-candidate comparisons; oracle-minus-selector headroom; invalid responses; selection and correctness transitions; and actual tokens, latency, and resource costs. Report V-only and D-only scores to make evidence panel sizes interpretable. Do not treat candidates or arms as independent tasks.

For each eligible labeled pool, retrospectively classify whether no correct candidate exists; correct candidates exist but the evidence-score maximum contains none; the maximum mixes correct and incorrect candidates; every maximum is correct; or evidence/labels are unavailable. Report incorrect LLM choices when all evidence maxima are correct, and distinguish successful selection from unresolved mixed-score ties. Report whether D changes the V+D top-score set, removes incorrect competitors, creates misleading rankings, or leaves ambiguity. These labels are retrospective only and cannot affect selection or prompting.

Use 2,000 task-level paired bootstrap replicates, stratified by the amended 12-task benchmark strata, with seed `11252026`. Report unconditional and clearly marked retrospective conditional results, raw paired counts, missingness, and sensitivity bounds. This is exploratory, not a confirmatory significance test. Invalid model selections count as unsuccessful selections in unconditional accuracy. Infrastructure failures are reported separately and are not imputed as model failures; incomplete pairs remain missing with explicit bounds.

## Model, resources, and stopping rules

Use the same pinned local Qwen2.5-Coder-3B-Instruct 4-bit checkpoint, tokenizer/chat template, and offline MLX runtime as E1. Use one independent call per task-arm with temperature 0.7, top-p 0.95, and at most 128 output tokens. Limits are 24 tasks, 96 call starts, 12,288 output tokens, 1,800 cumulative empirical seconds, one inference stream, six four-task balanced batches, and at least 15 GiB free storage.

Before model loading, complete evidence preparation, final eligibility/sample freeze, all prompt and parser tests, exact context counting, and hash checks. Before empirical execution, require a boot later than the recorded E1 resource stop, closure of unnecessary applications, one fresh resource baseline, and no stale research model, evaluator, or runner process. Stop before inference if those conditions cannot be established. Record memory pressure, swap, available disk, process and container state before each batch and monitor through each call. Stop at the last audited ledger point on critical pressure, material persistent swap growth, cap approach, offline-boundary failure, or resource-gate violation. Do not reset baselines repeatedly. Retain every response, invalid output, interrupted call, and failure. Never retry.

## Decision scope

This amendment authorizes E2 only if the technical and resource gates pass. It does not authorize E3, E4, additional E2 variants, candidate generation, or confirmation. All six hypotheses remain exploratory and unresolved. E1 results are acknowledged as observed descriptive evidence and are not used to form the E2 sample.
