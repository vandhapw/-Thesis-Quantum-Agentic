"""
Cache-only analysis to support supervisor remediation decision.
Re-aggregates from existing 500 LLM calls in cache. No new LLM calls.

Computes:
  - Option C: deepseek-only metrics
  - Option B: 2-tier collapse (Action vs NoAction) on full ensemble
  - Per-LLM ordinal error pattern (mean tier-distance from GT per LLM)
  - Per-tier confusion: which true tier is hardest
  - qwen3.5 JSON failure pattern: empty content vs malformed JSON
"""
import json, re
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, f1_score, confusion_matrix

OUT_DIR = Path(r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-L2_agentic_validation")
TIERS = ["Critical", "High", "Medium", "Low"]
TIER_TO_INT = {t: i for i, t in enumerate(TIERS)}
INT_TO_TIER = {i: t for t, i in TIER_TO_INT.items()}

with open(OUT_DIR / "raw_results.json") as f:
    results = json.load(f)
print(f"Loaded {len(results)} cases")

LLMS = ["glm-5.1:cloud", "qwen3.5:cloud", "kimi-k2.6:cloud", "deepseek-v4-pro:cloud"]

# ---------- Option C: deepseek-only ----------
print("\n" + "="*70)
print("OPTION C: deepseek-only (no ensemble)")
print("="*70)
ds_arr = np.array([TIER_TO_INT.get(r["per_llm"]["deepseek-v4-pro:cloud"]["parsed_tier"], -1) for r in results])
gt_arr = np.array([TIER_TO_INT[r["gt_tier"]] for r in results])
valid = ds_arr >= 0
print(f"Valid deepseek predictions: {int(valid.sum())}/{len(results)}")
gt_v, ds_v = gt_arr[valid], ds_arr[valid]
qwk_ds = cohen_kappa_score(gt_v, ds_v, weights="quadratic", labels=[0,1,2,3])
mf1_ds = f1_score(gt_v, ds_v, labels=[0,1,2,3], average="macro", zero_division=0)
cm_ds = confusion_matrix(gt_v, ds_v, labels=[0,1,2,3])
print(f"  QW-Kappa: {qwk_ds:.4f}")
print(f"  Macro F1: {mf1_ds:.4f}")
# bootstrap CI
rng = np.random.default_rng(42)
boot = [cohen_kappa_score(gt_v[idx], ds_v[idx], weights="quadratic", labels=[0,1,2,3])
        for idx in (rng.integers(0, len(gt_v), len(gt_v)) for _ in range(1000))]
print(f"  95% CI: [{np.quantile(boot, 0.025):.4f}, {np.quantile(boot, 0.975):.4f}]")
print(f"  Confusion matrix (rows=GT, cols=Pred):")
print(f"    {'        '+''.join(f'{t:>10s}' for t in TIERS)}")
for i, t in enumerate(TIERS):
    row = "    " + f"{t:8s}" + "".join(f"{cm_ds[i,j]:>10d}" for j in range(4))
    print(row)

# ---------- Option B: 2-tier collapse on full ensemble ----------
print("\n" + "="*70)
print("OPTION B: 2-tier collapse — NeedsAction (Crit/High/Med) vs NoAction (Low)")
print("="*70)
# Use existing ensemble votes
ens_arr = np.array([TIER_TO_INT.get(r["ensemble_tier"], -1) for r in results])
valid_e = ens_arr >= 0
gt2 = (gt_arr[valid_e] != 3).astype(int)   # 1 = NeedsAction (NOT Low), 0 = NoAction
en2 = (ens_arr[valid_e] != 3).astype(int)
qwk2 = cohen_kappa_score(gt2, en2)   # binary kappa = unweighted = QWK
mf1_2 = f1_score(gt2, en2)
cm2 = confusion_matrix(gt2, en2)
print(f"Valid ensemble predictions: {int(valid_e.sum())}/{len(results)}")
print(f"  Cohen's Kappa (binary): {qwk2:.4f}")
print(f"  F1 (NeedsAction class): {mf1_2:.4f}")
print(f"  Confusion (rows=GT, cols=Pred):")
print(f"    {'           NoAction  NeedsAction'}")
for i, lbl in enumerate(["NoAction", "NeedsAction"]):
    print(f"    {lbl:11s} {cm2[i,0]:>9d}  {cm2[i,1]:>11d}")
boot2 = [cohen_kappa_score(gt2[idx], en2[idx]) for idx in (rng.integers(0, len(gt2), len(gt2)) for _ in range(1000))]
print(f"  95% CI: [{np.quantile(boot2, 0.025):.4f}, {np.quantile(boot2, 0.975):.4f}]")

# ---------- Option A+B: 2-tier with deepseek-only ----------
print("\n" + "="*70)
print("OPTION B+C: 2-tier collapse — deepseek-only")
print("="*70)
gt2_ds = (gt_v != 3).astype(int)
ds2 = (ds_v != 3).astype(int)
qwk2_ds = cohen_kappa_score(gt2_ds, ds2)
print(f"  Cohen's Kappa (binary): {qwk2_ds:.4f}")
mf1_2_ds = f1_score(gt2_ds, ds2)
print(f"  F1 (NeedsAction): {mf1_2_ds:.4f}")
boot2_ds = [cohen_kappa_score(gt2_ds[idx], ds2[idx]) for idx in (rng.integers(0, len(gt2_ds), len(gt2_ds)) for _ in range(1000))]
print(f"  95% CI: [{np.quantile(boot2_ds, 0.025):.4f}, {np.quantile(boot2_ds, 0.975):.4f}]")

# ---------- Per-LLM ordinal error distance ----------
print("\n" + "="*70)
print("PER-LLM ORDINAL ERROR PATTERN")
print("="*70)
for model in LLMS:
    pred = np.array([TIER_TO_INT.get(r["per_llm"][model]["parsed_tier"], -1) for r in results])
    v = pred >= 0
    if v.sum() < 10: continue
    distances = np.abs(gt_arr[v] - pred[v])
    dist_dist = pd.Series(distances).value_counts().to_dict()
    mean_dist = float(distances.mean())
    print(f"  {model:30s}  valid={int(v.sum())}/125  mean_tier_distance={mean_dist:.3f}  dist_hist={dist_dist}")

# ---------- qwen3.5 failure pattern ----------
print("\n" + "="*70)
print("qwen3.5 JSON FAILURE PATTERN ANALYSIS")
print("="*70)
qwen_fails = []
for r in results:
    qq = r["per_llm"]["qwen3.5:cloud"]
    if qq["parsed_tier"] is None:
        raw = qq.get("raw", "")
        category = "empty" if not raw.strip() else \
                   "no_braces" if "{" not in raw else \
                   "malformed_json"
        qwen_fails.append({
            "machine_id": r["machine_id"],
            "gt_tier": r["gt_tier"],
            "raw_first_100": raw[:100].replace("\n", "\\n"),
            "category": category,
        })
print(f"Total qwen3.5 failures: {len(qwen_fails)}/125")
cat_counts = pd.Series([f["category"] for f in qwen_fails]).value_counts().to_dict()
print(f"Failure categories: {cat_counts}")
print("First 5 failure samples:")
for f in qwen_fails[:5]:
    print(f"  M-{f['machine_id']:3d} GT={f['gt_tier']:8s} cat={f['category']:15s} raw={f['raw_first_100']!r}")

# ---------- Save aggregated analysis ----------
analysis = {
    "option_C_deepseek_only": {
        "qw_kappa": float(qwk_ds), "macro_f1": float(mf1_ds),
        "ci_95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
        "valid_n": int(valid.sum()),
    },
    "option_B_2tier_ensemble": {
        "kappa_binary": float(qwk2), "f1_needs_action": float(mf1_2),
        "ci_95": [float(np.quantile(boot2, 0.025)), float(np.quantile(boot2, 0.975))],
        "valid_n": int(valid_e.sum()),
    },
    "option_BC_2tier_deepseek_only": {
        "kappa_binary": float(qwk2_ds), "f1_needs_action": float(mf1_2_ds),
        "ci_95": [float(np.quantile(boot2_ds, 0.025)), float(np.quantile(boot2_ds, 0.975))],
        "valid_n": int(valid.sum()),
    },
    "qwen35_failure_categories": cat_counts,
}
with open(OUT_DIR / "remediation_analysis.json", "w") as f:
    json.dump(analysis, f, indent=2)
print(f"\nSaved: {OUT_DIR / 'remediation_analysis.json'}")
