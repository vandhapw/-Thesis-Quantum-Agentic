# E5 — Out-of-Distribution Robustness Statistical Report

**Date:** 2026-05-03
**Sample:** 25 test machines × 5 perturbation types × 4 approaches
**Pre-registration:** Phase 1 design protocol Section E5

---

## ⚠️ ACADEMIC ETHICS DISCLOSURE

This experiment applies **synthetic perturbations to synthetic digital-twin output**.
Findings should be interpreted as:

✅ "Behavior of detector approaches under controlled synthetic perturbations of digital-twin streaming data"

NOT as:

❌ "Evidence of real-world OOD robustness"

Real-world OOD validation requires evaluation on **independent industrial datasets** (NASA C-MAPSS, FEMTO Bearing, IMS Bearing, etc.). E2 protocol (planned) addresses this with C-MAPSS turbofan transfer evaluation.

---

## 1. Baseline Detection (Clean Data)

| Approach | F1 | Precision | Recall |
|---|---|---|---|
| **Hybrid_Combined** | **0.800** | 0.762 | 0.842 |
| Pure_Rule_Based | 0.686 | 0.706 | 0.667 |
| Fleet_Relative | 0.688 | 0.667 | 0.708 |
| Sliding_Window | 0.483 | 0.583 | 0.412 |

Hybrid (any-of-3 voting) wins baseline F1 = 0.800.

## 2. F1 Retention per Perturbation

| Perturbation | Pure_Rule_Based | Fleet_Relative | Sliding_Window | Hybrid_Combined |
|---|---|---|---|---|
| P1 sensor failure (temp stuck at 75°C) | 100.0% | 87.3% | 74.0% | 92.1% |
| P2 combined failure (temp+vib ×1.20) | 105.3% | 100.0% | **138.1%** | 102.6% |
| P3 environmental shift (all ×1.20) | **112.2%** | 100.0% | **138.1%** | 103.7% |
| P4 sensor drift (slow bias) | 100.0% | 105.8% | **138.1%** | 102.6% |
| P5 adversarial perturbation (×1.05) | 105.3% | 100.0% | 114.3% | 102.6% |
| **Mean retention** | **104.6% ± 4.5%** | **98.6% ± 6.1%** | **120.5% ± 25.0%** | **100.7% ± 4.3%** |

## 3. ⚠️ Counterintuitive Finding — IMPORTANT INTERPRETATION

**Many retention values are >100%** (perturbation IMPROVES F1 instead of degrading). This requires honest interpretation:

### Why this happens

- Test data has many machines with sensor values JUST BELOW threshold
- Perturbations that increase feature values (P2, P3, P4, P5) push these borderline cases OVER the threshold
- For machines whose ground-truth label is "needs_attention", crossing threshold = TP increase
- This artificially inflates F1

### What this DOES NOT mean

- ❌ Does NOT mean detectors are "more robust" to perturbations
- ❌ Does NOT mean perturbations help in real OOD scenarios

### What this DOES mean

- ✅ Our detector approaches have **conservative thresholds** that miss many true positives at baseline (clean F1 ≈ 0.69-0.80, not 1.0)
- ✅ Synthetic upward perturbations **trivially improve threshold-based detectors** by pushing borderline cases over
- ✅ Sliding_Window's 138% retention is a metric artifact of low baseline (F1=0.483) + perturbation pushing more cases above threshold

## 4. Honest Methodological Limitations

This experiment has several limitations that constrain claim strength:

1. **Synthetic-on-synthetic** — perturbations applied to data from a digital-twin, not real sensor readings
2. **Ground truth unchanged** — perturbing inputs but keeping GT fixed assumes failure occurrence is independent of sensor variance, which is NOT physically realistic
3. **Asymmetric perturbations** — most perturbations push features UP, biasing toward more detections (no DOWN perturbations tested)
4. **No cross-validation** — single seed, single snapshot
5. **Ceiling/floor effects** — already-conservative detectors easily improve with upward perturbation; truly OOD-robust detectors would show DIFFERENT pattern

## 5. What CAN Be Claimed (Honest)

✅ **Pure_Rule_Based and Hybrid_Combined show stable retention** (4-5% stdev across 5 perturbations) — suggests **threshold-based logic is mathematically resilient** to small input shifts (predictably, since thresholds are continuous functions of input).

✅ **Fleet_Relative shows minor degradation** (98.6% mean) — population-relative scoring is sensitive to global perturbations because all machines shift together.

✅ **Sliding_Window has highest variance** (25% stdev) — per-machine z-score with shorter history is sensitive to single-cycle perturbations, but baseline F1=0.48 makes percentage interpretation unreliable.

## 6. What CANNOT Be Claimed (Avoid Overclaim)

❌ "Hybrid_Combined is robust to OOD events" — these are NOT real OOD events
❌ "Sliding_Window is more robust than rule-based" — its 120% retention reflects baseline-F1 floor, not adaptation
❌ "Detectors degrade gracefully under sensor failure" — only ONE sensor failure mode (constant value) tested
❌ "Approach X is best for production OOD" — cannot generalize from synthetic to real OOD

## 7. Recommended Future Work (For Real OOD Validation)

For thesis-defendable OOD claims, do one or more:

1. **E2 with NASA C-MAPSS** — true cross-domain transfer (PdM turbofan data)
2. **Real Plalion sensor failure data** — log natural sensor faults if any historical data exists
3. **Bidirectional perturbations** — test both UP and DOWN perturbations
4. **Multi-seed cross-validation** — repeat with different random splits
5. **Physical-realistic perturbations** — base perturbations on documented failure mechanisms

## 8. Defense-Ready Summary

> *"E5 measures detector approach behavior under five synthetic perturbations of digital-twin streaming data. Findings show (a) threshold-based approaches have stable retention (Pure_Rule_Based 104.6% ± 4.5%; Hybrid_Combined 100.7% ± 4.3%); (b) population-relative approach has minor degradation (Fleet_Relative 98.6% ± 6.1%); (c) per-machine sliding window approach has highest variance (Sliding_Window 120.5% ± 25.0%, but starting from low baseline F1=0.48). However, retention >100% in many conditions reflects ceiling/floor artifacts of upward-only perturbations on conservative-threshold detectors, NOT true OOD adaptation. Real-world OOD validation requires evaluation on independent industrial datasets, which is reserved for E2 (NASA C-MAPSS transfer) as future work."*

This honest framing **cannot be attacked** by panel — we explicitly disclaim what cannot be concluded.

---

**Result file:** `experiments/E5_ood_robustness/results.json`
**Raw log:** Available in this script's stdout
