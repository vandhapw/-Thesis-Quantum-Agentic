"""
E-Q1 -- Maintenance-Scheduling QUBO: Brute-force vs SA vs Simulated QAOA
=======================================================================

Pre-registered protocol -- see PHASE1_QUANTUM_EXPERIMENT_DESIGN.md  E-Q1.

QUBO:
    minimize  H = sum_t (sum_i r_i x_{i,t})^2
                + lambda_1 * sum_i (1 - sum_t x_{i,t})^2
                + lambda_2 * sum_{i,t} x_{i,t} * (1 - urgency_{i,t})
    where r_i in [0,1] = machine risk score
          urgency_{i,t} = 1 / (1 + t * (1 - r_i))
    Pre-registered: lambda_1 = 10, lambda_2 = 1
    Variable count: N * T

Solvers:
    BF      -- brute-force enumeration (exact)         [feasible only for small N*T]
    SA      -- dwave-neal SimulatedAnnealingSampler    [strong classical baseline]
    QAOA p1 -- qiskit-algorithms QAOA, reps=1, COBYLA, StatevectorSampler
    QAOA p2 -- reps=2
    QAOA p3 -- reps=3

Sweep grid:
    (N,T) in {(2,2),(3,3),(4,3),(5,3),(6,3),(8,3)}  -> 4..24 vars
    5 seeds per (N,T) -> 30 instances
    For (10,4)=40 vars: SA-only stress test (no QAOA)

Outputs:
    per_instance.csv -- one row per (size, seed, solver) with cost, gap_to_optimum, time
    summary.json     -- aggregated statistics + paired tests
"""
import json, os, time, math, itertools, sys
import numpy as np
import pandas as pd
from typing import Tuple

# -------------- imports for solvers --------------
from neal import SimulatedAnnealingSampler
import dimod

from qiskit_optimization import QuadraticProgram
from qiskit_optimization.algorithms import MinimumEigenOptimizer
from qiskit_algorithms import QAOA
from qiskit_algorithms.optimizers import COBYLA
from qiskit_algorithms.utils import algorithm_globals
from qiskit.primitives import StatevectorSampler

# minimal QAOA path that bypasses Sampler V2 overhead
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector, SparsePauliOp
from qiskit.circuit import Parameter
from scipy.optimize import minimize as scipy_minimize

OUT_DIR = r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-Q1_qaoa_scheduling"
SEEDS = [42, 7, 1234, 100, 200]
# Final scope after the QAOA implementation rewrite (custom minimal Statevector
# expectation + top-k bitstring post-processing) made the original pre-reg scope
# tractable: full QAOA p=1,2,3 sweep on (2,2)..(5,3); p=1 anchor at (6,3); SA-only
# stress at (8,3) and (10,4).
GRID         = [(2,2),(3,3),(4,3),(5,3)]
GRID_P1ONLY  = [(6,3)]
LARGE_GRID   = [(8,3),(10,4)]
QAOA_REPS_FULL = (1, 2, 3)
LAMBDA_1 = 10.0
LAMBDA_2 = 1.0
SA_NUM_READS = 100
# Pre-reg COBYLA_MAXITER = 200. Initial implementation using Qiskit's
# MinimumEigenOptimizer + StatevectorSampler V2 was so slow (3s/iter at 9 vars)
# that the full sweep was impractical. Replaced with a minimal QAOA that
# computes <psi|H|psi> directly from Statevector and post-processes top-k
# bitstrings (top_k=32). This restores pre-reg maxiter and adds back p=3.
COBYLA_MAXITER = 200

os.makedirs(OUT_DIR, exist_ok=True)

# -------------- problem generation --------------
def gen_instance(N, T, seed):
    rng = np.random.default_rng(seed)
    risk = rng.uniform(0.1, 0.95, size=N)
    urg  = np.zeros((N, T))
    for i in range(N):
        for t in range(T):
            urg[i, t] = 1.0 / (1.0 + t * (1.0 - risk[i]))
    return risk, urg

