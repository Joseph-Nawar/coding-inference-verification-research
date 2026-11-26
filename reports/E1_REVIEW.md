# E1 researcher review

26 November 2026. **Stopped at the registered resource gate after 20 of 40 development tasks.** Four balanced chunks completed, containing 10 tasks per benchmark and 160 candidate calls. The fifth chunk did not start. Swap grew from 954.69 MiB to 1,310.62 MiB and then 1,821.00 MiB across successive checkpoints. The stop followed the pre-outcome rule. The partial results are exploratory and have substantial uncertainty.

## Development integrity and availability

All 40 registered development records underwent the pre-generation audit. None invokes a registered mutation-sensitive or permissive special oracle. Two MBPP tasks require the official tuple input conversion. One task's reference output exceeds the validated transport limits, so its full and H-only labels are unavailable. Its visible and diagnostic panels remain available. Two further tasks have qualified reference concerns and retain official-compatible labels while being excluded from the integrity-qualified endpoint. One has a naming convention that differs from common usage, and another reference disagreed with decimal normalization on five of six valid-format cases checked. These qualifications were set before generation. The audit found 39 tasks eligible for D and 38 with usable H panels. [Experiment record](../docs/10_e1_experiment.md)

The partial run has 19 complete official-compatible eight-candidate pools and 18 integrity-qualified pools. Twenty tasks were unrun, and one additional completed task lacks full labels due to the transport limit. The integrity endpoint excludes one further completed task. No task or test was replaced or removed. Bootstrap intervals are conditional on available task labels and do not resolve the missing half of the registered population. Exact visible signatures can separate outputs that a tolerant oracle would consider equivalent.

## Candidate-pool composition

| Endpoint and pool | All correct | Mixed | All incorrect | Incomplete or unrun |
| --- | ---: | ---: | ---: | ---: |
| Official, first 4 | 8 | 7 | 4 | 21 |
| Official, first 8 | 7 | 9 | 3 | 21 |
| Integrity-qualified, first 4 | 8 | 7 | 3 | 22 |
| Integrity-qualified, first 8 | 7 | 8 | 3 | 22 |

The full-bank proportions among the 19 labeled tasks indicate a ceiling on seven tasks and mixed pools on nine. The 21 missing or unrun tasks leave the population ceiling unresolved.

## Generation and selection

### Official compatible

Each cell shows the point estimate, paired task-bootstrap 95% interval, and task denominator. Differences are percentage points.

| Metric | k=1 | k=2 | k=4 | k=8 |
| --- | --- | --- | --- | --- |
| First candidate | 47.4% [25.0%, 69.6%] · 19 | 47.4% [25.0%, 69.6%] · 19 | 47.4% [25.0%, 69.6%] · 19 | 47.4% [25.0%, 69.6%] · 19 |
| Uniform random expectation | 47.4% [25.0%, 69.6%] · 19 | 57.9% [39.5%, 76.2%] · 19 | 61.8% [43.8%, 78.8%] · 19 | 63.8% [46.7%, 79.4%] · 19 |
| V pass count | 47.4% [25.0%, 69.6%] · 19 | 63.2% [42.1%, 83.3%] · 19 | 68.4% [47.6%, 87.5%] · 19 | 68.4% [47.6%, 87.5%] · 19 |
| V behavioral consensus | 47.4% [25.0%, 69.6%] · 19 | 57.9% [35.0%, 78.9%] · 19 | 63.2% [42.1%, 83.3%] · 19 | 68.4% [47.6%, 87.5%] · 19 |
| Empirical prefix oracle | 47.4% [25.0%, 69.6%] · 19 | 73.7% [53.3%, 92.9%] · 19 | 78.9% [60.0%, 95.0%] · 19 | 84.2% [66.7%, 100.0%] · 19 |
| Unbiased pass@k | 63.8% [46.7%, 79.4%] · 19 | 75.0% [58.5%, 89.6%] · 19 | 81.9% [64.6%, 96.2%] · 19 | 84.2% [66.7%, 100.0%] · 19 |
| Oracle minus V pass count | 0.0% [0.0%, 0.0%] · 19 | 10.5% [0.0%, 26.7%] · 19 | 10.5% [0.0%, 26.7%] · 19 | 15.8% [0.0%, 34.8%] · 19 |
| Oracle minus consensus | 0.0% [0.0%, 0.0%] · 19 | 15.8% [0.0%, 35.3%] · 19 | 15.8% [0.0%, 33.4%] · 19 | 15.8% [0.0%, 34.8%] · 19 |
| V pass count minus first | 0.0% [0.0%, 0.0%] · 19 | 15.8% [0.0%, 33.3%] · 19 | 21.1% [5.0%, 40.0%] · 19 | 21.1% [5.0%, 40.0%] · 19 |
| Consensus minus first | 0.0% [0.0%, 0.0%] · 19 | 10.5% [0.0%, 26.1%] · 19 | 15.8% [0.0%, 33.3%] · 19 | 21.1% [5.0%, 40.0%] · 19 |

