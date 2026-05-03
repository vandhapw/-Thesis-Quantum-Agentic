"""
E-L3A -- Static Scheduling: Classical vs Quantum Comparison
============================================================

Pre-registered protocol: PHASE1_PROTOCOL_V2_ALIGNED_3LAYER.md  4
Authorization: E-L2 V3 cleared kappa = 0.7425 >= 0.6 threshold

Problem: Schedule maintenance tasks across employees and time slots to
minimize makespan.

Decision variable: x[m,e,s] = 1 iff machine m STARTS maintenance with
employee e at slot s. Machine m occupies slots [s, s+d_m).

Constraints:
  C1 each machine assigned exactly once: sum_{e,s} x[m,e,s] = 1
  C2 each employee at most 1 task per slot
  C3 maintenance duration d_m occupies consecutive slots
  C4 no spillover past slot S_max

Objective: makespan = max over assigned (start + duration)

Maintenance duration mapping (Mobley 2002 / Gulati 2013 / ISO 17359):
  Vibration Issue: 2 slots; Overheating: 2; Pressure Drop: 2;
  Electrical Fault: 3; Normal/preventive: 1

Sweep: 3 sizes x 3 employee groups x 5 seeds = 45 controlled + Layer 2
integration test (3 cases).

Solvers (with size-appropriate skipping):
  - Greedy (informational baseline): all sizes
  - GA (DEAP): all sizes
  - SA (dwave-neal): all sizes
  - TS (custom Tabu Search): all sizes
  - QAOA (qiskit Statevector): Small only (qubit budget)
  - QA (dwave-neal Ising mode): all sizes (separate run from SA)
  - SBM (Simulated Bifurcation, Goto 2019): all sizes

Primary metric: makespan
Secondary: wall-clock, constraint-sat-rate, real-time feasibility (<=60s)
"""
import os, sys, json, time, math, random, copy, argparse
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize as scipy_minimize

sys.path.insert(0, r"D:/AI-LLM/Claude Experiment/Ver13")

OUT_DIR = Path(r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-L3A_static_scheduling")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FAILURE_DURATION = {
    "Vibration Issue": 2, "Overheating": 2, "Pressure Drop": 2,
    "Electrical Fault": 3, "Normal": 1,
}
DEFAULT_DURATION = 1
SLOTS_PER_DAY = 9       # 09:00-18:00
SEEDS = [42, 7, 1234, 100, 200]
SIZES = [
    ("Small",  5,  1, [1, 3, 5]),       # (label, n_machines, n_days, employee_groups)
    ("Medium", 20, 3, [3, 5, 10]),
    ("Large",  50, 5, [5, 10, 20]),
]

# ----------------------------------------------------------------------------
# Problem instance generation
# ----------------------------------------------------------------------------
FAILURE_TYPES = ["Vibration Issue", "Overheating", "Pressure Drop", "Electrical Fault", "Normal"]

def gen_instance(n_machines, n_days, n_employees, seed):
    rng = np.random.default_rng(seed)
    failure_types = list(rng.choice(FAILURE_TYPES, size=n_machines, p=[0.25, 0.20, 0.20, 0.15, 0.20]))
    durations = [FAILURE_DURATION.get(ft, DEFAULT_DURATION) for ft in failure_types]
    n_slots = SLOTS_PER_DAY * n_days
    return {
        "n_machines": n_machines, "n_employees": n_employees,
        "n_days": n_days, "n_slots": n_slots,
        "failure_types": failure_types, "durations": durations,
        "seed": seed,
    }

# ----------------------------------------------------------------------------
# Solution representation & evaluation
# ----------------------------------------------------------------------------
def empty_schedule(inst):
    """Schedule = list of (machine_id, employee_id, start_slot) tuples."""
    return []

def add_assignment(sched, m, e, s):
    sched.append((m, e, s))

def is_feasible(sched, inst):
    """Check all constraints. Returns (feasible: bool, violations: dict)."""
    n_m, n_e, n_s = inst["n_machines"], inst["n_employees"], inst["n_slots"]
    durations = inst["durations"]
    assigned = set(); violations = {"C1_unassigned": 0, "C1_double": 0, "C2_overlap": 0, "C4_spillover": 0}

    # C1: each machine exactly once
    machines = [m for (m, _, _) in sched]
    for m in range(n_m):
        c = machines.count(m)
        if c == 0: violations["C1_unassigned"] += 1
        elif c > 1: violations["C1_double"] += c - 1

    # C4: no spillover past n_s
    for (m, e, s) in sched:
        if s + durations[m] > n_s:
            violations["C4_spillover"] += 1

    # C2: each employee at most 1 task per slot
    occ = {}  # (e, t) -> count
    for (m, e, s) in sched:
        for t in range(s, min(s + durations[m], n_s)):
            occ[(e, t)] = occ.get((e, t), 0) + 1
    for k, v in occ.items():
        if v > 1: violations["C2_overlap"] += v - 1

    feasible = sum(violations.values()) == 0 and len(machines) == n_m
    return feasible, violations

