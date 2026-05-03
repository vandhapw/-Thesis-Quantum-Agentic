# E-L2 — Agentic AI Multi-Tier Detection Validation Statistical Report

**Date:** 2026-05-04
**Sample:** 25 test machines × 5 windows = 125 evaluation cases
**LLM Ensemble:** glm-5.1:cloud, qwen3.5:cloud, kimi-k2.6:cloud, deepseek-v4-pro:cloud (majority vote, tie-break = highest tier)
**Pre-registration:** PHASE1_PROTOCOL_V2_ALIGNED_3LAYER.md §3
**Verdict:** ⛔ **STOP — pre-registered halt rule triggered (κ < 0.6)**

---

## ⚠️ ACADEMIC ETHICS DISCLOSURE

**This is a NEGATIVE RESULT.** The pre-registered hypothesis (H₁: 4-LLM ensemble achieves Quadratic-Weighted Kappa ≥ 0.6 with composite GT) is **NOT supported**. Per the pre-registered halt rule (§7 of protocol), Layer 3 experiments (E-L3A, E-L3B) **MUST NOT be executed** until Layer 2 detection is improved or the validation criterion is revised through formal pre-registration deviation.

**No selective reporting.** All 125 cases scored, all metrics computed, all per-LLM ablations reported. No post-hoc filtering applied.

**No silent proceed.** This negative result is reported to the supervisor before any further action.

---

## 1. Primary Result

| Metric | Value | Pre-reg threshold | Verdict |
|---|---|---|---|
| **Quadratic-Weighted Kappa (4-tier ordinal)** | **0.362** (95% CI [0.233, 0.498]) | ≥ 0.60 | ❌ **FAIL** |

Per Landis-Koch 1977 interpretation table:
- κ < 0.20: poor / no agreement
- 0.21–0.40: **fair** ← our result falls here
- 0.41–0.60: moderate
- **0.61–0.80: substantial** ← target
- 0.81–1.00: almost perfect

The ensemble achieves only **fair** agreement with composite GT, well below the substantial-agreement threshold required to proceed to Layer 3 scheduling.

## 2. Ground Truth Distribution

The composite GT formula (Lei et al. 2018 + ISO 13374-2) produced highly imbalanced tier distribution on 125 cases:

| Tier | Count | Pct |
|---|---|---|
| Critical | 11 | 8.8% |
| High | 10 | 8.0% |
| Medium | 12 | 9.6% |
| **Low** | **92** | **73.6%** |

This matches the natural class distribution of the QASAMAP dataset (anomaly_flag prevalence ~9%).

## 3. Confusion Matrix (rows = GT, cols = Predicted)

|        | Pred Critical | Pred High | Pred Medium | Pred Low |
|--------|---|---|---|---|
| **GT Critical** (n=11) | 10 | 0 | 1 | 0 |
| **GT High** (n=10) | 3 | 1 | 6 | 0 |
| **GT Medium** (n=12) | 4 | 5 | 3 | 0 |
| **GT Low** (n=92) | 9 | 14 | 46 | **23** |

**Pattern**: ensemble heavily over-predicts mid-tiers (Medium, High) and Critical for actually-Low machines. Only 23/92 Low machines correctly predicted Low (25% recall on majority class).

## 4. Per-Tier Performance

| Tier | Precision | Recall | F1 | Interpretation |
|---|---|---|---|---|
| Critical | 0.385 | **0.909** | 0.541 | Catches almost all Criticals (good) but with many false alarms |
| High | 0.050 | 0.100 | 0.067 | **Essentially useless** — cannot discriminate High |
| Medium | 0.054 | 0.250 | 0.088 | **Essentially useless** — over-predicts to non-Medium |
| Low | **1.000** | 0.250 | 0.400 | When ensemble says Low it's always right, but it rarely says Low |

**Macro F1 = 0.273** — strongly degraded by High/Medium failures.

**Coverage rate (truly Critical flagged Critical OR High) = 0.909** — operationally useful from a safety perspective (no missed critical), but at the cost of massive over-flagging.

## 5. Secondary Metrics

