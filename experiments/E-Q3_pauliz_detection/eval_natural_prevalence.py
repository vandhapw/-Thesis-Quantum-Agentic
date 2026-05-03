"""
Re-evaluate E-Q3 detectors on a non-stratified test sample matching the natural
anomaly prevalence (~8.9%). The main run uses 50/50 stratified test for power on
McNemar; this side-eval verifies behavior under realistic class imbalance.
"""
import json
import math
import numpy as np
import pandas as pd
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector, SparsePauliOp

DATA_CSV    = r"D:/AI-LLM/Claude Experiment/Ver13/smart_manufacturing_data.csv"
BOUNDS_JSON = r"D:/AI-LLM/Claude Experiment/Ver13/sensor_bounds_derived.json"
THRESH_JSON = r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-Q3_pauliz_detection/metrics.json"
SENSORS = ["temperature","vibration","humidity","pressure","energy_consumption"]
SEED = 43  # different from main to avoid overlap

with open(BOUNDS_JSON) as f: bounds = json.load(f)
with open(THRESH_JSON) as f: prev = json.load(f)
test_ids = bounds["test_machine_ids"]
ranges = {s: (bounds[s]["min"], bounds[s]["max"]) for s in SENSORS}

df = pd.read_csv(DATA_CSV)
test_pool = df[df["machine_id"].isin(test_ids)].reset_index(drop=True)
# Sample 4000 rows preserving natural prevalence
sample = test_pool.sample(n=4000, random_state=SEED).reset_index(drop=True)
print(f"natural-prev sample: n={len(sample)}, anomaly_rate={sample['anomaly_flag'].mean():.4f}")

def angle(v, lo, hi):
    x = np.clip((v-lo)/max(hi-lo,1e-9), 0, 1)
    return x * math.pi

def pauli_z_sum(n):
    paulis = []
    for i in range(n):
        s = ["I"]*n; s[n-1-i] = "Z"; paulis.append("".join(s))
    return SparsePauliOp(paulis, coeffs=[1.0]*n)

ZSUM = pauli_z_sum(5)
def s_ent(angles):
    qc = QuantumCircuit(5)
    for i,a in enumerate(angles): qc.ry(a,i)
    for i in range(4): qc.cx(i,i+1)
    return float(np.real(Statevector.from_instruction(qc).expectation_value(ZSUM)))

def s_sep(angles): return float(sum(math.cos(a) for a in angles))

scores_ent, scores_sep, scores_b3 = [], [], []
for _, r in sample.iterrows():
    angs = [angle(r[s], *ranges[s]) for s in SENSORS]
    scores_sep.append(s_sep(angs))
    scores_ent.append(s_ent(angs))
    scores_b3.append(sum(0.2 * math.cos(a) for a in angs))
sample["S_quantum"]   = scores_sep
sample["S_entangled"] = scores_ent
sample["S_B3"]        = scores_b3

# B1 thresholds from main run
b1 = prev["thresholds"]["B1_per_sensor"]
def b1_pred(r):
    p = 0
    for j, s in enumerate(SENSORS):
        lo, hi = ranges[s]
        x = float(np.clip((r[s]-lo)/max(hi-lo,1e-9), 0, 1))
        if b1[j]["dir"] == "high":
            if x > b1[j]["tau"]: p = 1
        else:
            if -x > b1[j]["tau"]: p = 1
    return p

# B2 Mahalanobis from train -- recompute with same train sample for fairness
train_ids = bounds["train_machine_ids"]
np.random.seed(SEED)
def normfeat(df):
    out = np.zeros((len(df), 5))
    for j, s in enumerate(SENSORS):
        lo, hi = ranges[s]
        out[:, j] = np.clip((df[s].values - lo) / max(hi - lo, 1e-9), 0, 1)
    return out

train_sample = df[df["machine_id"].isin(train_ids)].sample(2000, random_state=SEED)
Xtr = normfeat(train_sample)
mu = Xtr.mean(axis=0); cov = np.cov(Xtr, rowvar=False)
covinv = np.linalg.pinv(cov + 1e-6*np.eye(5))
Xte = normfeat(sample)
diff = Xte - mu
maha = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", diff, covinv, diff), 0))

th = prev["thresholds"]
preds = {
    "S_quantum":    (sample["S_quantum"].values   < th["S_quantum_lower"]).astype(int),
    "S_entangled":  (sample["S_entangled"].values < th["S_entangled_lower"]).astype(int),
    "B1_threshold": np.array([b1_pred(r) for _, r in sample.iterrows()]),
    "B2_maha":      (maha > th["B2_mahalanobis_upper"]).astype(int),
    "B3_weighted":  (sample["S_B3"].values        < th["S_B3_lower"]).astype(int),
}
y = sample["anomaly_flag"].values

def m(p, y):
    p = np.asarray(p).astype(int); y = np.asarray(y).astype(int)
    tp = int(((p==1)&(y==1)).sum()); fp = int(((p==1)&(y==0)).sum())
    fn = int(((p==0)&(y==1)).sum()); tn = int(((p==0)&(y==0)).sum())
    pr = tp/(tp+fp) if tp+fp else 0; rc = tp/(tp+fn) if tp+fn else 0
    f1 = 2*pr*rc/(pr+rc) if (pr+rc) else 0
    return dict(f1=f1, prec=pr, rec=rc, tp=tp, fp=fp, fn=fn, tn=tn)

print("\nNatural-prevalence (8.9% anomaly) results:")
out = {}
for n, p in preds.items():
    r = m(p, y)
    out[n] = r
    print(f"  {n:14s} F1={r['f1']:.3f} P={r['prec']:.3f} R={r['rec']:.3f}  TP={r['tp']} FP={r['fp']} FN={r['fn']} TN={r['tn']}")

# Save
import json as J
with open(r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-Q3_pauliz_detection/metrics_natural_prev.json", "w") as f:
    J.dump({"n": int(len(sample)), "anomaly_rate": float(y.mean()), "metrics": out}, f, indent=2)
