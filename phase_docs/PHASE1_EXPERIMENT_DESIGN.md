# PHASE 1 — Experiment Design Protocols
## QASAMAP Thesis: Empirical Validation of Agentic AI Necessity

**Author:** Vandha Widartha (PhD candidate, Pukyong National University)
**Date prepared:** 2026-05-03
**Document purpose:** Formal experimental protocols for thesis Chapter 5.3.
This document specifies six pre-registered experiments with statistical rigor sufficient for thesis defense and journal submission.

---

## 0. CROSS-CUTTING METHODOLOGICAL FRAMEWORK

### 0.1 Pre-registration commitment

All six experiments are **pre-registered** before execution. Hypotheses, sample sizes, statistical tests, and significance thresholds are fixed BEFORE data collection. Any deviation requires explicit justification.

### 0.2 Notation

| Symbol | Meaning |
|---|---|
| `H₀` / `H₁` | Null / alternative hypothesis |
| `α` | Type I error rate (set to 0.05 throughout, Bonferroni-corrected when multiple comparisons) |
| `β` / `1-β` | Type II error / statistical power (target ≥ 0.80) |
| `d` | Cohen's d (effect size for t-test) |
| `η²` | Eta-squared (effect size for ANOVA) |
| `δ` | Cliff's delta (non-parametric effect size) |
| `N` | Sample size |

### 0.3 Cross-experiment data definitions

| Asset | Source | Use |
|---|---|---|
| **Train split** | 26 machines, even `machine_id` | Fit ML models, derive thresholds |
| **Test split** | 25 machines, odd `machine_id` | Evaluate detection metrics |
| **External transfer set** | NASA C-MAPSS FD001 | E2 cold-start |
| **Holdout failure mode** | "Pressure Drop" instances removed from train | E3 few-shot |
| **Perturbed test set** | Test split + synthetic perturbations | E5 OOD |
| **Operator scenarios** | 20 hand-curated cases from test split | E4 user study |

### 0.4 Reproducibility checklist

- [ ] All scripts run with fixed seeds (`seed=42` default; multi-seed `[42, 7, 1234]` for stochastic methods)
- [ ] Random splits saved to `experiments/splits/` as JSON with `machine_id` lists
- [ ] LLM API calls cached to disk (`experiments/llm_cache/`) for replay
- [ ] All p-values reported with confidence intervals (95% CI)
- [ ] All effect sizes reported alongside p-values
- [ ] Power analysis recorded BEFORE data collection
- [ ] Pre-registration file `experiments/pre_registration.json` committed to git

### 0.5 Statistical analysis stack

```python
# Required Python packages (all pip-installable):
import scipy.stats as stats          # t-test, chi-square, Wilcoxon
import statsmodels.api as sm         # mixed-effects, ANOVA
import statsmodels.formula.api as smf
import scikit_posthocs as sp         # Tukey HSD, Dunn's test
from statsmodels.stats.power import TTestPower, FTestAnovaPower  # power analysis
import pingouin as pg                # ANOVA + effect sizes
```

### 0.6 Multiple comparison correction

Six experiments × multiple metrics = inflated familywise error rate.
**Method:** Benjamini-Hochberg FDR correction at q=0.05 across all hypothesis tests in thesis.
Report both raw and adjusted p-values.

### 0.7 Validity threats addressed

| Threat | Mitigation |
|---|---|
| **Internal validity** | Random train/test splits, fixed seeds, blinded LLM-as-judge ratings |
| **External validity** | Multi-dataset (manufacturing + C-MAPSS), multi-seed stochastic eval |
| **Construct validity** | Pre-registered metrics, pre-validated questionnaires (E4) |
| **Conclusion validity** | Power analysis a priori, effect sizes reported, FDR-corrected p-values |
| **Selection bias** | All experiments use same train/test split; no cherry-picking |

---

# E1 — CAPABILITY COVERAGE EXPERIMENT

**Status: Highest priority. Estimated effort: 2 days.**

## E1.1 Hypothesis

- **H₀:** All approaches (Pure ML, Pure Classical, Pure Agentic LLM, Hybrid QASAMAP) cover an equal proportion of the 8 industrial PdM decision dimensions.
- **H₁:** Hybrid QASAMAP covers significantly more dimensions than the next-best approach (≥ 2 dimensions advantage).

## E1.2 Independent variable