def makespan(sched, inst):
    if not sched: return inst["n_slots"]
    durations = inst["durations"]
    return max(s + durations[m] for (m, e, s) in sched)

def objective_with_penalty(sched, inst, lam=1000.0):
    """Objective for solvers: makespan + heavy penalty for violations."""
    feas, viol = is_feasible(sched, inst)
    pen = lam * sum(viol.values())
    return makespan(sched, inst) + pen

# ----------------------------------------------------------------------------
# Greedy baseline (informational; also serves as initial solution)
# ----------------------------------------------------------------------------
def greedy_schedule(inst):
    """Sort machines by descending duration, assign to first feasible (e,s)."""
    n_m, n_e, n_s = inst["n_machines"], inst["n_employees"], inst["n_slots"]
    durations = inst["durations"]
    order = sorted(range(n_m), key=lambda m: -durations[m])
    sched = []
    employee_load = [[0]*n_s for _ in range(n_e)]   # 1 if occupied
    for m in order:
        d = durations[m]
        placed = False
        for s in range(n_s - d + 1):
            for e in range(n_e):
                if all(employee_load[e][t] == 0 for t in range(s, s+d)):
                    add_assignment(sched, m, e, s)
                    for t in range(s, s+d): employee_load[e][t] = 1
                    placed = True
                    break
            if placed: break
        if not placed:
            # infeasible — give up (no slot fits); add at slot 0 to mark unfit
            add_assignment(sched, m, 0, 0)
    return sched

# ----------------------------------------------------------------------------
# Solver: Simulated Annealing on schedule
# ----------------------------------------------------------------------------
def solve_sa(inst, max_iter=2000, T0=10.0, T_min=1e-4, seed=42):
    rng = random.Random(seed)
    sched = greedy_schedule(inst)
    best, best_obj = list(sched), objective_with_penalty(sched, inst)
    cur, cur_obj = list(sched), best_obj
    n_m, n_e, n_s = inst["n_machines"], inst["n_employees"], inst["n_slots"]
    alpha = (T_min / T0) ** (1.0 / max(max_iter,1))
    T = T0
    for it in range(max_iter):
        # propose move: pick random machine, change its (e, s)
        idx = rng.randrange(len(cur))
        m, e, s = cur[idx]
        d = inst["durations"][m]
        new_e = rng.randrange(n_e)
        new_s = rng.randrange(max(1, n_s - d + 1))
        cand = list(cur); cand[idx] = (m, new_e, new_s)
        cand_obj = objective_with_penalty(cand, inst)
        delta = cand_obj - cur_obj
        if delta < 0 or rng.random() < math.exp(-delta / max(T, 1e-9)):
            cur, cur_obj = cand, cand_obj
            if cand_obj < best_obj:
                best, best_obj = list(cand), cand_obj
        T *= alpha
    return best, best_obj

# ----------------------------------------------------------------------------
# Solver: Tabu Search on schedule
# ----------------------------------------------------------------------------
def solve_ts(inst, max_iter=500, tenure=15, seed=42):
    rng = random.Random(seed)
    cur = greedy_schedule(inst)
    best = list(cur); best_obj = objective_with_penalty(cur, inst)
    cur_obj = best_obj
    tabu = []  # list of (idx, e, s) recent moves
    n_m, n_e, n_s = inst["n_machines"], inst["n_employees"], inst["n_slots"]
    plateau = 0
    for it in range(max_iter):
        # generate candidate moves from current
        best_move = None; best_move_obj = float("inf"); best_move_ix = -1
        sample_size = min(50, n_m * n_e * 5)  # sample neighbor subset
        for _ in range(sample_size):
            idx = rng.randrange(len(cur))
            m, e, s = cur[idx]
            d = inst["durations"][m]
            new_e = rng.randrange(n_e)
            new_s = rng.randrange(max(1, n_s - d + 1))
            move_key = (idx, new_e, new_s)
            if move_key in tabu and (best_move_obj > best_obj):  # aspiration: allow if improves best
                continue
            cand = list(cur); cand[idx] = (m, new_e, new_s)
            obj = objective_with_penalty(cand, inst)
            if obj < best_move_obj:
                best_move_obj = obj; best_move = cand; best_move_ix = move_key
        if best_move is None: break
        cur, cur_obj = best_move, best_move_obj
        tabu.append(best_move_ix)
        if len(tabu) > tenure: tabu.pop(0)
        if cur_obj < best_obj:
            best, best_obj = list(cur), cur_obj
            plateau = 0
        else:
            plateau += 1
            if plateau >= 100:
                # restart from best with random perturbation
                cur = list(best); plateau = 0
    return best, best_obj

