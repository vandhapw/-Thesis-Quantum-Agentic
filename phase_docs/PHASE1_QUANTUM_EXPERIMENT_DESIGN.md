# PHASE 1 — Quantum Experiment Design Protocols
## QASAMAP Thesis: Empirical Validation of Quantum Computational Layer

**Author:** Vandha Widartha (PhD candidate, Pukyong National University)
**Date prepared:** 2026-05-03
**Document purpose:** Formal experimental protocols for thesis Chapter 6.3.
This document specifies pre-registered quantum experiments with NISQ-honest framing sufficient for thesis defense.

---

## ⚠️ CRITICAL FRAMING — MUST PRECEDE ALL CLAIMS

Quantum computing in QASAMAP is in the **NISQ era with simulator-based evaluation**. This Phase 1 protocol explicitly:

1. **Does NOT claim quantum advantage** over classical for general PdM tasks.
2. **Tests for empirical parity** — i.e., that the quantum layer reaches comparable solution quality on real QASAMAP problem instances.
3. **Reports honest cost in time** — quantum simulator runtime is intentionally tracked even though it is *upper-bounded* by hardware: a quantum-simulator that takes 60 s today on a small QUBO will, in principle, run in ms on real hardware (subject to compilation overhead, noise, calibration).
4. **Uses pre-registered ablation framing** — quantum component is ON / OFF, classical baseline is brute-force or simulated annealing — so any "quantum win" claim requires significance test against well-tuned classical.
5. **All results disclose simulator backend, qubit count, shots, depth** — to make honest reproducibility possible.

This honest framing is **defense-proof**; overclaim framing will fail.

---

## 0. CROSS-CUTTING METHODOLOGICAL FRAMEWORK

### 0.1 Pre-registration commitment

Both quantum experiments (E-Q1, E-Q3) are **pre-registered** before execution. Hypotheses, sample sizes, statistical tests, and significance thresholds are fixed BEFORE data collection. Any deviation requires explicit justification in the report.

### 0.2 Notation (consistent with agentic Phase 1)

| Symbol | Meaning |
|---|---|
| `H₀` / `H₁` | Null / alternative hypothesis |
| `α` | Type I error rate (set to 0.05 throughout, FDR-corrected for multi-test families) |
| `β` / `1-β` | Type II error / statistical power (target ≥ 0.80) |
| `d` | Cohen's d (effect size for paired t-test) |
| `r` | Spearman / matched-rank correlation effect size |
| `δ` | Cliff's delta (non-parametric effect size) |
| `N` | Sample size (problem instances or test cases) |
| `Q` | QUBO matrix |
| `H` | Hamiltonian operator |
| `⟨ψ|H|ψ⟩` | Expectation value of H on state ψ |

### 0.3 Quantum stack & reproducibility

| Component | Library | Version-pinned use |
|---|---|---|
| Statevector simulator | `qiskit-aer ≥ 0.13` | E-Q3 Pauli-Z exact expectation |
| QAOA optimizer | `qiskit-algorithms ≥ 0.3` + `qiskit-aer` | E-Q1 ansatz + COBYLA optimizer |
| QUBO conversion | `qiskit-optimization ≥ 0.6` | E-Q1 problem encoding |
| Simulated annealing | `dwave-neal ≥ 0.6` | E-Q1 strong classical baseline |
| Brute-force exact | NumPy enumeration | E-Q1 ground-truth optimum (small N only) |
| Statistical tests | `scipy.stats`, `statsmodels` | shared with agentic Phase 1 |

**Reproducibility checklist**

- [ ] Fixed seeds (`numpy seed=42`, `qiskit_algorithms_global_seed=42`, `neal seed=42`)
- [ ] Multi-seed protocol for stochastic QAOA: `[42, 7, 1234]` → report mean ± std
- [ ] All circuits saved as `qasm` text in `experiments/E-Q*/circuits/`
- [ ] All optimization traces saved as JSON in `experiments/E-Q*/traces/`
- [ ] Backend disclosure mandatory in every result row (statevector vs noisy, qubit count, shots)

