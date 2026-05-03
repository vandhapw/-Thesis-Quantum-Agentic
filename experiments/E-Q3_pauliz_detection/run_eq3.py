"""
E-Q3 — Pauli-Z Compound Anomaly Detection vs Classical Baselines
================================================================

Pre-registered protocol — see PHASE1_QUANTUM_EXPERIMENT_DESIGN.md §E-Q3.

Encoding (5 qubits, 1 per sensor):
    sensor_value -> normalized to [0, pi] via sensor_bounds_derived.json
    angle theta_i -> RY(theta_i) on qubit i
Two scores:
    S_quantum    = <psi| sum_i Z_i |psi> = sum_i cos(theta_i)         (separable -- equivalent to classical)
    S_entangled  = <psi'| sum_i Z_i |psi'> after CNOT chain 0->1->2->3->4

Lower S => closer to |1> on more qubits => more sensors at extreme of normalized range
=> we treat (-S) as anomaly score so larger anomaly_score = more anomalous.
Threshold tau is selected on TRAIN split to maximize Youden's J (TPR - FPR).

Baselines:
    B1 single-threshold:  per-sensor best Youden threshold, OR-aggregated
    B2 Mahalanobis:       distance to train mean using train cov, threshold on ROC
    B3 weighted-sum:      classical sum_i w_i * cos(theta_i) -- mathematically same family as S_quantum

Sample design:
    Test split = 25 odd-id machines * subsampled rows
    Pre-registered: sample 80 rows per test machine (balanced anomaly/normal where possible)
    => N = up to 2000 test cases for paired comparisons
    GT = anomaly_flag column from CSV (0/1)

Outputs:
    results.json  -- raw per-row predictions + scores
    metrics.json  -- F1/precision/recall + McNemar p + Cliff's delta + Wilson CI
"""
import json
import os
import time
import math
import sys
import numpy as np
import pandas as pd

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector, SparsePauliOp

DATA_CSV   = r"D:/AI-LLM/Claude Experiment/Ver13/smart_manufacturing_data.csv"
BOUNDS_JSON = r"D:/AI-LLM/Claude Experiment/Ver13/sensor_bounds_derived.json"
OUT_DIR    = r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-Q3_pauliz_detection"
SENSORS    = ["temperature", "vibration", "humidity", "pressure", "energy_consumption"]
ROWS_PER_MACHINE = 80         # pre-registered sub-sample for tractability
SEED = 42
np.random.seed(SEED)

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def normalize_to_angle(v, lo, hi):
    """Map sensor value v in [lo, hi] to angle in [0, pi]. Outside range clamped."""
    x = (v - lo) / (hi - lo) if hi > lo else 0.5
    x = float(np.clip(x, 0.0, 1.0))
    return x * math.pi

def pauli_z_sum_op(n):
    """Sum_i Z_i operator as SparsePauliOp (n qubits)."""
    paulis = []
    for i in range(n):
        s = ["I"] * n
        s[n - 1 - i] = "Z"  # qiskit indexing
        paulis.append("".join(s))
    return SparsePauliOp(paulis, coeffs=[1.0] * n)

def expectation_z_sum(circ, op):
    sv = Statevector.from_instruction(circ)
    return float(np.real(sv.expectation_value(op)))

def best_youden_threshold(scores, labels):
    """Sort and find threshold maximizing TPR - FPR. Returns tau."""
    order = np.argsort(scores)
    s_sorted = np.array(scores)[order]
    y_sorted = np.array(labels)[order]
    P = y_sorted.sum()
    N = len(y_sorted) - P
    if P == 0 or N == 0:
        return float(np.median(scores))
    best_j = -1.0
    best_tau = s_sorted[0]
    tp = P
    fp = N
    for k in range(len(s_sorted)):
        # threshold = s_sorted[k] -> predict positive iff score > threshold
        # we evaluate just BEFORE removing this point (i.e., score >= s_sorted[k])
        tpr = tp / P if P else 0
        fpr = fp / N if N else 0
        j = tpr - fpr
        if j > best_j:
            best_j = j
            best_tau = float(s_sorted[k]) - 1e-12
        # remove this point from "positive predictions"
        if y_sorted[k] == 1:
            tp -= 1
        else:
            fp -= 1
    return best_tau

