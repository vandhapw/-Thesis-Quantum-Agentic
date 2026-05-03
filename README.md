# Quantum-Agentic Smart Manufacturing Thesis (QASAMAP)

PhD thesis source by **Vandha Pradwiyasma Widartha**, Pukyong National University. Defense scheduled August 2026.

## Repository structure

```
.
├── main.tex                       # 12pt report driver, includes all chapters
├── thesis.bib                     # Bibliography (~668 lines)
├── structures/                    # Chapter LaTeX sources
│   ├── introduction.tex
│   ├── related_works.tex
│   ├── method.tex
│   ├── experimental.tex
│   ├── analysis_discussion.tex
│   ├── conclusion.tex
│   ├── agentic_AI_orchestration.tex     # Chapter 5 -- post-audit honest content (integrates phase_docs/PHASE0+1+2: E1, E3, E5, E6)
│   ├── quantum_integration.tex          # Chapter 6 -- post-audit honest content (integrates phase_docs/PHASE0+1+2 quantum: E-Q1, E-Q3)
│   └── ...                              # abstracts, appendix, ack, etc.
├── figures/                       # PNG figures (architecture, datasets, performance, quantum circuit)
├── tables/                        # LaTeX tables
├── phase_docs/                    # Pre-registered protocols + integrated results
│   ├── PHASE0_AGENTIC_AI_LITERATURE_FOUNDATION.md
│   ├── PHASE0_QUANTUM_LITERATURE_FOUNDATION.md
│   ├── PHASE1_EXPERIMENT_DESIGN.md
│   ├── PHASE1_QUANTUM_EXPERIMENT_DESIGN.md
│   ├── PHASE2_RESULTS_MASTER_REPORT.md       # Combined agentic + quantum master report
│   └── PHASE2_QUANTUM_TRACK_APPENDIX.md
└── experiments/                   # Reproducibility artifacts (scripts + results + statistical reports)
    ├── E1_capability_coverage/         # Hybrid 55% vs Pure ML 20% (Cochran's Q sig 6/8 dims)
    ├── E2_cold_start/                  # NASA C-MAPSS plan (deferred, honest framing)
    ├── E3_few_shot/                    # In-context learning preliminary (+0.048 F1)
    ├── E4_user_study/                  # IRB application + Streamlit prototype + 20 scenarios
    ├── E5_ood_robustness/              # Synthetic perturbations (methodologically limited)
    ├── E6_multi_agent_ablation/        # COUNTER-RESULT honestly reported
    ├── E-Q1_qaoa_scheduling/           # SA vs simulated QAOA -- parity at p>=2 (Wilcoxon p=0.317)
    └── E-Q3_pauliz_detection/          # Pauli-Z entangled detector -- F1 0.290 at natural prevalence (best)
```

## Headline empirical findings (V2 protocol, honest framing throughout)

The V2 protocol (PHASE1_PROTOCOL_V2_ALIGNED_3LAYER.md) is the active execution plan, aligned with the supervisor-confirmed 3-layer architecture: T-GCN+Kafka (Layer 1, existing) → Agentic AI multi-tier detection (Layer 2) → Scheduling optimization classical vs quantum (Layer 3). The earlier V1 experiments (E1, E3, E5, E6, E-Q1, E-Q3) are preserved in `experiments/` for archive but were re-scoped under V2 because their framing did not match the 3-layer design.

**Layer 2 (Agentic AI Multi-Tier Detection) — E-L2:**
- V1 (4 LLMs, sensor-only prompt): κ=0.362 (fair, below threshold) → STOP
- V2 (3 LLMs after dropping qwen3.5 due to 53% empty-content rate, decision-tree prompt): κ=0.191 (worse) → STOP. Exposed methodological flaw: GT formula uses 4 fields (RUL, anomaly_flag, downtime_risk, maintenance_required) that LLM was not given.
- **V3 (3 LLMs, realistic deployment input set including upstream classifier outputs): κ = 0.7425 (95% CI [0.619, 0.835]) → PASS substantial agreement.** Critical precision = 1.000, Critical-or-High coverage of true Critical = 1.000, ensemble e2e p95 latency = 32.7s within 60s Kafka cycle.
- 3 pre-registered deviations documented; all V1/V2/V3 results preserved in repo.

