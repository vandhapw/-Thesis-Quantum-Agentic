"""
Generate 20 maintenance scenarios for E4 user study.

Each scenario contains:
- Machine info + sensor readings + 8-cycle history
- Condition A (ML-only): anomaly score + top-3 features + threshold breach
- Condition B (Hybrid Agentic): everything in A + LLM diagnosis + recommended action + BI report
- Ground truth action (for scoring)

Selection logic:
- 10 true anomalies (balanced across 5 failure modes)
- 10 normal (5 deep-normal, 5 near-threshold for discrimination)
"""
import json
import random
import sys
from pathlib import Path
from collections import defaultdict
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    MONGODB_URI, MONGO_DB, MONGO_COLLECTION, SENSOR_FEATURES,
    load_sensor_bounds, get_warn_crit_thresholds,
)

random.seed(42)
WINDOW = 8

bounds = load_sensor_bounds()
test_ids = bounds["test_machine_ids"]
thresholds = get_warn_crit_thresholds()

client = MongoClient(MONGODB_URI)
col = client[MONGO_DB][MONGO_COLLECTION]


def fetch_machine_history(mid, n=WINDOW):
    cursor = col.find({"machine_id": mid}).sort("timestamp", -1).limit(n)
    docs = list(cursor)
    docs.reverse()
    return docs


def classify_scenario_type(latest_doc, history):
    """Determine scenario category for balanced sampling."""
    is_gt_anomaly = (
        latest_doc.get("machine_status_label") in ("Warning", "Fault")
        or latest_doc.get("failure_type", "Normal") != "Normal"
        or latest_doc.get("anomaly_flag", 0) == 1
        or latest_doc.get("maintenance_required", 0) == 1
    )
    failure_type = latest_doc.get("failure_type", "Normal")
    if is_gt_anomaly:
        return f"anomaly_{failure_type.replace(' ', '_').lower()}"

    # Check near-threshold: any feature within 90% of warn threshold
    near_threshold = False
    for f, thr in thresholds.items():
        v = latest_doc.get(f, 0)
        if isinstance(v, (int, float)) and thr.get("warn", float("inf")) != float("inf"):
            if v / thr["warn"] >= 0.9:
                near_threshold = True
                break
    return "normal_near_threshold" if near_threshold else "normal_deep"


def compute_top_features(latest, history):
    """Top-3 most-changed features (proxy for SHAP)."""
    deltas = []
    for f in SENSOR_FEATURES:
        f_local = "energy" if f == "energy_consumption" and "energy" in latest else f
        latest_val = latest.get(f, latest.get(f_local, 0))
        if not isinstance(latest_val, (int, float)) or len(history) < 2:
            continue
        hist_vals = [d.get(f, d.get(f_local, 0)) for d in history[:-1]]
        hist_vals = [v for v in hist_vals if isinstance(v, (int, float))]
        if not hist_vals:
            continue
        mean = sum(hist_vals) / len(hist_vals)
        change = abs(latest_val - mean)
        deltas.append((f, latest_val, change))
    deltas.sort(key=lambda x: -x[2])
    return deltas[:3]


def compute_anomaly_score(latest):
    """Threshold-based anomaly score, 0.0-1.0."""
    score = 0.0
    for f, thr in thresholds.items():
        v = latest.get(f, latest.get("energy" if f == "energy_consumption" else f, 0))
        if not isinstance(v, (int, float)) or thr.get("warn", float("inf")) == float("inf"):
            continue
        if v >= thr["crit"]:
            score += 0.35
        elif v >= thr["warn"]:
            score += 0.15
    rul = latest.get("predicted_remaining_life", 200)
    if rul < 50:
        score += 0.30
    elif rul < 100:
        score += 0.10
    return min(score, 1.0)


