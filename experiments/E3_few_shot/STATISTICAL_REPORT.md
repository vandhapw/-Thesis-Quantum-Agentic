# E3 — Few-Shot Adaptation Statistical Report

**Date:** 2026-05-03
**Sample:** 10 evaluation cases (5 holdout-positive Pressure Drop + 5 negative) × 4 N levels (0, 1, 3, 5)
**Model:** glm-5.1:cloud
**Pre-registration:** Phase 1 design protocol Section E3

---

## ⚠️ ACADEMIC ETHICS DISCLOSURE

**Limitations that constrain claim strength:**

1. **Ground truth is digital-twin classifier output**, NOT expert annotations. Previously documented 56% flip rate in classifier means GT itself is unreliable.
2. **Small evaluation set (N=10)** limits statistical power.
3. **Single random seed** — no replicates yet.
4. **Asymmetric LLM bias** — model classifies almost all cases as positive (see findings).

Findings should be read as **"preliminary evidence of LLM in-context learning behavior in this digital-twin setup"**, NOT as definitive few-shot performance benchmarks.

---

## 1. Results Table

### LLM Few-Shot Performance per N

| N examples | F1 | Precision | Recall | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|
| 0 (zero-shot) | 0.667 | 0.500 | 1.000 | 5 | 5 | 0 | 0 |
| 1 | 0.667 | 0.500 | 1.000 | 5 | 5 | 0 | 0 |
| 3 | 0.714 | 0.556 | 1.000 | 5 | 4 | 0 | 1 |
| 5 | 0.714 | 0.556 | 1.000 | 5 | 4 | 0 | 1 |

### Non-Learning Baseline (constant across N)

| Approach | F1 | Note |
|---|---|---|
| Pure_Rule_Based | 0.722 | No learning mechanism |
| Fleet_Relative | 0.688 | No per-failure adaptation |
| Sliding_Window | 0.743 | No per-failure adaptation |

## 2. Linear Trend Analysis

- Slope of F1 vs N: **+0.0113 F1 per example**
- F1 improvement N=0 → N=5: **+0.048**

**Direction:** LLM F1 increases with examples (slope > 0), suggesting in-context learning IS happening. However:

- Magnitude small (0.05 over 5 examples)
- May be within noise floor for N=10 eval set
- Without replicates, cannot test statistical significance

## 3. ⚠️ Critical Honest Findings

### Finding 1: LLM has strong bias toward positive prediction

In **all 4 N levels**, LLM predicts POSITIVE for **9 or 10 out of 10 cases**. This pattern persists with and without few-shot examples.

**Interpretation:**
- Recall 100% — catches all true positives ✓
- Precision 50-55% — half of predicted positives are false alarms
- LLM behaves like an "always alarm" detector, not a discriminative classifier

**Implication:** LLM in-context learning here is NOT learning to discriminate. It's already biased toward "anomaly" given how the prompt is framed ("examples of anomalous machines: ...") which biases the LLM toward outputting anomaly for any input. This is a **prompt design issue**, not necessarily an LLM capability limitation.

### Finding 2: LLM F1 < non-learning baseline approaches

| Comparison | LLM N=5 | Best non-learning |
|---|---|---|
| F1 | 0.714 | 0.743 (Sliding_Window) |
| Recall | 1.000 | varies |
| Precision | 0.556 | varies |

**Honest interpretation:** Non-learning baselines (Sliding_Window F1=0.743) outperform LLM at any tested N level. This does NOT support the original Phase 1 hypothesis "Hybrid Agentic reaches F1 ≥ 0.60 with N ≤ 5 examples while Pure ML requires N ≥ 30".

**However:** Phase 1 hypothesis was about ML retraining vs LLM in-context. Non-learning baselines (rule-based, fleet-relative, sliding-window) sit between these — they don't retrain but they don't use few-shot either. So the comparison is not apples-to-apples.

### Finding 3: F1 plateau at N=3

LLM F1 doesn't change between N=3 and N=5 (both 0.714). Adding more examples beyond 3 yields no marginal benefit in this setup.

**Possible explanations:**
- LLM saturates on this task with very few examples
- Examples may be redundant (all from same failure type)
- Eval set too small to discriminate

## 4. What CAN Be Claimed (Honest)

✅ **LLM detects all 5 true positives at every N level** — high recall is consistent
✅ **F1 marginally increases with examples** (+0.05 over 5 examples) — direction-of-effect supports VP5 (in-context adaptation), but magnitude is small
✅ **Non-learning baselines remain competitive** — Sliding_Window F1=0.743 outperforms LLM at all tested N

## 5. What CANNOT Be Claimed (Avoid Overclaim)

❌ "LLM achieves rapid few-shot adaptation" — improvement is +0.05, marginal
❌ "Few-shot LLM beats traditional ML" — was not directly compared (would need ML retraining experiments)
❌ "LLM in-context learning saturates at N=3" — could be eval-set-size artifact
❌ "VP5 empirically validated" — preliminary evidence only; full validation needs:
  - ≥ 30 evaluation cases (vs current 10)
  - Multiple replicates with different example samples
  - Comparison vs ML retrained on N examples

## 6. Methodological Issues to Address in Replicates

1. **Prompt bias:** Examples-as-anomalies framing biases LLM toward anomaly output. Fix: include negative examples too in prompt ("These are NORMAL machines: …").

2. **Example diversity:** All 5 examples from same failure type. Fix: sample from multiple failure types for "fault category" learning.

3. **Eval set size:** N=10 → low power. Fix: ≥ 30 eval cases.

4. **Ground truth quality:** Use expert-validated labels, not classifier outputs. Fix: manual review of held-out test set.

5. **Deterministic LLM:** No temperature control set; rerun with `temperature=0` for reproducibility.

## 7. Defense-Ready Summary

> *"E3 provides preliminary evidence that LLM agentic AI exhibits in-context learning behavior on the QASAMAP digital-twin held-out failure type (Pressure Drop): F1 increases from 0.667 (N=0) to 0.714 (N=5), a +0.048 improvement with positive direction-of-effect. However, several methodological limitations constrain claim strength: small evaluation set (N=10), noisy proxy ground truth, single seed, and observed LLM bias toward positive prediction. Non-learning baseline approaches (Sliding_Window F1=0.743) outperform LLM at all N levels in this setup. The findings support **VP5 (in-context adaptation) directionally** but require **larger eval set + expert annotations + multiple replicates** for statistical significance claims, recommended as priority follow-up before publication-grade evaluation."*

This honest framing positions E3 as **preliminary** rather than definitive — defense-proof against rigorous methodological critique.

---

**Result file:** `experiments/E3_few_shot/results.json`
**Raw log:** `experiments/E3_few_shot/run_e3.log`