### 0.4 Cross-experiment data definitions

| Asset | Source | Use |
|---|---|---|
| **Train/test split** | Same as agentic Phase 1 (51 machines, even/odd id) | E-Q3 detection eval |
| **Sensor bounds** | `sensor_bounds_derived.json` | E-Q3 normalization |
| **QUBO problem instances** | Synthetic QASAMAP scheduling: N machines × T time slots × cost matrix derived from MongoDB risk_score | E-Q1 |
| **Risk score field** | MongoDB collection digital_twin output | E-Q1 cost matrix construction |

### 0.5 Honest reporting requirements

Every quantum experiment report MUST include:

1. **Backend disclosure** — `aer_simulator_statevector` vs `aer_simulator_density_matrix`, ideal vs noisy
2. **Qubit count, circuit depth, gate count** per problem instance
3. **Wall-clock timing breakdown** — circuit construction, transpilation, shot execution, classical optimizer iterations
4. **Comparison vs strong classical baseline** — never just "quantum vs random"
5. **Effect size + p-value + 95% CI** for any claim of difference
6. **Explicit statement** of whether result is "advantage", "parity", or "deficit" relative to classical

### 0.6 Validity threats addressed

| Threat | Mitigation |
|---|---|
| **"Toy problem" critique** | Use REAL QASAMAP machine instances + REAL risk scores from MongoDB digital twin |
| **Simulator ≠ hardware** | Explicitly disclose statevector vs noisy backend; report depth as proxy for hardware feasibility |
| **Cherry-picked QAOA depth** | Pre-register p ∈ {1, 2, 3} layers; report all, not just best |
| **Optimizer hyperparameter fishing** | Pre-register COBYLA maxiter=200, no tuning beyond pre-reg |
| **Selection bias on problem instances** | Random sampling with fixed seed from QASAMAP test split |

---

# E-Q3 — PAULI-Z COMPOUND ANOMALY DETECTION

**Pre-registration date:** 2026-05-03
**Status:** Pre-registered, ready for execution

## E-Q3.1 Research question

> *Does a multi-qubit Pauli-Z encoded compound score on QASAMAP sensor inputs offer empirically demonstrable detection improvement over a tuned single-threshold classical baseline on the same data?*

## E-Q3.2 Hypotheses

- **H₀ (null):** F1 of Pauli-Z compound detector equals F1 of best single-threshold classical detector on QASAMAP test split (mean diff = 0).
- **H₁ (alternative):** Pauli-Z compound F1 differs from single-threshold F1 (two-tailed; honest, no direction asserted because simulator-based parity is the realistic expectation).

## E-Q3.3 Quantum encoding (honest specification)

Five sensor inputs `(temperature, vibration, humidity, pressure, energy_consumption)` are normalized to `[0, π]` using bounds from `sensor_bounds_derived.json`, then encoded into a 5-qubit register via single-qubit `RY(θᵢ)` rotations. The compound score is computed as the expectation value:

```
S_quantum(machine) = ⟨ψ| Σᵢ Zᵢ ⊗ Iⱼ≠ᵢ |ψ⟩
                   = Σᵢ cos(θᵢ)
```

Plus an entangling layer `CNOT(0,1) · CNOT(1,2) · CNOT(2,3) · CNOT(3,4)` followed by re-evaluation:

```
S_entangled(machine) = ⟨ψ_entangled| Σᵢ Zᵢ |ψ_entangled⟩
```

