"""
E3 — Few-Shot Adaptation Experiment (HONEST scope)

ETHICAL DISCLOSURE (academic integrity):
  This experiment evaluates how each approach's detection performance evolves with
  small numbers of "labeled examples" of a held-out failure type. The "labels"
  used as ground truth here are themselves outputs of the digital-twin's XGBoost
  classifier — which we previously documented has a 56% flip rate (label
  instability across cycles for the same underlying physical state). Therefore
  results should be read as "few-shot adaptation behavior against a noisy proxy
  ground truth" — NOT as evidence of few-shot performance against true expert
  annotations. For real expert-validated few-shot evaluation, manual labeling
  by domain experts on a held-out test set would be required.

Held-out failure type: "Pressure Drop" (most prevalent in current snapshot).
Labels: digital-twin classifier output (binary needs_attention).
Approach behavior:
  - Pure_Rule_Based:   no learning from examples; same thresholds always
  - Fleet_Relative:    no per-failure-type adaptation; uses A from training
  - Sliding_Window:    no per-failure-type adaptation; uses fleet bounds

These three approaches do NOT have a few-shot learning mechanism in their
current form. Therefore E3 in its strict pre-registered protocol form would
require ML retraining (which we don't have implemented for the LSTM/TCN).

REVISED HONEST SCOPE for E3:
  Demonstrate that NONE of our current detector approaches improve with
  N labeled examples. This is a "what's missing" result that motivates
  future work (in-context LLM adaptation, ML retraining pipeline).

If the LLM agentic pipeline were given N few-shot examples in its prompt
(in-context learning), we would expect adaptation. We test this by:
  - Building a few-shot LLM prompt with N=0,1,3,5 example anomalies
  - Comparing LLM detection on held-out failure type with/without examples
  - This isolates the in-context learning capability claim (VP5)
"""
import json
import sys
import statistics
from copy import deepcopy
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from comparative_study import (
    load_test_data, build_ground_truth,
    NonAgenticPipeline, FleetRelativePipeline, SlidingWindowPipeline,
    compute_detection_metrics,
)
from config import (
    OLLAMA_API_KEY, OLLAMA_MODEL, MONGODB_URI, MONGO_DB, MONGO_COLLECTION,
    load_sensor_bounds,
)
from ollama import Client
from pymongo import MongoClient

HOLDOUT_FAILURE = "Pressure Drop"
N_LEVELS = [0, 1, 3, 5]   # few-shot example counts to test


# ─────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────
print("=" * 80)
print(" E3 — Few-Shot Adaptation Experiment (HONEST scope)")
print("=" * 80)
print()
print("⚠️  ACADEMIC ETHICS DISCLOSURE:")
print("   Ground-truth labels here are digital-twin XGBoost classifier outputs")
print("   (previously documented 56% flip rate). Findings = 'adaptation against")
print("   noisy proxy GT', NOT against expert annotations. Real few-shot eval")
print("   requires human-labeled held-out set.")
print()
print(f"Held-out failure type: {HOLDOUT_FAILURE}")
print(f"N levels tested: {N_LEVELS}")
print()

print("[1/5] Loading data + identifying held-out cases...")
train_events, test_events = load_test_data()
gt_baseline = build_ground_truth(test_events)

# Identify held-out positive cases (failure_type = HOLDOUT)
holdout_positives = [e for e in test_events
                      if e.get("_gt_failure_type") == HOLDOUT_FAILURE]
non_holdout_test = [e for e in test_events
                    if e.get("_gt_failure_type") != HOLDOUT_FAILURE]
n_holdout = len(holdout_positives)
n_non_holdout = len(non_holdout_test)
print(f"  Holdout positives ({HOLDOUT_FAILURE}): {n_holdout}")
print(f"  Non-holdout test cases: {n_non_holdout}")

if n_holdout < 5:
    print(f"\n⚠️  WARNING: only {n_holdout} holdout examples — N=5 level not feasible.")
    print(f"    Will limit N levels to: {[n for n in N_LEVELS if n <= n_holdout]}")
    N_LEVELS = [n for n in N_LEVELS if n <= n_holdout]
