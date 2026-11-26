# E2 pre-inference decision record

**Date:** 26 November 2026
**Stage:** E2 preparation; selector inference not started
**Research status:** E1 is closed as incomplete exploratory work. The program remains active. H1–H6 remain unresolved.

## Decision and chronology

E2 v1 prospectively replaced the unestablished hash-order artifact with a label-blind balanced sample procedure and acknowledged the already observed E1-R aggregates. Technical amendments v2 and v3 corrected cached-failure handling and preserved cached source for candidates with registered parse failures. Amendment v4 bound the E1 parent, continuation, dataset, and private E2 roots into the private registration and made the runner reject incomplete sandbox denial lists before resource checks or model startup. Each amendment predates selector inference, E2 outcomes, and correctness-label joins. Superseded private registrations are retained separately.

During final registration verification, a reporting-only defect was found in how missing prompt counts were described. It did not affect eligibility, sample membership, prompt content, or any call identity. The reason classification was corrected, a fresh create-only registration was written, and its task sample was verified identical to the superseded registration. No protocol or scientific decision changed.

## E1 evidence preservation and verification

E1 remains closed at six of eight completed chunks: 30 checkpointed tasks, 240 checkpointed candidates, 13 generation-only outputs, one interrupted generation, and 66 unstarted identities. The original resource stop, all prior E1-R reports, the original and continuation manifests, the technical projection, and private registrations remain preserved. No candidate was executed, no reference was recomputed, no candidate was regenerated, and no confirmation record was accessed for E2 preparation.

The archived E1-R worklog records the full six-checkpoint integrity validator as passed. In this phase, the original parent evidence manifest and continuation segment manifest were independently checked against their listed artifact hashes; both checks passed. The label-free technical projection matched its previously recorded digest. A fresh invocation of the full pinned parent validator could not run because the required local parent-ledger environment pin was absent. The validator was not bypassed and no replacement pin was inferred. This limitation is retained for the next gated session.

## Label-blind E2 technical freeze

The final technical population contains 13 eligible HumanEval+ and 14 eligible MBPP+ tasks from the 30 completed E1 tasks. Three tasks are technically unavailable: two could not fit all final prompts under the registered 8,064-token input limit; one lacked a complete cached D panel needed for the registered D condition. No task was excluded for correctness, candidate-pool composition, difficulty, or selector behavior. The label-blind hash order yields a private 12/12 sample and six balanced four-task batches. Exact task membership, candidate mapping, prompts, cached traces, and private registration hashes are not published.

All 96 final prompts were rendered with the pinned local tokenizer and actual Qwen chat template, then independently recounted. No prompt was truncated. The planned total is 181,478 input tokens. Per-arm counts are:

| Condition | Calls | Input tokens | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: |
| A | 24 | 23,304 | 424 | 1,796 |
| B | 24 | 25,554 | 516 | 1,890 |
| C | 24 | 59,381 | 1,085 | 4,986 |
| D | 24 | 73,239 | 1,484 | 6,143 |

Candidate source and identity order are identical across conditions. B adds visible summaries, C adds the cached diagnostic panel, and D adds the authorized diagnostic references and actual cached comparator results. The private plan freezes candidate mappings, deterministic baselines, seeds, call IDs, and the balanced arm schedule before any E2 label join.

## Information boundary and runtime checks

The pinned model files and tokenizer were hash-checked; the tokenizer loaded locally in offline mode. Installed MLX and tokenizer package metadata matched the pinned inference lock. No MLX model load or selector worker startup occurred.

The runner requires sandbox denials to cover four registered private roots: E1 parent evidence, continuation evidence, benchmark data, and private E2 artifacts. A live synthetic sandbox probe confirmed that the profile denied read access to canaries under all four roots and denied a loopback network connection. The probe did not load a model or execute candidate code. The selector receives only the current frozen prompt, seed, and input-token count through its bounded request frame.

## Resource gate and execution decision

The resource snapshot was taken at 22:23:28 Cairo time on 26 November 2026. The machine had 16 GiB physical memory, an estimated 3.72 GiB available, memory-pressure level 1, 1,996.62 MiB swap in use, and 95.7 GiB free disk. Docker Desktop was running with about 11.67 GiB configured for its VM; the read-only Docker query found zero running containers. One Ollama process and nine foreground applications were present. The recorded boot time was 13:43:08 Cairo time on 25 November, earlier than the required post-stop boot threshold of 13:45:06 Cairo time on 26 November.

The required fresh boot and application-closure conditions were therefore not met. This is an environment/resource gate, not scientific evidence and not a program NO-GO. E2 inference was not started. There were zero model-call starts, zero actual model input or output tokens, zero selector responses, zero candidate executions, zero reference recomputations, zero correctness-label joins, and zero confirmation accesses. Response parsing and model throughput are not applicable because no response was generated.

The earlier E1 resource stop remains unexplained. The current low pressure reading does not establish resource stability because it is not a fresh post-stop baseline. No restart, application termination, or Docker shutdown was attempted by this process.

## Next authorized action

The frozen E2 sample and prompts remain ready in the private create-only registration. Before inference, a researcher-controlled fresh boot and closure of unnecessary applications are required, along with the local parent-integrity pin so the full evidence validator can be rerun. The runner must then pass its unchanged resource gate and verify the registered sandbox denials. If those gates pass, only the original 96-call E2 schedule remains authorized. E3, E4, additional E2 variants, candidate generation, and confirmation remain unauthorized.

E2 generated no scientific outcomes. H1–H6 remain unresolved.
