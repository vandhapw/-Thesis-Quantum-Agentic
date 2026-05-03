"""
E-L2 V3 -- Realistic Deployment Input Set (Option 1 remediation)
Pre-registration deviation #003: prompt extended to include ALL upstream pipeline
outputs (RUL, anomaly_flag, downtime_risk, maintenance_required) in addition to
sensor readings + failure_type. GT formula remains undisclosed.
"""
import os, sys, json, time, hashlib, math, argparse
from pathlib import Path
import numpy as np
import pandas as pd
from ollama import Client
from sklearn.metrics import cohen_kappa_score, f1_score, precision_score, recall_score, confusion_matrix

sys.path.insert(0, r"D:/AI-LLM/Claude Experiment/Ver13")
from config import OLLAMA_API_KEY

DATA_CSV    = r"D:/AI-LLM/Claude Experiment/Ver13/smart_manufacturing_data.csv"
BOUNDS_JSON = r"D:/AI-LLM/Claude Experiment/Ver13/sensor_bounds_derived.json"
OUT_DIR     = Path(r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-L2_agentic_validation")
CACHE_DIR   = OUT_DIR / "llm_cache_v3"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LLMS = ["glm-5.1:cloud", "kimi-k2.6:cloud", "deepseek-v4-pro:cloud"]   # 3-LLM per dev #002
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

SYSTEM_V3 = (
    "You are a senior predictive-maintenance engineer at a smart manufacturing facility. "
    "You receive aggregated input from the upstream sensor stream, T-GCN forecaster, and "
    "supervised classifier, and you assign a maintenance priority tier based on combined "
    "evidence. You output ONLY a valid JSON object with no surrounding text."
)

def render_prompt_v3(case):
    return (
        "You are evaluating one machine in our 50-machine fleet. The upstream pipeline\n"
        "has produced the following aggregated evidence about this machine's current state:\n\n"
        "  ───── Sensor readings ─────\n"
        f"  Temperature:        {case['temperature']:.2f} C   (warning >= 82, critical >= 88)\n"
        f"  Vibration:          {case['vibration']:.2f}        (warning >= 55, critical >= 70)\n"
        f"  Humidity:           {case['humidity']:.2f} %       (warning >= 68, critical >= 75)\n"
        f"  Pressure:           {case['pressure']:.2f} bar     (warning >= 4.3, critical >= 4.8)\n"
        f"  Energy Consumption: {case['energy']:.2f} kWh       (warning >= 3.8, critical >= 4.5)\n\n"
        "  ───── Upstream classifier output ─────\n"
        f"  Failure-mode signature:           \"{case['failure_type']}\"\n"
        "                                    (one of: Normal, Vibration Issue, Overheating,\n"
        "                                     Pressure Drop, Electrical Fault)\n"
        f"  Anomaly flag:                     {case['anomaly_flag']}            (0 = normal, 1 = anomalous)\n"
        f"  Downtime risk score:              {case['downtime_risk']:.2f}        (0.0 = no risk, 1.0 = certain downtime)\n"
        f"  Maintenance recommendation flag:  {case['maintenance_required']}    (0 = not flagged, 1 = flagged)\n"
        f"  Predicted Remaining Useful Life:  {case['rul']:.0f} hours           (estimated time to failure)\n\n"
        "Your task: assign exactly ONE of four maintenance priority tiers based on integrated\n"
        "reasoning over ALL the evidence above:\n\n"
        "  - \"Critical\": machine is at imminent failure risk, requires intervention within hours.\n"
        "                Strong indicators include very low predicted remaining life, high downtime\n"
        "                risk score, anomalous state combined with severe failure types (Electrical\n"
        "                Fault, Pressure Drop), or multiple sensors past critical thresholds.\n\n"
        "  - \"High\":     machine shows elevated risk requiring inspection within the next workday.\n"
        "                Indicators include moderately low remaining life, anomaly flagged together\n"
        "                with maintenance recommendation, or warning-level breaches combined with\n"
        "                non-Normal failure signature.\n\n"
        "  - \"Medium\":   machine warrants scheduled maintenance within the work week.\n"
        "                Indicators include either anomaly flag OR maintenance flag present, single\n"
        "                warning-level sensor breach, or mild degradation pattern.\n\n"
        "  - \"Low\":      machine is operating within acceptable bounds, routine monitoring suffices.\n"
        "                All indicators normal: anomaly flag = 0, maintenance flag = 0, no sensors\n"
        "                past warning, RUL well above critical-life threshold.\n\n"
        "Reasoning guidance:\n"
        "  - INTEGRATE all evidence sources. Do not rely on a single field.\n"
        "  - The classifier outputs (anomaly_flag, downtime_risk, maintenance_required) are\n"
        "    high-quality signals — give them appropriate weight alongside RUL and sensor breaches.\n"
        "  - When evidence is mixed (e.g., anomaly flag = 1 but RUL is high and sensors normal),\n"
        "    use your judgment to choose the tier that best balances safety with actionability.\n"
        "  - Be conservative on Critical — escalate only when multiple strong indicators converge.\n"
        "  - Default to lower tier when in doubt.\n\n"
        "OUTPUT FORMAT — output exactly this JSON object, nothing else:\n\n"
        "{\"tier\": \"Critical|High|Medium|Low\", \"reasoning\": \"<one short sentence integrating the key evidence>\", \"confidence\": <float 0.0-1.0>}"
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
                            messages=[{"role":"system","content":SYSTEM_V3},
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
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    print("[E-L2 V3] building eval set", flush=True)
    cases, bounds = build_eval_set()
    if args.smoke: cases = cases[:5]
    print(f"[E-L2 V3] total cases: {len(cases)}; querying {len(LLMS)} LLMs = {len(LLMS)*len(cases)} calls")
    print(f"[E-L2 V3] num_predict={NUM_PREDICT}; cache_dir={CACHE_DIR.name}", flush=True)

    results = []
    t_start = time.time()
    for i, case in enumerate(cases):
        prompt = render_prompt_v3(case)
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

    suffix = "_smoke" if args.smoke else "_v3"
    with open(OUT_DIR / f"raw_results{suffix}.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    if args.smoke:
        print("\n=== SMOKE PARSE RATES ===")
        for model in LLMS:
            valid = sum(1 for r in results if r["per_llm"][model]["parsed_tier"] in TIERS)
            print(f"  {model:30s}: {valid}/{len(results)}")
            for r in results:
                t = r["per_llm"][model]
                preview = t["raw"][:100].replace("\n"," ")
                print(f"    M-{r['machine_id']:3d} GT={r['gt_tier']:8s} parsed={t['parsed_tier']!s:8s} lat={t['elapsed_s']:.1f}s raw={preview!r}")
        return

    # Full metrics
    print("\n[E-L2 V3] computing metrics ...", flush=True)
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

    truly_crit = gt_v == 0; n_crit = int(truly_crit.sum())
    cov = float(((en_v == 0) | (en_v == 1))[truly_crit].sum() / max(n_crit, 1))
    print(f"  Critical coverage: {cov:.3f}")

    all_lat = [r["per_llm"][m]["elapsed_s"] for r in results for m in LLMS if r["per_llm"][m].get("elapsed_s")]
    e2e = []
    for r in results:
        ls = [r["per_llm"][m]["elapsed_s"] for m in LLMS if r["per_llm"][m].get("elapsed_s")]
        if ls: e2e.append(max(ls))
    print(f"  Latency per-LLM:    median={np.median(all_lat):.2f}s p95={np.quantile(all_lat,0.95):.2f}s")
    print(f"  Ensemble e2e (max): median={np.median(e2e):.2f}s p95={np.quantile(e2e,0.95):.2f}s")

    print("\n[E-L2 V3] per-LLM ablation:")
    per_llm_metrics = {}
    for model in LLMS:
        ll = np.array([TIER_TO_INT.get(r["per_llm"][model]["parsed_tier"], -1) for r in results])
        v = ll >= 0
        if v.sum() < 10: continue
        kp = cohen_kappa_score(gt_arr[v], ll[v], weights="quadratic", labels=[0,1,2,3])
        mf1 = f1_score(gt_arr[v], ll[v], labels=[0,1,2,3], average="macro", zero_division=0)
        print(f"  {model:30s}: valid={int(v.sum())}/{len(results)}  QWK={kp:.4f}  macroF1={mf1:.4f}")
        per_llm_metrics[model] = {"valid_n": int(v.sum()), "qw_kappa": float(kp), "macro_f1": float(mf1)}

    metrics = {
        "experiment": "E-L2 V3",
        "deviation_doc": "PRE_REG_DEVIATION_003.md",
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
    with open(OUT_DIR / "metrics_v3.json", "w") as f: json.dump(metrics, f, indent=2)

    rows = []
    for r in results:
        rows.append({"machine_id": r["machine_id"], "timestamp": r["timestamp"],
                     "gt_tier": r["gt_tier"], "ensemble_tier": r["ensemble_tier"],
                     **{f"llm_{m}": r["per_llm"][m]["parsed_tier"] for m in LLMS},
                     **{f"lat_{m}": r["per_llm"][m]["elapsed_s"] for m in LLMS}})
    pd.DataFrame(rows).to_csv(OUT_DIR / "per_case_predictions_v3.csv", index=False)
    print(f"\n[E-L2 V3] saved metrics_v3.json + raw_results_v3.json + per_case_predictions_v3.csv")
    print(f"\n=== VERDICT V3: QWK = {qw_kappa:.4f}  threshold=0.6  -> {'PROCEED to E-L3A' if qw_kappa >= 0.6 else 'STOP - do not proceed'} ===")

if __name__ == "__main__":
    main()
