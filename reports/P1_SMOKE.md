# P1 smoke status

25 November 2026 · **NOT RUN** · P0 evaluator decision pending.

The P0 evaluator audit found that EvalPlus v0.3.1 rejects valid returns for a required special oracle and that its in-process comparator cannot establish label isolation. P1 stopped at its entry gate. The eight smoke tasks were fixed by the published split rule. No runner, model session, reference execution, candidate execution, replay or smoke result was produced. [P0 findings](P0_PREFLIGHT.md)

| Check or measurement | Result |
| --- | --- |
| Known-correct, known-incorrect and deliberately invalid fixtures | NOT RUN |
| Official runtime parity, special comparators and timeouts | NOT RUN |
| Runtime isolation, resource enforcement, cleanup and leakage canaries | NOT RUN |
| Stage-lock and resume validation | NOT RUN |
| Smoke tasks selected / prompted / scored | 8 / 0 / 0 |
| Model calls, input tokens, output tokens | 0 / 0 / 0 |
| Candidate submissions, runner invocations, reference executions | 0 / 0 / 0 |
| Selector calls, repair calls, cached and live replays | 0 / 0 / 0 / 0 |
| V/D/H evaluations, labels disclosed to a model | 0 / 0 |
| Confirmation access | 80 mechanical JSON decodes for ID commitments. 0 detailed inspections, prompts, predictions or evaluations. |
| E1–E4 and final-task calls | 0 |
| Competence, scoring, throughput, prefill, peak RSS/MLX memory | Unmeasured |
| Resource use | P0 host/VM/disk measurements are in the preflight. No P1 runtime or cloud computation. |

There is no measured E1 budget. The existing proposal of 320 calls, 245,760 output tokens and 480 minutes remains an unapproved ceiling. For review after a valid P1, calculate serial wall time from measured per-call prefill/load overhead, realized output length divided by measured decode rate, runner/container startup and test-suite time, plus fixed setup/cleanup and a margin for slow inputs. Estimate in balanced five-task chunks and retain the single-stream and single-worker caps. E1 remains subject to separate approval. The blocked stage provides no evidence about model competence or any hypothesis.
