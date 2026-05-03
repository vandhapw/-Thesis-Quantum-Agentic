# Quantum-Agentic Smart Manufacturing Thesis (QASAMAP)

PhD thesis source by **Vandha Pradwiyasma Widartha**, Pukyong National University. Defense scheduled August 2026.

## Repository structure

```
.
├── main.tex                          # 11pt report driver (8 chapters)
├── thesis.bib                        # Bibliography
├── structures/                       # Chapter LaTeX sources (NewThesis-aligned 7-chapter structure)
│   ├── title.tex                     # Title page
│   ├── approval_form.tex             # Committee signature page
│   ├── kor_abstract.tex              # Korean abstract
│   ├── eng_abstract.tex              # English abstract
│   ├── introduction.tex              # Ch. 1 — Background, Motivation, Contribution, Thesis Structure
│   ├── related_works.tex             # Ch. 2 — Literature Review (8 sections × multiple subsections)
│   ├── method.tex                    # Ch. 3 — Quantum-Agentic Smart Manufacturing Framework
│   ├── experimental.tex              # Ch. 4 — Data Ingestion + T-GCN spatiotemporal modeling
│   ├── analysis_discussion.tex       # Ch. 5 — Multi-Agent System for Monitoring, Diagnosis, Planning, Action
│   ├── chapter6.tex                  # Ch. 6 — Quantum Approaches for Optimizing Maintenance Scheduling
│   ├── conclusion.tex                # Ch. 7 — Conclusions and Future Work
│   ├── references.tex                # Bibliography include
│   ├── appendix.tex                  # Appendices
│   ├── acknowledgment.tex            # Acknowledgements
│   ├── publication_list.tex          # Author's publications
│   ├── agentic_AI_orchestration.tex  # Standalone agentic content (legacy, not in main.tex flow)
│   ├── quantum_integration.tex       # Standalone quantum content (legacy)
│   ├── related_works-.tex            # Legacy backup
│   ├── libraries.tex                 # LaTeX preamble
│   ├── list_table_figure.tex
│   └── table_of_content.tex
├── tables/                           # Standalone table .tex files (referenced by chapters)
├── figures/                          # Figure .tex sources + images/
│   ├── *.tex                         # TikZ/standalone figures
│   └── images/                       # PNG figures (T-GCN architecture, Pauli-Z circuit, V2 pipeline diagrams, etc.)
├── phase_docs/                       # Pre-registered protocols + integrated results (V2 follow-up)
│   ├── PHASE0_AGENTIC_AI_LITERATURE_FOUNDATION.md
│   ├── PHASE0_QUANTUM_LITERATURE_FOUNDATION.md
│   ├── PHASE1_EXPERIMENT_DESIGN.md
│   ├── PHASE1_QUANTUM_EXPERIMENT_DESIGN.md
│   ├── PHASE1_PROTOCOL_V2_ALIGNED_3LAYER.md  # Active V2 protocol (3-layer architecture)
│   ├── PHASE2_RESULTS_MASTER_REPORT.md
│   └── PHASE2_QUANTUM_TRACK_APPENDIX.md
└── experiments/                      # Reproducibility artifacts (scripts + results + statistical reports)
    ├── E1_capability_coverage/        # V1 archived
    ├── E2_cold_start/                 # V1 archived (deferred plan)
    ├── E3_few_shot/                   # V1 archived
    ├── E4_user_study/                 # V1 archived (IRB pending)
    ├── E5_ood_robustness/             # V1 archived
    ├── E6_multi_agent_ablation/       # V1 archived
    ├── E-Q1_qaoa_scheduling/          # V1 archived
    ├── E-Q3_pauliz_detection/         # V1 archived
    ├── E-L2_agentic_validation/       # V2 — Layer 2 multi-tier ensemble (κ=0.7425 substantial agreement)
    ├── E-L2-MultiAgent_Pipeline/      # V2 — Sequential 4-stage Monitoring→Diagnosing→Planning→Action pipeline
    ├── E-L3A_static_scheduling/       # V2 — Static scheduling classical-vs-quantum (classical-dominant honest finding)
    └── E-L3B_dynamic_scheduling/      # V2 — Dynamic rolling-horizon real-time feasibility (4 classical solvers PASS)
```

## Chapter narrative (NewThesis-aligned 7-chapter structure)