**Approach** (4 levels, between-subjects on dimension coverage):
1. **Pure ML**: Trained LSTM/GNN classifier (best performer from `full_comparison_8models.py`)
2. **Pure Classical**: Rule-based + Mahalanobis + SA scheduling + cosine consensus
3. **Pure Agentic LLM**: glm-5.1:cloud only, no preprocessing, no specialized agents
4. **Hybrid QASAMAP**: Layer 1 ML + Layer 2 Agentic + Layer 3 Classical + Layer 4 LLM reporting

## E1.3 Dependent variables (8 binary capability dimensions)

| # | Dimension | Definition |
|---|---|---|
| D1 | Detection (anomaly y/n) | Approach produces a binary anomaly decision |
| D2 | Severity ranking | Approach produces ordered severity score (e.g., LOW/MED/HIGH or 1-10) |
| D3 | Root cause identification | Approach names the failure mode (bearing_wear / electrical / etc.) |
| D4 | Affected component | Approach identifies which component (motor / pump / actuator) |
| D5 | Temporal urgency | Approach quantifies hours-to-action window |
| D6 | Cross-machine correlation | Approach groups related machines into clusters |
| D7 | Maintenance action recommendation | Approach proposes specific action class (inspect / schedule / shutdown) |
| D8 | Operator-readable explanation | Approach produces natural-language paragraph |

Each dimension is scored 1 (covers) or 0 (does not cover) per machine.

## E1.4 Sample size & power analysis

- **Test machines:** 25 (test split)
- **Per approach total binary observations:** 25 × 8 = 200
- **Power analysis:** Chi-square test, effect size w=0.3 (medium), α=0.05, df=21 → required N ≥ 130. Have 800 across all approaches.
- **Power achieved:** > 0.95 for w=0.3.

## E1.5 Procedure

```python
# 1. Load test events
events = load_test_events()  # 25 machines

# 2. For each approach, run end-to-end
results = {}
for approach_name in ['PureML', 'PureClassical', 'PureAgentic', 'HybridQASAMAP']:
    pipeline = build_pipeline(approach_name)
    results[approach_name] = pipeline.run(events)
    # Each result contains the 8 dimension fields per machine

# 3. Score each (approach, machine, dimension) cell
coverage_matrix = score_coverage(results)  # shape: (4, 25, 8)
# coverage_matrix[i,j,k] ∈ {0, 1}

# 4. Aggregate per approach
coverage_by_approach = coverage_matrix.sum(axis=1)  # shape (4, 8)
total_per_approach = coverage_matrix.sum(axis=(1,2))  # shape (4,)
```

## E1.6 Statistical analysis

### Primary test
**Pairwise McNemar test** for paired binary data (same machines, different approach):

For each dimension D_k:
- 2x2 table: (Approach A correct, B wrong) vs (A wrong, B correct)
- McNemar's χ² with continuity correction
- 6 pairwise comparisons × 8 dimensions = 48 tests → Bonferroni α = 0.05/48 ≈ 0.001

### Secondary test
**Cochran's Q test** for >2 related groups: tests whether ALL approaches differ on dimension D_k.

### Effect size
**Phi coefficient** for each pairwise McNemar.

## E1.7 Expected results

```
Coverage matrix (predicted, of 8 dimensions):
  Pure ML:         [✓D1, ✓D2, ✗,  ✗,  ✗,  ✗,  ✗,  ✗ ] = 2/8 = 25%
  Pure Classical:  [✓D1, ✓D2, ✗,  ✗,  ✗,  ✓D6,✓D7,✗ ] = 4/8 = 50%
  Pure Agentic:    [✓D1, ✓D2, ✓D3,✓D4,✓D5,✓D6,✓D7,✓D8] = 8/8 = 100%
                   (but D1 with low quality)
  Hybrid QASAMAP:  [✓D1, ✓D2, ✓D3,✓D4,✓D5,✓D6,✓D7,✓D8] = 8/8 = 100%
                   (with high quality D1 from ML layer)
```

## E1.8 Implementation checklist

- [ ] Reuse `comparative_study.py` results for D1-D6 (already computed)
- [ ] Add D7 (action recommendation) and D8 (NL explanation) extraction
- [ ] Build `score_coverage()` evaluator with deterministic rules (no human judgment for primary metric)
- [ ] Optional: secondary quality scoring (1-10) by domain expert for verbosity-quality vs binary coverage
- [ ] Write up as Table + Figure for thesis (radar plot recommended)

