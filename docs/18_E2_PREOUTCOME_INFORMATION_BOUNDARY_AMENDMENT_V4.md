# E2 pre-outcome information-boundary amendment v4

**Registered:** 26 November 2026, before E2 selector inference, E2 outcome access, and correctness-label joins
**Status:** E2 remains conditionally authorized; the fresh-boot and resource gate is currently unsatisfied.
**Research status:** E1 remains closed as an incomplete exploratory stage. The research program remains active; H1–H6 remain unresolved.

## Reason and chronology

During a final pre-inference security audit after technical amendment v3, the runner was found to accept operator-supplied sandbox read-denial paths without checking that they covered the private E1 parent evidence, continuation evidence, benchmark data, and E2 registration/evidence root. The selector receives only a frozen prompt over a bounded pipe, but an incomplete deny list could leave protected files readable by its worker process. No selector worker or model was started, no E2 call was made, and no E2 correctness label was joined before this finding.

This amendment makes the protected roots part of the private frozen registration and requires the runner to prove that the effective sandbox deny paths cover every registered root before it samples resources, verifies model files, or starts a worker. The local roots are not published. The registered roots are the resolved E1 parent, E1 continuation, dataset, and private E2 evidence directories. Any missing, unresolved, duplicate, overlapping-with-model, or insufficient denial fails closed. The private registration schema advances to `ciresearch-e2-private-registration.v3`; earlier private registrations remain preserved and superseded.

## Information boundary

The selector child receives exactly one frozen task-arm prompt, its deterministic seed, and its registered token count through a bounded JSON request. It receives no task ID, candidate identity map, evaluator object, label record, reference implementation, confirmation manifest, or filesystem path as request data. Its environment is offline and contains no credentials. The macOS sandbox denies network access and read access under each registered protected root. A denied root may be covered by an equal or ancestor sandbox denial path; a denial below a protected root does not count as coverage. A denial that would also hide the pinned model is rejected.

The E2 private root is denied so the child cannot read the frozen registration, other tasks' prompts, candidate banks, traces, or future call responses. The E1 roots and dataset root are denied so it cannot read existing correctness labels, expected outputs, task archives, split records, or reference code from disk. Authorized evidence for the current condition is supplied only inside the current prompt. The host supervisor retains the mapping needed to turn the index-only response into a frozen candidate identity.

This is an inference-worker boundary, not candidate-code containment. E2 does not execute candidate code. The previously validated E1 candidate execution sandbox remains unchanged.

## Unchanged E2 design

Amendments v1–v3 remain in force. The correction does not alter the 12/12 label-blind sample rule, first-four candidate pool, A–D evidence, model, sampling parameters, parser, tie-breaking, endpoints, analysis, caps, or scientific questions. Exact prompts and call identities remain private and are frozen only after final technical eligibility and actual tokenizer counts. The model remains unloaded until the fresh-boot, application-closure, stale-process, Docker, disk, and memory gates pass.

## Decision scope

This is a prospective implementation and containment correction required to satisfy the approved information boundary. It is not an outcome-driven change or scientific-direction change. It authorizes only the originally specified E2, conditional on all technical and resource gates. It does not authorize E3, E4, another E2 variant, candidate generation, or confirmation.