print()

# ─────────────────────────────────────────────
# Test 1: Non-learning approaches (baseline)
# ─────────────────────────────────────────────
print("[2/5] Baseline test (non-learning approaches)...")
print("  These approaches have NO few-shot mechanism; F1 should be constant across N.")

bounds = load_sensor_bounds()
train_ids = bounds["train_machine_ids"]
test_ids = bounds["test_machine_ids"]

baseline_metrics_per_N = {}
for N in N_LEVELS:
    # For non-learning approaches, N doesn't matter — they always run the same
    # We just record their F1 once and replicate
    if N == 0:
        rb_results = NonAgenticPipeline().analyze(test_events)
        rb_metrics = compute_detection_metrics(rb_results, gt_baseline)
        fr = FleetRelativePipeline(); fr.fit(train_events)
        fr_results = fr.analyze(test_events)
        fr_metrics = compute_detection_metrics(fr_results, gt_baseline)
        sw = SlidingWindowPipeline(window=12, z_threshold=2.5); sw.fit(train_ids)
        sw_results = sw.analyze(test_ids)
        sw_metrics = compute_detection_metrics(sw_results, gt_baseline)
    baseline_metrics_per_N[N] = {
        "Pure_Rule_Based": rb_metrics,
        "Fleet_Relative": fr_metrics,
        "Sliding_Window": sw_metrics,
    }
    print(f"  N={N}: Pure_Rule_Based F1={rb_metrics['f1_score']:.3f}, "
          f"Fleet F1={fr_metrics['f1_score']:.3f}, "
          f"Sliding F1={sw_metrics['f1_score']:.3f}")

# ─────────────────────────────────────────────
# Test 2: LLM in-context learning (the actual hypothesis)
# ─────────────────────────────────────────────
print("\n[3/5] LLM in-context learning test (the actual VP5 hypothesis)...")
print("  Sample held-out examples; build prompts with 0/1/3/5 examples;")
print("  evaluate LLM detection on a fixed set of evaluation cases.")

# Pre-fetch sensor history for each holdout-positive (use as in-context examples)
# Build evaluation set: 10 cases (5 holdout positives + 5 negatives)
# We test LLM's ability to detect the holdout failure type given examples

mongo = MongoClient(MONGODB_URI)
col = mongo[MONGO_DB][MONGO_COLLECTION]

# Build example pool from train split
print(f"  Building example pool from train split (looking for {HOLDOUT_FAILURE} examples)...")
# Note: train events don't have failure_type filtered, so look in MongoDB
example_candidates = []
for mid in train_ids:
    docs = list(col.find({"machine_id": mid, "failure_type": HOLDOUT_FAILURE})
                .sort("timestamp", -1).limit(2))
    for d in docs:
        example_candidates.append({
            "machine_id": mid,
            "temperature": d.get("temperature", 0),
            "vibration": d.get("vibration", 0),
            "humidity": d.get("humidity", 0),
            "energy_consumption": d.get("energy_consumption", 0),
            "predicted_remaining_life": d.get("predicted_remaining_life", 200),
            "ground_truth_label": "ANOMALY",
            "ground_truth_failure_type": d.get("failure_type"),
        })
mongo.close()
print(f"  Example pool size: {len(example_candidates)} {HOLDOUT_FAILURE} cases from train split")

if len(example_candidates) < max(N_LEVELS):
    print(f"  WARNING: example pool ({len(example_candidates)}) < max N ({max(N_LEVELS)}). Limiting.")
    N_LEVELS = [n for n in N_LEVELS if n <= len(example_candidates)]
    print(f"  Adjusted N levels: {N_LEVELS}")

# Build evaluation set: take the holdout positives from test + 5 negatives
import random
random.seed(42)
eval_positives = holdout_positives[:5] if len(holdout_positives) >= 5 else holdout_positives
eval_negatives = random.sample([e for e in test_events
                                 if e.get("_gt_failure_type") == "Normal"
                                 and e.get("_gt_machine_status_label") == "Normal"],
                                min(5, sum(1 for e in test_events
                                           if e.get("_gt_failure_type") == "Normal"
                                           and e.get("_gt_machine_status_label") == "Normal")))