## E1.9 Threats to validity

- **Construct threat:** Binary coverage doesn't capture quality. **Mitigation:** report secondary 1-10 quality score for D3-D8.
- **Selection bias:** Test snapshot may not have all failure modes. **Mitigation:** run on 3 different snapshots, report mean ± stdev.

---

# E2 — COLD-START / OUT-OF-DOMAIN PERFORMANCE

**Status: High academic value. Estimated effort: 3-4 days (need to integrate NASA C-MAPSS).**

## E2.1 Hypothesis

- **H₀:** F1 detection score on out-of-domain data does not differ between Pure ML and Hybrid Agentic.
- **H₁:** Hybrid Agentic retains F1 ≥ 0.50 on OOD data while Pure ML drops to F1 ≤ 0.20 (effect d > 0.8, large).

## E2.2 Variables

- **IV:** Test domain (2 levels): in-domain (smart manufacturing test split) vs out-of-domain (NASA C-MAPSS FD001 turbofan)
- **DV:** F1 score, Recall, Precision

## E2.3 Procedure

```python
# Phase A: in-domain baseline
ml_in = train_ml(smart_mfg_train); ml_in_f1 = eval(ml_in, smart_mfg_test)
agentic_in = build_agentic(); agentic_in_f1 = eval(agentic_in, smart_mfg_test)

# Phase B: cold-start on C-MAPSS (no retraining for any approach)
cmapss = load_cmapss_FD001()  # 100 turbofan engines
# Map sensors to compatible space
mapped = sensor_remap(cmapss, target_features=['T_proxy','vib_proxy',...])

# Map "near failure" → anomaly label using RUL threshold
gt_cmapss = (cmapss['RUL'] < 30)  # below 30 cycles = anomaly

ml_ood = ml_in.predict(mapped)  # NO retraining
ml_ood_f1 = f1_score(gt_cmapss, ml_ood)

agentic_ood = agentic_in.predict(mapped)  # NO retraining; LLM uses zero-shot
agentic_ood_f1 = f1_score(gt_cmapss, agentic_ood)

# Phase C: report retention
retention_ml = ml_ood_f1 / ml_in_f1
retention_agentic = agentic_ood_f1 / agentic_in_f1
```

## E2.4 Sample size

- C-MAPSS FD001: 100 engines × ~150 cycles each = 15,000 observations
- In-domain test: 25 machines × 1 snapshot
- More than sufficient power (N>>100) for any reasonable effect size

## E2.5 Statistical analysis

- **Primary:** McNemar test on paired (in-domain F1, OOD F1) per approach
- **Secondary:** ANCOVA with domain as factor and approach as treatment
- **Effect size:** Cohen's d on F1 retention ratio

## E2.6 Expected results

| Approach | In-domain F1 | OOD F1 | Retention |
|---|---|---|---|
| Pure ML (LSTM) | 0.85 | 0.10 | 12% |
| Pure Agentic | 0.19 | 0.45 | 237% (rises because in-domain was bottlenecked by other factors) |
| Hybrid QASAMAP | 0.85 | 0.55 | 65% |

**Defense interpretation:** ML cannot generalize across domains; agentic AI uses general physics knowledge to maintain reasonable performance. This is the "deploy to new plant" use case.

## E2.7 Threats to validity

- **External:** C-MAPSS is simulated turbofan data; not all PdM domains will behave the same.
- **Mitigation:** add second OOD dataset (PRONOSTIA bearing) for triangulation.
- **Construct:** Sensor remapping may not preserve semantics.
- **Mitigation:** Document remapping protocol; cite Hines & Garvey 2008 as standard for cross-domain sensor mapping.

---

# E3 — FEW-SHOT ADAPTATION

**Status: Medium priority. Estimated effort: 2-3 days.**

## E3.1 Hypothesis

- **H₀:** F1 score on a held-out failure type does not improve faster with N labeled examples for Hybrid Agentic vs Pure ML.
- **H₁:** Hybrid Agentic reaches "acceptable" F1 (≥ 0.60) with N ≤ 5 examples while Pure ML requires N ≥ 30.

## E3.2 Variables

