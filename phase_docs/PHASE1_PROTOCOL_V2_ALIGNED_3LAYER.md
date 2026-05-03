# PHASE 1 — Pre-Registration Protocol V2
## QASAMAP Thesis: 3-Layer Architecture Aligned with Supervisor Design

**Author:** Vandha Pradwiyasma Widartha (PhD candidate, Pukyong National University)
**Date prepared:** 2026-05-04
**Status:** Pre-registered protocol; supersedes V1 (E1, E3, E5, E6, E-Q1, E-Q3) which was misaligned with thesis 3-layer design.

---

## 0. CRITICAL RE-ALIGNMENT NOTICE

Phase 1 V1 (PHASE1_EXPERIMENT_DESIGN.md and PHASE1_QUANTUM_EXPERIMENT_DESIGN.md, dated 2026-05-03) misinterpreted the thesis 3-layer architecture. V1 designed quantum experiments for **anomaly detection** (E-Q3 Pauli-Z) and treated multi-agent vs single-call as a quality competition (E6) — neither of which matches the supervisor-confirmed design.

**V2 corrects this** by aligning fully with the 3-layer architecture:

| Layer | Function | V1 misalignment | V2 correction |
|---|---|---|---|
| **Layer 1** | T-GCN + Kafka real-time forecasting | (existing, no change needed) | Documented as upstream input source |
| **Layer 2** | **Agentic AI multi-tier detection** | E1/E3/E5/E6 framed as VP capability matrix; quantum used here too | **Single experiment E-L2**: 4-LLM ensemble for 4-tier detection, validated against composite GT |
| **Layer 3** | **Scheduling optimization (classical vs quantum)** | E-Q1 used synthetic risk + wrong constraints | **E-L3A static + E-L3B dynamic**: real maintenance constraints (work hours, employees, durations) |

**V1 experiments archived for git history; V2 is the active execution plan.**

---

## 1. 3-LAYER ARCHITECTURE (per supervisor confirmation)

### Layer 1 — T-GCN + Kafka Real-Time Forecasting (existing)

- Apache Kafka producer streaming sensor data every 1 minute
- T-GCN spatiotemporal model consumes stream, produces per-machine sensor forecasts
- Already deployed (Skenario A weighted-influence + Skenario B true multi-node forward at remote 10.247.166.188)
- **No new experiment in V2** — output of Layer 1 (sensor stream + T-GCN forecasts) feeds Layer 2

### Layer 2 — Agentic AI Multi-Tier Detection (V2 NEW)

- Input: real-time sensor + T-GCN output (per machine)
- Multi-agent LLM orchestration → produces **4-tier criticality label** per machine
- Output feeds Layer 3 as candidate maintenance machines
- **MUST** be validated before Layer 3 can run (see Section 7)

### Layer 3 — Scheduling Optimization Classical vs Quantum (V2 NEW)

- Input: machines flagged Critical+High by Layer 2 + current real-time clock
- Constraints (industrial-realistic):
  - Working hours **09:00–18:00** (9 slots × 60 min/day)
  - Working days **Monday–Friday**
  - Employee pool sizes sweep: small (1–3), medium (3–5), large (5–20)
  - Employee skills interchangeable, multi-task sequential
  - Maintenance duration per failure type (literature-anchored, see §4.2)
- Problem class: **NP-Hard** combinatorial scheduling
- **Comparison**: classical (GA, SA, TS) vs quantum (QAOA, Quantum Annealing) vs quantum-inspired (Simulated Bifurcation)
- Two sub-experiments:
  - **E-L3A** static (one-shot scheduling for given problem instance)
  - **E-L3B** dynamic rolling-horizon (event-driven re-scheduling)

---

## 2. COMPOSITE GROUND TRUTH FORMULA

Reference: **Lei et al. 2018** *"Machinery health prognostics: A systematic review from data acquisition to RUL prediction"* Mech. Syst. Signal Process. 104, 799-834; **ISO 13374-2:2007** Condition monitoring and diagnostics — Data processing.

Each test machine row receives a tier label `t ∈ {Critical, High, Medium, Low}` per:

```python
def composite_gt_tier(row):
    rul = row['predicted_remaining_life']
    af  = row['anomaly_flag']
    ft  = row['failure_type']
    mr  = row['maintenance_required']
    dr  = row['downtime_risk']
    if (rul < 10) or (af == 1 and ft in {'Electrical Fault', 'Pressure Drop'}) or (dr >= 0.8):
        return 'Critical'
    if (10 <= rul < 50) or (mr == 1 and af == 1):
        return 'High'
    if mr == 1 or af == 1:
        return 'Medium'
    return 'Low'
```

