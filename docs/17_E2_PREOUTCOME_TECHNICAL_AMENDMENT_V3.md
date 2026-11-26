# E2 pre-outcome technical amendment v3

**Registered:** 26 November 2026, before E2 selector inference, E2 outcome access, and correctness-label joins
**Status:** E2 remains conditionally authorized; model inference is still gated on a verified fresh boot and stable resource baseline.
**Research status:** E1 remains closed as an incomplete exploratory stage. The program remains active. H1–H6 remain unresolved.

## Reason and chronology

The E1-R findings were already observed before E2 registration. Amendment v1 recorded that history and established the new label-blind hash-order rule. Amendment v2 recorded corrections to the split reader, deterministic-baseline adapter, and technical treatment of cached parse and initialization failures. During a subsequent code-to-protocol audit, the implementation was found to set the cached extracted source to `null` whenever a candidate had a non-`ok` parse status, even though E1 had retained source strings for the registered `invalid_syntax`, `missing_entry`, and `truncated` outcomes. This made those otherwise represented candidates invalidate prompts and could incorrectly reduce technical eligibility.

This amendment corrects that implementation defect before any E2 selector call, E2 outcome, or correctness-label join. The original private preflight artifacts `registration-v1.json` and `registration-v2.json` remain unchanged and are superseded; neither is the final E2 registration. The final private registration uses schema `ciresearch-e2-private-registration.v2` and binds this amendment, the resolved E2 configuration, the dependency lock, model-file manifest, tokenizer files, frozen prompts, and call schedule by SHA-256.

## Candidate-source handling

For each of the first four registered E1 candidates, preflight now requires the cached E1 code record to agree with the immutable candidate parse status and to contain a source string. The same cached source string is included in every A–D prompt, quoted as untrusted data, with its explicit parse status. This applies to `ok`, `invalid_syntax`, `missing_entry`, and `truncated` records. No candidate is repaired, re-extracted, regenerated, retried, or executed. If a cached source string or matching parse record is absent or malformed, that task is technically unavailable and the reason is retained; the source is never synthesized.

The prompt builder therefore receives the same four registered candidate identities in all conditions, including candidates whose E1 parse or execution failed. The parse status and cached visible/diagnostic execution statuses remain explicit. This may increase the technical eligible population compared with the superseded preflight artifacts, but cannot alter the registered task order, candidate pool, correctness endpoint, or selection rules. Sample construction is rerun from scratch using only the final label-free technical eligibility view and actual tokenizer counts.

## Unchanged E2 protocol

Amendments v1 and v2 remain in force except where this document records the candidate-source correction. The sample remains 12 HumanEval+ and 12 MBPP+ tasks selected by the registered SHA-256 technical hash order, from the six validated E1 checkpoints only. Eligibility does not use full-suite or H correctness labels and does not depend on whether a pool is all-correct, mixed, all-incorrect, or easy to select. Candidate ordering, per-call seeds, balanced batches, arm schedule, prompt schema, output parser, model, sampling settings, endpoints, analysis plan, and all resource caps remain unchanged.

Conditions A–D continue to receive only the evidence authorized for that condition. The selector worker receives only a frozen prompt, seed, and token count. Confirmation records and protected task data remain outside the workflow. No selector response or correctness label has been accessed at registration time.

## Decision scope

This is a pre-outcome implementation correction needed to honor the previously approved E2 population and evidence rules. It is not an outcome-driven eligibility change, scientific hypothesis revision, or new experiment. E2 inference remains blocked until the separately registered fresh-boot, application-closure, stale-process, Docker, disk, and memory-pressure gates pass. No E3, E4, additional E2 variant, candidate generation, or confirmation is authorized.