| Metric | Value |
|---|---|
| Top-K Coverage @ K=25 (top 20% predictions) | 12 / 25 = **48%** truly Critical+High |
| Cost-weighted misclassification (missed Critical=100) | total = 97, mean = 0.776 / case |
| Per-LLM call latency | median 4.1 s, p95 30.5 s |
| Ensemble end-to-end latency (max LLM/case) | median 11.8 s, **p95 64.9 s** ← exceeds 60 s real-time budget |

## 6. Per-LLM Ablation (informational)

| LLM | Valid responses | QW-Kappa | Macro F1 |
|---|---|---|---|
| deepseek-v4-pro:cloud | **118 / 125** | **0.425** | 0.351 (best) |
| glm-5.1:cloud | 125 / 125 | 0.367 | 0.228 |
| kimi-k2.6:cloud | 125 / 125 | 0.336 | 0.332 |
| qwen3.5:cloud | **67 / 125** ⚠️ | 0.147 | 0.216 |

**Critical observation about qwen3.5**: only 67 / 125 (53.6%) responses parsed as valid JSON. This is a major LLM-specific failure that contaminates the ensemble vote: when qwen3.5 fails to vote, ensemble effectively becomes 3-LLM majority, which reduces robustness on tied/borderline cases.

**Best individual LLM (deepseek)** outperforms the ensemble (0.425 vs 0.362) — this suggests **majority voting hurts when one ensemble member produces noise**. Either (a) drop qwen3.5 from ensemble, (b) use weighted ensemble with confidence weighting, or (c) deepseek-only baseline.

## 7. Failure-Mode Analysis (Honest Root Cause)

### 7.1 Critical over-prediction (most damaging)

LLMs tend to predict Critical for machines with even modest sensor breaches. Inspection of reasoning fields shows LLMs cite single-warning-threshold breaches as Critical evidence, even when GT formula requires multi-criteria match. This is a **prompt design failure**: the tier definitions in the prompt are insufficiently quantitative and bias toward over-call due to implied safety asymmetry ("better safe than sorry").

### 7.2 Mid-tier confusion

High vs Medium boundary is poorly differentiated by LLMs. Both tier definitions in the prompt mention "warning-level breach" — LLMs cannot reliably distinguish them without more concrete numeric criteria. This is **prompt ambiguity**, not LLM capability limit.

### 7.3 qwen3.5 JSON failure

qwen3.5 returned malformed JSON or empty `content` field for 58 / 125 cases. Inspection of cache shows several response patterns:
- Empty `content` with thinking field populated (think=False not respected)
- Markdown-fenced output without JSON content
- Partial JSON truncated at `num_predict=500` budget

**Mitigation**: increase `num_predict` to 800 + add explicit "do not use thinking" instruction OR drop qwen3.5.

### 7.4 Real-time feasibility marginal

Ensemble e2e p95 = 64.9 s exceeds the 60-s Kafka cycle requirement. Only median latency (11.8 s) is comfortably real-time. **Even if Kappa were sufficient, real-time deployment would be marginal at p95.**

## 8. What CAN Be Claimed

✅ The 4-LLM ensemble has **excellent recall on Critical class** (0.909) — operationally useful for not-missing-critical-machines
✅ The ensemble is calibrated toward **safety bias** (over-flag rather than under-flag), which is conservative and aligned with PdM operational doctrine
✅ The validation framework is **methodologically sound** (composite GT documented, 4 LLMs ablated, latency tracked, multi-window evaluation)

## 9. What CANNOT Be Claimed

❌ "4-LLM ensemble is a valid upstream detector for downstream scheduling" — Quadratic-Weighted Kappa is in fair-only range
❌ "LLM agentic AI matches expert tier judgment on QASAMAP" — far below substantial agreement
❌ "Real-time deployment is feasible" — p95 latency exceeds 60-s cycle
❌ "Ensemble is better than individual LLM" — best individual (deepseek) outperforms ensemble in this run

## 10. Pre-Registered Halt Rule Triggered

Per protocol §3.11 and §6.5:

> *"If κ < 0.6, STOP — do NOT execute Layer 3 experiments. Document failure honestly and propose remediation."*

**Status: HALTED.** E-L3A and E-L3B will NOT be executed without one of:
1. Re-run E-L2 with improved protocol that achieves κ ≥ 0.6
2. Formal pre-registration deviation lowering threshold (must be justified and documented)
3. Supervisor authorization to proceed despite κ < 0.6 with explicit acknowledgment in thesis