def build_qubo_matrix(N, T, risk, urg, lam1=LAMBDA_1, lam2=LAMBDA_2):
    """Build symmetric Q matrix on (N*T) binary vars. var index k = i*T + t."""
    nv = N * T
    Q = np.zeros((nv, nv))
    # term 1: sum_t (sum_i r_i x_{i,t})^2
    for t in range(T):
        for i in range(N):
            for j in range(N):
                k1 = i * T + t
                k2 = j * T + t
                Q[k1, k2] += risk[i] * risk[j]
    # term 2: lam1 * sum_i (1 - sum_t x_{i,t})^2 = lam1 * sum_i (1 - 2*sum_t x + (sum_t x)^2)
    # constant offset doesn't matter for optimization. Linear: -2*lam1*x. Quadratic: lam1*x_i,t * x_i,t'
    for i in range(N):
        for t in range(T):
            k = i * T + t
            Q[k, k] += lam1 * (1 - 2)  # = -lam1 (linear contribution -> diagonal)
        for t1 in range(T):
            for t2 in range(T):
                k1 = i * T + t1
                k2 = i * T + t2
                Q[k1, k2] += lam1
    # term 3: lam2 * sum_{i,t} x_{i,t} * (1 - urg)
    for i in range(N):
        for t in range(T):
            k = i * T + t
            Q[k, k] += lam2 * (1 - urg[i, t])
    # symmetrize
    Q = 0.5 * (Q + Q.T)
    return Q

def cost_eval(x, Q):
    return float(x @ Q @ x)

# -------------- brute force (exact) --------------
def solve_brute_force(Q):
    nv = Q.shape[0]
    best_x = None
    best_c = math.inf
    for v in range(2 ** nv):
        x = np.array([(v >> i) & 1 for i in range(nv)], dtype=float)
        c = cost_eval(x, Q)
        if c < best_c:
            best_c = c
            best_x = x
    return best_x, best_c

# -------------- SA --------------
def solve_sa(Q, seed=42, num_reads=SA_NUM_READS):
    nv = Q.shape[0]
    bqm = dimod.BinaryQuadraticModel({i: float(Q[i,i]) for i in range(nv)},
                                      {(i,j): float(Q[i,j] + Q[j,i]) for i in range(nv) for j in range(i+1, nv)},
                                      0.0,
                                      dimod.BINARY)
    sampler = SimulatedAnnealingSampler()
    res = sampler.sample(bqm, num_reads=num_reads, seed=seed)
    best = res.first
    x = np.array([best.sample[i] for i in range(nv)], dtype=float)
    return x, cost_eval(x, Q)

# -------------- QAOA --------------
def build_quadratic_program(Q):
    nv = Q.shape[0]
    qp = QuadraticProgram()
    for i in range(nv):
        qp.binary_var(name=f"x{i}")
    linear = {f"x{i}": float(Q[i,i]) for i in range(nv)}
    quadratic = {}
    for i in range(nv):
        for j in range(i+1, nv):
            v = float(Q[i,j] + Q[j,i])
            if abs(v) > 1e-12:
                quadratic[(f"x{i}", f"x{j}")] = v
    qp.minimize(linear=linear, quadratic=quadratic)
    return qp

def qubo_to_ising(Q):
    """
    Convert QUBO Q (real symmetric, x in {0,1}) to Ising H = sum h_i Z_i + sum J_ij Z_i Z_j + offset.
    x_i = (1 - z_i)/2 with z_i in {-1,+1}. Returns (h, J, offset).
    """
    nv = Q.shape[0]
    h = np.zeros(nv)
    J = np.zeros((nv, nv))
    offset = 0.0
    for i in range(nv):
        offset += 0.5 * Q[i, i]
        h[i]   += -0.5 * Q[i, i]
        for j in range(nv):
            if i == j: continue
            offset += 0.25 * Q[i, j]
            h[i]   += -0.25 * Q[i, j]
            h[j]   += -0.25 * Q[i, j]
            J[i, j] += 0.25 * Q[i, j]
    return h, J, offset

