"""
E-L2 -- Agentic AI Multi-Tier Detection Validation
==================================================

Pre-registered protocol -- see PHASE1_PROTOCOL_V2_ALIGNED_3LAYER.md  3.

Sample design:
  - 25 test machines (odd machine_id) x 5 windows = 125 evaluation cases
  - Each case scored independently by 4 LLMs:
      glm-5.1:cloud, qwen3.5:cloud, kimi-k2.6:cloud, deepseek-v4-pro:cloud
  - Ensemble = majority-vote per machine tier (tie -> highest tier wins)

Composite GT formula (Lei 2018 + ISO 13374-2):
  Critical: RUL<10  OR  (anomaly_flag=1 AND failure_type in {Electrical Fault, Pressure Drop})  OR  downtime_risk>=0.8
  High:     RUL in [10,50)  OR  (maintenance_required=1 AND anomaly_flag=1)
  Medium:   maintenance_required=1  OR  anomaly_flag=1
  Low:      otherwise

Metrics:
  primary   = Cohen's Quadratic-Weighted Kappa (with bootstrap 95% CI)
  secondary = Top-K Coverage @ K=ceil(0.2*N), Cost-weighted misclass (missed Critical=100x), per-tier F1/P/R, end-to-end latency
"""
import os, sys, json, time, hashlib, math
from pathlib import Path
import numpy as np
import pandas as pd
from ollama import Client
from sklearn.metrics import cohen_kappa_score, f1_score, precision_score, recall_score, confusion_matrix

sys.path.insert(0, r"D:/AI-LLM/Claude Experiment/Ver13")
from config import OLLAMA_API_KEY

