"""
E-L2 V2 -- Re-run with improved prompt (Option A remediation).
Pre-registration deviation #001 documented.

Changes vs V1:
  - prompt_template_v2 (concrete numeric thresholds, decision tree, 4 worked examples, anti-overcall rules)
  - num_predict 500 -> 800 (mitigate qwen3.5 empty content)
  - cache namespace: llm_cache_v2/ (V1 cache preserved)
  - output files suffixed _v2
  - smoke_only=True flag for 5-case smoke test before full run
"""
import os, sys, json, time, hashlib, math, argparse
from pathlib import Path
import numpy as np
import pandas as pd
from ollama import Client
from sklearn.metrics import cohen_kappa_score, f1_score, precision_score, recall_score, confusion_matrix

sys.path.insert(0, r"D:/AI-LLM/Claude Experiment/Ver13")
from config import OLLAMA_API_KEY

DATA_CSV   = r"D:/AI-LLM/Claude Experiment/Ver13/smart_manufacturing_data.csv"
BOUNDS_JSON = r"D:/AI-LLM/Claude Experiment/Ver13/sensor_bounds_derived.json"
OUT_DIR    = Path(r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-L2_agentic_validation")
CACHE_DIR  = OUT_DIR / "llm_cache_v2"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LLMS = ["glm-5.1:cloud", "kimi-k2.6:cloud", "deepseek-v4-pro:cloud"]   # qwen3.5 dropped per PRE_REG_DEVIATION_002
N_MACHINES = 25
N_WINDOWS  = 5
SEED = 42
NUM_PREDICT = 800
TIERS = ["Critical", "High", "Medium", "Low"]
TIER_TO_INT = {t: i for i, t in enumerate(TIERS)}

COST_MATRIX = np.zeros((4, 4), dtype=float)
for gt in range(4):
    for pred in range(4):
        if gt == pred: COST_MATRIX[gt, pred] = 0.0
        elif gt == 0 and pred == 3: COST_MATRIX[gt, pred] = 100.0
        elif gt == 0: COST_MATRIX[gt, pred] = 10.0
        else: COST_MATRIX[gt, pred] = 1.0

client = Client(host="https://ollama.com",
                headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"})

def composite_gt(row) -> str:
    rul = float(row["predicted_remaining_life"]); af = int(row["anomaly_flag"])
    ft  = str(row["failure_type"]); mr = int(row["maintenance_required"])
    dr  = float(row["downtime_risk"])
    if (rul < 10) or (af == 1 and ft in {"Electrical Fault", "Pressure Drop"}) or (dr >= 0.8):
        return "Critical"
    if (10 <= rul < 50) or (mr == 1 and af == 1):
        return "High"
    if mr == 1 or af == 1:
        return "Medium"
    return "Low"

def build_eval_set():
    with open(BOUNDS_JSON) as f: bounds = json.load(f)
    test_ids = bounds["test_machine_ids"][:N_MACHINES]
    df = pd.read_csv(DATA_CSV)
    rng = np.random.default_rng(SEED)
    cases = []
    for mid in test_ids:
        sub = df[df["machine_id"] == mid].reset_index(drop=True)
        if len(sub) < N_WINDOWS:
            picks = sub.sample(N_WINDOWS, replace=True, random_state=int(rng.integers(0, 2**31-1)))
        else:
            picks = sub.sample(N_WINDOWS, replace=False, random_state=int(rng.integers(0, 2**31-1)))
        for _, r in picks.iterrows():
            cases.append({
                "machine_id": int(mid), "timestamp": str(r["timestamp"]),
                "temperature": float(r["temperature"]), "vibration": float(r["vibration"]),
                "humidity": float(r["humidity"]), "pressure": float(r["pressure"]),
                "energy": float(r["energy_consumption"]), "failure_type": str(r["failure_type"]),
                "rul": float(r["predicted_remaining_life"]), "anomaly_flag": int(r["anomaly_flag"]),
                "downtime_risk": float(r["downtime_risk"]), "maintenance_required": int(r["maintenance_required"]),
                "gt_tier": composite_gt(r),
            })
    return cases, bounds

SYSTEM_V2 = (
    "You are a senior predictive-maintenance engineer. You are conservative: you only "
    "escalate machines when the evidence clearly supports it. You output ONLY a valid "
    "JSON object with no surrounding text."
)

def render_prompt_v2(case):
    return (
        f"Sensor readings for one machine in our 50-machine fleet:\n\n"
        f"  Temperature:        {case['temperature']:.2f} C   (warning >= 82, critical >= 88)\n"
        f"  Vibration:          {case['vibration']:.2f}        (warning >= 55, critical >= 70)\n"
        f"  Humidity:           {case['humidity']:.2f} %       (warning >= 68, critical >= 75)\n"
        f"  Pressure:           {case['pressure']:.2f} bar     (warning >= 4.3, critical >= 4.8)\n"
        f"  Energy Consumption: {case['energy']:.2f} kWh       (warning >= 3.8, critical >= 4.5)\n\n"
        f"Failure-mode signature (from upstream classifier): \"{case['failure_type']}\"\n"
        f"(Possible values: \"Normal\", \"Vibration Issue\", \"Overheating\", \"Pressure Drop\", \"Electrical Fault\")\n\n"
        "Decide ONE of four maintenance priority tiers using this DECISION TREE\n"
        "(evaluate top to bottom, return first match):\n\n"
        "  IF (>=2 sensors past CRITICAL threshold)\n"
        "     OR (>=1 sensor past CRITICAL threshold AND failure_type in {\"Electrical Fault\", \"Pressure Drop\"})\n"
        "     OR (failure_type == \"Electrical Fault\" AND temperature >= 88):\n"
        "       => \"Critical\"\n\n"
        "  ELIF (>=1 sensor past CRITICAL threshold)\n"
        "     OR (>=2 sensors past WARNING threshold AND failure_type != \"Normal\"):\n"
        "       => \"High\"\n\n"
        "  ELIF (>=1 sensor past WARNING threshold)\n"
        "     OR (failure_type != \"Normal\"):\n"
        "       => \"Medium\"\n\n"
        "  ELSE:\n"
        "       => \"Low\"\n\n"
        "Important rules:\n"
        "  - DO NOT escalate to Critical based on a single sensor warning.\n"
        "  - DO NOT escalate to High when failure_type is \"Normal\" and only one sensor is at warning level.\n"
        "  - \"Low\" is the correct answer when no sensor is past warning AND failure_type is \"Normal\".\n"
        "  - When in doubt between two adjacent tiers, choose the LOWER tier (less aggressive).\n\n"
        "WORKED EXAMPLES (study these patterns):\n\n"
        "  Example 1 (Critical):\n"
        "    temp=92.0 (>= critical 88), vib=72.0 (>= critical 70), failure_type=\"Electrical Fault\"\n"
        "    -> 2 critical breaches + electrical -> \"Critical\"\n\n"
        "  Example 2 (High):\n"
        "    temp=85.0 (warning), vib=60.0 (warning), failure_type=\"Vibration Issue\"\n"
        "    -> 2 warnings + non-normal failure -> \"High\"\n\n"
        "  Example 3 (Medium):\n"
        "    temp=85.0 (warning), vib=50.0 (ok), pressure=3.0 (ok), failure_type=\"Normal\"\n"
        "    -> 1 warning + normal failure -> \"Medium\"\n\n"
        "  Example 4 (Low):\n"
        "    temp=75.0 (ok), vib=50.0 (ok), humidity=55.0 (ok), pressure=2.5 (ok), energy=2.0 (ok), failure_type=\"Normal\"\n"
        "    -> all normal, no failure signature -> \"Low\"\n\n"
        "OUTPUT FORMAT — output exactly this JSON object, nothing else:\n\n"
        "{\"tier\": \"Critical|High|Medium|Low\", \"reasoning\": \"<one short sentence citing the rule from decision tree>\", \"confidence\": <float 0.0-1.0>}"
    )

def extract_json(text):
    if not text: return None
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)
        t = t[1] if len(t) > 1 else ""
        if t.lower().startswith("json"): t = t[4:]
        if "```" in t: t = t.split("```")[0]
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < 0 or j < i: return None
    blob = t[i:j+1]
    try: return json.loads(blob)
    except Exception:
        try: return json.loads(blob.replace(",}", "}").replace(",]", "]"))
        except Exception: return None

def normalize_tier(s):
    if not s: return None
    s = str(s).strip().capitalize()
    if s in TIERS: return s
    for t in TIERS:
        if s.lower() == t.lower(): return t
    return None

def cache_key(model, prompt):
    h = hashlib.sha256((model + "\n\n" + prompt).encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{model.replace(':','_').replace('/','_')}__{h[:16]}.json"

def call_llm(model, prompt, max_retries=3):
    cf = cache_key(model, prompt)
    if cf.exists():
        with open(cf) as f: return json.load(f)
    last_err = None
    for attempt in range(max_retries):
        t0 = time.time()
        try:
            r = client.chat(model=model,
                            messages=[{"role":"system","content":SYSTEM_V2},
                                       {"role":"user","content":prompt}],
                            options={"temperature":0, "num_predict":NUM_PREDICT},
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

def ensemble_vote(per_llm_tiers):
    valid = [t for t in per_llm_tiers if t in TIERS]
    if not valid: return None
    from collections import Counter
    counts = Counter(valid)
    max_c = max(counts.values())
    candidates = [t for t, c in counts.items() if c == max_c]
    if len(candidates) == 1: return candidates[0]
    return min(candidates, key=lambda t: TIER_TO_INT[t])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="run only 5 cases for smoke test")
    args = ap.parse_args()

    print(f"[E-L2 V2] building eval set", flush=True)
    cases, bounds = build_eval_set()
    if args.smoke:
        cases = cases[:5]
        print(f"[E-L2 V2 SMOKE] using only {len(cases)} cases", flush=True)
    print(f"[E-L2 V2] total cases: {len(cases)}; querying {len(LLMS)} LLMs = {len(LLMS)*len(cases)} calls")
    print(f"[E-L2 V2] num_predict={NUM_PREDICT}; cache_dir={CACHE_DIR.name}", flush=True)

    results = []
    t_start = time.time()
    for i, case in enumerate(cases):
        prompt = render_prompt_v2(case)
        per_llm = {}
        for model in LLMS:
            r = call_llm(model, prompt)
            parsed = extract_json(r.get("content", ""))
            tier = normalize_tier(parsed.get("tier") if parsed else None)
            per_llm[model] = {"raw": r.get("content","")[:300], "parsed_tier": tier,
                              "elapsed_s": r.get("elapsed_s"), "error": r.get("error")}
        ens = ensemble_vote([per_llm[m]["parsed_tier"] for m in LLMS])
        results.append({**case, "per_llm": per_llm, "ensemble_tier": ens})
        if (i+1) % 10 == 0 or i == len(cases)-1 or args.smoke:
            elapsed = time.time() - t_start
            print(f"  [{i+1}/{len(cases)}] {elapsed:.0f}s elapsed", flush=True)

    # Save
    suffix = "_smoke" if args.smoke else "_v2"
    with open(OUT_DIR / f"raw_results{suffix}.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    # quick parse-rate report (smoke)
    if args.smoke:
        print("\n=== SMOKE TEST PARSE RATES ===")
        for model in LLMS:
            valid = sum(1 for r in results if r["per_llm"][model]["parsed_tier"] in TIERS)
            print(f"  {model:30s}: {valid}/{len(results)} parsed")
            for r in results:
                t = r["per_llm"][model]
                preview = t["raw"][:80].replace("\n"," ")
                print(f"    M-{r['machine_id']:3d} GT={r['gt_tier']:8s} parsed={t['parsed_tier']!s:8s} latency={t['elapsed_s']:.1f}s raw={preview!r}")
        return

    # Full metrics (only when not smoke)
    print("\n[E-L2 V2] computing metrics ...", flush=True)
    gt_arr = np.array([TIER_TO_INT[c["gt_tier"]] for c in results])
    ens_arr = np.array([TIER_TO_INT.get(c["ensemble_tier"], -1) for c in results])
    valid_mask = ens_arr >= 0
    n_valid = int(valid_mask.sum())
    print(f"  valid ensemble: {n_valid}/{len(results)} ({100*n_valid/len(results):.1f}%)")
    gt_v, en_v = gt_arr[valid_mask], ens_arr[valid_mask]

    qw_kappa = cohen_kappa_score(gt_v, en_v, weights="quadratic", labels=[0,1,2,3])
    rng = np.random.default_rng(SEED)
    boot = []
    for _ in range(1000):
        idx = rng.integers(0, n_valid, n_valid)
        try: boot.append(cohen_kappa_score(gt_v[idx], en_v[idx], weights="quadratic", labels=[0,1,2,3]))
        except Exception: pass
    boot = np.array(boot)
    ci_lo, ci_hi = np.quantile(boot, [0.025, 0.975])
    print(f"  Quadratic-Weighted Kappa = {qw_kappa:.4f}  (95% CI [{ci_lo:.4f}, {ci_hi:.4f}])")

    K = int(math.ceil(0.2 * n_valid))
    truly_ch = (gt_v <= 1).astype(int)
    order = np.argsort(en_v, kind="stable")[:K]
    top_k_truly = int(truly_ch[order].sum())
    top_k_cov = top_k_truly / max(K, 1)
    print(f"  Top-K @ K={K}: {top_k_truly}/{K} = {100*top_k_cov:.1f}% truly Critical+High")

    cm = confusion_matrix(gt_v, en_v, labels=[0,1,2,3])
    total_cost = float((cm * COST_MATRIX).sum()); mean_cost = total_cost / n_valid
    print(f"  Cost-weighted: total={total_cost:.0f}, mean={mean_cost:.3f}")

    macro_f1 = float(f1_score(gt_v, en_v, labels=[0,1,2,3], average="macro", zero_division=0))
    print(f"  Macro F1: {macro_f1:.4f}")
    per_p = precision_score(gt_v, en_v, labels=[0,1,2,3], average=None, zero_division=0)
    per_r = recall_score(gt_v, en_v, labels=[0,1,2,3], average=None, zero_division=0)
    per_f1 = f1_score(gt_v, en_v, labels=[0,1,2,3], average=None, zero_division=0)
    for ti, t in enumerate(TIERS):
        print(f"    {t:8s}  P={per_p[ti]:.3f}  R={per_r[ti]:.3f}  F1={per_f1[ti]:.3f}")

    truly_crit = gt_v == 0
    n_crit = int(truly_crit.sum())
    cov = float(((en_v == 0) | (en_v == 1))[truly_crit].sum() / max(n_crit, 1))
    print(f"  Critical coverage: {cov:.3f}")

    all_lat = [r["per_llm"][m]["elapsed_s"] for r in results for m in LLMS if r["per_llm"][m].get("elapsed_s")]
    e2e = []
    for r in results:
        ls = [r["per_llm"][m]["elapsed_s"] for m in LLMS if r["per_llm"][m].get("elapsed_s")]
        if ls: e2e.append(max(ls))
    print(f"  Latency per-LLM:    median={np.median(all_lat):.2f}s p95={np.quantile(all_lat,0.95):.2f}s")
    print(f"  Ensemble e2e (max): median={np.median(e2e):.2f}s p95={np.quantile(e2e,0.95):.2f}s")

    print("\n[E-L2 V2] per-LLM ablation:")
    per_llm_metrics = {}
    for model in LLMS:
        ll = np.array([TIER_TO_INT.get(r["per_llm"][model]["parsed_tier"], -1) for r in results])
        v = ll >= 0
        if v.sum() < 10:
            print(f"  {model:30s}: too few ({int(v.sum())})")
            continue
        kp = cohen_kappa_score(gt_arr[v], ll[v], weights="quadratic", labels=[0,1,2,3])
        mf1 = f1_score(gt_arr[v], ll[v], labels=[0,1,2,3], average="macro", zero_division=0)
        print(f"  {model:30s}: valid={int(v.sum())}/{len(results)}  QWK={kp:.4f}  macroF1={mf1:.4f}")
        per_llm_metrics[model] = {"valid_n": int(v.sum()), "qw_kappa": float(kp), "macro_f1": float(mf1)}

    metrics = {
        "experiment": "E-L2 V2",
        "deviation_doc": "PRE_REG_DEVIATION_001.md",
        "date": "2026-05-04",
        "seed": SEED, "num_predict": NUM_PREDICT,
        "n_cases": len(results), "n_valid": n_valid,
        "primary": {"metric": "Cohen Quadratic-Weighted Kappa (4-tier ordinal)",
                    "value": float(qw_kappa),
                    "ci_95_lower": float(ci_lo), "ci_95_upper": float(ci_hi),
                    "threshold_for_proceed": 0.6,
                    "verdict": "PROCEED to E-L3A" if qw_kappa >= 0.6 else "STOP"},
        "secondary": {"top_k_coverage": {"K": int(K), "rate": float(top_k_cov)},
                      "cost_weighted_misclass": {"total": total_cost, "mean": mean_cost},
                      "macro_f1": macro_f1,
                      "per_tier": {TIERS[i]: {"P": float(per_p[i]), "R": float(per_r[i]), "F1": float(per_f1[i])} for i in range(4)},
                      "coverage_critical": float(cov),
                      "latency": {"per_llm_median_s": float(np.median(all_lat)), "per_llm_p95_s": float(np.quantile(all_lat,0.95)),
                                  "ensemble_e2e_median_s": float(np.median(e2e)), "ensemble_e2e_p95_s": float(np.quantile(e2e,0.95))}},
        "per_llm_ablation": per_llm_metrics,
        "confusion_matrix": cm.tolist(),
        "tier_index_order": TIERS,
    }
    with open(OUT_DIR / "metrics_v2.json", "w") as f: json.dump(metrics, f, indent=2)

    rows = []
    for r in results:
        rows.append({"machine_id": r["machine_id"], "timestamp": r["timestamp"],
                     "gt_tier": r["gt_tier"], "ensemble_tier": r["ensemble_tier"],
                     **{f"llm_{m}": r["per_llm"][m]["parsed_tier"] for m in LLMS},
                     **{f"lat_{m}": r["per_llm"][m]["elapsed_s"] for m in LLMS}})
    pd.DataFrame(rows).to_csv(OUT_DIR / "per_case_predictions_v2.csv", index=False)
    print(f"\n[E-L2 V2] saved metrics_v2.json + raw_results_v2.json + per_case_predictions_v2.csv")
    print(f"\n=== VERDICT V2: QWK = {qw_kappa:.4f}  threshold=0.6  -> {'PROCEED to E-L3A' if qw_kappa >= 0.6 else 'STOP - do not proceed'} ===")

if __name__ == "__main__":
    main()
