# P0/P1 researcher review v1

25 November 2026 · **TECHNICAL_BLOCKED** · Stop for researcher review.

## P0 recovery and P1 status

The existing P0 commit and evidence were verified before recovery. Seven tracked deliverables and 155 private evidence files matched their original manifests. The recovery uses a new evidence directory. The evaluator comparison reproduced the bookkeeping fix and showed that the proposed broad revision also changes a correctness verdict under its default timeout. The two-line release-based correction is proposed for approval. The issue affecting the canonical reference remains open upstream and outside this recovery's benchmark access. [Version decision, source hashes and regression results](EVALPLUS_DECISION_V1.md)

| Check | Result |
| --- | --- |
| Official checker diagnostics on independent synthetic inputs | 51/51 expected verdict and detail assertions across three pinned sources |
| Initial synthetic environment probe | Failed on inactive tunnel interface names. Outputs retained. The corrected check verified the interface flags and empty IPv4 route table. |
| Synthetic containment | Three ARM64 fixture containers completed. Docker inspection verified the resource settings, no mounts, network mode, read-only root and user. Runtime verified only loopback was up, tmpfs and root writes behaved as expected, the socket was absent, effective capabilities were empty, and seccomp and no-new-privileges were active. All fixture containers were removed by ID. |
| Production candidate isolation and separated scorer | Gated. The fixture uses authored synthetic inputs and the stock checker within its dedicated container. It does not establish label isolation for candidate execution. |
| Separated scorer parity, smoke-task parity, malformed wire responses, output flooding, supervisor expiry and leakage canaries | NOT RUN |
| Full evaluator lock and runtime | NOT RUN. The synthetic checker has its own two-wheel hash lock. |
| P1 local model, tokenizer and offline runtime | NOT RUN. Existing P0 source and metadata pins are preserved. |
| Model calls and tokens | 0 calls, 0 input tokens, 0 output tokens |
| Empirical executions and protected access | 0 generated executions, 0 reference executions, 0 benchmark evaluations, 0 confirmation record reads or outcomes in this recovery |
| E1–E4 | NOT RUN |

The isolated diagnostic accepts only the authored fixture program in its pinned build, runs one container at a time, inspects configuration before starting, and records bounded output and cleanup. It is distinct from the separated architecture required for P1. That architecture will need a worker with candidate code and only the input for the current invocation, preserving function state across a panel. The trusted side will need to hold expected outputs and comparison code, validate bounded typed response data, and handle mutation-sensitive comparisons and unsupported types explicitly. Production label canaries and comparator parity are still required. [Reproduction guide](../docs/08_evalplus_regression.md) · [Security contract](../docs/04_security.md)

## Resource measurements and E1

The completed three-source synthetic run took 4.73 seconds wall time. The host launcher peak RSS was 30,752,768 bytes. That excludes Docker VM and contained process memory. The base-layer manifest declared 45,068,039 compressed bytes and the two wheel files total 14,298,006 bytes. The two additional EvalPlus archives were less than 2 MiB combined. These sizes exclude HTTP overhead and Docker build cache. At the reported follow-up the project and Docker host volumes had 102,897,572 KiB and 177,855,324 KiB free. P1 inference speed, scorer overhead, MLX allocation, competence and P1 total cost remain unmeasured.

Keep the proposed E1 scope at 40 development tasks and eight independent candidates per task, serially in balanced five-task chunks after valid P1 measurement and separate authorization. The original ceilings are 320 calls, 245,760 output tokens and 480 minutes. They are planning limits. A throughput-based estimate needs P1 prefill/decode rates, realized output lengths, scorer overhead and memory measurements.

## Decision chronology

1. Verified and preserved the original P0 history and hashes. The researcher approved auditing an alternate revision, conditionally continuing to P1, and independently publishing safe materials.
2. Checked issue metadata, source history and source hashes. Built a synthetic image using the already proposed ARM64 base digest and separately pinned fixture dependencies.
3. Preserved the initial fixture-environment failure, corrected the network observation without changing restrictions, and reran the fixed synthetic suite. The broad revision was declined because of demonstrated timeout drift. No empirical outcomes preceded that decision.
4. Recorded the narrow release-based proposal. P1 remains gated on researcher approval, a validated dependency build, implementation of the separate label boundary and passing parity and containment checks.
5. Prepared a separate publication history because the preserved local P0 history contains a machine-specific commit identity and information that would permit reconstruction of the sealed split. The public snapshot removes such material and includes reproduction instructions for the synthetic diagnostic. Public files exclude protected data and raw evidence.

The six hypotheses remain untested. The outstanding decision is whether to approve the narrow checker amendment and resume the P1 engineering gates. The reported upstream issue needs its own decision before any future confirmatory lock.