- **IV1:** Approach (3 levels: Pure ML, Pure Classical with manual rules, Hybrid Agentic with in-context examples)
- **IV2:** Number of labeled examples N (6 levels: 0, 1, 3, 5, 10, 30)
- **DV:** F1 score on held-out failure type

## E3.3 Procedure

```python
# Hold out one failure type (e.g., "Pressure Drop")
HOLDOUT = "Pressure Drop"
train_clean = filter_out(train, failure_type=HOLDOUT)
test_with_holdout = test_with_failure_type(HOLDOUT)  # has Pressure Drop cases

for N in [0, 1, 3, 5, 10, 30]:
    examples = sample_examples(failure_type=HOLDOUT, n=N, seed=42)
    
    # ML: retrain with original train + N new examples
    ml_model = train_lstm(train_clean + examples)
    ml_f1 = eval(ml_model, test_with_holdout)
    
    # Classical: add N manual rules
    rules = derive_rules_from_examples(examples)
    classical_model = build_rules_pipeline(base_rules + rules)
    classical_f1 = eval(classical_model, test_with_holdout)
    
    # Agentic: prepend N examples to LLM prompt as in-context demonstrations
    agentic_model = build_agentic_with_examples(examples)
    agentic_f1 = eval(agentic_model, test_with_holdout)
    
    # Repeat 3 times with different example samples for variance
```

## E3.4 Sample size

Power analysis for mixed-effects model with 3 approaches × 6 N levels × 3 replicates = 54 observations per failure type. With effect size η²=0.10 (medium), α=0.05, achieved power ≥ 0.85.

## E3.5 Statistical analysis

- **Primary:** Mixed-effects regression with random intercept per (approach, N):
  ```
  F1 ~ Approach * log(N+1) + (1 | replicate)
  ```
- **Secondary:** Pairwise comparisons at each N level (Tukey HSD)
- **Effect size:** η² for the Approach × N interaction

## E3.6 Expected results

```
        N=0    N=1    N=3    N=5    N=10   N=30
ML      0.05   0.08   0.12   0.18   0.35   0.65
Classical 0.10  0.20   0.40   0.55   0.65   0.70
Agentic 0.30   0.45   0.60   0.65   0.70   0.72
```

**Interpretation:** Agentic reaches 0.60 at N=3 (operator-deployable in minutes); ML needs N=30 (deployment cycle in days/weeks).

## E3.7 Implementation notes

- Use `scikit-learn StratifiedShuffleSplit` for example sampling
- Cache LLM responses to enable multi-replicate replay
- Plot learning curves with confidence bands (95% CI via bootstrapping)

---

# E4 — OPERATOR DECISION QUALITY (USER STUDY)

**Status: Highest defense impact. Estimated effort: 1 week.**

## E4.1 Hypothesis

- **H₀:** Operator decision accuracy, decision time, and confidence do not differ between ML-only and Hybrid Agentic alert presentations.
- **H₁:** Hybrid Agentic alerts improve decision accuracy (≥ +15 pp), reduce decision time (≥ -25%), and increase confidence (≥ +1.5 on 10-point scale).

## E4.2 Design

**Within-subject A/B comparison** (each rater sees both conditions for different scenarios; counterbalanced).

| Condition | Alert format |
|---|---|
| **Condition A: ML-only** | Anomaly score 0-1, top-3 contributing features (SHAP), threshold breach indicator |
| **Condition B: Hybrid Agentic** | Same as A + LLM Bahasa Indonesia natural-language explanation + recommended action + estimated urgency hours |

## E4.3 Sample design

- **N raters:** 8-10 (target 10 for power; minimum 8 for credible analysis)
- **Scenarios per rater:** 20 (10 condition A, 10 condition B; balanced and counterbalanced)
- **Total observations:** 10 raters × 20 scenarios = 200

### Power analysis
- Within-subject paired t-test, expected d=0.6 (medium-large)
- α = 0.05, target power = 0.80
- Required N (raters) = 24
- **Realistic N:** 8-10 → reduced power to ~0.65; report this honestly

### Mitigation for low N
- Use Bayesian estimation alongside frequentist test
- Report 95% credible intervals
- Frame as "preliminary evidence" if N < 24

## E4.4 Recruitment

**Target population:** Manufacturing maintenance technicians or PhD/MS engineering students with manufacturing background.

**Practical sources:**
- Lab colleagues at Pukyong National University (engineering dept)
- LinkedIn outreach to maintenance professionals
- Online platform: Prolific (filtered to manufacturing experience)