Rule precedence: top-down (first match wins). Critical takes precedence over all lower tiers if any criterion holds.

**Pre-registered**: this formula is fixed before any LLM evaluation; no post-hoc adjustment.

---

## 3. EXPERIMENT E-L2 — AGENTIC AI MULTI-TIER DETECTION VALIDATION

### 3.1 Research question

> *Does a 4-LLM cloud agentic ensemble achieve substantial agreement with the composite ground truth criticality tier on QASAMAP test machines under multi-window evaluation?*

### 3.2 Hypothesis

- **H₀** (null): 4-LLM ensemble Quadratic-Weighted Kappa with composite GT < 0.6 (less than substantial agreement per Landis-Koch 1977).
- **H₁** (alternative): 4-LLM ensemble Quadratic-Weighted Kappa ≥ 0.6.

### 3.3 LLM ensemble specification

Four cloud LLMs via Ollama Cloud API:
- `glm-5.1:cloud`
- `qwen3.5:cloud`
- `kimi-k2.6:cloud`
- `deepseek-v4-pro:cloud`

**Aggregation method**: each LLM independently runs the full prompt → returns one tier per machine. Final ensemble tier = **majority vote** across 4 LLMs. Tie-break: highest tier wins (conservative bias toward maintenance).

### 3.4 Prompt design (fixed before execution)

Single per-machine prompt template includes:
- Sensor readings (5 channels: temperature, vibration, humidity, pressure, energy)
- T-GCN forecasted next-step values (if available; else marked "not available")
- Operating bounds (`sensor_bounds_derived.json` p05/p50/p90/p99/min/max per sensor)
- Failure type prior (from `smart_manufacturing_data.csv`)
- Tier definitions (4 tiers with per-tier criteria written in plain English, NOT the GT formula — to avoid label leakage)
- Output schema: strict JSON `{"tier": "...", "reasoning": "...", "confidence": 0.0-1.0}`

Prompt frozen as `experiments/E-L2_agentic_validation/prompt_template.md` before execution.

### 3.5 Sample design

