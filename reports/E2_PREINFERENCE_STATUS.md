# E2 pre-inference status

**Status: technical preflight complete; selector execution blocked by the registered resource gate.** No E2 responses, scores, or hypothesis evidence were generated. This is a technical pause, not a scientific NO-GO.

## Research state

E1 is closed as an incomplete exploratory stage. Its 40-task registration, 30 completed task checkpoints, 240 checkpointed candidates, 13 generation-only outputs, interrupted generation, 66 unstarted identities, resource stops, cached evaluations, E1-R reports, and prior decisions remain preserved. No E1 work was resumed. No candidate program was executed, no reference was recomputed, and no confirmation record was accessed during E2 preparation.

The E1-R findings were already observed before E2 registration and are acknowledged as exploratory evidence. E2 technical eligibility and the task sample were constructed without correctness-label fields. The final private registration freezes 24 tasks, 12 from each benchmark, the first four registered candidates per task, 96 calls, common candidate permutations, prompts, seeds, call IDs, deterministic baselines, and a balanced arm schedule. Exact membership, candidate mappings, prompts, cached traces, and private registration hashes remain local.

All six hypotheses remain unresolved. E2 has not tested H1 or H3; H2, H4, H5, and cross-model H6 also remain open.

## E1 evidence checks

The preserved E1-R worklog records that the full six-checkpoint integrity validator passed. In this phase:

- The original parent evidence manifest and continuation segment manifest were checked against their listed artifact hashes; both passed.
- The label-free technical projection matched its previously recorded digest.
- A current rerun of the full pinned parent validator was blocked before validation because its required local parent-ledger environment pin was not supplied to this shell. No pin was inferred and the validator was not bypassed.

This current revalidation limitation is preserved in the private diagnostic record and must be cleared before a later model run. The E2 preflight read only the existing six-checkpoint technical projection, completed development task prompts, cached first-four candidate/V/D records, and registered D references. It did not read confirmation records or E2 correctness labels, execute candidates, regenerate candidates, or recompute references.

## Technical eligibility and context

Twenty-seven of the 30 checkpointed tasks met the registered technical criteria: 13 HumanEval+ and 14 MBPP+. Three tasks were unavailable for E2: two could not fit all required prompts under the 8,064-token input allowance; one lacked a complete cached diagnostic panel for the registered D comparison. The D limitation also prevents a complete D baseline for that task. The 12/12 sample was selected by the label-blind hash order. No task was excluded for correctness, pool composition, difficulty, or prior selector behavior.

All prompts were rendered with the pinned local tokenizer and actual Qwen chat template, then independently recounted. No prompt was truncated. The 96-call input-token forecast is 181,478:

| Arm | Calls | Planned input tokens | Min per call | Max per call |
| --- | ---: | ---: | ---: | ---: |
| A | 24 | 23,304 | 424 | 1,796 |
| B | 24 | 25,554 | 516 | 1,890 |
| C | 24 | 59,381 | 1,085 | 4,986 |
| D | 24 | 73,239 | 1,484 | 6,143 |

Every prompt is below the 8,064-token input cap, with the registered 128-token output reserve inside the 8,192-token context. The candidate order and code are common across A–D. C uses the cached diagnostic inputs and candidate results; D adds the registered diagnostic expected outputs and actual comparator results. D is oracle-assisted and is not a deployable verification method.

## Model and information boundary

The local Qwen2.5-Coder-3B-Instruct 4-bit checkpoint revision and model-file hashes were verified during preflight; the tokenizer loaded in local-only mode. Installed MLX, mlx-metal, mlx-lm, transformers, and tokenizers package versions matched the locked versions. The MLX model was not loaded and the inference worker did not start.

The private registration binds four worker read-protected roots: E1 parent evidence, continuation evidence, benchmark data, and private E2 artifacts. The runner checks that the effective sandbox deny paths cover each root before it samples resources or verifies model files. A live synthetic sandbox probe denied reads to canaries in all four roots and denied loopback network access. The probe did not start the model worker or execute candidate code. The selector request contains only one frozen prompt, its seed, and its expected token count; it carries no task ID, candidate mapping, labels, or evaluator objects.