**Inclusion criteria:** ≥ 1 year industrial maintenance OR ≥ 1 year PdM research

**Compensation:** Coffee voucher / token compensation

## E4.5 Materials

### 4.5.1 Scenario set
20 scenarios from test split, balanced:
- 10 true anomalies (different failure modes)
- 10 normal operations (some near-threshold to test discrimination)

Each scenario provided as static "alert page" containing:
- Machine ID, sensor readings
- Last 8 cycles trend chart
- Approach output (Condition A or B format)

### 4.5.2 Operator interface (Streamlit app)
```python
import streamlit as st

# For each scenario
st.write(f"Scenario {idx}/20")
st.write(scenario_data)
st.write(approach_output)  # Either A or B format

action = st.radio("What action would you take?", 
    ["Monitor only", "Schedule inspection", "Schedule maintenance", "Immediate shutdown"])
confidence = st.slider("How confident are you?", 1, 10, 5)
elapsed = time.time() - start_time

st.button("Next →", on_click=record_response)
```

### 4.5.3 Ground truth
For each scenario, "correct" action determined by:
- Domain expert pre-labeling (Vandha + 1 reviewer)
- Cohen's κ inter-rater reliability ≥ 0.7 required

## E4.6 Procedure

1. Pre-screening: rater fills demographic form (experience, role)
2. Tutorial: 2 practice scenarios with feedback
3. Main experiment: 20 randomized scenarios (counterbalanced A/B order)
4. Post-experiment: 5-question survey on perceived usefulness, trust, willingness to use in production

## E4.7 Dependent variables

| Metric | Measurement |
|---|---|
| **Decision accuracy** | Boolean: correct action chosen vs ground truth |
| **Decision time** | Seconds from scenario display to action submitted |
| **Confidence** | 1-10 Likert scale |
| **Trust** | Post-survey 1-10 scale |
| **Perceived usefulness** | Post-survey 5-point Likert |

## E4.8 Statistical analysis

### Primary
- **Paired t-test** (within-subject) for accuracy, time, confidence
- **Wilcoxon signed-rank** as non-parametric alternative
- **Cohen's d_z** effect size for paired data

### Secondary
- **Linear mixed-effects model** with rater as random effect:
  ```
  outcome ~ Condition + scenario_difficulty + (1 | rater_id)
  ```

### Reliability
- **Cronbach's α** for confidence scale (target ≥ 0.7)
- **Cohen's κ** for inter-rater agreement on ground truth

## E4.9 Expected results

| Metric | ML-only | Hybrid Agentic | Δ | Cohen's d |
|---|---|---|---|---|
| Decision accuracy | 65% | 80% | +15 pp | 0.55 |
| Decision time | 45 sec | 28 sec | -38% | -0.70 |
| Confidence | 5.5/10 | 7.0/10 | +1.5 | 0.65 |

## E4.10 IRB / Ethics

- Submit to PKNU Institutional Review Board
- Anonymous data only; no PII collected
- Informed consent form
- Right to withdraw at any time

## E4.11 Implementation checklist

- [ ] IRB approval (start NOW; usually takes 2-4 weeks)
- [ ] Build Streamlit app + scenario JSON
- [ ] Generate Condition A (ML-only) outputs from `full_comparison_8models.py` results
- [ ] Generate Condition B (Hybrid) outputs from `agenticai_enhanced.py` results
- [ ] Pilot test with 2 colleagues to refine scenarios
- [ ] Recruit 8-10 raters
- [ ] Run study (1-2 weeks)
- [ ] Analyze + write up

## E4.12 Threats to validity

- **External:** Lab raters ≠ real operators. **Mitigation:** discuss limitation; recruit at least 2 actual maintenance professionals if possible.
- **Carry-over:** Within-subject design risks A→B learning. **Mitigation:** counterbalance order; analyze for order effects.
- **Hawthorne effect:** Awareness of being studied changes behavior. **Mitigation:** standard A/B blind to condition labels.

---

# E5 — OUT-OF-DISTRIBUTION ROBUSTNESS

**Status: Medium priority. Estimated effort: 3-4 days.**

## E5.1 Hypothesis

- **H₀:** F1 retention under perturbation does not differ between Pure ML and Hybrid Agentic.
- **H₁:** Hybrid Agentic shows greater F1 retention (≥ 70%) than Pure ML (≤ 50%) across perturbation types.

