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
│   ├── agentic_AI_orchestration.tex     # legacy (pre-audit) -- to be replaced by chapter5_agentic_v2
│   ├── quantum_integration.tex          # legacy (pre-audit) -- to be replaced by chapter6_quantum_v2
│   ├── chapter5_agentic_v2.tex          # NEW -- integrates phase_docs/PHASE0+1+2 (E1, E3, E5, E6)
│   ├── chapter6_quantum_v2.tex          # NEW -- integrates phase_docs/PHASE0+1+2 quantum (E-Q1, E-Q3)
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

## Headline empirical findings (honest framing throughout)

**Agentic track:**
- E1 STRONG: Hybrid QASAMAP covers 55% of PdM decision dimensions vs Pure ML 20% (Cochran's Q significant on 6/8 dimensions, p<0.05)
- E3 PRELIMINARY: LLM in-context learning F1 +0.048 over 5 examples (small but positive direction)
- E5 LIMITED: Synthetic-on-synthetic perturbations cannot validate true OOD; threshold detectors stable
- E6 COUNTER-RESULT: Single-call LLM beats specialized 9-agent on composite quality (Q=0.820 vs 0.630, F(2,12)=3.84). Reconciled with E1 by breadth-vs-quality distinction
- E2, E4 DEFERRED with documented honest plans

**Quantum track (NISQ-honest, simulator-based):**
- E-Q3: 5-qubit Pauli-Z entangled detector achieves F1 = 0.290 at natural anomaly prevalence (9.6%) -- highest of 5 baselines, beating mathematically-isolated separable equivalent by +0.078 F1 (37% relative). Entanglement-driven lift verified by floating-point algebraic equivalence sanity check. McNemar p<0.0001 Bonferroni-corrected.
- E-Q1: Simulated QAOA reaches solution-quality parity with classical Simulated Annealing at depth p>=2 (Wilcoxon p=0.317 for p=2, p=0.180 for p=3, N=20 paired instances). QAOA p=1 significantly worse (p=0.0077) -- replicates expected NISQ shallow-ansatz weakness. SA wall-clock 2-3 orders of magnitude faster (simulator overhead, not algorithmic).

## Building the thesis

```bash
cd thesis_project   # if cloned into a subdirectory
latexmk -pdf main.tex
```

The current `main.tex` includes the legacy `agentic_AI_orchestration.tex` and `quantum_integration.tex`. To switch to the post-audit V2 chapters, edit `main.tex` to `\input{structures/chapter5_agentic_v2}` and `\input{structures/chapter6_quantum_v2}` (or include them as new chapters alongside the legacy ones for comparison).

## Reproducibility

All experiment scripts live in `experiments/<Ex>/run_*.py` with deterministic seeds. Statistical reports (`STATISTICAL_REPORT.md`) accompany each experiment with explicit pre-registration deviation disclosures, multi-comparison correction details, and what-can/cannot-be-claimed sections.

Quantum experiments require `qiskit`, `qiskit-aer`, `qiskit-algorithms`, `qiskit-optimization`, `dwave-neal`. See each script for exact dependency list.

## Academic ethics commitment

Mixed-evidence portfolio reported honestly: 1 strong + 2 preliminary + 1 counter-result + 2 deferred (agentic), 2 simulator-scale parity-or-better (quantum). All claims are calibrated to the evidence level actually achieved. NISQ caveats explicit throughout. No quantum-advantage claim is made.