At k=8 by benchmark. All other benchmark estimates and intervals are in the aggregate data.

| Benchmark | First | Uniform | V pass count | V consensus | Oracle |
| --- | --- | --- | --- | --- | --- |
| humaneval | 66.7% [33.3%, 100.0%] · 9 | 75.0% [48.6%, 95.3%] · 9 | 77.8% [44.4%, 100.0%] · 9 | 77.8% [44.4%, 100.0%] · 9 | 88.9% [62.5%, 100.0%] · 9 |
| mbpp | 30.0% [0.0%, 60.0%] · 10 | 53.8% [30.2%, 77.5%] · 10 | 60.0% [28.6%, 90.0%] · 10 | 60.0% [28.6%, 90.0%] · 10 | 80.0% [50.0%, 100.0%] · 10 |

### Integrity qualified

Each cell shows the point estimate, paired task-bootstrap 95% interval, and task denominator. Differences are percentage points.

| Metric | k=1 | k=2 | k=4 | k=8 |
| --- | --- | --- | --- | --- |
| First candidate | 50.0% [27.3%, 72.7%] · 18 | 50.0% [27.3%, 72.7%] · 18 | 50.0% [27.3%, 72.7%] · 18 | 50.0% [27.3%, 72.7%] · 18 |
| Uniform random expectation | 50.0% [27.3%, 72.7%] · 18 | 61.1% [41.7%, 78.6%] · 18 | 65.3% [46.9%, 81.9%] · 18 | 66.0% [48.3%, 82.5%] · 18 |
| V pass count | 50.0% [27.3%, 72.7%] · 18 | 66.7% [45.0%, 87.5%] · 18 | 72.2% [50.0%, 91.7%] · 18 | 72.2% [50.0%, 91.7%] · 18 |
| V behavioral consensus | 50.0% [27.3%, 72.7%] · 18 | 61.1% [37.5%, 82.4%] · 18 | 66.7% [45.0%, 87.5%] · 18 | 72.2% [50.0%, 91.7%] · 18 |
| Empirical prefix oracle | 50.0% [27.3%, 72.7%] · 18 | 77.8% [57.1%, 94.7%] · 18 | 83.3% [64.7%, 100.0%] · 18 | 83.3% [64.7%, 100.0%] · 18 |
| Unbiased pass@k | 66.0% [48.3%, 82.5%] · 18 | 76.6% [59.2%, 91.7%] · 18 | 82.1% [63.9%, 97.7%] · 18 | 83.3% [64.7%, 100.0%] · 18 |
| Oracle minus V pass count | 0.0% [0.0%, 0.0%] · 18 | 11.1% [0.0%, 27.3%] · 18 | 11.1% [0.0%, 27.3%] · 18 | 11.1% [0.0%, 27.3%] · 18 |
| Oracle minus consensus | 0.0% [0.0%, 0.0%] · 18 | 16.7% [0.0%, 36.4%] · 18 | 16.7% [0.0%, 35.7%] · 18 | 11.1% [0.0%, 27.3%] · 18 |
| V pass count minus first | 0.0% [0.0%, 0.0%] · 18 | 16.7% [0.0%, 35.7%] · 18 | 22.2% [5.3%, 42.9%] · 18 | 22.2% [5.3%, 42.9%] · 18 |
| Consensus minus first | 0.0% [0.0%, 0.0%] · 18 | 11.1% [0.0%, 26.7%] · 18 | 16.7% [0.0%, 35.7%] · 18 | 22.2% [5.3%, 42.9%] · 18 |

At k=8 by benchmark. All other benchmark estimates and intervals are in the aggregate data.