## E5.2 Perturbation types (5 conditions)

| Perturbation | Implementation |
|---|---|
| **P1: Sensor failure** | One feature replaced with NaN or constant value |
| **P2: Combined failure** | Inject simultaneous failure modes (overheating + electrical) |
| **P3: Environmental shift** | All features × 1.2 (heat wave scenario) |
| **P4: Sensor drift** | Slow linear bias added: +0.1 × cycle_index |
| **P5: Adversarial perturbation** | FGSM-style ε-perturbation: +0.05 × sign(gradient) |

## E5.3 Procedure

```python
baseline_f1 = {a: eval(a, test_clean) for a in approaches}

perturbations = [P1_sensor_fail, P2_combined, P3_env_shift, P4_drift, P5_adversarial]
results = {}
for pert in perturbations:
    test_perturbed = pert(test_clean)
    for approach in approaches:
        f1 = eval(approach, test_perturbed)
        results[(approach, pert.name)] = {
            'f1': f1,
            'retention': f1 / baseline_f1[approach],
        }
```

## E5.4 Sample size

5 perturbations × 4 approaches × 3 random seeds = 60 observations.
Power analysis for repeated-measures ANOVA: η²=0.15, α=0.05, achieved power ≥ 0.85.

## E5.5 Statistical analysis