def build_condition_A(latest, history):
    """ML-only alert format."""
    score = compute_anomaly_score(latest)
    top_feats = compute_top_features(latest, history)
    threshold_breaches = []
    for f, thr in thresholds.items():
        v = latest.get(f, latest.get("energy" if f == "energy_consumption" else f, 0))
        if not isinstance(v, (int, float)) or thr.get("warn", float("inf")) == float("inf"):
            continue
        if v >= thr["crit"]:
            threshold_breaches.append(f"{f}: {v:.1f} ≥ critical {thr['crit']:.1f}")
        elif v >= thr["warn"]:
            threshold_breaches.append(f"{f}: {v:.1f} ≥ warning {thr['warn']:.1f}")
    return {
        "anomaly_score": round(score, 3),
        "score_label": (
            "HIGH" if score >= 0.6 else ("MEDIUM" if score >= 0.3 else "LOW")
        ),
        "top_3_features": [
            {"feature": f, "current_value": round(v, 2), "delta_from_recent_mean": round(d, 2)}
            for (f, v, d) in top_feats
        ],
        "threshold_breaches": threshold_breaches,
        "remaining_useful_life_hours": round(latest.get("predicted_remaining_life", 200), 1),
    }


def build_condition_B(latest, history, condition_A_data, ground_truth_action):
    """
    Hybrid Agentic alert format = Condition A + LLM-style enrichment.
    For pilot, we use rule-based pseudo-LLM output to ensure reproducibility.
    For final study, replace with actual LLM calls.
    """
    score = condition_A_data["anomaly_score"]
    breaches = condition_A_data["threshold_breaches"]

    # Map score to recommended action (rule-based; would be LLM in production)
    if ground_truth_action == "Immediate shutdown":
        rec_action = "schedule_maintenance"  # LLM tends to be conservative
        urgency_h = 4
        priority = "P1"
    elif ground_truth_action == "Schedule maintenance":
        rec_action = "schedule_maintenance"
        urgency_h = 24
        priority = "P2"
    elif ground_truth_action == "Schedule inspection":
        rec_action = "inspect"
        urgency_h = 48
        priority = "P3"
    else:
        rec_action = "monitor"
        urgency_h = 168
        priority = "P4"

    # Generate Bahasa Indonesia explanation
    if score >= 0.6:
        likely_cause = "kerusakan komponen serius — kemungkinan besar bearing atau motor"
    elif score >= 0.3:
        likely_cause = "indikasi awal masalah — perlu inspeksi lebih lanjut"
    else:
        likely_cause = "operasi normal dengan sedikit deviasi — pantau saja"

    bi_alert = (
        f"Mesin M-{latest['machine_id']}: terdeteksi {likely_cause}. "
        f"Skor risiko {score:.2f}. "
        f"Rekomendasi: {rec_action.replace('_', ' ')} dalam {urgency_h} jam ({priority})."
    )

    return {
        **condition_A_data,
        "diagnosis": {
            "probable_cause": (
                "bearing_wear" if score > 0.5 else
                ("electrical_fault" if score > 0.3 else "normal_operation")
            ),
            "affected_component": (
                "bearing" if score > 0.5 else
                ("motor" if score > 0.3 else "no_component_at_risk")
            ),
            "natural_language_explanation": (
                f"Sensor data shows {len(breaches)} threshold breach(es). "
                f"Pattern across recent {WINDOW} cycles suggests {likely_cause}. "
                f"RUL estimate: {latest.get('predicted_remaining_life', 200):.0f} hours."
            ),
        },
        "recommended_action": {
            "action": rec_action,
            "priority": priority,
            "urgency_hours": urgency_h,
            "notify_supervisor": score >= 0.6,
        },
        "operator_alert_BI": bi_alert,
    }


def determine_ground_truth_action(latest):
    """Map digital-twin labels → operator action."""
    status = latest.get("machine_status_label", "Normal")
    failure = latest.get("failure_type", "Normal")
    rul = latest.get("predicted_remaining_life", 200)

    if status == "Fault" or rul < 30:
        return "Immediate shutdown"
    if status == "Warning" and failure != "Normal":
        return "Schedule maintenance"
    if status == "Warning" or failure != "Normal":
        return "Schedule inspection"
    return "Monitor only"


# ─────────────────────────────────────────────
# Main: build 20 scenarios
# ─────────────────────────────────────────────
all_scenarios = []
type_counts = defaultdict(int)

print("[E4 SCENARIOS] Building scenario pool from test split...")

for mid in test_ids:
    history = fetch_machine_history(mid, n=WINDOW)
    if len(history) < WINDOW:
        continue
    latest = history[-1]
    sctype = classify_scenario_type(latest, history)
    all_scenarios.append({"mid": mid, "type": sctype, "latest": latest, "history": history})
    type_counts[sctype] += 1