| Ch | Title | Source file | Headline result |
|---|---|---|---|
| 1 | Introduction | `introduction.tex` | Background, Motivation, Contribution (4 primary + 3 V2 follow-up), Thesis Structure |
| 2 | Literature Review | `related_works.tex` | 8 sections covering Industry 4.0, anomaly detection, prognostics, agentic AI, quantum optimization, hybrid systems |
| 3 | QASAMAP Framework | `method.tex` | 3-layer architecture (T-GCN forecasting, agentic AI, quantum-inspired heuristics) + V2 deployment patterns note |
| 4 | T-GCN Spatiotemporal Modeling | `experimental.tex` | T-GCN R²=0.7702 vs LSTM 0.6853; 5 ensemble classifiers F1 up to 0.999 |
| 5 | Multi-Agent System | `analysis_discussion.tex` | Post-audit AgenticAI F1=0.00 / F1=0.33 + LLM benchmark **+ V2 follow-up: 3-LLM ensemble κ=0.7425, sequential 4-stage Monitoring→Diagnosing→Planning→Action pipeline** |
| 6 | Quantum Maintenance Scheduling | `chapter6.tex` | Classical-heuristic disclosure (Pauli-Z = L2 distance, QUBO = local search, QAOA = graph message passing) **+ V2 follow-up: full $x_{m,e,s}$ scheduling QUBO benchmark, classical-dominant honest finding** |
| 7 | Conclusions and Future Work | `conclusion.tex` | 4 primary contributions + Objectives 1-5 verified + Limitations + Future Work + V2 follow-up section |

## Headline V2 empirical findings

**Layer 2 (Multi-LLM ensemble for criticality detection):**
- 3 LLMs (`glm-5.1:cloud`, `kimi-k2.6:cloud`, `deepseek-v4-pro:cloud`) majority-vote on 4-tier classification
- 25 test machines × 5 windows = 125 evaluation cases against composite GT (Lei 2018 + ISO 13374-2)
- **Quadratic-Weighted Kappa κ = 0.7425 (95% CI [0.619, 0.835])** — substantial agreement (Landis-Koch 1977)
- Critical-tier precision = 1.000; Critical-or-High coverage = 1.000 (no missed Critical)
- End-to-end p95 latency = 32.7s within 60s Kafka producer cycle
- Three pre-registered methodology deviations documented transparently (V1→V2→V3)

**Multi-Agent Pipeline (Monitoring → Diagnosing → Planning → Action):**
- Sequential 4-stage role-specialised LLM pipeline; Layer 1 evidence → CMMS work order
- Demonstrated on 5 machines spanning all 4 GT criticality tiers
- All 5 pipelines complete all 4 stages within 60s real-time budget (max 53.1s)
- Critical-tier machine (M-29, RUL=7h) → P2 repair + supervisor approval gate
- Lower-tier machines → auto-dispatch
- Code: `experiments/E-L2-MultiAgent_Pipeline/run_pipeline.py`; visualizations in same dir

**Layer 3 (Maintenance scheduling: classical vs quantum):**
- 6 solvers benchmarked: Greedy / GA / SA / TS classical + simulated QA + Simulated Bifurcation quantum-inspired
- 315 controlled solver runs (3 sizes × 3 employee groups × 5 seeds) + 135 dynamic re-optimization events
- **All four classical solvers converge to identical optimal makespan** with 100% feasibility
- **QA_neal + SBM consistently fail** to produce feasible solutions on dense scheduling QUBO (Wilcoxon p<1e-5)
- Gate-model QAOA not applicable at meaningful problem sizes (qubit budget)
- All 4 classical solvers PASS real-time feasibility (p95 < 1.5s vs 60s budget)
- End-to-end Layer 2 + Layer 3 fits 60s Kafka cycle by ≥26s margin
- Honest finding: classical heuristics dominate quantum-class methods at simulator-only evaluation
- Real D-Wave Advantage hardware was sought but Leap free tier not available

## Building the thesis

```bash
cd thesis_project
latexmk -pdf main.tex
```

## Reproducibility

All experiment scripts (`experiments/<E>/run_*.py`) use deterministic seeds. Statistical reports (`STATISTICAL_REPORT.md` per experiment) include explicit pre-registration deviation disclosures, multi-comparison correction details, and what-can/cannot-be-claimed sections. LLM ensemble experiments (E-L2, E-L2-MultiAgent_Pipeline) include disk-cached LLM responses for fully reproducible replay without re-incurring API cost.

Quantum experiments require: `qiskit`, `qiskit-aer`, `qiskit-algorithms`, `qiskit-optimization`, `dwave-neal`. LLM experiments require: `ollama` Python client + Ollama Cloud API key (`OLLAMA_API_KEY` env var or `.env` file).

## Academic ethics commitment

Mixed-evidence portfolio reported honestly throughout. Three pre-registered methodology deviations across V2 documented inline; both successful runs and failed runs preserved as historical record. No quantum-advantage claim is made on QASAMAP; all quantum-class results are at simulator-only evaluation. Classical-heuristic disclosure (Chapter 6) explicitly identifies that the original "quantum" components were L2 distance, local search, and graph message passing — not quantum algorithms. Real D-Wave hardware testing reserved as future work pending Leap programme access.

## Provenance

The chapter structure of this repository follows the NewThesis layout (https://github.com/vandhapw/NewThesis as observed) with V2 follow-up content (E-L2 V3 ensemble, Multi-Agent Pipeline demonstration, E-L3A + E-L3B scheduling) added as new sections within existing chapters. Original NewThesis section/subsection titles are preserved; V2 evidence is integrated as additional sections marked with explicit "V2 Follow-Up" labels.
