"""
E-L3B -- Dynamic Rolling-Horizon Scheduling Real-Time Feasibility Test
=======================================================================

Pre-registered protocol: PHASE1_PROTOCOL_V2_ALIGNED_3LAYER.md  5
Authorization: E-L2 V3 cleared (kappa=0.7425); E-L3A static comparison done.

Per E-L3A finding, QA_neal and SBM consistently fail to produce feasible solutions
on dense scheduling QUBO; therefore E-L3B focuses on classical solver real-time
feasibility validation under event-driven re-optimization.

Setup:
  - Simulated 8-hour working day (9:00 - 17:00) at Medium size
  - Initial Layer-2-style schedule: 20 machines × 5 employees × 3 days = 27-slot horizon
  - Event stream:
      * New machine flag (Poisson lambda = 2/hour)
      * Employee finish early (per active task, prob = 0.1)
      * Employee task delay (per active task, prob = 0.05)
  - Re-optimize on each event using current solver
  - Record per-event wall-clock + total deadline-miss count

Solvers compared (classical only per E-L3A finding):
  - Greedy
  - GA
  - SA
  - TS

Real-time feasibility threshold: <=60s wall-clock per re-optimization event.
"""
import os, sys, json, time, math, random, copy
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, r"D:/AI-LLM/Claude Experiment/Ver13")
sys.path.insert(0, r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-L3A_static_scheduling")
from run_el3a import (
    gen_instance, greedy_schedule, solve_ga, solve_sa, solve_ts,
    is_feasible, makespan, objective_with_penalty, FAILURE_TYPES, FAILURE_DURATION,
    SLOTS_PER_DAY,
)

OUT_DIR = Path(r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-L3B_dynamic_scheduling")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SOLVERS = {
    "Greedy": lambda inst, seed=42: (greedy_schedule(inst), objective_with_penalty(greedy_schedule(inst), inst)),
    "GA":     solve_ga,
    "SA":     solve_sa,
    "TS":     solve_ts,
}

# Simulation parameters
N_MACHINES_INIT = 20
N_EMPLOYEES = 5
N_DAYS = 3
SIM_HOURS = 8                  # 9:00-17:00
EVENT_LAMBDA_PER_HOUR = 2.0    # new machine flags / hour (Poisson)
EMP_FINISH_EARLY_P = 0.10      # per active task
EMP_DELAY_P = 0.05
RT_BUDGET_S = 60.0
SEEDS = [42, 7, 1234]

def simulate_one(seed):
    """Run 8-hour event-driven simulation for ALL solvers, recording per-event wall-clock."""
    rng_sim = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    # Initial instance: 20 machines as our starting maintenance pool
    inst0 = gen_instance(N_MACHINES_INIT, N_DAYS, N_EMPLOYEES, seed)
    # Generate event stream FIRST (deterministic for fair comparison across solvers)
    events = []
    t_now = 0.0
    while t_now < SIM_HOURS:
        # Poisson inter-arrival
        gap = np_rng.exponential(1.0 / EVENT_LAMBDA_PER_HOUR)
        t_now += gap
        if t_now >= SIM_HOURS: break
        # event type: new machine flag (always for now); could extend with finish/delay
        new_ft = rng_sim.choices(FAILURE_TYPES, weights=[0.25,0.20,0.20,0.15,0.20])[0]
        events.append({"t_hr": t_now, "type": "new_flag", "failure_type": new_ft})
    # Add a few finish-early / delay events at random times (proxy)
    n_finish = max(1, int(EMP_FINISH_EARLY_P * len(events)))
    n_delay  = max(1, int(EMP_DELAY_P * len(events)))
    for _ in range(n_finish):
        events.append({"t_hr": np_rng.uniform(0, SIM_HOURS), "type": "finish_early"})
    for _ in range(n_delay):
        events.append({"t_hr": np_rng.uniform(0, SIM_HOURS), "type": "delay"})
    events.sort(key=lambda e: e["t_hr"])
    print(f"[seed {seed}] generated {len(events)} events over {SIM_HOURS}h", flush=True)

    results = {sname: {"events": [], "total_wall_s": 0.0, "infeasible_count": 0, "exceed_60s_count": 0}
                for sname in SOLVERS}

    # Per-solver simulation (independent runs)
    for sname, sfn in SOLVERS.items():
        cur_inst = copy.deepcopy(inst0)
        for ev_i, ev in enumerate(events):
            # Mutate instance based on event type
            if ev["type"] == "new_flag":
                cur_inst["n_machines"] += 1
                cur_inst["failure_types"].append(ev["failure_type"])
                cur_inst["durations"].append(FAILURE_DURATION.get(ev["failure_type"], 1))
            # finish_early / delay: no instance change in this simplified sim (just trigger re-opt)
            # Re-optimize
            t0 = time.time()
            try:
                sched, obj = sfn(cur_inst, seed=seed + ev_i)
                elapsed = time.time() - t0
                feas, viol = is_feasible(sched, cur_inst)
                ms = makespan(sched, cur_inst)
            except Exception as e:
                elapsed = time.time() - t0
                feas = False; ms = None; obj = None
            results[sname]["events"].append({
                "t_hr": ev["t_hr"], "type": ev["type"],
                "n_machines": cur_inst["n_machines"],
                "wall_s": elapsed, "feasible": bool(feas), "makespan": int(ms) if ms else None,
            })
            results[sname]["total_wall_s"] += elapsed
            if not feas: results[sname]["infeasible_count"] += 1
            if elapsed > RT_BUDGET_S: results[sname]["exceed_60s_count"] += 1
        print(f"  [{sname:6s}] {len(events)} re-opts, total_wall={results[sname]['total_wall_s']:.1f}s, "
              f"infeas={results[sname]['infeasible_count']}, exceed60s={results[sname]['exceed_60s_count']}",
              flush=True)
    return events, results

def main():
    all_results = {}
    for seed in SEEDS:
        print(f"\n[E-L3B] seed={seed} ====================", flush=True)
        events, res = simulate_one(seed)
        all_results[seed] = {"events": events, "results": res}

    # Aggregate
    print("\n[E-L3B] aggregate per-solver metrics across seeds:", flush=True)
    rows = []
    for sname in SOLVERS:
        all_walls = []; all_feas = []; all_exceed = []
        per_seed_totals = []
        for seed in SEEDS:
            r = all_results[seed]["results"][sname]
            for ev in r["events"]:
                all_walls.append(ev["wall_s"])
                all_feas.append(int(ev["feasible"]))
            all_exceed.append(r["exceed_60s_count"])
            per_seed_totals.append(r["total_wall_s"])
        all_walls = np.array(all_walls); all_feas = np.array(all_feas)
        row = {
            "solver": sname, "n_events_total": int(len(all_walls)),
            "feas_rate": float(all_feas.mean()),
            "wall_median_s": float(np.median(all_walls)),
            "wall_p95_s":    float(np.quantile(all_walls, 0.95)),
            "wall_p99_s":    float(np.quantile(all_walls, 0.99)),
            "wall_max_s":    float(np.max(all_walls)),
            "exceed_60s_total": int(sum(all_exceed)),
            "rt_feasibility_rate": float(1.0 - (sum(all_exceed) / len(all_walls))),
            "total_wall_per_day_mean_s": float(np.mean(per_seed_totals)),
        }
        rows.append(row)
        print(f"  {sname:6s} feas_rate={row['feas_rate']:.3f}  "
              f"wall median/p95/max = {row['wall_median_s']:.2f}/{row['wall_p95_s']:.2f}/{row['wall_max_s']:.2f}s  "
              f"exceed60s={row['exceed_60s_total']}/{row['n_events_total']}  "
              f"rt_ok_rate={row['rt_feasibility_rate']:.3f}")

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(OUT_DIR / "summary.csv", index=False)

    with open(OUT_DIR / "raw_results.json", "w") as f:
        json.dump({str(s): {"events": d["events"], "results": d["results"]} for s, d in all_results.items()},
                   f, indent=2, default=str)
    print(f"\n[E-L3B] saved summary.csv + raw_results.json")

    # Final verdict per solver
    print("\n=== REAL-TIME FEASIBILITY VERDICT ===")
    for r in rows:
        verdict = "PASS" if r["wall_p95_s"] <= 60.0 and r["feas_rate"] > 0.95 else "FAIL"
        print(f"  {r['solver']:6s}: wall p95 = {r['wall_p95_s']:.2f}s  feas = {r['feas_rate']:.3f}  -> {verdict}")

if __name__ == "__main__":
    main()