| Benchmark | First | Uniform | V pass count | V consensus | Oracle |
| --- | --- | --- | --- | --- | --- |
| humaneval | 66.7% [33.3%, 100.0%] · 9 | 75.0% [48.6%, 95.3%] · 9 | 77.8% [44.4%, 100.0%] · 9 | 77.8% [44.4%, 100.0%] · 9 | 88.9% [62.5%, 100.0%] · 9 |
| mbpp | 33.3% [0.0%, 66.7%] · 9 | 56.9% [31.2%, 82.2%] · 9 | 66.7% [33.3%, 100.0%] · 9 | 66.7% [33.3%, 100.0%] · 9 | 77.8% [45.5%, 100.0%] · 9 |

The official-compatible V selector at k=8 retained correctness on all nine initially correct labeled tasks, improved four initially incorrect tasks, and left six initially incorrect. Three labeled tasks had a correct candidate in the pool that V selection missed. These are retrospective paired counts from the 19 available tasks.

## Evidence quality and failure distribution

Across 152 candidates with official Y and V labels, 17 of 55 incorrect candidates visibly passed, a false-acceptance rate of 30.9% with a paired task-bootstrap interval of 7.5–55.6%. Zero of 97 correct candidates visibly failed. Of 114 visible passes with H results, 16 failed the independently executed H-only panel, or 14.0% with interval 2.7–29.0%. The integrity-qualified endpoint has 13 of 49 false accepts and zero of 95 false rejects. Its H disagreement is 12 of 108 visible passes.

Among the completed eight-candidate pools, three visible behavior clusters contained both correct and incorrect candidates. Their sizes were 6, 6 and 8. The integrity-qualified view has two such clusters with sizes 6 and 8. Two clusters were mixed in the first four candidates. The signature is exact typed output and execution status, with unsupported or incomplete traces omitted. Cluster counts and the 189 missing signatures in the 40-task table include unrun candidates.

The 160 generated outputs included 158 parseable programs and two token-limit truncations. Four extracted-code duplicates occurred within task pools. The recorded full-panel executions had 51 incorrect visible-case outputs and 5,798 incorrect plus-case outputs across 34 candidate programs, plus 52 plus-case exceptions across two programs. Twenty-seven candidate initializations raised exceptions. These categories overlap. Eight full labels are unavailable on the large-reference-output task and seven candidate panels explicitly recorded reference unavailability. Runtime timeout counts were zero in the completed official panels. Unsupported or unavailable labels were excluded from correctness denominators.

## Resources, boundary and limitations

The run used 18,904 input and 41,376 output tokens in 160 completed calls. It ran for 1,112.97 seconds, with 729.61 seconds summed generation time. Median prefill and decode were 913.46 and 60.39 tokens/s. Peak reported MLX allocation was 2,174,428,680 bytes and peak recorded model-process RSS was 867,319,808 bytes. These are different measures. The first-chunk estimate for a complete run was 1,892.51 seconds, with 86.16 seconds of separately measured reference audit time. The resource gate, rather than the projected 60-minute limit, stopped the run.

The structural boundary audit found 618 cleaned candidate containers and 136,447 case requests across V, D, full-plus and H-only panels. Each candidate request contained its code and entry point or one case and its timer. Selection decisions were frozen before the chunk's full and withheld labels were joined. The remaining candidate bank and protected input/output traces remain local. No confirmation records or outcomes were accessed during E1. The residual worker-output spoofing limitation and benchmark contamination risk remain.

## Hypothesis portfolio and next decision

- **H1** is informed by 16 of 19 pools with at least one full-suite pass and three pools where V selection missed that opportunity at k=8. Missing tasks, model capability and evidence ambiguity remain competing explanations. E2 can hold a fixed four-candidate pool and vary available evidence.
- **H2** is not tested by this fixed panel comparison. Matched diagnostic interventions in E3 or a separately approved follow-up can distinguish feedback content from repair ability and length.
- **H3** is consistent with weak visible discrimination in some completed pools. V false acceptance and mixed clusters do not identify a cause or dependence between generator and verifier. E2 can test interpretation with valid fixed evidence. E4 can later compare discrimination and label validity.
- **H4** and **H5** require revision interventions and cannot be inferred from this candidate bank. E3's context-by-feedback and preservation panels directly measure them.
- **H6** remains open. One checkpoint and a partial task population cannot establish cross-model or task-difficulty interactions.

The most informative next investigation is **E2 after a resource-stable continuation or a prospectively registered revised setup**. Mixed first-four pools show that fixed candidate comparisons are feasible, and E2 distinguishes evidence that fails to separate candidates from evidence the model fails to interpret. The present sample and missing half are too small to settle that distinction. The system's persistent swap growth should be addressed before additional execution. E2 and any continuation require researcher authorization.