# ----------------------------------------------------------------------------
# Solver: Genetic Algorithm (custom, no DEAP dependency)
# ----------------------------------------------------------------------------
def encode_sched(sched, n_m):
    """Encode as flat tuple (e0, s0, e1, s1, ..., e_{n_m-1}, s_{n_m-1})."""
    arr = [0] * (2 * n_m)
    for (m, e, s) in sched:
        arr[2*m] = e; arr[2*m+1] = s
    return arr

def decode_sched(arr, n_m):
    return [(m, arr[2*m], arr[2*m+1]) for m in range(n_m)]

def solve_ga(inst, pop_size=80, generations=150, mut_rate=0.1, seed=42):
    rng = random.Random(seed)
    n_m, n_e, n_s = inst["n_machines"], inst["n_employees"], inst["n_slots"]

    def random_individual():
        arr = []
        for m in range(n_m):
            d = inst["durations"][m]
            arr.append(rng.randrange(n_e))
            arr.append(rng.randrange(max(1, n_s - d + 1)))
        return arr

    def evaluate(arr):
        return objective_with_penalty(decode_sched(arr, n_m), inst)

    def crossover(p1, p2):
        cut = rng.randrange(1, n_m)
        c1 = p1[:2*cut] + p2[2*cut:]
        c2 = p2[:2*cut] + p1[2*cut:]
        return c1, c2

    def mutate(arr):
        new = list(arr)
        for m in range(n_m):
            if rng.random() < mut_rate:
                new[2*m] = rng.randrange(n_e)
            if rng.random() < mut_rate:
                d = inst["durations"][m]
                new[2*m+1] = rng.randrange(max(1, n_s - d + 1))
        return new

    # init population
    pop = [encode_sched(greedy_schedule(inst), n_m)] + [random_individual() for _ in range(pop_size - 1)]
    fitness = [evaluate(ind) for ind in pop]

    for gen in range(generations):
        # tournament select 2 parents
        new_pop = []
        elite_idx = min(range(pop_size), key=lambda i: fitness[i])
        new_pop.append(list(pop[elite_idx]))
        while len(new_pop) < pop_size:
            t1 = min(rng.sample(range(pop_size), 3), key=lambda i: fitness[i])
            t2 = min(rng.sample(range(pop_size), 3), key=lambda i: fitness[i])
            c1, c2 = crossover(pop[t1], pop[t2])
            new_pop.append(mutate(c1))
            if len(new_pop) < pop_size: new_pop.append(mutate(c2))
        pop = new_pop
        fitness = [evaluate(ind) for ind in pop]
    best_idx = min(range(pop_size), key=lambda i: fitness[i])
    return decode_sched(pop[best_idx], n_m), fitness[best_idx]