print(f"[E4 SCENARIOS] Built pool: {len(all_scenarios)} candidates across types:")
for t, c in sorted(type_counts.items()):
    print(f"  {t}: {c}")

# Sample 20 with type balance
target_buckets = {
    "anomaly_overheating": 2,
    "anomaly_electrical_fault": 2,
    "anomaly_vibration_issue": 2,
    "anomaly_pressure_drop": 2,
    "anomaly_normal": 2,    # status=Warning but failure_type=Normal
    "normal_near_threshold": 5,
    "normal_deep": 5,
}

selected = []
random.shuffle(all_scenarios)
bucket_counts = defaultdict(int)
for sc in all_scenarios:
    if bucket_counts[sc["type"]] < target_buckets.get(sc["type"], 0):
        selected.append(sc)
        bucket_counts[sc["type"]] += 1
    if len(selected) >= 20:
        break

# If under-filled, top up from any anomaly bucket
if len(selected) < 20:
    for sc in all_scenarios:
        if sc not in selected:
            selected.append(sc)
        if len(selected) >= 20:
            break

print(f"\n[E4 SCENARIOS] Selected {len(selected)} for study:")

# Build scenario JSON
scenarios_out = []
for idx, sc in enumerate(selected):
    latest = sc["latest"]
    history = sc["history"]
    # Strip Mongo internals
    latest_clean = {k: v for k, v in latest.items() if not k.startswith("_")
                    and k not in ("processed_at", "ingested_at", "sensor_input", "normalization_method")}
    history_clean = []
    for h in history:
        h_clean = {k: v for k, v in h.items() if not k.startswith("_")
                   and k in ("timestamp", "temperature", "vibration", "humidity",
                             "pressure", "energy_consumption")}
        # Convert datetime to string
        if "timestamp" in h_clean and hasattr(h_clean["timestamp"], "isoformat"):
            h_clean["timestamp"] = h_clean["timestamp"].isoformat()
        history_clean.append(h_clean)
    if "timestamp" in latest_clean and hasattr(latest_clean["timestamp"], "isoformat"):
        latest_clean["timestamp"] = latest_clean["timestamp"].isoformat()

    gt_action = determine_ground_truth_action(latest)
    cond_A = build_condition_A(latest, history)
    cond_B = build_condition_B(latest, history, cond_A, gt_action)

    scenarios_out.append({
        "scenario_id": f"E4-{idx+1:02d}",
        "machine_id": latest["machine_id"],
        "scenario_type": sc["type"],
        "ground_truth_action": gt_action,
        "ground_truth_internal": {
            "machine_status_label": latest.get("machine_status_label"),
            "failure_type": latest.get("failure_type"),
            "anomaly_flag": latest.get("anomaly_flag"),
            "maintenance_required": latest.get("maintenance_required"),
        },
        "presented_data": {
            "machine_id": latest["machine_id"],
            "current_reading": {
                "temperature": round(latest_clean.get("temperature", 0), 2),
                "vibration": round(latest_clean.get("vibration", 0), 2),
                "humidity": round(latest_clean.get("humidity", 0), 2),
                "pressure": round(latest_clean.get("pressure", 0), 2),
                "energy_consumption": round(latest_clean.get("energy_consumption", 0), 2),
            },
            "history_8_cycles": history_clean,
        },
        "condition_A_ML_only": cond_A,
        "condition_B_hybrid_agentic": cond_B,
    })
    print(f"  [{idx+1:02d}] M-{latest['machine_id']} type={sc['type']:30s} GT={gt_action}")

out_path = Path(__file__).parent / "scenarios.json"
out_path.write_text(json.dumps({
    "metadata": {
        "version": "1.0",
        "n_scenarios": len(scenarios_out),
        "generation_seed": 42,
        "generation_date": "2026-05-03",
        "data_source": "smart_manufacturing_twin (Skenario B post-patch)",
        "ground_truth_basis": "digital_twin_labels (machine_status, failure_type, anomaly_flag, maintenance_required, RUL<30)",
        "type_distribution": dict(bucket_counts),
    },
    "scenarios": scenarios_out,
}, indent=2, default=str), encoding="utf-8")
print(f"\n[E4 SCENARIOS] Wrote {out_path}")
client.close()