- **25 test machines** (odd machine_id, per existing test/train split)
- **5 evaluation windows** per machine (each window = 60-minute Kafka snapshot, sampled at random non-overlapping timestamps from machine's history)
- Total: **125 evaluation cases**
- Each case scored by all 4 LLMs → 500 LLM calls total

### 3.6 Validation metrics (pre-registered)

**Primary metric:**
1. **Cohen's Quadratic-Weighted Kappa** (Cohen 1968 *Educ. Psychol. Meas.*) between ensemble prediction and composite GT. Quadratic weights penalize misclassifications proportional to the squared distance between tiers (Critical → Low penalized 9× harder than Critical → High).

**Secondary metrics:**
2. **Top-K Coverage @ K = ⌈0.2N⌉**: of top-K machines ranked by predicted criticality, % that are truly Critical or High.
3. **Cost-weighted misclassification** (Liu et al. 2019 *IEEE Trans. Ind. Informatics*): missed Critical (predicted Low) penalty = 100, all other errors penalty = 1; report mean cost per case.
4. **Per-tier F1 / Precision / Recall** (4-class macro-averaged + per-class).
5. **Coverage rate**: % of truly Critical machines flagged as Critical OR High.
6. **End-to-end latency** per case (median, p95): time from receiving sensor data to producing ensemble tier.

### 3.7 Sample size & power analysis

- N = 125 cases
- For Quadratic-Weighted Kappa estimate, 95% CI half-width ≈ 0.05 at κ ≈ 0.6 with N = 125 (per Sim & Wright 2005 *Phys. Ther.* power tables)
- Sufficient to discriminate κ = 0.6 (substantial) from κ = 0.4 (moderate) at α = 0.05 with power ≥ 0.80

### 3.8 Pre-registered procedure

1. Generate 125 evaluation cases (25 machines × 5 windows, fixed seed=42 for window selection)
2. Compute composite GT tier per case (frozen formula §2)
3. For each case, query all 4 LLMs in parallel → record tier + reasoning + confidence + latency
4. Aggregate via majority-vote-with-tier-tiebreak per case
5. Compute all metrics §3.6 with bootstrap 95% CI (1000 resamples)
6. Per-LLM ablation: compute metrics for each individual LLM as well (informational, not ensemble claim)

### 3.9 What CAN be claimed (if H₀ rejected)

✅ "4-LLM ensemble achieves substantial agreement with composite GT (κ ≥ 0.6, 95% CI [...]) on N=125 windowed cases from 25 test machines, supporting use of this ensemble as the upstream detection layer for downstream scheduling"

### 3.10 What CANNOT be claimed

❌ "LLM detection is operationally validated for production use" — composite GT is itself a proxy (digital-twin labels), not expert annotation
❌ "This generalizes to other manufacturing domains" — single dataset
❌ "Specific LLM is best" — ensemble is the unit of analysis, not individual LLMs (per-LLM ablation is informational only)

### 3.11 Halt rule

If **κ < 0.6**, **STOP** — do NOT execute Layer 3 experiments. Document failure honestly and propose remediation (better prompt, more diverse window selection, expert annotation collection, etc.).

---

## 4. EXPERIMENT E-L3A — STATIC SCHEDULING (CLASSICAL vs QUANTUM)

### 4.1 Problem formulation

**Decision variable**: $x_{m,e,s} \in \{0,1\}$ = 1 iff machine $m$ assigned to employee $e$ at slot $s$.

**Sets**:
- $M$ = machines flagged Critical or High by Layer 2 (or pre-registered synthetic instances for controlled sweeps)
- $E$ = employees (sweep over 1-3, 3-5, 5-20 sizes)
- $S$ = time slots (60-min slots in 09:00-18:00 Mon-Fri = 9 slots × 5 days = 45 slots/week)

**Constraints**:
- C1 each machine assigned exactly once: $\sum_{e,s} x_{m,e,s} = 1 \quad \forall m$
- C2 each employee at most one machine per slot: $\sum_m x_{m,e,s} \leq 1 \quad \forall e, s$
- C3 maintenance duration: machine $m$ occupies $d_m$ consecutive slots from start (extension via auxiliary variables or block-encoding)
- C4 working hours only (09:00-18:00 Mon-Fri): infeasible slots set to 0
- C5 no overtime: tasks must end by slot 9 of each day (no spillover into next day)

**Objective**: minimize **makespan** = $\max_{m,e,s} \{s + d_m \cdot x_{m,e,s}\}$ (last completion slot across all machines).

### 4.2 Maintenance duration mapping

Reference: **Mobley R.K. (2002)** *"An Introduction to Predictive Maintenance"* 2nd ed., Butterworth-Heinemann; **Gulati R. (2013)** *"Maintenance and Reliability Best Practices"* 2nd ed., Industrial Press; **ISO 17359:2018** Condition monitoring and diagnostics of machines.

| Failure Type | Typical CMMS duration | Slots (60 min each) |
|---|---|---|
| Vibration Issue | 60–90 min (bearing, alignment) | **2** |
| Overheating | 60–120 min (cooling, fan) | **2** |
| Pressure Drop | 90–180 min (seal, valve) | **2** |
| Electrical Fault | 120–240 min (wiring, control board) | **3** |
| Normal/preventive | 30–60 min (inspection only) | **1** |

Machines flagged by Layer 2 with known failure type get specific duration; default = 1 slot for preventive/unknown.

### 4.3 Solvers compared

| Class | Solver | Library | Hyperparameters |
|---|---|---|---|
| Classical heuristic | Genetic Algorithm (GA) | DEAP | pop=100, generations=200, tournament select, 1-point crossover, swap mutation 0.1 |
| Classical heuristic | Simulated Annealing (SA) | dwave-neal | num_reads=100, beta range auto |
| Classical heuristic | Tabu Search (TS) | Custom impl | tabu tenure=15, max iter=500, restart on plateau |
| Quantum gate-model | QAOA | qiskit-aer Statevector + custom QAOA per E-Q1 V1 | reps p ∈ {1,2,3}, COBYLA maxiter=200 |
| Quantum annealing | Simulated quantum annealing | dwave-neal Ising | num_reads=200 (separate call from classical SA) |
| Quantum hybrid | D-Wave Hybrid solver | dwave-cloud-client | if Leap free tier available; else marked N/A |
| Quantum-inspired | Simulated Bifurcation Machine | `bifurcation-machine` py pkg or custom impl per Goto et al. 2019 *Sci. Adv.* | dt=0.5, K=1.0, T=10, default Toshiba SBM params |

### 4.4 Problem instance sweep (Q15 = both)

**Controlled synthetic sweep:**
| Tier | Machines | Days | Employees | Total var ~ |
|---|---|---|---|---|
| Small | 5 | 1 | 1, 3, 5 | 5×1×9 = 45 |
| Medium | 20 | 3 | 3, 5, 10 | 20×3×27 = 1620 |
| Large | 50 | 5 | 5, 10, 20 | 50×5×45 = 11250 |

Per problem-size cell: 5 random seeds → 45 controlled instances total.

**Real-time integration test:**
- Run E-L2 ensemble over a 24-hour Kafka window
- Collect Critical+High machines as they appear
- Feed to scheduler at simulated 1-minute intervals → variable problem size
- One run per group-size, total 3 integration instances

### 4.5 Pre-registered procedure

1. For each (problem size, employee group, seed) combination:
   a. Generate problem instance (controlled sweep) or collect from Layer 2 (integration)
   b. Run each solver with fixed hyperparameters
   c. Record: best makespan found, solution feasibility (all constraints satisfied?), wall-clock time, peak memory
2. For exact verification on Small (≤45 vars): brute-force or MIP via OR-Tools CP-SAT to compute optimal makespan
3. Compute optimality gap = (solver_makespan − optimal) / optimal where optimum known

### 4.6 Statistical analysis plan

- **Primary**: paired Wilcoxon signed-rank on makespan per (size, employee group) cell, classical-best (best of GA/SA/TS) vs quantum-best (best of QAOA/QA/SBM)
- Bonferroni-correct over 9 cells (3 sizes × 3 employee groups)
- Effect size: Cliff's δ on makespan distributions
- Report all per-solver per-instance results in CSV (full transparency)

### 4.7 Primary claim (if quantum-best ≤ classical-best on makespan)

✅ "Quantum and quantum-inspired solvers achieve makespan parity-or-better with the best classical heuristic baseline (GA/SA/TS) at simulator scale across N×T problem sizes from 5 to 50 machines (Wilcoxon signed-rank p > 0.05 vs classical-best per cell, Cliff's δ in [-0.3, 0.3])"

### 4.8 Secondary disclosure (always reported, no claim attached)

- Wall-clock per solver per instance (mean ± std)
- Constraint satisfaction rate per solver
- Real-time feasibility (≤60s for next 1-minute Kafka cycle? yes/no per instance)
- Per-solver scaling: log-log fit of wall-clock vs N×T

### 4.9 What CANNOT be claimed

❌ "Quantum advantage on QASAMAP" — simulator backend, no real hardware
❌ "Quantum is faster" — simulator wall-clock dominated by Python overhead, not algorithmic
❌ "Solution found by quantum is provably optimal" — only if brute-force / MIP optimal also computed (which we do for Small only)

---

## 5. EXPERIMENT E-L3B — DYNAMIC ROLLING-HORIZON SCHEDULING

### 5.1 Research question

> *Can the quantum/quantum-inspired solvers maintain real-time feasibility (≤60s per re-optimization) under event-driven re-scheduling triggered by new Layer 2 detections or employee finish/delay events?*

### 5.2 Hypothesis

- **H₀**: at least one solver class fails to maintain ≤60s re-optimization wall-clock on Medium problem instance
- **H₁**: all solvers maintain ≤60s re-optimization

### 5.3 Simulation protocol

- Simulated 8-hour working day (9:00–17:00) at Medium problem size (20 machines, 5 employees)
- Initial Layer 2 output at t=9:00 → initial schedule via each solver
- Event stream over the day:
  - Stochastic new machine flags from Layer 2 ensemble (Poisson arrival rate λ = 2/hour)
  - Stochastic employee finish-early (β = 0.1 probability per task, finish at 0.7×duration)
  - Stochastic employee delay (β = 0.05, finish at 1.5×duration)
- Re-optimize on each event using current solver
- Record: per-event re-opt wall-clock, makespan progression, total deadline misses

### 5.4 Statistical analysis

- Per-solver: median + p95 + p99 re-opt wall-clock, % events where re-opt ≤ 60s
- Total deadline-miss count over 8-hour simulation
- Wilcoxon signed-rank: classical-best vs quantum-best on per-event wall-clock (paired by event)

### 5.5 Primary claim (if all solvers ≤60s p95)

✅ "All evaluated solvers (classical + quantum + quantum-inspired) sustain real-time feasibility (p95 wall-clock ≤ 60s per re-optimization event) under event-driven dynamic scheduling on Medium problem instance over an 8-hour simulated working day"

### 5.6 What CANNOT be claimed

❌ "This works at Large scale in real-time" — only Medium is tested in dynamic mode
❌ "Real industrial deployment validated" — simulated event stream, not real factory log

---

## 6. CROSS-CUTTING METHODOLOGICAL FRAMEWORK

### 6.1 Pre-registration commitment

This document hash (SHA-256 of `PHASE1_PROTOCOL_V2_ALIGNED_3LAYER.md` at first commit) constitutes the pre-registration timestamp. Any deviation requires explicit justification in result reports.

### 6.2 Reproducibility checklist

- [ ] Fixed seeds: numpy=42, qiskit=42, dwave-neal=42, scipy=42, deap=42
- [ ] Multi-seed for stochastic components: [42, 7, 1234] minimum
- [ ] All LLM API calls cached to `experiments/E-L2_agentic_validation/llm_cache/`
- [ ] Per-instance CSV with full per-solver per-seed results
- [ ] Per-experiment STATISTICAL_REPORT.md with what-can/cannot-be-claimed
- [ ] Backend disclosure mandatory in every quantum result

### 6.3 Multi-comparison correction

Bonferroni-correction across all hypothesis tests within an experiment. Report both raw and adjusted p-values.

### 6.4 Validity threats addressed

| Threat | Mitigation |
|---|---|
| GT noise | composite GT documented + Cohen's QW-Kappa with bootstrap CI; manual spot-check 10 random cases for plausibility |
| LLM stochasticity | 4-LLM ensemble + per-LLM ablation as informational |
| Solver hyperparameter cherry-picking | All hyperparameters frozen in this document before execution |
| Cherry-picked seeds | Multi-seed protocol (≥3) reported with mean ± std |
| Backend disclosure | Every quantum/quantum-inspired result tags backend, qubit count, depth, shots |

### 6.5 Halt conditions across experiments

| Trigger | Action |
|---|---|
| E-L2 κ < 0.6 | STOP. Do not execute E-L3A or E-L3B. Document Layer 2 failure honestly. |
| E-L3A: any solver fails to produce feasible solution on Small | Investigate constraint encoding, fix and re-run; document the issue. |
| E-L3B: any solver p95 > 600s | Document and exclude that solver from real-time feasibility claim. |
| LLM API outage > 30 min | Pause execution, resume from cache when restored. |

### 6.6 Honest reporting requirements

Every experiment STATISTICAL_REPORT.md MUST include:
1. Pre-registered hypothesis verbatim
2. Empirical result vs hypothesis verdict (supported / not supported / inconclusive)
3. Effect size + p-value + 95% CI
4. Section "What CAN be claimed"
5. Section "What CANNOT be claimed"
6. Methodological caveats explicitly enumerated
7. Defense-ready one-paragraph summary

---

## 7. EXECUTION SEQUENCE

```
Step 1: E-L2 (Layer 2 validation)
        ├── If κ ≥ 0.6 → proceed to Step 2
        └── If κ < 0.6 → STOP, document failure, propose remediation

Step 2: E-L3A (Layer 3 static scheduling sweep)
        ├── Controlled sweep: 3 sizes × 3 employee groups × 5 seeds × 7 solvers
        ├── Real-time integration: Layer 2 output × 3 employee groups × 7 solvers
        └── Generate STATISTICAL_REPORT.md

Step 3: E-L3B (Layer 3 dynamic rolling-horizon)
        ├── Simulated 8-hour day at Medium size × 7 solvers × 3 seeds
        └── Generate STATISTICAL_REPORT.md

Step 4: Update PHASE2_RESULTS_MASTER_REPORT.md with E-L2/E-L3A/E-L3B
        Update thesis Chapter 5 (agentic) and Chapter 6 (quantum scheduling)
        Push to GitHub.
```

---

## 8. DELIVERABLES

After execution:
- `experiments/E-L2_agentic_validation/` — prompt template, run script, 4-LLM cache, STATISTICAL_REPORT.md
- `experiments/E-L3A_static_scheduling/` — solver implementations, problem instances JSON, per-instance CSV, STATISTICAL_REPORT.md
- `experiments/E-L3B_dynamic_scheduling/` — event stream JSON, simulation log, STATISTICAL_REPORT.md
- Updated `PHASE2_RESULTS_MASTER_REPORT.md` (replaces V1 results)
- Updated thesis chapters (5 + 6) with V2 results

---

**END OF PHASE 1 PROTOCOL V2.**

Pre-registration completed 2026-05-04. Execution may proceed pending supervisor approval of this protocol.
