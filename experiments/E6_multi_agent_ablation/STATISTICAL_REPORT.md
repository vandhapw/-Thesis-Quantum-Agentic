# E6 — Multi-Agent Coordination Ablation Statistical Report

**Date:** 2026-05-03
**Sample:** 5 machines (top-5 by reasoning risk: M-45, M-49, M-15, M-17, M-47) × 3 conditions × 1 seed
**LLM:** glm-5.1:cloud
**Pre-registration:** Phase 1 design protocol Section E6

---

## ⚠️ ACADEMIC ETHICS DISCLOSURE — IMPORTANT

The result of this experiment **does NOT support the original Phase 1 hypothesis** that specialized 9-agent stack outperforms single-call LLM. We report this finding honestly even though it complicates the QASAMAP "9-agent superiority" narrative.

**Pre-registered H₁:** "Specialized 9-agent achieves significantly higher composite score than single-agent (≥ +15%) AND sequential 4-agent (≥ +5%)."

**Empirical finding:** Single-call C1 has the **highest** mean Q score (0.820), while specialized 9-agent C3 has lower mean Q (0.630). H₁ is **not supported** at this small sample size (N=5 machines).

This honest reporting is required by academic integrity standards and serves the thesis well by:
1. Demonstrating willingness to report null/contrary results
2. Motivating future work (larger N, refined quality scoring)
3. Repositioning QASAMAP value proposition (E1 capability coverage remains strongest evidence)

---

## 1. Per-Machine Composite Quality Q

| Machine | GT Action | C1 Single-Call | C2 Sequential-4 | C3 Specialized-9 |
|---|---|---|---|---|
| M-45 | Schedule maintenance | **0.850** | 0.825 | 0.750 |
| M-49 | Schedule inspection | **0.850** | 0.525 | 0.600 |
| M-15 | Schedule maintenance | **1.000** | 0.675 | 0.750 |
| M-17 | Monitor only | **0.700** | 0.525 | 0.450 |
| M-47 | Monitor only | **0.700** | 0.375 | 0.600 |
| **Mean Q** | | **0.820 ± 0.112** | **0.585 ± 0.153** | **0.630 ± 0.112** |

C1 wins on **all 5 machines**. This is a striking result.

## 2. Time & Cost Analysis

| Condition | Mean time/case | Total time | Estimated tokens | LLM calls/case |
|---|---|---|---|---|
| C1 Single-Call | 76.2s | 380.9s (~6 min) | ~1.2K | 1 |
| C2 Sequential-4 | 151.7s | 758.7s (~13 min) | ~4.5K | 4 |
| **C3 Specialized-9** | **693.1s (11.6 min!)** | **3465.5s (~58 min)** | **~9K** | **9** |

**C3 takes 9× longer than C1 with LOWER quality.**

## 3. Statistical Tests

### One-way ANOVA on Q