# -----------------------------------------------------------------------------
# Configuration (frozen pre-registration)
# -----------------------------------------------------------------------------
DATA_CSV   = r"D:/AI-LLM/Claude Experiment/Ver13/smart_manufacturing_data.csv"
BOUNDS_JSON = r"D:/AI-LLM/Claude Experiment/Ver13/sensor_bounds_derived.json"
OUT_DIR    = Path(r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-L2_agentic_validation")
CACHE_DIR  = OUT_DIR / "llm_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LLMS = ["glm-5.1:cloud", "qwen3.5:cloud", "kimi-k2.6:cloud", "deepseek-v4-pro:cloud"]
N_MACHINES = 25       # all odd machine_id (test split)
N_WINDOWS  = 5        # per machine
SEED = 42
TIERS = ["Critical", "High", "Medium", "Low"]
TIER_TO_INT = {t: i for i, t in enumerate(TIERS)}     # 0=Crit, 3=Low
INT_TO_TIER = {i: t for t, i in TIER_TO_INT.items()}

# Cost matrix for cost-weighted misclassification (rows=GT, cols=Pred)
# GT Critical missed (predicted Low) = 100; everything else = 1; correct = 0
COST_MATRIX = np.zeros((4, 4), dtype=float)
for gt in range(4):
    for pred in range(4):
        if gt == pred: COST_MATRIX[gt, pred] = 0.0
        elif gt == 0 and pred == 3: COST_MATRIX[gt, pred] = 100.0  # missed critical
        elif gt == 0: COST_MATRIX[gt, pred] = 10.0                  # critical -> high/med
        else: COST_MATRIX[gt, pred] = 1.0                            # other errors

client = Client(host="https://ollama.com",
                headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"})

# -----------------------------------------------------------------------------
# Composite GT (frozen formula)
# -----------------------------------------------------------------------------
def composite_gt(row) -> str:
    rul = float(row["predicted_remaining_life"])
    af  = int(row["anomaly_flag"])
    ft  = str(row["failure_type"])
    mr  = int(row["maintenance_required"])
    dr  = float(row["downtime_risk"])
    if (rul < 10) or (af == 1 and ft in {"Electrical Fault", "Pressure Drop"}) or (dr >= 0.8):
        return "Critical"
    if (10 <= rul < 50) or (mr == 1 and af == 1):
        return "High"
    if mr == 1 or af == 1:
        return "Medium"
    return "Low"

# -----------------------------------------------------------------------------
# Sample design (deterministic per SEED)
# -----------------------------------------------------------------------------
def build_eval_set():
    with open(BOUNDS_JSON) as f:
        bounds = json.load(f)
    test_ids = bounds["test_machine_ids"][:N_MACHINES]   # 25 odd-id machines
    df = pd.read_csv(DATA_CSV)
    rng = np.random.default_rng(SEED)
    cases = []
    for mid in test_ids:
        sub = df[df["machine_id"] == mid].reset_index(drop=True)
        if len(sub) < N_WINDOWS:
            print(f"WARN: machine {mid} has only {len(sub)} rows, sampling with replacement")
            picks = sub.sample(N_WINDOWS, replace=True, random_state=int(rng.integers(0, 2**31-1)))
        else:
            picks = sub.sample(N_WINDOWS, replace=False, random_state=int(rng.integers(0, 2**31-1)))
        for _, r in picks.iterrows():
            cases.append({
                "machine_id": int(mid),
                "timestamp":  str(r["timestamp"]),
                "temperature": float(r["temperature"]),
                "vibration":   float(r["vibration"]),
                "humidity":    float(r["humidity"]),
                "pressure":    float(r["pressure"]),
                "energy":      float(r["energy_consumption"]),
                "failure_type": str(r["failure_type"]),
                "rul":          float(r["predicted_remaining_life"]),
                "anomaly_flag": int(r["anomaly_flag"]),
                "downtime_risk": float(r["downtime_risk"]),
                "maintenance_required": int(r["maintenance_required"]),
                "gt_tier": composite_gt(r),
            })
    return cases, bounds

# -----------------------------------------------------------------------------
# Prompt rendering
# -----------------------------------------------------------------------------
SYSTEM = (
    "You are an experienced predictive-maintenance engineer at a smart manufacturing "
    "facility. You assess machine health from sensor readings and assign a maintenance "
    "priority tier. You output ONLY a valid JSON object with no surrounding text."
)

def render_prompt(case, bounds):
    def b(s, k): return f"{bounds[s][k]:.2f}"
    return (
        f"A machine in our 50-machine fleet is currently producing the following sensor readings:\n\n"
        f"  - Temperature:        {case['temperature']:.2f} C\n"
        f"  - Vibration:          {case['vibration']:.2f}\n"
        f"  - Humidity:           {case['humidity']:.2f} %\n"
        f"  - Pressure:           {case['pressure']:.2f} bar\n"
        f"  - Energy Consumption: {case['energy']:.2f} kWh\n\n"
        f"Operating bounds derived from training-machine fleet (training-only, no test leakage):\n"
        f"  - Temperature: warning at 82.0 C, critical at 88.0 C (training p90/p99 = {b('temperature','p90')}/{b('temperature','p99')})\n"
        f"  - Vibration:   warning at 55.0,    critical at 70.0    (training p90/p99 = {b('vibration','p90')}/{b('vibration','p99')})\n"
        f"  - Humidity:    warning at 68.0 %,  critical at 75.0 %  (training p90/p99 = {b('humidity','p90')}/{b('humidity','p99')})\n"
        f"  - Pressure:    warning at 4.3 bar, critical at 4.8 bar (training p90/p99 = {b('pressure','p90')}/{b('pressure','p99')})\n"
        f"  - Energy:      warning at 3.8 kWh, critical at 4.5 kWh (training p90/p99 = {b('energy_consumption','p90')}/{b('energy_consumption','p99')})\n\n"
        f"The machine identifies as exhibiting failure-mode signature: \"{case['failure_type']}\".\n\n"
        f"Your task: assign exactly ONE of four maintenance priority tiers, defined as:\n\n"
        f'  - "Critical": machine is at imminent failure risk, requires intervention within hours;\n'
        f"                indicators include severe sensor breach (multiple critical thresholds),\n"
        f"                hard-failure-pattern signature, or imminent end-of-life trajectory.\n"
        f'  - "High":     machine shows elevated risk, requires inspection within the next workday;\n'
        f"                indicators include warning-level sensor breach AND failure-mode signature,\n"
        f"                OR moderate end-of-life trajectory.\n"
        f'  - "Medium":   machine warrants scheduled maintenance within the work week;\n'
        f"                indicators include single warning-level sensor breach, OR known\n"
        f"                degradation pattern without acute breach.\n"
        f'  - "Low":      machine is operating within acceptable bounds, routine monitoring suffices.\n\n'
        f"Output your assessment as a single JSON object with exactly these three fields:\n"
        f'  "tier"       : one of "Critical" | "High" | "Medium" | "Low"\n'
        f'  "reasoning"  : a single-sentence justification anchored in the sensor readings and failure signature\n'
        f'  "confidence" : a float in [0.0, 1.0] reflecting your subjective certainty\n\n'
        f"Do not include any other text, markdown formatting, or explanations outside the JSON object."
    )

# -----------------------------------------------------------------------------
# JSON extraction (robust to ```json fences + leading/trailing junk)
# -----------------------------------------------------------------------------
def extract_json(text):
    if not text: return None
    t = text.strip()
    # strip ```json ... ``` fence
    if t.startswith("```"):
        t = t.split("```", 2)
        t = t[1] if len(t) > 1 else ""
        if t.lower().startswith("json"): t = t[4:]
        if "```" in t: t = t.split("```")[0]
    # find first { and last }
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < 0 or j < i: return None
    blob = t[i:j+1]
    try:
        return json.loads(blob)
    except Exception:
        # try to clean common issues (trailing comma)
        blob2 = blob.replace(",}", "}").replace(",]", "]")
        try: return json.loads(blob2)
        except Exception: return None

def normalize_tier(s):
    if not s: return None
    s = str(s).strip().capitalize()
    if s in TIERS: return s
    # fuzzy
    for t in TIERS:
        if s.lower() == t.lower(): return t
    return None

# -----------------------------------------------------------------------------
# LLM call with disk cache + retry
# -----------------------------------------------------------------------------
def cache_key(model, prompt):
    h = hashlib.sha256((model + "\n\n" + prompt).encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{model.replace(':','_').replace('/','_')}__{h[:16]}.json"

def call_llm(model, prompt, max_retries=3):
    cf = cache_key(model, prompt)
    if cf.exists():
        with open(cf) as f:
            return json.load(f)
    last_err = None
    for attempt in range(max_retries):
        t0 = time.time()
        try:
            r = client.chat(model=model,
                            messages=[{"role":"system","content":SYSTEM},
                                       {"role":"user",  "content":prompt}],
                            options={"temperature":0, "num_predict":500},
                            think=False)
            elapsed = time.time() - t0
            content = r["message"].get("content", "")
            data = {"model": model, "content": content, "elapsed_s": elapsed,
                    "attempt": attempt+1, "ts": time.time()}
            with open(cf, "w") as f: json.dump(data, f)
            return data
        except Exception as e:
            last_err = str(e)[:300]
            if "503" in last_err or "overloaded" in last_err:
                time.sleep(3 + attempt*2); continue
            break
    return {"model": model, "content": "", "error": last_err, "elapsed_s": time.time()-t0,
            "attempt": max_retries+1, "ts": time.time()}

# -----------------------------------------------------------------------------
# Ensemble aggregation: majority vote, tie-break = highest tier (lowest int)
# -----------------------------------------------------------------------------
def ensemble_vote(per_llm_tiers):
    """per_llm_tiers: list of tier strings (or None for unparseable). Returns ensemble tier or None if all None."""
    valid = [t for t in per_llm_tiers if t in TIERS]
    if not valid:
        return None
    # count
    from collections import Counter
    counts = Counter(valid)
    max_c = max(counts.values())
    candidates = [t for t, c in counts.items() if c == max_c]
    if len(candidates) == 1:
        return candidates[0]
    # tie -> highest priority (lowest int)
    return min(candidates, key=lambda t: TIER_TO_INT[t])

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    print(f"[E-L2] building eval set: {N_MACHINES} machines x {N_WINDOWS} windows", flush=True)
    cases, bounds = build_eval_set()
    print(f"[E-L2] total cases: {len(cases)}; GT distribution:")
    gt_dist = pd.Series([c["gt_tier"] for c in cases]).value_counts()
    for t in TIERS:
        print(f"  {t:8s}: {int(gt_dist.get(t,0))}")

    print(f"[E-L2] querying {len(LLMS)} LLMs x {len(cases)} cases = {len(LLMS)*len(cases)} calls", flush=True)
    results = []
    t_start = time.time()
    for i, case in enumerate(cases):
        prompt = render_prompt(case, bounds)
        per_llm = {}
        for model in LLMS:
            r = call_llm(model, prompt)
            parsed = extract_json(r.get("content", ""))
            tier = normalize_tier(parsed.get("tier") if parsed else None)
            per_llm[model] = {"raw": r.get("content","")[:300], "parsed_tier": tier,
                              "elapsed_s": r.get("elapsed_s"), "error": r.get("error")}
        ens = ensemble_vote([per_llm[m]["parsed_tier"] for m in LLMS])
        results.append({**case, "per_llm": per_llm, "ensemble_tier": ens})
        if (i+1) % 10 == 0 or i == len(cases)-1:
            elapsed = time.time() - t_start
            rate = (i+1) / elapsed
            eta = (len(cases) - (i+1)) / max(rate, 1e-6)
            print(f"  [{i+1}/{len(cases)}] {elapsed:.0f}s elapsed, ETA {eta:.0f}s", flush=True)

    # Save raw results
    with open(OUT_DIR / "raw_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Compute metrics
    print("\n[E-L2] computing metrics ...", flush=True)
    gt_arr = np.array([TIER_TO_INT[c["gt_tier"]] for c in results])
    ens_arr = np.array([TIER_TO_INT.get(c["ensemble_tier"], -1) for c in results])

    valid_mask = ens_arr >= 0
    n_valid = int(valid_mask.sum())
    print(f"  valid ensemble predictions: {n_valid}/{len(results)} ({100*n_valid/len(results):.1f}%)")
    if n_valid < 10:
        print("ERROR: too few valid predictions to compute metrics; aborting")
        return

    gt_v = gt_arr[valid_mask]
    en_v = ens_arr[valid_mask]

    # Quadratic-weighted Kappa (primary)
    qw_kappa = cohen_kappa_score(gt_v, en_v, weights="quadratic", labels=[0,1,2,3])
    # bootstrap CI
    rng = np.random.default_rng(SEED)
    boot = []
    for _ in range(1000):
        idx = rng.integers(0, n_valid, n_valid)
        try: boot.append(cohen_kappa_score(gt_v[idx], en_v[idx], weights="quadratic", labels=[0,1,2,3]))
        except Exception: pass
    boot = np.array(boot); ci_lo, ci_hi = np.quantile(boot, [0.025, 0.975])
    print(f"  Quadratic-Weighted Kappa = {qw_kappa:.4f}  (95% CI [{ci_lo:.4f}, {ci_hi:.4f}], boot N={len(boot)})")

    # Top-K coverage (K = ceil(0.2*N))
    K = int(math.ceil(0.2 * n_valid))
    truly_critical_high = (gt_v <= 1).astype(int)
    pred_priority = en_v.copy()  # lower = higher priority
    # rank cases by predicted priority asc; take top K; check how many truly Critical/High
    order = np.argsort(pred_priority, kind="stable")
    top_k_idx = order[:K]
    top_k_truly_crit = int(truly_critical_high[top_k_idx].sum())
    top_k_coverage = top_k_truly_crit / max(K, 1)
    print(f"  Top-K Coverage @ K={K}: {top_k_truly_crit}/{K} = {100*top_k_coverage:.1f}% truly Critical+High")

    # Cost-weighted misclassification
    cm = confusion_matrix(gt_v, en_v, labels=[0,1,2,3])
    total_cost = float((cm * COST_MATRIX).sum())
    mean_cost = total_cost / n_valid
    print(f"  Cost-weighted misclassification: total={total_cost:.0f}, mean per case={mean_cost:.3f}")

    # Per-tier F1/P/R + macro
    per_tier_f1 = f1_score(gt_v, en_v, labels=[0,1,2,3], average=None, zero_division=0)
    per_tier_p  = precision_score(gt_v, en_v, labels=[0,1,2,3], average=None, zero_division=0)
    per_tier_r  = recall_score(gt_v, en_v, labels=[0,1,2,3], average=None, zero_division=0)
    macro_f1 = float(f1_score(gt_v, en_v, labels=[0,1,2,3], average="macro", zero_division=0))
    print(f"  Macro F1: {macro_f1:.4f}")
    for ti, t in enumerate(TIERS):
        print(f"    tier={t:8s}  P={per_tier_p[ti]:.3f}  R={per_tier_r[ti]:.3f}  F1={per_tier_f1[ti]:.3f}")

    # Coverage rate (truly Critical flagged Critical or High)
    truly_crit_mask = gt_v == 0
    n_truly_crit = int(truly_crit_mask.sum())
    if n_truly_crit > 0:
        flagged_high = int(((en_v == 0) | (en_v == 1))[truly_crit_mask].sum())
        coverage_rate = flagged_high / n_truly_crit
    else:
        coverage_rate = float("nan")
    print(f"  Coverage rate (truly Critical flagged Critical|High): {coverage_rate:.3f}")

    # Latency
    all_lat = [r["per_llm"][m]["elapsed_s"] for r in results for m in LLMS if r["per_llm"][m].get("elapsed_s")]
    e2e_per_case = []
    for r in results:
        ls = [r["per_llm"][m]["elapsed_s"] for m in LLMS if r["per_llm"][m].get("elapsed_s")]
        if ls: e2e_per_case.append(max(ls))   # ensemble latency = slowest LLM
    print(f"  Per-LLM latency:    median={np.median(all_lat):.2f}s  p95={np.quantile(all_lat,0.95):.2f}s")
    print(f"  Ensemble e2e (max): median={np.median(e2e_per_case):.2f}s  p95={np.quantile(e2e_per_case,0.95):.2f}s")

    # Per-LLM ablation (informational)
    print("\n[E-L2] per-LLM ablation (informational, not the primary claim):")
    per_llm_metrics = {}
    for model in LLMS:
        ll_arr = np.array([TIER_TO_INT.get(r["per_llm"][model]["parsed_tier"], -1) for r in results])
        valid = ll_arr >= 0
        if valid.sum() < 10:
            print(f"  {model:30s}: too few valid ({int(valid.sum())}); skip")
            continue
        kp = cohen_kappa_score(gt_arr[valid], ll_arr[valid], weights="quadratic", labels=[0,1,2,3])
        mf1 = f1_score(gt_arr[valid], ll_arr[valid], labels=[0,1,2,3], average="macro", zero_division=0)
        print(f"  {model:30s}: valid={int(valid.sum())}/{len(results)}  QWK={kp:.4f}  macroF1={mf1:.4f}")
        per_llm_metrics[model] = {"valid_n": int(valid.sum()), "qw_kappa": float(kp), "macro_f1": float(mf1)}

    # Save metrics
    metrics = {
        "experiment": "E-L2",
        "date": "2026-05-04",
        "seed": SEED,
        "n_cases": len(results),
        "n_valid": n_valid,
        "gt_distribution": {t: int(gt_dist.get(t,0)) for t in TIERS},
        "primary": {
            "metric": "Cohen Quadratic-Weighted Kappa (4-tier ordinal)",
            "value": float(qw_kappa),
            "ci_95_lower": float(ci_lo),
            "ci_95_upper": float(ci_hi),
            "bootstrap_n": int(len(boot)),
            "threshold_for_proceed": 0.6,
            "verdict": "PROCEED to E-L3A" if qw_kappa >= 0.6 else "STOP",
        },
        "secondary": {
            "top_k_coverage": {"K": int(K), "top_k_truly_critical_high": top_k_truly_crit, "rate": float(top_k_coverage)},
            "cost_weighted_misclass": {"total": total_cost, "mean_per_case": mean_cost,
                                        "cost_matrix_label": "missed_critical=100, critical_other=10, other=1"},
            "macro_f1": macro_f1,
            "per_tier": {TIERS[i]: {"precision": float(per_tier_p[i]), "recall": float(per_tier_r[i]), "f1": float(per_tier_f1[i])} for i in range(4)},
            "coverage_critical_flagged": float(coverage_rate),
            "latency": {
                "per_llm_median_s": float(np.median(all_lat)),
                "per_llm_p95_s":    float(np.quantile(all_lat, 0.95)),
                "ensemble_e2e_median_s": float(np.median(e2e_per_case)),
                "ensemble_e2e_p95_s":    float(np.quantile(e2e_per_case, 0.95)),
            },
        },
        "per_llm_ablation": per_llm_metrics,
        "confusion_matrix": cm.tolist(),
        "tier_index_order": TIERS,
    }
    with open(OUT_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # Save case-level CSV
    rows = []
    for r in results:
        rows.append({
            "machine_id": r["machine_id"], "timestamp": r["timestamp"],
            "gt_tier": r["gt_tier"], "ensemble_tier": r["ensemble_tier"],
            **{f"llm_{m}": r["per_llm"][m]["parsed_tier"] for m in LLMS},
            **{f"lat_{m}": r["per_llm"][m]["elapsed_s"] for m in LLMS},
        })
    pd.DataFrame(rows).to_csv(OUT_DIR / "per_case_predictions.csv", index=False)

    print(f"\n[E-L2] saved: metrics.json, raw_results.json, per_case_predictions.csv")
    print(f"\n=== VERDICT: QWK = {qw_kappa:.4f}, threshold = 0.6 -> {'PROCEED to E-L3A' if qw_kappa >= 0.6 else 'STOP - do not proceed'} ===")

if __name__ == "__main__":
    main()