# ----------------------------------------------------------------------------
# Solver: Quantum Annealing (dwave-neal Ising-mode QUBO)
# ----------------------------------------------------------------------------
def build_qubo(inst):
    """Build QUBO Q matrix on x[m,e,s] variables.
    Encode constraints as quadratic penalties; objective = mean start time as proxy for makespan.
    Variable index k = m*n_e*n_s + e*n_s + s.
    """
    n_m, n_e, n_s = inst["n_machines"], inst["n_employees"], inst["n_slots"]
    durations = inst["durations"]
    nv = n_m * n_e * n_s
    Q = {}
    def k(m, e, s): return m * n_e * n_s + e * n_s + s
    def addq(i, j, v):
        if i > j: i, j = j, i
        Q[(i, j)] = Q.get((i, j), 0.0) + v

    LAM = 5000.0    # constraint penalty (raised from 100 after smoke showed QA/SBM picked violation over makespan minimization)
    # Objective: prefer earlier start (proxy for makespan); coefficient = (s + d_m)
    for m in range(n_m):
        d = durations[m]
        for e in range(n_e):
            for s in range(n_s - d + 1):
                addq(k(m,e,s), k(m,e,s), float(s + d))   # linear

    # C1: each machine exactly one assignment -> LAM * (1 - sum_{e,s} x_{m,e,s})^2
    for m in range(n_m):
        d = durations[m]
        # quadratic expansion: LAM * (1 - 2*sum + sum^2)
        for e1 in range(n_e):
            for s1 in range(n_s - d + 1):
                addq(k(m,e1,s1), k(m,e1,s1), -2*LAM)   # linear -2*LAM*x
                for e2 in range(n_e):
                    for s2 in range(n_s - d + 1):
                        addq(k(m,e1,s1), k(m,e2,s2), LAM)   # quadratic LAM*x*x

    # C2 + C3: each (e, t) at most one task occupies it
    # For each (e, t), penalize sum of x_{m,e,s} where s <= t < s+d_m
    for e in range(n_e):
        for t in range(n_s):
            occupants = []
            for m in range(n_m):
                d = durations[m]
                for s in range(max(0, t - d + 1), min(n_s - d + 1, t + 1)):
                    occupants.append(k(m, e, s))
            # penalty LAM * (sum > 1)^2 -> LAM * sum_{i!=j} x_i x_j
            for i in range(len(occupants)):
                for j in range(i+1, len(occupants)):
                    addq(occupants[i], occupants[j], LAM)
    return Q, nv

def solve_qa_neal(inst, num_reads=1000, seed=42):
    """Quantum Annealing simulation via dwave-neal (Ising-mode SA, separate from classical SA)."""
    try:
        import dimod
        from neal import SimulatedAnnealingSampler
    except ImportError:
        return None, float("inf")
    Q_dict, nv = build_qubo(inst)
    if nv > 5000:
        return None, float("inf")  # too big for in-memory QUBO
    bqm = dimod.BinaryQuadraticModel({i: 0.0 for i in range(nv)}, {}, 0.0, dimod.BINARY)
    for (i, j), v in Q_dict.items():
        if i == j: bqm.linear[i] = bqm.linear.get(i, 0.0) + v
        else:      bqm.add_quadratic(i, j, v)
    sampler = SimulatedAnnealingSampler()
    res = sampler.sample(bqm, num_reads=num_reads, seed=seed)
    best = res.first.sample
    n_m, n_e, n_s = inst["n_machines"], inst["n_employees"], inst["n_slots"]
    sched = []
    for m in range(n_m):
        for e in range(n_e):
            for s in range(n_s):
                idx = m * n_e * n_s + e * n_s + s
                if best.get(idx, 0) == 1:
                    sched.append((m, e, s))
                    break
            else: continue
            break
    if not sched: return None, float("inf")
    return sched, objective_with_penalty(sched, inst)