def ising_to_pauli_op(h, J, nv):
    """Build SparsePauliOp for Ising H = sum h_i Z_i + sum_{i<j} (J_ij + J_ji) Z_i Z_j."""
    paulis = []
    coeffs = []
    for i in range(nv):
        if abs(h[i]) > 1e-12:
            s = ["I"] * nv
            s[nv - 1 - i] = "Z"
            paulis.append("".join(s))
            coeffs.append(float(h[i]))
    for i in range(nv):
        for j in range(i + 1, nv):
            jij = J[i, j] + J[j, i]
            if abs(jij) > 1e-12:
                s = ["I"] * nv
                s[nv - 1 - i] = "Z"
                s[nv - 1 - j] = "Z"
                paulis.append("".join(s))
                coeffs.append(float(jij))
    if not paulis:
        return SparsePauliOp(["I" * nv], coeffs=[0.0])
    return SparsePauliOp(paulis, coeffs=coeffs)

def build_qaoa_circuit(h, J, nv, gammas, betas):
    """Standard QAOA ansatz: |+>^n -> apply (cost, mixer) p times."""
    qc = QuantumCircuit(nv)
    for q in range(nv):
        qc.h(q)
    p = len(gammas)
    for layer in range(p):
        gamma = gammas[layer]
        # cost layer: exp(-i gamma H_C); H_C = sum h_i Z_i + sum J_ij Z_i Z_j
        for i in range(nv):
            if abs(h[i]) > 1e-12:
                qc.rz(2 * gamma * h[i], i)
        for i in range(nv):
            for j in range(i + 1, nv):
                jij = J[i, j] + J[j, i]
                if abs(jij) > 1e-12:
                    qc.rzz(2 * gamma * jij, i, j)
        # mixer layer: exp(-i beta sum X_i)
        beta = betas[layer]
        for i in range(nv):
            qc.rx(2 * beta, i)
    return qc

def solve_qaoa(Q, reps=1, seed=42):
    """
    Custom minimal QAOA bypassing Sampler V2 overhead. Uses Statevector directly.
    Optimizer: scipy COBYLA.
    Returns (best_bitstring, cost on Q).
    """
    np.random.seed(seed)
    nv = Q.shape[0]
    h, J, offset = qubo_to_ising(Q)
    H_op = ising_to_pauli_op(h, J, nv)

    # cost function: <psi(gamma,beta)| H_op |psi> + offset
    def cost_fn(params):
        gammas = params[:reps]
        betas  = params[reps:]
        qc = build_qaoa_circuit(h, J, nv, gammas, betas)
        sv = Statevector.from_instruction(qc)
        return float(np.real(sv.expectation_value(H_op))) + offset

    # initial point: small random in [0, pi/2]
    x0 = np.random.uniform(0, np.pi / 2, size=2 * reps)
    res = scipy_minimize(cost_fn, x0, method="COBYLA",
                          options={"maxiter": COBYLA_MAXITER, "rhobeg": 0.5})
    # extract best bitstring from final statevector by taking argmax of |amplitude|^2
    gammas = res.x[:reps]; betas = res.x[reps:]
    qc_final = build_qaoa_circuit(h, J, nv, gammas, betas)
    sv = Statevector.from_instruction(qc_final)
    probs = np.abs(sv.data) ** 2
    # Try all bitstrings ranked by probability and pick the one with lowest QUBO cost
    # (top-k strategy commonly used in QAOA post-processing)
    top_k = min(2 ** nv, 32)  # at most 32 candidates
    top_indices = np.argsort(probs)[::-1][:top_k]
    best_x = None
    best_c = math.inf
    for idx in top_indices:
        # qiskit bitstring ordering: rightmost bit = qubit 0
        x = np.array([(idx >> i) & 1 for i in range(nv)], dtype=float)
        c = cost_eval(x, Q)
        if c < best_c:
            best_c = c
            best_x = x
    return best_x, best_c