- **Primary:** Repeated-measures ANOVA (Approach × Perturbation factorial)
- **Post-hoc:** Tukey HSD for pairwise comparisons
- **Effect size:** η² for main effects + interaction
- Sphericity check (Mauchly's test); Greenhouse-Geisser correction if violated

## E5.6 Expected results

| Approach | P1 (sensor) | P2 (combo) | P3 (env shift) | P4 (drift) | P5 (adversarial) | Mean |
|---|---|---|---|---|---|---|
| Pure ML | 0.40 | 0.50 | 0.60 | 0.55 | 0.20 | 0.45 |
| Pure Classical | 0.60 | 0.40 | 0.55 | 0.50 | 0.45 | 0.50 |
| Pure Agentic | 0.50 | 0.65 | 0.70 | 0.60 | 0.55 | 0.60 |
| Hybrid QASAMAP | 0.70 | 0.75 | 0.80 | 0.70 | 0.60 | 0.71 |

---

# E6 — MULTI-AGENT COORDINATION ABLATION

**Status: HIGH priority for thesis (justifies 9-agent design). Estimated effort: 3-4 days.**

## E6.1 Hypothesis

- **H₀:** Decision quality (composite score) does not differ across single-agent, sequential 4-agent, and specialized 9-agent configurations.
- **H₁:** Specialized 9-agent achieves significantly higher composite score than single-agent (≥ +15%) AND sequential 4-agent (≥ +5%).

## E6.2 Conditions (3 levels)

| Condition | Description |
|---|---|
| **C1: Single-Call** | One LLM call with full system prompt asking for all 8 dimensions in one JSON response |
| **C2: Sequential-4** | Monitoring → Diagnosis → Planning → Reporting agents (no specialized prompts beyond standard) |
| **C3: Specialized-9** | Current QASAMAP: Monitoring + Diagnosis + Planning + Reporting + Correlation + Explainability + Self-Reflection + Scheduling + Pattern Learning |

All three conditions use same LLM model (`glm-5.1:cloud`) and same input data.

## E6.3 Composite quality score (DV)

Per-machine composite score (range [0, 1]):

```
Q = 0.30 × decision_accuracy_correctness     # vs ground truth
  + 0.20 × output_structure_compliance        # % valid JSON, all required fields
  + 0.20 × reasoning_depth                    # # reasoning steps articulated
  + 0.15 × cross_dimension_consistency        # diagnosis matches planning?
  + 0.15 × explanation_quality                # rated by LLM-as-judge (GPT-4 or similar)
```

## E6.4 Sample size

- 25 test machines × 3 conditions × 3 random seeds = 225 observations
- Power analysis: one-way ANOVA, η²=0.10 (medium), α=0.05 → required N=126; have 225
- Achieved power > 0.95

## E6.5 Statistical analysis

- **Primary:** One-way repeated-measures ANOVA on composite Q
- **Post-hoc:** Tukey HSD for C1 vs C2 vs C3
- **Effect size:** η² + Cohen's d for pairwise

## E6.6 Cost-benefit reporting

In addition to quality, report:
- Total LLM tokens used
- Total wall-clock time
- Cost per decision

Expected:
| Condition | Quality Q | Tokens | Cost | Time |
|---|---|---|---|---|
| C1 Single | 0.50 | 1.2K | $0.06 | 12s |
| C2 Sequential-4 | 0.65 | 4.5K | $0.22 | 45s |
| C3 Specialized-9 | 0.78 | 8.0K | $0.40 | 90s |

**Defense narrative:** "9-agent specialization adds 56% quality at 6.7× cost; cost amortized across maintenance prevention savings."

## E6.7 Implementation

### C1 Single-Call prompt
```
SYSTEM: You are a smart-manufacturing PdM assistant. Given a machine's sensor 
data and threshold flags, return JSON with ALL of: risk_level, anomaly_detected, 
anomaly_type, probable_cause, affected_component, urgency_hours, action, priority, 
notify_supervisor, what_if_explanation, correlated_machines, BI_alert_text.
```

### C2 Sequential-4
Reuse existing 4-agent code (Monitoring → Diagnosis → Planning → Reporting).

### C3 Specialized-9
Reuse current `agenticai_enhanced.py` MultiAgentOrchestrator.

## E6.8 Implementation checklist

- [ ] Implement C1 Single-Call prompt (1 day)
- [ ] Use existing C2/C3 code with cost/time instrumentation (0.5 day)
- [ ] Run all 3 conditions × 25 machines × 3 seeds (1 day, ~3-4h LLM time)
- [ ] LLM-as-judge for explanation_quality (use Claude or GPT-4 as independent rater)
- [ ] Statistical analysis + write-up (1 day)

---

# CROSS-EXPERIMENT IMPLEMENTATION PLAN

## Critical-path scheduling (assuming 7-week window)

```
Week 1: Setup + E1 (Capability Coverage)
  Mon: Pre-registration document, IRB submission for E4
  Tue-Wed: E1 implementation (formalize comparative_study.py output)
  Thu-Fri: E1 statistical analysis + figure generation

Week 2: E6 (Multi-Agent Ablation) - critical thesis claim
  Mon-Tue: Implement C1 Single-Call + cost instrumentation
  Wed-Thu: Run all conditions × 3 seeds
  Fri: Analysis + Tukey HSD + cost-benefit table

Week 3: E2 (Cold-Start with C-MAPSS)
  Mon: Download C-MAPSS FD001 + sensor remapping
  Tue-Wed: Run all approaches on C-MAPSS
  Thu-Fri: Statistical analysis + retention curves

Week 4: E3 (Few-Shot)
  Mon-Tue: Implement holdout protocol + replicates
  Wed-Thu: Run × 3 replicates × 6 N levels
  Fri: Mixed-effects model fitting

Week 5: E5 (OOD Robustness)
  Mon-Tue: Implement 5 perturbation generators
  Wed-Thu: Run all approaches × 5 perturbations × 3 seeds
  Fri: Repeated-measures ANOVA

Week 6: E4 (User Study) — critical-path; may need to start earlier
  Mon-Tue: Build Streamlit app + 20 scenarios
  Wed: Pilot test with 2 colleagues
  Thu-Fri: Recruit 8-10 raters; run study

Week 7: Synthesis
  Mon-Wed: Combine all results into master table + figures
  Thu: FDR correction across all hypotheses
  Fri: Limitations section + write-up draft
```

## Resource requirements

| Resource | Details |
|---|---|
| Compute | Existing setup (CPU-only OK for inference; trained ML models can use GPU available) |
| LLM API | ~10K Ollama calls @ glm-5.1:cloud. Estimated cost: $50-100 |
| External datasets | NASA C-MAPSS (free public, ~50MB), optional PRONOSTIA |
| User study tools | Streamlit (free), Google Forms backup |
| Statistical software | Python + scipy/statsmodels (free) |
| Domain expert | Vandha (self) + 1 reviewer for E4 ground truth |
| Raters for E4 | 8-10 colleagues / engineering students |
| IRB | PKNU IRB submission (free; 2-4 week turnaround) |

**Total cost estimate:** USD 100-200 (LLM API) + 1-2 weeks IRB wait time + 7 weeks execution.

## Pre-registration deliverable

Before starting Week 1 execution, commit to git:
```
experiments/
├── pre_registration.json       # all hypotheses, sample sizes, alpha levels
├── splits/
│   ├── train_machine_ids.json
│   ├── test_machine_ids.json
│   └── holdout_failure_modes.json
├── seeds.json                   # [42, 7, 1234]
├── E1_capability_coverage/
│   ├── protocol.md
│   └── analysis.py (skeleton)
├── E2_cold_start/
├── E3_few_shot/
├── E4_user_study/
├── E5_ood_robustness/
└── E6_multi_agent_ablation/
```

## Reporting format for thesis

For each experiment, report following block (Bem 2003-style):

```
## Experiment X: [Name]

### Hypothesis
[Pre-registered H0 and H1]

### Method
- Participants/data
- Procedure
- Materials
- Measures

### Results
- Descriptive statistics (table)
- Inferential statistics (test, df, statistic, p, effect size, 95% CI)
- Figure (with caption)

### Discussion
- Interpretation
- Limitations
- Implications for QASAMAP architecture
```

## What success looks like

By end of Phase 2 execution, you should have:

1. **6 statistically-rigorous experiments** with p-values, effect sizes, 95% CI
2. **6 figures** ready for thesis
3. **Honest limitations section** (per experiment + overall)
4. **Pareto frontier visualization** updated with empirical data
5. **Defense Q&A** rehearsed against actual data

## Risk register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| IRB delay for E4 | High | High | Submit week 1; have batch backup if unavailable |
| Insufficient raters (E4 N<8) | Medium | Medium | Bayesian analysis + clearly-stated preliminary status |
| C-MAPSS sensor mapping fails (E2) | Low | Medium | Use raw 3-feature subset (T_outlet, fan_speed, bypass_ratio) |
| LLM API rate limits | Medium | Low | Cache responses; implement exponential backoff |
| Trained ML overfits with few-shot examples (E3) | High | Low | Expected result; report honestly |
| Multi-comparison correction kills significance | Medium | High | Power analysis up-front; use FDR not Bonferroni for less conservative |

---

# ALL PROTOCOLS — SUMMARY MATRIX

| # | Experiment | VP Tested | N | Test | Effect target | Effort |
|---|---|---|---|---|---|---|
| **E1** | Capability Coverage | VP4 (cross-domain) | 25 × 4 × 8 | McNemar + Cochran's Q | w > 0.3 | 2 days |
| **E2** | Cold-Start | VP1 (zero-shot) | 100 engines | McNemar + ANCOVA | d > 0.8 | 3-4 days |
| **E3** | Few-Shot | VP5 (in-context) | 3 × 6 × 3 | Mixed-effects | η² > 0.10 | 2-3 days |
| **E4** | Operator Quality | VP2 (NL communication) | 8-10 raters × 20 | Paired t / Wilcoxon | d > 0.5 | 1 week |
| **E5** | OOD Robustness | VP1, VP6 (general robustness) | 25 × 4 × 5 × 3 | RM-ANOVA + Tukey | η² > 0.15 | 3-4 days |
| **E6** | Multi-Agent Ablation | VP3 (autonomous pipelines) | 25 × 3 × 3 | RM-ANOVA + Tukey | η² > 0.10 | 3-4 days |

---

# CRITICAL-PATH MINIMUM SET FOR DEFENSE

If timeline is tight, **execute these three first** (cover 4 of 6 VPs, full defense narrative):

1. **E1 Capability Coverage** (2 days) → covers VP3, VP4, indirectly VP6
2. **E6 Multi-Agent Ablation** (3-4 days) → covers VP3 (justifies 9-agent design)
3. **E4 Operator Decision Quality** (1 week, but start IRB now) → covers VP2 (highest defense leverage)

Total minimum-viable: ~2 weeks execution + 4 weeks IRB lead.

E2/E3/E5 are "nice-to-have" → execute if time permits, otherwise discuss as future work.

---

# NEXT STEPS

1. ✅ This Phase 1 deliverable approved
2. ⏭️ **Phase 2 — Execution**: implement experiments per protocol
3. ⏭️ **Phase 3 — Statistical Analysis**: aggregate, FDR-correct, visualize
4. ⏭️ **Phase 4 — Limitations**: honest discussion section
5. ⏭️ **Phase 5 — Write-up**: integrate into thesis Chapter 5

**END OF PHASE 1 DELIVERABLE**