# ----------------------------------------------------------------------------
# Solver: Simulated Bifurcation Machine (Goto 2019, Toshiba SBM)
# ----------------------------------------------------------------------------
def solve_sbm(inst, n_steps=500, dt=0.5, K=1.0, seed=42):
    """Simulated Bifurcation: minimize Ising H = -1/2 sum J_ij s_i s_j - sum h_i s_i.
    Map QUBO to Ising: x_i = (1+s_i)/2, then transform Q to (h, J).
    """
    rng = np.random.default_rng(seed)
    Q_dict, nv = build_qubo(inst)
    if nv > 3000: return None, float("inf")  # SBM at this scale gets memory-heavy
    # Build h, J from Q
    h = np.zeros(nv); J = np.zeros((nv, nv))
    for (i, j), v in Q_dict.items():
        if i == j: h[i] += v / 2.0
        else:
            J[i, j] += v / 4.0; J[j, i] += v / 4.0
            h[i] += v / 4.0; h[j] += v / 4.0
    # Initialize positions x and momenta y
    x = rng.normal(0, 0.1, nv); y = rng.normal(0, 0.1, nv)
    # SBM dynamics
    for k in range(n_steps):
        a = (k + 1) / n_steps   # ramp parameter
        # gradient of energy
        grad = -h - J @ np.sign(x)
        y = y + dt * (K * (a - 1) * x + grad)
        x = x + dt * y
        # binarize during evolution to constrain
        if k > n_steps * 0.5:
            x = np.clip(x, -1, 1)
    spins = np.sign(x); bits = ((spins + 1) // 2).astype(int)
    n_m, n_e, n_s = inst["n_machines"], inst["n_employees"], inst["n_slots"]
    sched = []
    for m in range(n_m):
        for e in range(n_e):
            for s in range(n_s):
                if bits[m * n_e * n_s + e * n_s + s] == 1:
                    sched.append((m, e, s))
                    break
            else: continue
            break
    if not sched: return None, float("inf")
    return sched, objective_with_penalty(sched, inst)

# ----------------------------------------------------------------------------
# Solver: QAOA (gate model, Statevector — Small only)
# ----------------------------------------------------------------------------
def solve_qaoa(inst, reps=2, max_iter=200, seed=42):
    try:
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Statevector, SparsePauliOp
    except ImportError:
        return None, float("inf")
    Q_dict, nv = build_qubo(inst)
    if nv > 18:   # statevector limit ~18 qubits comfortably
        return None, float("inf")
    # QUBO to Ising
    h = np.zeros(nv); J = np.zeros((nv, nv)); offset = 0.0
    for (i, j), v in Q_dict.items():
        if i == j:
            offset += v / 2.0; h[i] += -v / 2.0
        else:
            offset += v / 4.0
            h[i] += -v / 4.0; h[j] += -v / 4.0
            J[i, j] += v / 4.0
    # Build SparsePauliOp
    paulis, coeffs = [], []
    for i in range(nv):
        if abs(h[i]) > 1e-12:
            s = ["I"] * nv; s[nv - 1 - i] = "Z"
            paulis.append("".join(s)); coeffs.append(float(h[i]))
    for i in range(nv):
        for j in range(i+1, nv):
            jij = J[i, j] + J[j, i]
            if abs(jij) > 1e-12:
                s = ["I"] * nv; s[nv - 1 - i] = "Z"; s[nv - 1 - j] = "Z"
                paulis.append("".join(s)); coeffs.append(float(jij))
    if not paulis:
        return None, float("inf")
    H_op = SparsePauliOp(paulis, coeffs=coeffs)

    def ansatz(params):
        gammas = params[:reps]; betas = params[reps:]
        qc = QuantumCircuit(nv)
        for q in range(nv): qc.h(q)
        for layer in range(reps):
            g = gammas[layer]
            for i in range(nv):
                if abs(h[i]) > 1e-12: qc.rz(2*g*h[i], i)
            for i in range(nv):
                for j in range(i+1, nv):
                    jij = J[i, j] + J[j, i]
                    if abs(jij) > 1e-12: qc.rzz(2*g*jij, i, j)
            b = betas[layer]
            for i in range(nv): qc.rx(2*b, i)
        return qc

    def cost_fn(params):
        qc = ansatz(params)
        sv = Statevector.from_instruction(qc)
        return float(np.real(sv.expectation_value(H_op))) + offset

    np.random.seed(seed)
    x0 = np.random.uniform(0, np.pi/2, size=2*reps)
    res = scipy_minimize(cost_fn, x0, method="COBYLA",
                          options={"maxiter": max_iter, "rhobeg": 0.5})
    qc_final = ansatz(res.x)
    sv = Statevector.from_instruction(qc_final)
    probs = np.abs(sv.data) ** 2
    top_k = min(2 ** nv, 32)
    top_idx = np.argsort(probs)[::-1][:top_k]
    n_m, n_e, n_s = inst["n_machines"], inst["n_employees"], inst["n_slots"]
    best_sched = None; best_obj = float("inf")
    for idx in top_idx:
        bits = [(idx >> i) & 1 for i in range(nv)]
        sched = []
        for m in range(n_m):
            for e in range(n_e):
                for s in range(n_s):
                    if bits[m * n_e * n_s + e * n_s + s] == 1:
                        sched.append((m, e, s)); break
                else: continue
                break
        if not sched: continue
        obj = objective_with_penalty(sched, inst)
        if obj < best_obj:
            best_obj = obj; best_sched = sched
    return best_sched, best_obj

# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------
def evaluate_solver(name, fn, inst, seed):
    t0 = time.time()
    try:
        sched, obj = fn(inst, seed=seed)
    except Exception as e:
        return {"solver": name, "obj": None, "feasible": False, "violations": str(e)[:100],
                "wall_clock_s": time.time() - t0, "makespan": None, "skipped": True}
    if sched is None:
        return {"solver": name, "obj": None, "feasible": False, "wall_clock_s": time.time() - t0,
                "makespan": None, "skipped": True}
    feas, viol = is_feasible(sched, inst)
    return {"solver": name, "obj": float(obj), "feasible": feas, "violations": viol,
            "wall_clock_s": time.time() - t0, "makespan": int(makespan(sched, inst)),
            "n_assignments": len(sched), "skipped": False}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="reduce sweep to 1 seed for testing")
    args = ap.parse_args()
    seeds = SEEDS[:1] if args.quick else SEEDS

    rows = []
    print(f"[E-L3A] starting sweep: {len(SIZES)} sizes × employee_groups × {len(seeds)} seeds")
    print(f"        QAOA available only when n_vars <= 18; QA <= 5000; SBM <= 3000\n")

    for (size_label, n_m, n_d, emp_groups) in SIZES:
        for n_e in emp_groups:
            for seed in seeds:
                inst = gen_instance(n_m, n_d, n_e, seed)
                nv = n_m * n_e * inst["n_slots"]
                print(f"[{size_label}] N={n_m} D={n_d} E={n_e} seed={seed} | nv={nv} | running solvers...", flush=True)

                # Greedy (informational)
                t0 = time.time()
                gsched = greedy_schedule(inst)
                gfeas, gviol = is_feasible(gsched, inst)
                gobj = objective_with_penalty(gsched, inst)
                gtime = time.time() - t0
                rows.append({"size": size_label, "N": n_m, "D": n_d, "E": n_e, "seed": seed, "nv": nv,
                              "solver": "Greedy", "obj": float(gobj), "makespan": int(makespan(gsched, inst)),
                              "feasible": gfeas, "violations": gviol, "wall_clock_s": gtime, "skipped": False})

                # GA, SA, TS — all sizes
                for sname, sfn in [("GA", solve_ga), ("SA", solve_sa), ("TS", solve_ts)]:
                    r = evaluate_solver(sname, sfn, inst, seed)
                    r.update({"size": size_label, "N": n_m, "D": n_d, "E": n_e, "seed": seed, "nv": nv})
                    rows.append(r)

                # QA, SBM — size-conditional
                for sname, sfn, max_nv in [("QA_neal", solve_qa_neal, 5000), ("SBM", solve_sbm, 3000)]:
                    if nv > max_nv:
                        rows.append({"size": size_label, "N": n_m, "D": n_d, "E": n_e, "seed": seed, "nv": nv,
                                      "solver": sname, "skipped": True, "skip_reason": f"nv > {max_nv}"})
                        continue
                    r = evaluate_solver(sname, sfn, inst, seed)
                    r.update({"size": size_label, "N": n_m, "D": n_d, "E": n_e, "seed": seed, "nv": nv})
                    rows.append(r)

                # QAOA — dropped from E-L3A: scheduling QUBO encoding requires N*E*S vars
                # (>=45 for our smallest meaningful instance), exceeds practical statevector
                # simulator limit (~18 qubits). QAOA was evaluated in E-Q1 V1 at simpler 4-15 var
                # scale where parity with SA was demonstrated; not retested here.
                rows.append({"size": size_label, "N": n_m, "D": n_d, "E": n_e, "seed": seed, "nv": nv,
                              "solver": "QAOA_p2", "skipped": True,
                              "skip_reason": "scheduling QUBO nv > 18 even at smallest instance; see E-Q1 V1 for QAOA scaling evaluation"})

                # report this instance's best per-solver
                latest = [r for r in rows if r.get("seed") == seed and r.get("N") == n_m and r.get("E") == n_e]
                summary_line = "  -> "
                for r in latest:
                    if r.get("skipped"): continue
                    feas = "F" if r.get("feasible") else "X"
                    summary_line += f"{r['solver']}={r.get('makespan','-')}({feas},{r.get('wall_clock_s',0):.1f}s) "
                print(summary_line, flush=True)

    # Save full per-run CSV
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "per_run.csv", index=False)
    print(f"\n[E-L3A] saved per_run.csv with {len(rows)} rows")

    # Aggregate per (size, E, solver): mean makespan + mean wall-clock + feasibility rate
    agg = df[~df.get("skipped", pd.Series([False]*len(df))).fillna(False)].copy()
    if len(agg):
        summary = agg.groupby(["size","N","E","solver"]).agg(
            n_runs=("seed","count"),
            mean_makespan=("makespan","mean"),
            std_makespan=("makespan","std"),
            mean_wall_s=("wall_clock_s","mean"),
            feas_rate=("feasible","mean"),
        ).reset_index()
        summary.to_csv(OUT_DIR / "summary.csv", index=False)
        print(summary.to_string())
    else:
        print("[E-L3A] no successful runs")

if __name__ == "__main__":
    main()