## Resource gate

The recorded snapshot was taken at 22:23 Cairo time on 26 November 2026:

| Measurement | Snapshot |
| --- | ---: |
| Physical memory | 16 GiB |
| Estimated available memory | 3.72 GiB |
| macOS memory-pressure level | 1 |
| Swap in use | 1,996.62 MiB |
| Free disk | 95.7 GiB |
| Foreground applications | 9 |
| Ollama processes | 1 |
| Docker Desktop | Running |
| Docker VM memory setting | 11.67 GiB |
| Running Docker containers | 0 |

The boot was recorded at 13:43:08 Cairo time on 25 November, before the required threshold of 13:45:06 Cairo time on 26 November. Unnecessary applications were still open. Docker Desktop and Ollama were active. The fresh-boot/application gate therefore failed even though measured pressure was low and disk capacity exceeded the floor. The earlier E1 resource stop remains unexplained; this snapshot is not a fresh post-stop baseline. No restart, process termination, or Docker shutdown was attempted.

## E2 activity counters

| Counter | Result |
| --- | ---: |
| Frozen selector calls | 96 |
| Model-call starts | 0 |
| Actual model input tokens | 0 |
| Generated tokens | 0 |
| Selector responses | 0 |
| Invalid responses | Not applicable; no response was generated |
| Candidate executions | 0 |
| Reference recomputations | 0 |
| E2 correctness-label joins | 0 |
| Confirmation accesses | 0 |

No condition accuracy, paired difference, baseline correctness, response validity, latency, throughput, or model-memory measurement can be reported because inference did not start.

## Commands and pinned public inputs

The final resolved public configuration is [e2-v4.yaml](../configs/e2-v4.yaml). Its SHA-256 is `1cbe5b51e76e77b8c7fa3e3d600f0d475f82a92e37af1d874bd2b710976e5440`. The inference dependency lock SHA-256 is `0cce4c3b86cafcf7c3369f423f54af27dde21a0e2e8b167bcb7d49d62c7fee54`. The protocol/amendment chain is recorded in [v1](../docs/15_E2_PROTOCOL_AMENDMENT_V1.md), [v2](../docs/16_E2_PREOUTCOME_TECHNICAL_AMENDMENT_V2.md), [v3](../docs/17_E2_PREOUTCOME_TECHNICAL_AMENDMENT_V3.md), and [v4](../docs/18_E2_PREOUTCOME_INFORMATION_BOUNDARY_AMENDMENT_V4.md).

From the repository root, the automated test command is:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py' -v
```

The label-blind preflight interface is:

```sh
PYTHONPATH=src python -m ciresearch.e2_preflight \
  --technical-view <private-label-free-technical-view> \
  --data-root <local-pinned-dataset-directory> \
  --model-root <local-pinned-model-directory> \
  --output <new-private-registration-path>
```

The private plan and all raw evidence remain outside the public repository. The selector runner must not be invoked until the local integrity pin and fresh-boot resource gates pass.

The final focused E2 suite passed **28/28 tests**. The full repository suite passed **108 tests** with **11 environment-gated Docker tests skipped**. The suite includes prompt/schema checks, task ordering and call identities, cached comparator fixtures for special oracles and tolerances, non-execution statuses, sandbox denial configuration, a live synthetic sandbox probe, a synthetic 96-call ledger using a fake model, and a check that a stale boot stops before model verification or loading. The synthetic call ledger is infrastructure coverage only; it is not an E2 model run or production inference evidence.

## Decision

E2 is prepared but not executed. Resume only with the already frozen private registration after a researcher-controlled fresh boot, closure of unnecessary applications, full pinned evidence validation, and successful resource and sandbox checks. The same 96-call schedule remains the only authorized E2 execution. E3, E4, additional E2 variants, candidate generation, and confirmation remain unauthorized.