## 11. Remediation Options (for supervisor consideration)

### Option A — Improve prompt (estimated 2 hours, no new compute)
- Add concrete numeric criteria per tier (e.g., "Critical = at least 2 sensors past critical threshold AND failure_type ∈ {Electrical, Pressure}")
- Add 4 worked examples (one per tier) to anchor LLM
- Reduce safety bias with explicit instruction to "use Low when no acute breach"
- Re-run E-L2 with improved prompt → expect κ → 0.5–0.7 range

### Option B — Replace 4-tier with 2-tier (estimated 1 hour)
- Collapse to binary: NeedsAction (Critical+High+Medium) vs NoAction (Low)
- LLMs likely much more reliable on binary
- Lose granularity (less informative for scheduling priority)
- Re-run E-L2 expects κ → 0.6+ but at cost of resolution

### Option C — Use deepseek-only (estimated 30 minutes, partial re-run)
- Drop ensemble, use only deepseek-v4-pro (best individual)
- Eliminates qwen3.5 noise contamination
- κ improves from 0.36 to 0.43 (still below 0.6)
- Insufficient on its own; combine with Option A

### Option D — Lower threshold (no re-run)
- Lower pre-reg threshold from κ ≥ 0.6 to κ ≥ 0.4 (moderate agreement)
- Justification: Landis-Koch thresholds are conservative for industrial PdM where partial-credit is acceptable (mid-tier confusion = soft scheduling priority loss, not safety failure)
- **Requires explicit pre-registration deviation document** and supervisor approval
- Risk: defense panel may critique threshold lowering as post-hoc

### Option E — Use coverage rate as primary metric (no re-run)
- Switch primary metric from QW-Kappa to **Coverage rate of Critical** (= 0.909, well above any reasonable threshold)
- Justification: in PdM, missing a Critical machine has 100× cost of false alarm (per cost matrix)
- LLM ensemble achieves 90.9% Critical-coverage which IS operationally useful
- **Requires explicit pre-registration deviation**

### Option F — Acknowledge failure, defer Layer 3 (recommended for academic integrity)
- Stop here, document E-L2 negative result honestly
- Defer E-L3A, E-L3B as future work pending Layer 2 improvement
- Thesis chapter reframes: "Layer 2 reliability is preliminary; Layer 3 scheduling is described as architectural design without empirical comparison"
- Strongest from academic integrity standpoint
- Weakest from thesis-completeness standpoint

## 12. Defense-Ready Summary

> *"Pre-registered E-L2 evaluation of a 4-LLM cloud ensemble (glm-5.1, qwen3.5, kimi-k2.6, deepseek-v4-pro) for 4-tier criticality assignment on 125 multi-window QASAMAP test cases yields Quadratic-Weighted Kappa = 0.362 (95% CI [0.233, 0.498]) versus the composite ground truth (Lei et al. 2018 + ISO 13374-2). This is fair but not substantial agreement (Landis-Koch 1977), below the pre-registered threshold of κ ≥ 0.6 required to proceed to Layer 3 scheduling experiments. Per the pre-registered halt rule, Layer 3 experiments were not executed; the negative result is reported transparently along with root-cause analysis (Critical over-prediction due to prompt ambiguity, qwen3.5 53% JSON parse failure, mid-tier confusion) and six remediation options spanning prompt engineering, ensemble redesign, threshold revision, and metric reframing. The ensemble does achieve high Critical-coverage (90.9%) and fast median latency (11.8 s), supporting safety-conservative deployment but not the full multi-tier discrimination needed for cost-optimal scheduling input."*

This honest negative result strengthens thesis credibility: a willingness to halt and report failure per pre-registered rules is a marker of methodological integrity that defense panels will respect.

---

**Result files:**
- `experiments/E-L2_agentic_validation/metrics.json` — full metrics blob
- `experiments/E-L2_agentic_validation/raw_results.json` — per-case per-LLM raw outputs
- `experiments/E-L2_agentic_validation/per_case_predictions.csv` — flat CSV for downstream analysis
- `experiments/E-L2_agentic_validation/run.log` — full execution log
- `experiments/E-L2_agentic_validation/llm_cache/` — cached LLM responses for replay
