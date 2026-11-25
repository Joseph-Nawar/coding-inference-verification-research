# 01 — Research charter

## Scientific problem
What limits the effectiveness of inference-time computation for coding language models? Under what conditions do more samples, better execution evidence or refinement yield a more correct program, and why? We aim for a consequential new mechanistic insight, method or theory-supported empirical result, not an incremental benchmark leaderboard or automatic publication.

Initial domain: short deterministic Python function synthesis and repair. Start with a 4-bit Qwen2.5-Coder-3B-Instruct MLX checkpoint, subject to preflight. Later compare a 7B sibling and independent model family if warranted. No training or human labels initially. Use exact executable task labels, not LLM-as-judge ground truth. Generalization to realistic coding agents, other languages, or all programs is not assumed.

## Competing explanations
H1: generation headroom vs behavioral identifiability vs interpretation of discriminative evidence (E1/E2).
H2: diversity/informativeness of diagnostic feedback vs amount vs repair capability (E3 then targeted follow-up).
H3: weak or invalid verification evidence and shared generator/verifier errors (E1/E4).
H4: initial code context can help or harm refinement, and its effect depends on feedback (E3).
H5: refinement can regress initially correct behavior (E3, unconditional branch on base-pass programs).
H6: relative bottlenecks change with model capability, difficulty and budget (later, two or more matched models). All are exploratory, motivated by prior work; none is a novelty claim. See hypothesis register.

## Phases and decisions
P0: source and licensing audit, hardware, evaluator contract, split planning, threat model, dependencies. P1: bounded implementation smoke, sandbox adversarial fixtures, oracle parity, generation replay, task competence and resources. STOP for review. E1: shared candidate pool and deterministic selection; E2: fixed-pool evidence interpretation; E3: repair context × feedback and regressions; E4: verification quality and dependence. Each is separately approved; E2–E4 order may change based on E1 with a documented rationale. Targeted follow-up rounds investigate competing explanations with development tasks only. Then contribution selection and focused novelty inspection, followed by an independently locked confirmation plan and final evaluation. No confirmation runs in this handoff.

## Research decisions
Technical STOP = fix or redesign, not negative evidence. Unsupported hypothesis = retain evidence, consider competing hypotheses. Inadequate model competence/ceiling = qualify different model/task setup on new smoke or reserve development tasks; log all outcomes. Pause a branch when effect is trivial, unidentifiable, already adequately explained, or unaffordable. Reconsider the program only when useful branches are exhausted or resources/evaluation constraints make a consequential contribution unrealistic. Do not optimize for significant p-values. Time-box: after E1–E4 or two targeted follow-up rounds (whichever comes first), review scientific value, remaining compute and unresolved literature before authorizing more. No guarantee of publication.