eval_set = eval_positives + eval_negatives
print(f"\n  Evaluation set: {len(eval_set)} cases ({len(eval_positives)} pos + {len(eval_negatives)} neg)")

# LLM client
client = Client(host="https://ollama.com",
                headers={"Authorization": "Bearer " + OLLAMA_API_KEY})


def build_few_shot_prompt(examples, target_event):
    """Build LLM prompt with N few-shot examples."""
    base = (
        "You are a maintenance anomaly classifier. Determine whether the TARGET machine "
        "is showing anomaly that requires attention. Return JSON ONLY:\n"
        '{"is_anomaly": true|false, "confidence": 0.0-1.0}\n\n'
    )
    if examples:
        base += "EXAMPLES of anomalous machines (specifically: " + HOLDOUT_FAILURE + "):\n"
        for i, ex in enumerate(examples, 1):
            base += (
                f"Example {i}: temp={ex['temperature']:.1f}, vib={ex['vibration']:.1f}, "
                f"humi={ex['humidity']:.1f}, energy={ex['energy_consumption']:.1f}, "
                f"rul={ex['predicted_remaining_life']:.0f} → ANOMALY\n"
            )
        base += "\n"
    return base


def llm_detect(target_event, n_examples):
    examples = example_candidates[:n_examples] if n_examples > 0 else []
    system = build_few_shot_prompt(examples, target_event)
    user = (
        f"TARGET: temp={target_event.get('temperature', 0):.1f}, "
        f"vib={target_event.get('vibration', 0):.1f}, "
        f"humi={target_event.get('humidity', 0):.1f}, "
        f"energy={target_event.get('energy', target_event.get('energy_consumption', 0)):.1f}, "
        f"rul={target_event.get('predicted_remaining_life', 200):.0f}"
    )
    try:
        resp = client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        content = resp["message"]["content"].strip()
        if content.startswith("```"):
            content = "\n".join(line for line in content.split("\n")
                                 if not line.strip().startswith("```")).strip()
        try:
            parsed = json.loads(content)
            return bool(parsed.get("is_anomaly", False))
        except json.JSONDecodeError:
            return "anomaly" in content.lower()
    except Exception as e:
        print(f"    LLM error: {e}")
        return False


