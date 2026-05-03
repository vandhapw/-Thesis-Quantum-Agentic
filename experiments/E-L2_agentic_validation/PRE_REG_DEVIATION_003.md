# Pre-Registration Deviation #003 — Realistic Deployment Input Set (Option 1)

**Date:** 2026-05-04
**Original protocol:** PHASE1_PROTOCOL_V2_ALIGNED_3LAYER.md §3.4 (prompt design)
**Authorization:** Supervisor approval ("Lakukan Opsi 1") on 2026-05-04 after V2 negative result (κ=0.191) revealed information-asymmetry root cause

## Root cause acknowledged

V2 negative result (κ=0.191, worse than V1) is attributable to a **methodological flaw** in V1+V2 prompt design, not LLM capability. The composite GT formula uses 4 fields (`predicted_remaining_life`, `anomaly_flag`, `downtime_risk`, `maintenance_required`) that the LLM was NOT given in V1 or V2 prompts. The LLM was effectively asked to predict an output whose formula required hidden input — an information-asymmetric task.

V2's rigid decision-tree prompt made this worse by forcing LLM to reason ONLY from sensor breaches, while GT was largely driven by RUL + downtime_risk thresholds (not direct sensor values).

## What V3 changes

| Aspect | V2 | V3 |
|---|---|---|
| Input fields shown to LLM | 5 sensors + failure_type | 5 sensors + failure_type + **RUL + anomaly_flag + downtime_risk + maintenance_required** |
| Decision-tree prompt | Sensor-threshold pseudocode | Tier definitions in plain language; LLM reasons over the **realistic deployment input set** |
| Cache namespace | `llm_cache_v2/` | `llm_cache_v3/` |
| Output suffix | `_v2` | `_v3` |

## What V3 does NOT change (preserves pre-reg integrity)

- Composite GT formula (frozen since deviation #001)
- 125 evaluation cases (deterministic seed=42, same machines/windows)
- 3-LLM ensemble composition (glm-5.1, kimi-k2.6, deepseek-v4-pro)
- Majority-vote aggregation, tie-break = highest tier
- Primary metric: Quadratic-Weighted Kappa
- Halt threshold: κ ≥ 0.6
- num_predict = 800

## Justification for Option 1

In **realistic QASAMAP deployment**, the agentic AI Layer 2 receives upstream output from:
1. T-GCN spatiotemporal forecasts (sensor predictions)
2. Tree-ensemble classifier output (anomaly_flag probability, downtime_risk score, maintenance_required indicator)
3. RUL regression model (predicted_remaining_life estimate)
4. Failure-type classifier (failure mode signature)

These are precisely the 4 hidden fields the GT formula uses. **A real deployed agentic AI would have access to ALL of them** — they are not hidden from the production agent, only from the V1/V2 evaluation prompt.

Therefore V3 simulates **realistic deployment information set**, not a cheat. The LLM is still required to **reason** over this richer input to assign tier; the GT formula is still not disclosed in the prompt (LLM must infer from definitions and patterns).

## Why this is methodologically defensible

1. **Same primary metric + halt threshold** preserved.
2. **GT formula unchanged** — same target.
3. **Input set change matches deployment reality**, not arbitrary cherry-picking.
4. **Formula not disclosed in prompt** — LLM must still reason; not a calculator test.
5. **Halt rule preserved** — if V3 yields κ < 0.6, halt rule still triggers and proceeds to Option F (defer).

## Risk acknowledgement

- Defense panel may ask: "If V3 succeeds, does it just mean the LLM read RUL<10 and trivially mapped to Critical?" — Answer: per-LLM ablation + reasoning-text inspection will show whether LLMs use multi-criterion reasoning or shortcut. Will report transparently.
- V3 is the **third deviation**; further deviations will require strong supervisor justification. If V3 also fails κ<0.6, recommendation will be Option F (defer Layer 3).

## Files

V3 will produce:
- `prompt_template_v3.md` (active)
- `run_el2_v3.py`
- `metrics_v3.json`, `raw_results_v3.json`, `per_case_predictions_v3.csv`
- `llm_cache_v3/`
- `STATISTICAL_REPORT_v3.md` (after run completes)