Detection threshold τ chosen by ROC-on-train-split (point of max Youden's J). Final detection: `anomaly = S_entangled < τ`.

**Honest note:** Without entanglement the score equals the sum of cosines — equivalent to a classical weighted sum. The entanglement layer is what provides the *quantum* component; we explicitly evaluate both `S_quantum` (separable, ≡ classical) and `S_entangled` (genuinely quantum) so any difference is attributable to entanglement, not to "having quantum in the name".

## E-Q3.4 Classical baselines (strong, not strawmen)

| Baseline | Method | Justification |
|---|---|---|
| **B1: Best single-threshold** | per-sensor optimal Youden threshold, OR-aggregated | Strong classical floor |
| **B2: Multivariate Mahalanobis** | Mahalanobis distance from training mean covariance, threshold by ROC | Statistical multi-sensor baseline |
| **B3: Weighted-sum classical** | Σᵢ wᵢ·cos(θᵢ) — equivalent to `S_quantum` separable form | Direct algorithmic equivalent test |

If `S_entangled` does not beat B3 (its separable counterpart), then the entanglement adds no detection value — that is an honest negative result we must report.

## E-Q3.5 Sample size & power analysis

- Test split: 25 machines × ground-truth labels from digital-twin classifier
- For paired-machine F1 comparison, McNemar test power calculation: with discordant pair rate ≥ 0.20, N=25 yields power = 0.80 to detect a 25% effect difference at α=0.05
- Multi-seed (qubit ordering shuffles for noise-free statevector): `[42, 7, 1234]` (Statevector is deterministic; multi-seed only for shot-based mode if used)

## E-Q3.6 Pre-registered procedure

1. Load test split from `smart_manufacturing_data.csv` (odd machine_id).
2. Normalize each row's 5 sensors using `sensor_bounds_derived.json` to angles in `[0, π]`.
3. For each machine row:
   a. Build `RY⊗5` circuit
   b. Compute `S_quantum` via statevector
   c. Apply entangling layer, compute `S_entangled`
   d. Compute B1/B2/B3 baselines
4. Threshold each detector via ROC-on-train (held-out from test).
5. Predict anomaly per machine; compare vs ground-truth.
6. Report F1, precision, recall, McNemar p-value vs each baseline.
7. Report Cliff's δ effect size for raw score distributions.

## E-Q3.7 Statistical analysis plan

- McNemar test (binary disagreement) for `S_entangled` vs each baseline (B1, B2, B3)
- Bonferroni-correct over 3 comparisons (α=0.0167 per test)
- Cliff's δ on raw score distributions, separated by ground-truth class
- Report 95% Wilson CI on F1 estimates

## E-Q3.8 Honest expected outcome

Pre-execution honest expectation:

- `S_quantum` (separable) F1 ≈ B3 (mathematically equivalent, must be within seed/numerical tolerance)
- `S_entangled` F1 ≈ B1/B2 ± 5% (parity expected; entanglement on uncorrelated sensors should not provide major advantage)
- Most likely outcome: **NO statistically significant difference** at N=25, α=0.0167 Bonferroni
- This is **acceptable as PARITY result** — supports Q-VP3 ("sub-threshold detection capability exists with quantum-equivalent expressive power") without overclaiming.

## E-Q3.9 What CAN be claimed if H₀ NOT rejected

> *"The Pauli-Z compound detector achieves F1 within ε of best classical baseline at N=25 machines. This empirical parity demonstrates that the quantum representation is not a deficit relative to classical methods on QASAMAP test data — a necessary precondition for future-hardware advantage but not in itself a demonstration of quantum superiority."*

## E-Q3.10 What CAN be claimed if H₀ rejected (in either direction)

- If S_entangled BEATS classical: report effect size + warn that simulator-only result must be replicated on noisy hardware before strong claims
- If S_entangled LOSES to classical: report honestly; argue that the entanglement choice / encoding may need refinement; defer hardware evaluation as future work

---

# E-Q1 — SA vs SIMULATED QAOA SCHEDULING ABLATION

**Pre-registration date:** 2026-05-03
**Status:** Pre-registered, ready for execution

## E-Q1.1 Research question

> *Does a simulated QAOA solver for QASAMAP maintenance scheduling QUBO achieve solution-quality parity with a tuned classical Simulated Annealing solver across a range of problem sizes, and how does its wall-clock cost scale?*

## E-Q1.2 Hypotheses

- **H₀ (parity null):** Mean QAOA solution cost equals mean SA solution cost on identical QUBO instances (paired difference = 0).
- **H₁ (parity rejection):** QAOA mean cost differs from SA mean cost by more than the brute-force-distance threshold (paired difference ≠ 0, two-tailed).

For runtime:
- **H₀_runtime:** Wall-clock(QAOA simulator) ≤ 10× Wall-clock(SA) on small instances (N ≤ 8 machines).
- **H₁_runtime:** Wall-clock(QAOA simulator) > 10× Wall-clock(SA) — honest expected outcome given simulator overhead.

## E-Q1.3 QUBO formulation

QASAMAP maintenance scheduling assigns each of `N` machines to one of `T` maintenance time slots. Decision variables: `x_{i,t} ∈ {0,1}` = 1 iff machine i scheduled in slot t. Constraints + objective:

```
minimize  H = Σ_t (Σ_i r_i x_{i,t})²              [load-balance: avoid concentrating high-risk maintenance]
            + λ_1 · Σ_i (1 - Σ_t x_{i,t})²        [each machine assigned exactly once]
            + λ_2 · Σ_{i,t} x_{i,t} · (1 - urgency_i,t)   [prefer urgent slots first]
```

where `r_i` = risk score for machine i (from MongoDB digital-twin `risk_score` field), `urgency_{i,t} = 1/(1+t·(1-r_i))` (urgent machines bias toward earlier slots).

This produces an `N·T`-variable QUBO. Penalty weights `λ_1=10, λ_2=1` pre-registered (no tuning beyond this).

## E-Q1.4 Problem instance generation

Sweep grid:

| N (machines) | T (slots) | Variables = N·T | Quantum-simulable? | Brute-force feasible? |
|---|---|---|---|---|
| 2 | 2 | 4 | yes (4 qubits) | yes (16 states) |
| 3 | 3 | 9 | yes (9 qubits) | yes (512 states) |
| 4 | 3 | 12 | yes (12 qubits) | yes (4096 states) |
| 5 | 3 | 15 | yes (15 qubits) | yes (32K states) |
| 6 | 3 | 18 | tight (18 qubits, ~3 GB statevector) | yes (262K states) |
| 8 | 3 | 24 | very tight | yes (16M states; 1-2 min) |
| 10 | 4 | 40 | NO (40 qubits exceeds simulator practical limit) | NO (1 trillion) |

**Pre-registered execution scope:** N·T ∈ {4, 9, 12, 15, 18, 24}. N·T=40 included as **SA-only stress test** (no quantum comparison possible at simulator scale — honest disclosure of NISQ limitation).

5 random seeds per problem size → 30 problem instances total for quantum-comparable rows.

## E-Q1.5 Solvers compared

| Solver | Library | Hyperparameters | Reports |
|---|---|---|---|
| **Brute-force exact** | NumPy | enumerate all 2^(N·T) | true optimum, optimal cost |
| **Simulated Annealing** | `dwave-neal SimulatedAnnealingSampler` | num_reads=100, beta_range=auto | best of 100 reads |
| **QAOA p=1** | `qiskit-algorithms QAOA` + Aer statevector | reps=1, COBYLA maxiter=200 | best sampled state |
| **QAOA p=2** | same | reps=2 | same |
| **QAOA p=3** | same | reps=3 | same |
| **Greedy** | argsort on risk score | none | tie-breaker baseline |

For each instance & solver, record: best cost, time-to-best, total wall-clock, gap to brute-force optimum (ratio).

## E-Q1.6 Sample size & power analysis

- 5 seeds × 6 problem-size rows = 30 paired observations per (QAOA, SA) comparison
- For paired t-test on cost gap, with σ ≈ 0.1·optimum and target effect d=0.5, N=30 yields power ≈ 0.75 at α=0.05 (slightly under 0.80 — acceptable for parity test where rejection is not the goal)
- Wilcoxon signed-rank as non-parametric backup if normality fails Shapiro-Wilk

## E-Q1.7 Pre-registered procedure

1. For each problem size (N, T) in pre-registered grid:
   a. For each seed in [42, 7, 1234, 100, 200]:
      - Sample N machine risk scores from MongoDB (or synthetic uniform if MongoDB unavailable — disclose which)
      - Build QUBO matrix
      - Run brute-force enumeration → optimum_cost
      - Run SA with 100 reads → SA_cost, SA_time
      - Run QAOA p=1, p=2, p=3 → QAOA_cost_p, QAOA_time_p
      - Record gap_ratio = solver_cost / optimum_cost
2. Aggregate results across seeds (mean ± std per (size, solver))
3. Statistical tests:
   - Paired t-test on log(gap_ratio): QAOA_p3 vs SA
   - Wilcoxon signed-rank as backup
4. Runtime analysis: log-log plot of wall-clock vs N·T per solver

## E-Q1.8 Honest expected outcome

Pre-execution honest expectation:

- Brute-force is exact (gap = 1.0 by definition)
- SA gap ≈ 1.00–1.05 (SA is very strong on this size)
- QAOA p=1 gap likely ≈ 1.10–1.30 (NISQ p=1 known to underperform)
- QAOA p=3 gap likely ≈ 1.05–1.15
- Wall-clock: SA = ms, QAOA simulator = seconds to minutes (orders of magnitude slower)

**Most likely outcome:** SA wins on both quality and runtime; QAOA achieves *competitive* (within ~10–15%) but not better solution quality at much higher simulator runtime.

This is the **realistic NISQ-era result**. We will report it honestly as PARITY + simulator-runtime-deficit, with the explicit framing that QAOA's wall-clock disadvantage is *simulator-imposed*, not algorithmic — real hardware would change the picture.

## E-Q1.9 What CAN be claimed (regardless of outcome)

✅ **Solution quality parity demonstrated** if QAOA gap_ratio is within 1.15× SA gap_ratio across all problem sizes
✅ **Architectural readiness** — QASAMAP scheduling integrates a working QAOA module that produces feasible, near-optimal schedules
✅ **Cost transparency** — wall-clock cost is honestly reported; deficit attributed to simulator, not algorithm
✅ **Industrial precedent context** — D-Wave + Ford Otosan, BASF show real-hardware quantum has demonstrated speedup in adjacent scheduling problems (cite from Phase 0)

## E-Q1.10 What CANNOT be claimed (avoid overclaim)

❌ "QAOA outperforms SA" — almost certainly false at simulator scale
❌ "Quantum scheduling speedup" — wall-clock is dominated by simulator overhead, not algorithm
❌ "Hardware advantage demonstrated" — no real hardware was used
❌ "QASAMAP delivers quantum advantage" — only parity at simulator scale is reachable here

---

# 2. CRITICAL-PATH SUMMARY

| Experiment | Status | Effort | Defense value |
|---|---|---|---|
| E-Q3 (Pauli-Z compound detection) | Pre-registered | ~1 day implementation + ~1 hour execution | Provides quantum-encoding parity claim for Q-VP3 |
| E-Q1 (SA vs simulated QAOA) | Pre-registered | ~1 day implementation + ~2-4 hours execution | Provides scheduling parity + architectural readiness for Q-VP1 |

Both experiments produce **defense-proof PARITY claims** with honest NISQ caveats. Neither claims quantum advantage. Both anchor the QASAMAP "future-ready quantum layer" narrative.

# 3. INTEGRATION WITH AGENTIC PHASE 2

After E-Q1 and E-Q3 execute, results are appended to `PHASE2_RESULTS_MASTER_REPORT.md` under a new section "Quantum Track" so Option D chapter writing has the full unified portfolio:

- Agentic track: E1 (strong) + E3, E5 (preliminary) + E6 (counter-result, reconciled) + E2, E4 (deferred)
- Quantum track: E-Q1 + E-Q3 (parity expected, honest cost disclosure)

# 4. PRE-REGISTRATION HASH

Once this document is committed to git, its SHA constitutes the pre-registration timestamp. Any changes to hypotheses or procedures after that point require explicit deviation justification in the result reports.

---

**End of Phase 1 Quantum Experiment Design.**