def metrics(pred, gt):
    pred = np.asarray(pred).astype(int)
    gt   = np.asarray(gt).astype(int)
    tp = int(((pred == 1) & (gt == 1)).sum())
    fp = int(((pred == 1) & (gt == 0)).sum())
    fn = int(((pred == 0) & (gt == 1)).sum())
    tn = int(((pred == 0) & (gt == 0)).sum())
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec  = tp / (tp + fn) if (tp + fn) else 0.0
    f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=prec, recall=rec, f1=f1)

def wilson_ci(p, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    denom = 1 + z**2/n
    centre = p + z**2/(2*n)
    margin = z * math.sqrt(p*(1-p)/n + z**2/(4*n*n))
    return ((centre - margin)/denom, (centre + margin)/denom)

def mcnemar_exact(b, c):
    """Exact two-sided binomial-based McNemar; returns p."""
    from scipy.stats import binomtest
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return float(binomtest(k=k, n=n, p=0.5, alternative="two-sided").pvalue)

def cliffs_delta(x, y):
    x = np.asarray(x); y = np.asarray(y)
    nx, ny = len(x), len(y)
    if nx == 0 or ny == 0:
        return 0.0
    # rank-based dominance
    gt = 0; lt = 0
    # vectorized: compare via broadcasting in chunks if large
    for v in x:
        gt += int((v > y).sum())
        lt += int((v < y).sum())
    return (gt - lt) / (nx * ny)

# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------
print("[E-Q3] loading data...", flush=True)
with open(BOUNDS_JSON) as f:
    bounds = json.load(f)
train_ids = bounds["train_machine_ids"]
test_ids  = bounds["test_machine_ids"]

# Use min/max from training subset as the encoding range. For each sensor we use [min, max]
# of the training distribution (NOT p05/p99 because we want the WHOLE range covered for theta).
# However min/max are extremes; using p05/p99 keeps theta in tighter band where most data lives.
# Pre-reg choice: use [min, max] of training so encoding is bounded but covers extremes too.
ranges = {s: (bounds[s]["min"], bounds[s]["max"]) for s in SENSORS}
print(f"  train_ids={len(train_ids)}, test_ids={len(test_ids)}")
print(f"  encoding ranges:")
for s, (lo, hi) in ranges.items():
    print(f"    {s}: [{lo:.3f}, {hi:.3f}]")

df_all = pd.read_csv(DATA_CSV)
print(f"  total rows: {len(df_all)}, anomaly_rate={df_all['anomaly_flag'].mean():.3f}")

def sample_rows(df, ids, per_machine, rng):
    out = []
    for mid in ids:
        sub = df[df["machine_id"] == mid]
        if len(sub) == 0:
            continue
        if len(sub) <= per_machine:
            out.append(sub)
        else:
            # stratify by anomaly_flag if both classes present
            anom = sub[sub["anomaly_flag"] == 1]
            norm = sub[sub["anomaly_flag"] == 0]
            n_anom_target = per_machine // 2
            n_norm_target = per_machine - n_anom_target
            picks = []
            if len(anom) > 0:
                picks.append(anom.sample(min(len(anom), n_anom_target), random_state=int(rng.integers(0, 2**31-1))))
            if len(norm) > 0:
                picks.append(norm.sample(min(len(norm), n_norm_target), random_state=int(rng.integers(0, 2**31-1))))
            out.append(pd.concat(picks))
    return pd.concat(out).reset_index(drop=True)

rng = np.random.default_rng(SEED)
print(f"[E-Q3] sampling {ROWS_PER_MACHINE}/machine train + test (stratified)...", flush=True)
train_df = sample_rows(df_all, train_ids, ROWS_PER_MACHINE, rng)
test_df  = sample_rows(df_all, test_ids,  ROWS_PER_MACHINE, rng)
print(f"  train: {len(train_df)} rows, anomaly_rate={train_df['anomaly_flag'].mean():.3f}")
print(f"  test : {len(test_df)} rows, anomaly_rate={test_df['anomaly_flag'].mean():.3f}")

# ----------------------------------------------------------------------------
# Build quantum scores
# ----------------------------------------------------------------------------
N_QUBITS = 5
ZSUM = pauli_z_sum_op(N_QUBITS)
print("[E-Q3] computing quantum scores (statevector, exact)...", flush=True)

def angles_for_row(row):
    return [normalize_to_angle(row[s], *ranges[s]) for s in SENSORS]

def s_quantum_separable(angles):
    # sum_i cos(theta_i) -- closed form, no need to build circuit (verify with one circuit later)
    return float(sum(math.cos(a) for a in angles))

def s_entangled(angles):
    qc = QuantumCircuit(N_QUBITS)
    for i, a in enumerate(angles):
        qc.ry(a, i)
    for i in range(N_QUBITS - 1):
        qc.cx(i, i + 1)
    return expectation_z_sum(qc, ZSUM)

# sanity: verify s_quantum_separable matches expectation of full circuit (no CNOT)
test_angles = [0.3, 1.2, 2.0, 0.8, 1.5]
qc_no_ent = QuantumCircuit(N_QUBITS)
for i, a in enumerate(test_angles):
    qc_no_ent.ry(a, i)
direct = expectation_z_sum(qc_no_ent, ZSUM)
closed = s_quantum_separable(test_angles)
print(f"  sanity: separable closed-form={closed:.6f} vs circuit={direct:.6f} diff={abs(closed-direct):.2e}")

t0 = time.time()
def add_quantum_scores(df, label):
    sq, se = [], []
    n = len(df)
    angles_all = []
    for idx, row in df.iterrows():
        a = angles_for_row(row)
        angles_all.append(a)
        sq.append(s_quantum_separable(a))
        se.append(s_entangled(a))
        if (idx + 1) % 200 == 0:
            print(f"    {label}: {idx+1}/{n} ({time.time()-t0:.1f}s)", flush=True)
    df = df.copy()
    df["S_quantum"]   = sq    # separable expectation
    df["S_entangled"] = se    # post-CNOT expectation
    df["angles_json"] = [json.dumps(a) for a in angles_all]
    return df

train_df = add_quantum_scores(train_df, "train")
test_df  = add_quantum_scores(test_df,  "test")
print(f"  quantum scoring done in {time.time()-t0:.1f}s")

# ----------------------------------------------------------------------------
# Classical baselines
# ----------------------------------------------------------------------------
print("[E-Q3] computing classical baselines...", flush=True)

# B3 weighted-sum classical (equal weights = 0.2 each)
def s_B3(row):
    return float(sum(0.2 * math.cos(normalize_to_angle(row[s], *ranges[s])) for s in SENSORS))

train_df["S_B3"] = train_df.apply(s_B3, axis=1)
test_df["S_B3"]  = test_df.apply(s_B3,  axis=1)

# B1 best single-threshold per-sensor, OR-aggregated
def normalize_features(df):
    out = np.zeros((len(df), len(SENSORS)))
    for j, s in enumerate(SENSORS):
        lo, hi = ranges[s]
        out[:, j] = np.clip((df[s].values - lo) / max(hi - lo, 1e-9), 0, 1)
    return out

X_train = normalize_features(train_df)
y_train = train_df["anomaly_flag"].values
X_test  = normalize_features(test_df)
y_test  = test_df["anomaly_flag"].values

# Per-sensor ROC threshold (predict positive if value > tau OR value < (1-tau))
# Simpler: per-sensor optimal Youden on raw normalized value, two-tailed (predict positive if abs(x-0.5) > tau)
b1_taus = []
b1_dirs = []  # 'high', 'low', or 'two-tailed'
for j in range(len(SENSORS)):
    # try high-tail
    tau_hi = best_youden_threshold(X_train[:, j], y_train)
    pred_hi = (X_train[:, j] > tau_hi).astype(int)
    f1_hi = metrics(pred_hi, y_train)["f1"]
    # try low-tail (use -x)
    tau_lo_neg = best_youden_threshold(-X_train[:, j], y_train)
    pred_lo = (-X_train[:, j] > tau_lo_neg).astype(int)
    f1_lo = metrics(pred_lo, y_train)["f1"]
    if f1_hi >= f1_lo:
        b1_taus.append(tau_hi); b1_dirs.append("high")
    else:
        b1_taus.append(tau_lo_neg); b1_dirs.append("low")
print(f"  B1 per-sensor thresholds: " + ", ".join(f"{SENSORS[j]}({b1_dirs[j]},{b1_taus[j]:.3f})" for j in range(len(SENSORS))))

def b1_predict(X):
    preds = np.zeros(len(X), dtype=int)
    for j in range(len(SENSORS)):
        if b1_dirs[j] == "high":
            preds |= (X[:, j] > b1_taus[j]).astype(int)
        else:
            preds |= (-X[:, j] > b1_taus[j]).astype(int)
    return preds

# B2 Mahalanobis distance (training mean+cov)
mu  = X_train.mean(axis=0)
cov = np.cov(X_train, rowvar=False)
cov_inv = np.linalg.pinv(cov + 1e-6 * np.eye(cov.shape[0]))
def maha(X):
    diff = X - mu
    d = np.einsum("ij,jk,ik->i", diff, cov_inv, diff)
    return np.sqrt(np.maximum(d, 0))
maha_train = maha(X_train)
maha_test  = maha(X_test)
b2_tau = best_youden_threshold(maha_train, y_train)
print(f"  B2 Mahalanobis tau={b2_tau:.4f}")

# Threshold quantum scores on TRAIN -- anomaly_score = -S so larger = more anomalous
# But to keep thresholding consistent, threshold on S directly: predict positive if S < tau
# (because high anomaly => sensors at extreme angles => S is low/negative)
def fit_lower_thresh(scores, labels):
    """Find tau s.t. predict positive iff scores < tau, maximizing Youden."""
    return -best_youden_threshold(-np.asarray(scores), labels)

q_tau_sep = fit_lower_thresh(train_df["S_quantum"].values, y_train)
q_tau_ent = fit_lower_thresh(train_df["S_entangled"].values, y_train)
b3_tau    = fit_lower_thresh(train_df["S_B3"].values, y_train)
print(f"  S_quantum tau={q_tau_sep:.4f}, S_entangled tau={q_tau_ent:.4f}, B3 tau={b3_tau:.4f}")

# ----------------------------------------------------------------------------
# Predictions on TEST
# ----------------------------------------------------------------------------
preds = {
    "S_quantum":    (test_df["S_quantum"].values < q_tau_sep).astype(int),
    "S_entangled":  (test_df["S_entangled"].values < q_tau_ent).astype(int),
    "B1_threshold": b1_predict(X_test),
    "B2_maha":      (maha_test > b2_tau).astype(int),
    "B3_weighted":  (test_df["S_B3"].values < b3_tau).astype(int),
}

print("[E-Q3] test set metrics:")
results_metrics = {}
for name, p in preds.items():
    m = metrics(p, y_test)
    n = len(y_test)
    f1_lo, f1_hi = wilson_ci(m["f1"], n)
    p_lo, p_hi = wilson_ci(m["precision"], m["tp"] + m["fp"]) if (m["tp"] + m["fp"]) else (0,0)
    r_lo, r_hi = wilson_ci(m["recall"],    m["tp"] + m["fn"]) if (m["tp"] + m["fn"]) else (0,0)
    m["f1_95ci"] = [f1_lo, f1_hi]
    m["prec_95ci"] = [p_lo, p_hi]
    m["rec_95ci"]  = [r_lo, r_hi]
    results_metrics[name] = m
    print(f"  {name:14s} F1={m['f1']:.3f} [CI {f1_lo:.3f},{f1_hi:.3f}] P={m['precision']:.3f} R={m['recall']:.3f} TP={m['tp']} FP={m['fp']} FN={m['fn']} TN={m['tn']}")

# ----------------------------------------------------------------------------
# McNemar pairwise (S_entangled vs B1, B2, B3) Bonferroni-corrected
# ----------------------------------------------------------------------------
print("[E-Q3] McNemar tests (S_entangled vs baselines):")
mcnemar_results = {}
y_arr = y_test
ent = preds["S_entangled"]
for base_name in ["B1_threshold", "B2_maha", "B3_weighted", "S_quantum"]:
    base = preds[base_name]
    # discordant cells: b = ent right & base wrong; c = ent wrong & base right
    ent_right  = (ent  == y_arr)
    base_right = (base == y_arr)
    b = int((ent_right & ~base_right).sum())
    c = int((~ent_right & base_right).sum())
    p = mcnemar_exact(b, c)
    mcnemar_results[f"S_entangled_vs_{base_name}"] = dict(b=b, c=c, p=p, p_bonferroni3=min(p*3, 1.0))
    print(f"  vs {base_name:14s}: b={b:4d} c={c:4d} p={p:.4f} p_bonf={min(p*3,1.0):.4f}")

# ----------------------------------------------------------------------------
# Cliff's delta on raw scores (S_entangled vs S_quantum, by class)
# ----------------------------------------------------------------------------
print("[E-Q3] Cliff's delta on raw S_entangled scores (positive vs negative class):")
pos_scores = test_df.loc[y_test == 1, "S_entangled"].values
neg_scores = test_df.loc[y_test == 0, "S_entangled"].values
delta = cliffs_delta(pos_scores, neg_scores)  # expected NEGATIVE: positives have lower S
print(f"  S_entangled delta (pos vs neg) = {delta:.4f}  (negative = positives have lower S, expected)")
delta_sep = cliffs_delta(test_df.loc[y_test==1, "S_quantum"].values,
                          test_df.loc[y_test==0, "S_quantum"].values)
print(f"  S_quantum   delta (pos vs neg) = {delta_sep:.4f}")
delta_b3  = cliffs_delta(test_df.loc[y_test==1, "S_B3"].values,
                          test_df.loc[y_test==0, "S_B3"].values)
print(f"  S_B3        delta (pos vs neg) = {delta_b3:.4f}")

# ----------------------------------------------------------------------------
# Save
# ----------------------------------------------------------------------------
os.makedirs(OUT_DIR, exist_ok=True)
out_blob = {
    "experiment": "E-Q3",
    "date": "2026-05-03",
    "seed": SEED,
    "n_train": int(len(train_df)),
    "n_test":  int(len(test_df)),
    "rows_per_machine": ROWS_PER_MACHINE,
    "encoding_ranges": ranges,
    "thresholds": {
        "S_quantum_lower": float(q_tau_sep),
        "S_entangled_lower": float(q_tau_ent),
        "S_B3_lower": float(b3_tau),
        "B1_per_sensor": [{"sensor": SENSORS[j], "tau": float(b1_taus[j]), "dir": b1_dirs[j]} for j in range(len(SENSORS))],
        "B2_mahalanobis_upper": float(b2_tau),
    },
    "metrics": results_metrics,
    "mcnemar": mcnemar_results,
    "cliffs_delta": {
        "S_entangled_pos_vs_neg": delta,
        "S_quantum_pos_vs_neg":   delta_sep,
        "S_B3_pos_vs_neg":        delta_b3,
    },
}
with open(os.path.join(OUT_DIR, "metrics.json"), "w") as f:
    json.dump(out_blob, f, indent=2)

# Save per-row predictions
pred_df = test_df[["machine_id", "anomaly_flag", "S_quantum", "S_entangled", "S_B3"]].copy()
for name in preds:
    pred_df[f"pred_{name}"] = preds[name]
pred_df.to_csv(os.path.join(OUT_DIR, "test_predictions.csv"), index=False)
print(f"[E-Q3] saved metrics.json + test_predictions.csv to {OUT_DIR}")