# Run LLM eval at each N level
print(f"\n[4/5] Running LLM detection at each N level...")
llm_results_per_N = {}
for N in N_LEVELS:
    print(f"\n  N={N} examples in prompt:")
    correct_pos = 0
    correct_neg = 0
    fp = 0
    fn = 0
    for evt in eval_set:
        is_actual_pos = evt.get("_gt_failure_type") == HOLDOUT_FAILURE
        pred_pos = llm_detect(evt, N)
        if pred_pos and is_actual_pos: correct_pos += 1
        elif pred_pos and not is_actual_pos: fp += 1
        elif not pred_pos and is_actual_pos: fn += 1
        else: correct_neg += 1
        symbol = "✓" if (pred_pos == is_actual_pos) else "✗"
        print(f"    M-{evt['machine_id']:>2} actual={'POS' if is_actual_pos else 'NEG'} "
              f"pred={'POS' if pred_pos else 'NEG'} {symbol}")
    tp, tn, fp_count, fn_count = correct_pos, correct_neg, fp, fn
    total = tp + tn + fp_count + fn_count
    prec = tp / max(tp + fp_count, 1)
    rec = tp / max(tp + fn_count, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    acc = (tp + tn) / total if total > 0 else 0
    llm_results_per_N[N] = {
        "TP": tp, "FP": fp_count, "FN": fn_count, "TN": tn,
        "precision": round(prec, 4), "recall": round(rec, 4),
        "f1_score": round(f1, 4), "accuracy": round(acc, 4),
        "n": total,
    }
    print(f"    → TP={tp} FP={fp_count} FN={fn_count} TN={tn} "
          f"prec={prec:.3f} rec={rec:.3f} F1={f1:.3f}")

# ─────────────────────────────────────────────
# Statistical analysis
# ─────────────────────────────────────────────
print(f"\n[5/5] Statistical analysis...")
print(f"\n  Few-shot LLM F1 across N levels:")
print(f"  {'N examples':<12} {'F1':>8} {'Precision':>10} {'Recall':>8}")
for N in N_LEVELS:
    m = llm_results_per_N[N]
    print(f"  {N:<12} {m['f1_score']:>8.3f} {m['precision']:>10.3f} {m['recall']:>8.3f}")

# Trend analysis (simple linear regression on F1 vs N)
ns = list(N_LEVELS)
f1s = [llm_results_per_N[n]["f1_score"] for n in ns]
n_obs = len(ns)
if n_obs >= 2:
    mean_n = statistics.mean(ns)
    mean_f1 = statistics.mean(f1s)
    num = sum((ns[i] - mean_n) * (f1s[i] - mean_f1) for i in range(n_obs))
    den = sum((ns[i] - mean_n) ** 2 for i in range(n_obs))
    slope = num / den if den > 0 else 0
    print(f"\n  Linear trend: F1 improvement per added example = {slope:.4f}")
    if slope > 0:
        print(f"  → suggests LLM IS using few-shot examples to improve detection")
    elif slope < 0:
        print(f"  → suggests LLM does NOT improve with examples (or examples confuse)")
    else:
        print(f"  → no clear trend")

# Compare baseline (non-learning) approaches at any N (constant)
print(f"\n  Non-learning baseline F1 (constant across N — no few-shot mechanism):")
for ap in ["Pure_Rule_Based", "Fleet_Relative", "Sliding_Window"]:
    f1 = baseline_metrics_per_N[N_LEVELS[0]][ap]["f1_score"]
    print(f"    {ap:<22} F1={f1:.3f} (no learning)")

# ─────────────────────────────────────────────
# Save outputs
# ─────────────────────────────────────────────
out_dir = Path(__file__).parent
results_payload = {
    "metadata": {
        "experiment": "E3_Few_Shot_Adaptation",
        "ethical_disclosure": (
            "Ground-truth labels are digital-twin classifier outputs (56% flip rate). "
            "Findings = 'adaptation against noisy proxy GT', not against expert annotations. "
            "Real few-shot eval requires human-labeled held-out set."
        ),
        "holdout_failure_type": HOLDOUT_FAILURE,
        "n_levels_tested": N_LEVELS,
        "n_eval_cases": len(eval_set),
        "n_eval_positives": len(eval_positives),
        "n_eval_negatives": len(eval_negatives),
        "example_pool_size": len(example_candidates),
    },
    "baseline_non_learning": baseline_metrics_per_N[N_LEVELS[0]],
    "llm_few_shot_per_N": llm_results_per_N,
    "linear_trend_slope": slope if n_obs >= 2 else None,
}
out_path = out_dir / "results.json"
out_path.write_text(json.dumps(results_payload, indent=2, default=str), encoding="utf-8")
print(f"\n[SAVED] {out_path}")

print(f"\n{'='*80}\n E3 RESULTS SUMMARY (HONEST)\n{'='*80}")
print(f"  Held-out failure type: {HOLDOUT_FAILURE}")
print(f"  Eval set: {len(eval_set)} cases")
print(f"  LLM N=0 baseline F1: {llm_results_per_N[0]['f1_score']:.3f}")
print(f"  LLM N={max(N_LEVELS)} F1: {llm_results_per_N[max(N_LEVELS)]['f1_score']:.3f}")
print(f"  Improvement with examples: +{(llm_results_per_N[max(N_LEVELS)]['f1_score'] - llm_results_per_N[0]['f1_score']):.3f}")
print(f"\n  ⚠️  Caveats:")
print(f"     - Eval set is small (N={len(eval_set)})")
print(f"     - Ground truth = noisy classifier output, not expert labels")
print(f"     - Single seed; would need replicates for statistical claims")