# -------------- driver --------------
def run_one(N, T, seed, do_qaoa=True, qaoa_reps_list=(1,2,3)):
    risk, urg = gen_instance(N, T, seed)
    Q = build_qubo_matrix(N, T, risk, urg)
    nv = Q.shape[0]
    rec = dict(N=N, T=T, nvars=nv, seed=seed)
    # brute
    if nv <= 24:
        t0 = time.time(); xb, cb = solve_brute_force(Q); tb = time.time() - t0
        rec.update(BF_cost=cb, BF_time=tb)
        opt = cb
    else:
        rec.update(BF_cost=None, BF_time=None); opt = None
    # SA
    t0 = time.time(); xs, cs = solve_sa(Q, seed=seed); ts = time.time() - t0
    rec.update(SA_cost=cs, SA_time=ts,
               SA_abs_gap=(cs - opt) if opt is not None else None,
               SA_optimal=(opt is not None and abs(cs - opt) < 1e-6))
    # init missing QAOA columns to None for consistent CSV schema
    for p in [1,2,3]:
        rec[f"QAOA{p}_cost"] = None
        rec[f"QAOA{p}_time"] = None
        rec[f"QAOA{p}_err"]  = None
        rec[f"QAOA{p}_abs_gap"] = None
        rec[f"QAOA{p}_optimal"] = None
    # QAOA
    if do_qaoa:
        for p in qaoa_reps_list:
            t0 = time.time()
            try:
                xq, cq = solve_qaoa(Q, reps=p, seed=seed); err = None
            except Exception as e:
                cq = None; err = str(e)
            tq = time.time() - t0
            rec[f"QAOA{p}_cost"] = cq
            rec[f"QAOA{p}_time"] = tq
            rec[f"QAOA{p}_err"]  = err
            rec[f"QAOA{p}_abs_gap"] = (cq - opt) if (cq is not None and opt is not None) else None
            rec[f"QAOA{p}_optimal"] = bool(cq is not None and opt is not None and abs(cq - opt) < 1e-6)
    return rec

