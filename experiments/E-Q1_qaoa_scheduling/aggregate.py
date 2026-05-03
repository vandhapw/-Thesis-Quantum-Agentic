"""Compute clean summary tables from per_instance.csv."""
import json, numpy as np, pandas as pd

CSV = r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-Q1_qaoa_scheduling/per_instance.csv"
OUT = r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-Q1_qaoa_scheduling/summary.json"

df = pd.read_csv(CSV)
print(f"loaded {len(df)} rows")

# Coerce optional bool columns
for c in ["SA_optimal","QAOA1_optimal","QAOA2_optimal","QAOA3_optimal"]:
    df[c] = df[c].map({"True": True, "False": False, True: True, False: False})

def agg_size(sub):
    out = {"n": int(len(sub)), "nvars": int(sub.nvars.iloc[0])}
    for col in ["BF_cost","BF_time","SA_cost","SA_abs_gap","SA_time",
                "QAOA1_cost","QAOA1_abs_gap","QAOA1_time",
                "QAOA2_cost","QAOA2_abs_gap","QAOA2_time",
                "QAOA3_cost","QAOA3_abs_gap","QAOA3_time"]:
        v = pd.to_numeric(sub[col], errors="coerce").dropna()
        out[col + "_mean"] = round(float(v.mean()), 6) if len(v) else None
        out[col + "_std"]  = round(float(v.std(ddof=0)), 6) if len(v) else None
        out[col + "_n"]    = int(len(v))
    for col in ["SA_optimal","QAOA1_optimal","QAOA2_optimal","QAOA3_optimal"]:
        v = sub[col].dropna()
        out[col + "_rate"] = round(float(v.mean()), 4) if len(v) else None
        out[col + "_n"]    = int(len(v))
    return out

summary = {"per_size": {}, "paired_tests": {}}
for (N, T), sub in df.groupby(["N","T"]):
    summary["per_size"][f"N{N}_T{T}"] = agg_size(sub)

# Paired tests on absolute gap (QAOA p=1,2,3 vs SA, where both available)
from scipy.stats import wilcoxon, ttest_rel, shapiro
for p_target in (1, 2, 3):
    sub = df.dropna(subset=["SA_abs_gap", f"QAOA{p_target}_abs_gap"])
    gap_sa = pd.to_numeric(sub.SA_abs_gap, errors="coerce").values.astype(float)
    gap_q  = pd.to_numeric(sub[f"QAOA{p_target}_abs_gap"], errors="coerce").values.astype(float)
    diff = gap_q - gap_sa
    if len(diff) >= 3 and not np.allclose(diff, 0):
        try:
            sw_p = float(shapiro(diff).pvalue)
        except Exception:
            sw_p = 0.0
        try:
            wstat, pval = wilcoxon(gap_q, gap_sa, zero_method="wilcox")
            test_name = "wilcoxon"
        except ValueError:
            pval = None; test_name = "n/a"
    else:
        pval = None; test_name = "n/a (all-zero diffs)"
        sw_p = None
    summary["paired_tests"][f"QAOA{p_target}_vs_SA"] = dict(
        test=test_name,
        p=round(float(pval), 6) if pval is not None else None,
        n=int(len(diff)),
        mean_abs_gap_diff=round(float(diff.mean()), 6) if len(diff) else None,
        median_abs_gap_diff=round(float(np.median(diff)), 6) if len(diff) else None,
        SA_optimal_rate=round(float(sub.SA_optimal.dropna().mean()), 4) if len(sub) else None,
        QAOA_optimal_rate=round(float(sub[f"QAOA{p_target}_optimal"].dropna().mean()), 4) if len(sub) else None,
        shapiro_p=sw_p,
    )

with open(OUT, "w") as f:
    json.dump(summary, f, indent=2)
print(f"wrote {OUT}")
print(json.dumps(summary["paired_tests"], indent=2))
print("\nPer-size optimal rates:")
for k, v in summary["per_size"].items():
    print(f"  {k:14s} nv={v['nvars']:2d} n={v['n']:2d}  SA_opt={v['SA_optimal_rate']}  "
          f"Q1_opt={v['QAOA1_optimal_rate']}  Q2_opt={v['QAOA2_optimal_rate']}  Q3_opt={v['QAOA3_optimal_rate']}  "
          f"BF_t={v['BF_time_mean']}s  SA_t={v['SA_time_mean']}s  "
          f"Q1_t={v['QAOA1_time_mean']}s  Q2_t={v['QAOA2_time_mean']}s  Q3_t={v['QAOA3_time_mean']}s")