**Layer 3A (Static Scheduling Classical vs Quantum) — E-L3A:**
- 6 solvers tested across 3 sizes × 3 employee groups × 5 seeds = 315 solver runs.
- **Classical (Greedy / GA / SA / TS) all converge to identical optimal makespan** with 100% feasibility, wall-clock <2s at largest size (50 machines × 5 days × 20 employees = 45000 binary vars).
- **QA_neal and SBM consistently infeasible** on dense scheduling QUBO (feasibility 0.0–0.2 vs 1.0 classical), paired Wilcoxon p < 1e-5 against classical-best.
- **QAOA not applicable** — encoding requires N×E×S vars (≥45) exceeding 18-qubit statevector simulator practical limit.
- Honest finding: classical heuristics dominate on this scheduling QUBO at QASAMAP scale on simulator-only evaluation. Real D-Wave hardware was not available.

**Layer 3B (Dynamic Rolling-Horizon Real-Time Feasibility) — E-L3B:**
- Simulated 8-hour working day, event-driven re-optimization, 3 seeds × ~15 events = 45 events per solver.
- **All 4 classical solvers PASS real-time feasibility**: p95 wall-clock <1.5s vs 60-s Kafka cycle budget; 0 deadline-misses across 135 re-opt events.
- End-to-end Layer 2 (LLM ensemble p95 32.7s) + Layer 3 (classical p95 <1.5s) fits within 60-s budget with ≥26-s margin.
- QA/SBM excluded based on E-L3A static failure.

### V1 archive (NOT used for thesis defense — superseded by V2)
The earlier V1 experiments (E1 capability coverage, E3 few-shot, E5 OOD synthetic, E6 multi-agent ablation, E-Q1 SA vs QAOA, E-Q3 Pauli-Z compound detection) are preserved in `experiments/` and `phase_docs/` as historical record. They were superseded by V2 because they framed quantum for detection (not scheduling) and used different evaluation framing than the supervisor-confirmed 3-layer architecture.

## Building the thesis

```bash
cd thesis_project   # if cloned into a subdirectory
latexmk -pdf main.tex
```

`main.tex` now includes 8 chapters in order: Introduction, Related Works, Methods, Experimental Result, **Agentic AI Orchestration** (Ch. 5 -- new), **Quantum Computing Integration** (Ch. 6 -- new), Analysis and Discussion, Conclusion. The agentic and quantum chapters reference statistical artifacts in `experiments/` and source documents in `phase_docs/`.

Compile dependencies on the LaTeX side: standard packages from `structures/libraries.tex`. The new chapters cite keys (`cerezo2025bp`, `tsai2026roadmap`, `fordotosan2024dwave`, `basf2024dwave`, etc.) that may need to be added to `thesis.bib` if not already present.

## Reproducibility

All experiment scripts live in `experiments/<Ex>/run_*.py` with deterministic seeds. Statistical reports (`STATISTICAL_REPORT.md`) accompany each experiment with explicit pre-registration deviation disclosures, multi-comparison correction details, and what-can/cannot-be-claimed sections.

Quantum experiments require `qiskit`, `qiskit-aer`, `qiskit-algorithms`, `qiskit-optimization`, `dwave-neal`. See each script for exact dependency list.

## Academic ethics commitment

Mixed-evidence portfolio reported honestly: 1 strong + 2 preliminary + 1 counter-result + 2 deferred (agentic), 2 simulator-scale parity-or-better (quantum). All claims are calibrated to the evidence level actually achieved. NISQ caveats explicit throughout. No quantum-advantage claim is made.