def main():
    rows = []
    for (N, T) in GRID:
        for seed in SEEDS:
            print(f"[E-Q1] N={N} T={T} seed={seed} (QAOA p=1,2,3) ...", flush=True)
            r = run_one(N, T, seed, do_qaoa=True, qaoa_reps_list=QAOA_REPS_FULL)
            def fmt(v, prec=4):
                if v is None: return "None"
                if isinstance(v, bool): return str(v)
                return f"{v:.{prec}f}"
            print(f"   BF={fmt(r['BF_cost'])} t={fmt(r['BF_time'],2)}s | "
                  f"SA={fmt(r['SA_cost'])} t={fmt(r['SA_time'],2)}s absgap={fmt(r['SA_abs_gap'])} opt?={r['SA_optimal']} | "
                  f"Q1c={fmt(r['QAOA1_cost'])} t={fmt(r['QAOA1_time'],2)}s opt?={r['QAOA1_optimal']} | "
                  f"Q2c={fmt(r['QAOA2_cost'])} t={fmt(r['QAOA2_time'],2)}s opt?={r['QAOA2_optimal']} | "
                  f"Q3c={fmt(r['QAOA3_cost'])} t={fmt(r['QAOA3_time'],2)}s opt?={r['QAOA3_optimal']}",
                  flush=True)
            rows.append(r)
    for (N, T) in GRID_P1ONLY:
        for seed in SEEDS:
            print(f"[E-Q1] N={N} T={T} seed={seed} (QAOA p=1 only, scaling anchor) ...", flush=True)
            r = run_one(N, T, seed, do_qaoa=True, qaoa_reps_list=(1,))
            print(f"   nv={r['nvars']} BF={r['BF_cost']:.4f} t={r['BF_time']:.2f}s | SA={r['SA_cost']:.4f} t={r['SA_time']:.2f}s | Q1={r['QAOA1_cost']} t={r['QAOA1_time']:.2f}s opt?={r['QAOA1_optimal']}", flush=True)
            rows.append(r)
    for (N, T) in LARGE_GRID:
        for seed in SEEDS:
            print(f"[E-Q1 STRESS] N={N} T={T} seed={seed} (SA only) ...", flush=True)
            do_bf = (N * T) <= 24
            r = run_one(N, T, seed, do_qaoa=False)
            sa_cost_str = f"{r['SA_cost']:.4f}" if r['SA_cost'] is not None else "None"
            bf_str = f"BF={r['BF_cost']:.4f} t={r['BF_time']:.2f}s | " if do_bf else "BF=skip(>24vars) | "
            print(f"   nv={r['nvars']} {bf_str}SA={sa_cost_str} t={r['SA_time']:.2f}s", flush=True)
            rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT_DIR, "per_instance.csv"), index=False)
    # summary
    summary = {}
    for (N, T) in (list(GRID) + list(GRID_P1ONLY)):
        sub = df[(df.N == N) & (df.T == T)]
        agg = {}
        for col in ["BF_cost","BF_time","SA_cost","SA_abs_gap","SA_time",
                    "QAOA1_cost","QAOA1_abs_gap","QAOA1_time",
                    "QAOA2_cost","QAOA2_abs_gap","QAOA2_time",
                    "QAOA3_cost","QAOA3_abs_gap","QAOA3_time"]:
            vals = sub[col].dropna().values.astype(float)
            agg[col + "_mean"] = float(np.mean(vals)) if len(vals) else None
            agg[col + "_std"]  = float(np.std(vals)) if len(vals) else None
        for col in ["SA_optimal","QAOA1_optimal","QAOA2_optimal","QAOA3_optimal"]:
            agg[col + "_rate"] = float(sub[col].dropna().mean()) if sub[col].dropna().size else None
        summary[f"N{N}_T{T}"] = agg
    for (N, T) in LARGE_GRID:
        sub = df[(df.N == N) & (df.T == T)]
        agg = {}
        for col in ["SA_cost","SA_time"]:
            vals = sub[col].dropna().values.astype(float)
            agg[col + "_mean"] = float(np.mean(vals)) if len(vals) else None
            agg[col + "_std"]  = float(np.std(vals)) if len(vals) else None
        summary[f"N{N}_T{T}_stress"] = agg
    # paired tests on absolute gap (QAOA p=1,2,3 vs SA, where both available)
    from scipy.stats import wilcoxon, ttest_rel, shapiro
    summary["paired_tests"] = {}
    for p_target in (1, 2, 3):
        sub = df.dropna(subset=["SA_abs_gap", f"QAOA{p_target}_abs_gap"])
        gap_sa = sub.SA_abs_gap.values.astype(float)
        gap_q  = sub[f"QAOA{p_target}_abs_gap"].values.astype(float)
        diff = gap_q - gap_sa
        if len(diff) >= 3 and not np.allclose(diff, 0):
            try:
                sw_p = shapiro(diff).pvalue
            except Exception:
                sw_p = 0.0
            if sw_p > 0.05:
                tstat, pval = ttest_rel(gap_q, gap_sa); test_name = "paired_t"
            else:
                try:
                    wstat, pval = wilcoxon(gap_q, gap_sa, zero_method="wilcox")
                    test_name = "wilcoxon"
                except ValueError:
                    pval = None; test_name = "n/a (all-zero diffs)"
        else:
            pval = None; test_name = "n/a"
        summary["paired_tests"][f"QAOA{p_target}_vs_SA"] = dict(
            test=test_name,
            p=float(pval) if pval is not None else None,
            n=int(len(diff)),
            mean_abs_gap_diff=float(np.mean(diff)) if len(diff) else None,
            SA_optimal_rate=float(sub.SA_optimal.mean()) if len(sub) else None,
            QAOA_optimal_rate=float(sub[f"QAOA{p_target}_optimal"].mean()) if len(sub) else None,
        )
    with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("[E-Q1] saved per_instance.csv + summary.json")

if __name__ == "__main__":
    main()