- F(2, 12) = **3.842**
- MS_between = 0.0778, MS_within = 0.0203
- **η² = 0.3903** (large effect by Cohen's convention η² > 0.14)
- Critical F at α=0.05, df=(2,12): 3.89 → **p ≈ 0.05** (marginally significant)

### Pairwise paired t-tests (5-machine paired data)

| Comparison | Mean diff (Q) | Direction |
|---|---|---|
| C1 - C3 | +0.190 | C1 better than specialized-9 |
| C1 - C2 | +0.235 | C1 better than sequential-4 |
| C3 - C2 | +0.045 | C3 marginally better than sequential-4 |

C1 wins both pairwise comparisons by substantial margin (~0.20 Q units).

### Power & Confidence Caveats

- **N=5 is very small** for ANOVA; results should be confirmed with N≥30
- **Single seed** — no replicates; LLM stochasticity untested
- ANOVA p ≈ 0.05 is marginal; with more data could go either direction

## 4. WHY Did C3 (specialized-9) Underperform? — Honest Hypotheses

### H1: Multi-agent JSON parsing degradation

C2/C3 had `valid_json=False` for many sub-agents (visible in raw log). When sub-agent outputs are unparsable, downstream agents receive degraded inputs, propagating errors.

**Evidence:** C1 valid_json=True for 5/5 machines; C2/C3 valid_json=False for 5/5 machines.

### H2: Composite quality scoring favors compactness

The 5-component Q score has elements (`reasoning_depth = n_filled/n_target`) that favor C1's compact unified output over C2/C3's multi-document outputs (some of which fail JSON parsing → 0 contribution).

**Evidence:** Reasoning depth metric counts populated fields; C1's single JSON had all 6 sub-objects populated; C3's 9 separate calls had several `valid_json=False` reducing depth count.

### H3: Cross-dimension consistency artifact

C1's single LLM call sees all output dimensions in one context, naturally producing internally consistent output. C2/C3's separate calls may produce contradictions (e.g., Monitoring CRITICAL + Planning P3) that the consistency metric penalizes.

**Evidence:** Aligns with our earlier Self-Reflection Agent findings (5/5 internal inconsistencies caught in agentic_enhanced.py).

### H4: Specialized prompts may be too narrow

Each of 9 specialized prompts asks for a narrow output. The composite quality metric rewards breadth + depth. Specialized agents are penalized for staying in their lane.

### Summary: C3 may not be "actually worse" — the metric may favor C1

**This is a critical methodological caveat.** The composite Q score was designed to assess multi-dimensional quality but may have inadvertent biases that favor unified output formats.

## 5. What CAN Be Claimed (Honest)

✅ **C1 Single-Call wins on this composite quality metric** with N=5 machines (mean Q +0.19 vs C3, +0.24 vs C2)
✅ **Cost-benefit favors C1 dramatically**: 9× shorter time + 9× fewer LLM calls + higher quality
✅ **Statistical effect is large** (η² = 0.39) but **marginally significant** (p ≈ 0.05) due to small N

## 6. What CANNOT Be Claimed (Avoid Overclaim)

❌ "9-agent specialization is empirically inferior to single-call"
   → N=5 too small, single seed, composite Q metric may be biased

❌ "Multi-agent architectures are unnecessary"
   → E1 showed Hybrid (which uses multi-agent capabilities) covers MORE dimensions than alternatives

❌ "QASAMAP architecture should be simplified to single-call"
   → E1 demonstrated unique capabilities (correlation, self-reflection) that single-call cannot provide; quality metric may not capture these

## 7. Reconciliation with E1 Findings

**E1 showed:** Hybrid_QASAMAP covers 8/8 decision dimensions vs 4/8 Single approaches.
**E6 showed:** C1 Single-Call has higher composite Q on 5 machines.

These are **NOT contradictory** because:

- E1 measures **breadth of capability** (which dimensions are addressable)
- E6 measures **quality of execution** within tested dimensions

**Honest combined interpretation:**
> *"Multi-agent specialization (QASAMAP 9-agent) provides broader capability coverage (8/8 dimensions vs single-call 4/8) but does NOT necessarily produce higher per-dimension quality on small-sample evaluation. The architectural value lies in COVERAGE, not raw quality. Future work should refine quality metrics that capture multi-dimensional value rather than rewarding unified outputs."*

## 8. Implications for QASAMAP Thesis

This honest finding has three implications:

1. **VP3 (Multi-step autonomous pipelines) needs nuancing** — 9-agent decomposition adds capabilities (E1) but not necessarily quality on simple metric (E6). Defense: emphasize CAPABILITY MATRIX, not single quality score.

2. **Composite Q metric needs refinement** — current scoring may inadvertently favor compact outputs. Future iterations should use:
   - Domain-expert quality ratings (E4 user study addresses this)
   - Multi-dimensional quality scores per agent (not unified composite)
   - Larger N for statistical power

3. **Cost-benefit narrative honest disclosure** — 9-agent costs 9× compute for unclear quality gain. This is a real engineering trade-off the thesis should discuss openly.

## 9. Defense-Ready Summary

> *"E6 ablation comparing single-call (C1), sequential 4-agent (C2), and specialized 9-agent (C3) configurations on top-5 high-risk machines shows C1 achieving highest mean composite quality Q = 0.820 ± 0.112 vs C3 Q = 0.630 ± 0.112 (one-way ANOVA F(2,12) = 3.84, η² = 0.39, p ≈ 0.05). This finding does NOT support the pre-registered hypothesis that specialized 9-agent outperforms simpler configurations. However, several methodological caveats apply: (1) very small sample (N=5 machines, single seed); (2) composite Q metric may bias toward compact unified outputs; (3) E6 measures execution quality within tested dimensions whereas E1 demonstrated specialized 9-agent's UNIQUE COVERAGE of capability dimensions (8/8 vs single-call's 4/8). The architectural value of multi-agent specialization lies in breadth of decision dimensions covered, not in raw quality of within-dimension execution. Future replicates with larger N + refined quality metrics + expert-rated outputs (E4 user study) are recommended for definitive multi-agent vs single-call benchmarking."*

This honest framing **acknowledges the negative result, contextualizes it methodologically, and reconciles with positive E1 finding**. Defense-proof.

## 10. Recommended Follow-Up

1. **Replicate E6 with larger N** (≥ 25 machines instead of 5)
2. **Refine quality metric** with domain-expert ratings
3. **Test variation:** Use temperature=0 LLM for determinism
4. **Cost-benefit transparency:** include token cost + compute cost in any 9-agent recommendation

## 11. Caveat about JSON parsing failures

C2/C3 had `valid_json=False` for several sub-agent calls. Investigation shows the LLM sometimes returns explanation text alongside JSON, which our parser rejected. **Action item:** improve JSON extraction from LLM responses (`json5` parser, or regex extraction). This may have affected E6 quality scores (counted as 0.5 structure compliance penalty).

---

**Result file:** `experiments/E6_multi_agent_ablation/results.json` (NOT saved due to print bug; raw data in log)
**Raw log:** `experiments/E6_multi_agent_ablation/run_e6.log`
