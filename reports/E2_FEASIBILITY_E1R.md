# E2 Feasibility Assessment from E1-R

**Status:** Technical feasibility and retrospective composition only. No E2 selector calls were made, no candidate code was executed, and no confirmation records were accessed.

## Technical-only eligibility freeze

The assessment was computed from the frozen first-four candidate bank, visible-test summaries, cached diagnostic-panel records, registered prompts and tokenizer. It did not use full-suite or H labels to form eligibility. The eligibility artifact was frozen before the retrospective label join.

| Technical measure | Count |
| --- | ---: |
| Complete first-four pools | 30 |
| Pools with usable visible-test summaries | 30 |
| Pools with usable cached D evidence | 29 |
| Pools fitting all A–D size proxies | 28 |
| E2-eligible pools | 28 |
| Eligible HumanEval pools | 13 |
| Eligible MBPP pools | 15 |

One pool lacked usable D evidence. One additional pool had D input above the 8,064-token input budget after reserving 128 output tokens within the model's 8,192-token context. No tasks were removed from E1; these counts describe potential E2 eligibility only.

Cached D diagnostics contain ordered candidate outputs and execution statuses. Candidate initialization exceptions are retained as typed statuses and count as available recorded diagnostic evidence; they are not silently recast as missing outputs. The technical parser accepts only bounded wire representations and never deserializes candidate objects.

## Context-size proxy

The proxy uses the local pinned tokenizer and a generic selector message over task text, first-four code, V summaries, cached D inputs/outputs/statuses, plus expected D outputs and placeholder comparison booleans for condition D. It measures approximate prompt size; it is not the final E2 prompt and does not prove runtime context fit after a future prompt is frozen.

| Condition | Pools measured | Median input tokens | 95th percentile | Maximum | Fit with 128 output-token reserve |
| --- | ---: | ---: | ---: | ---: | ---: |
| A: task and candidates | 30 | 796 | 1,387 | 2,301 | 30 |
| B: A plus V outcomes | 30 | 832 | 1,423 | 2,337 | 30 |
| C: B plus D inputs and observed outputs/status | 29 | 1,989 | 5,847 | 8,023 | 29 |
| D: C plus reference values and comparison fields | 29 | 2,196 | 6,887 | 9,914 | 28 |

The model context cap is 8,192 tokens; the usable input allowance under the registered 128-token response reserve is 8,064. All 28 technically eligible pools fit the proxy in every condition. One other pool's D prompt does not fit; another has no usable D panel. C is close to the limit at its largest measured eligible-sized prompt. A final registered prompt can change these lengths and must be retested before calls.

The feasibility pass loads tokenizer metadata only. It does not load model weights or invoke inference. The existing generation worker has a code-generation system prompt and cannot faithfully serve as a selector without a versioned prompt mode, strict index-only response parser, and tests.

## Retrospective first-four composition

Correctness outcomes were joined only after the technical eligible set was frozen. The counts below are descriptive and were not used to select future tasks.

| Endpoint | All four correct | Mixed | All four incorrect | Incomplete |
| --- | ---: | ---: | ---: | ---: |
| Official-compatible | 11 | 11 | 6 | 0 |
| Integrity-qualified | 11 | 11 | 5 | 1 |

All 28 eligible pools have complete official first-four labels. One has incomplete integrity-qualified first-four labels. Among the 22 pools with a known correct candidate, the frozen visible pass-count selector selected an incorrect candidate in 2 tasks; visible consensus did so in 4. Those retrospective misses motivate the evidence-versus-interpretation question, but they are not valid E2 inclusion criteria.

The eligible pools show one, two, three or four distinct cached D behavior signatures in 13, 9, 5 and 1 tasks, respectively. A signature count is not correctness: valid alternative outputs and task-specific special oracles can make output differences harmless, and unavailable representations remain unavailable.

## Registered sample and cost

The current E2 protocol specifies the first 24 eligible development tasks in a prelocked hash order, ideally 12 per benchmark. No such E2 ordering artifact exists in the E1 registration or public protocol. Although the technical pool contains 13 HumanEval and 15 MBPP tasks, no sample was constructed here.

A prospective amendment should freeze a label-blind hash order and exact 12/12 selection before any selector call, along with one prompt skeleton, candidate order, output schema, invalid-response handling, context rule and call schedule. The all-four-arm context should be rechecked after the final prompt is fixed. No outcome-driven task selection is appropriate.

At 24 tasks, the original design requires 96 calls and permits at most 12,288 output tokens. For a balanced 12/12 sample, the four-arm prompt-input proxy has an expected total of about 161,160 tokens; the combinatorial subset range is 136,206–173,961. Using measured E1 median prefill/decode throughput gives about 168 seconds of prefill and up to 200 seconds of decoding at the output cap, or roughly 6.1 minutes of token work before model startup, call overhead, evaluation and resource variance. This is a throughput projection, not a measured E2 runtime.

The previous E1 continuation stopped after sustained swap growth. A fresh host/resource preflight is a prerequisite for any later inference phase.

## Recommendation

E2 is technically plausible on 28 tasks, enough for the registered 24-task cap and balanced design. It has the highest immediate information value for H1/H3 because it can compare evidence availability with interpretation while holding the candidate bank fixed. E1-R does not authorize E2. Before any E2 run, the researcher should approve a prospective amendment for the missing hash order and selector prompt implementation, then separately authorize execution.
