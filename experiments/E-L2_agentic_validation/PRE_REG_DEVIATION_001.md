# Pre-Registration Deviation #001 — E-L2 V2

**Date:** 2026-05-04
**Original protocol:** PHASE1_PROTOCOL_V2_ALIGNED_3LAYER.md §3
**Authorization:** Supervisor approval ("Kombinasi A") on 2026-05-04 after E-L2 V1 negative result (κ=0.362)

## What changed

| Aspect | V1 (original pre-reg) | V2 (this deviation) | Justification |
|---|---|---|---|
| Prompt template | `prompt_template.md` (vague tier definitions) | `prompt_template_v2.md` (concrete numeric thresholds + decision tree pseudocode + 4 worked examples + explicit anti-overcall rule) | V1 root-cause analysis identified prompt ambiguity as primary failure mode (Critical over-prediction, mid-tier confusion) |
| `num_predict` | 500 | 800 | qwen3.5 produced empty content for 58/125 cases under V1; root cause is `think=False` not respected on this LLM, content gets pushed past num_predict budget. Increasing budget mitigates without disabling thinking |
| Composite GT formula | unchanged | unchanged | GT remains frozen — only LLM-side prompt + token budget changes |
| Sample design (25 machines × 5 windows = 125) | unchanged | unchanged | Same evaluation set for direct comparison |
| LLM ensemble (4 models) | unchanged | unchanged | Supervisor did not authorise dropping qwen3.5 |
| Aggregation (majority vote, tie→highest) | unchanged | unchanged | |
| Metrics (QW-Kappa primary, threshold 0.6) | unchanged | unchanged | Same primary metric, same halt threshold |
| Halt rule (κ < 0.6 → STOP) | unchanged | unchanged | Same stop criterion |

## What was NOT changed (preserves pre-registration integrity)

- The composite GT formula (Lei 2018 + ISO 13374-2 mapping)
- The 125 evaluation cases (deterministic SEED=42)
- The primary metric (Quadratic-Weighted Kappa)
- The pre-registered halt threshold (κ ≥ 0.6 to proceed to Layer 3)
- The 4-LLM ensemble composition

## Why this is a methodologically defensible deviation

1. **Single revision, documented pre-execution**: only the prompt + token budget change, all other variables held constant
2. **Same primary metric + threshold preserved**: V2 must clear the same κ ≥ 0.6 bar; we are not lowering goalposts
3. **Cache separation**: V2 uses fresh cache namespace (`llm_cache_v2/`), V1 cache preserved for archive
4. **Honest reporting**: this deviation document accompanies V2 results in the thesis appendix
5. **Halt rule preserved**: if V2 also yields κ < 0.6, we will stop and not proceed to Layer 3 without further supervisor authorization

## Risk acknowledgement

- Defense panel may critique this as "trying again until it works" — but the singular nature of the change (prompt only) and unchanged threshold makes this defensible as engineering iteration, not p-hacking.
- If V2 succeeds, both V1 and V2 results will be reported in the thesis with full transparency.
- If V2 also fails, recommendation will be Option F (defer Layer 3 as future work).

## Cache & artifact preservation

V1 artifacts preserved:
- `metrics.json`, `raw_results.json`, `per_case_predictions.csv`, `STATISTICAL_REPORT.md`, `prompt_template.md`, `llm_cache/` (V1 LLM responses)

V2 will produce:
- `metrics_v2.json`, `raw_results_v2.json`, `per_case_predictions_v2.csv`, `STATISTICAL_REPORT_v2.md`, `prompt_template_v2.md`, `llm_cache_v2/` (V2 LLM responses)
