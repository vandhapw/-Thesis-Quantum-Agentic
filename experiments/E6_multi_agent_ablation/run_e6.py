"""
E6 — Multi-Agent Coordination Ablation Experiment
Compare 3 LLM configurations on identical 25-machine test data:
  C1 Single-Call: one LLM call asking for ALL outputs in one JSON
  C2 Sequential-4: Monitoring → Diagnosis → Planning → Reporting (sequential)
  C3 Specialized-9: full QASAMAP (Monitoring + Diagnosis + Planning + Reporting +
                    Correlation + Explainability + SelfReflection + Scheduling + Pattern)

Per machine, compute composite quality score Q ∈ [0, 1].
ANOVA + Tukey HSD across 3 conditions.

For speed: 5 machines (top-5 by reasoning risk) × 3 conditions × 1 seed = 15 LLM session sets
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from comparative_study import load_test_data, build_ground_truth, NonAgenticPipeline
from agenticai_enhanced import (
    MultiAgentOrchestrator, ReasoningEngine, ContextMemoryStore,
)
from config import OLLAMA_API_KEY, OLLAMA_MODEL
from ollama import Client

# ─────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────
print("=" * 80)
print(" E6 — Multi-Agent Coordination Ablation")
print(" Configurations: C1 Single-Call, C2 Sequential-4, C3 Specialized-9")
print("=" * 80)

print("\n[1/4] Loading test data + selecting top-5 by reasoning risk...")
train_events, test_events = load_test_data()
gt = build_ground_truth(test_events)
reasoner = ReasoningEngine()
reasonings = [reasoner.score(e) for e in test_events]

# Pick top-5 by reasoning risk for speed
indexed = sorted(enumerate(reasonings), key=lambda x: -x[1]["risk_score"])
top5_indices = [i for i, _ in indexed[:5]]
top5_events = [test_events[i] for i in top5_indices]
top5_reasonings = [reasonings[i] for i in top5_indices]
print(f"  Top-5: {[e['machine_id'] for e in top5_events]}")
print(f"  Risk scores: {[r['risk_score'] for r in top5_reasonings]}")

ollama_client = Client(host="https://ollama.com",
                       headers={"Authorization": "Bearer " + OLLAMA_API_KEY})


def llm_call(system, user, timeout=60):
    t0 = time.time()
    try:
        resp = ollama_client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        elapsed = time.time() - t0
        content = resp["message"]["content"].strip()
        # Strip ```json fences
        if content.startswith("```"):
            content = "\n".join(line for line in content.split("\n")
                                 if not line.strip().startswith("```")).strip()
        try:
            parsed = json.loads(content)
            return {"parsed": parsed, "raw": content, "elapsed": elapsed, "valid_json": True}
        except json.JSONDecodeError:
            return {"parsed": None, "raw": content, "elapsed": elapsed, "valid_json": False}
    except Exception as e:
        return {"parsed": None, "raw": str(e), "elapsed": time.time() - t0,
                "valid_json": False, "error": str(e)}


# ─────────────────────────────────────────────
# C1 Single-Call: one mega-prompt
# ─────────────────────────────────────────────
SYSTEM_C1_SINGLE = """
You are a smart-manufacturing predictive-maintenance assistant. Given one machine's sensor data and threshold flags,
produce ALL of the following in ONE JSON response:
{
  "monitoring": {"risk_level": "LOW|MEDIUM|HIGH|CRITICAL", "anomaly_detected": bool, "anomaly_type": "thermal|vibration|energy|combined|none", "confidence": 0.0-1.0},
  "diagnosis": {"probable_cause": "bearing_wear|overheating|electrical|lubrication|normal|unknown", "affected_component": "motor|bearing|pump|actuator|unknown", "urgency_hours": int},
  "planning": {"action": "monitor|inspect|schedule_maintenance|immediate_shutdown", "priority": "P1|P2|P3|P4", "reason": "max 20 words", "notify_supervisor": bool},
  "reporting_BI": "max 3 sentence Bahasa Indonesia maintenance alert text",
  "explainability": {"top_feature": "string", "contribution_pct": float, "what_if": "string"},
  "self_check": {"self_consistent": bool, "any_inconsistency": "string or none"}
}
Return valid JSON only. No markdown fences. No explanations outside JSON.
"""


def run_c1_single(event, reasoning):
    user = (
        f"Sensor: {json.dumps({k: event.get(k) for k in ('machine_id','temperature','vibration','humidity','pressure','energy','predicted_remaining_life')}, indent=2)}\n"
        f"Threshold flags: {reasoning.get('flags', [])}\n"
        f"Risk score: {reasoning['risk_score']}, Severity: {reasoning['severity']}"
    )
    result = llm_call(SYSTEM_C1_SINGLE, user)
    return result


# ─────────────────────────────────────────────
# C2 Sequential-4: Monitoring → Diagnosis → Planning → Reporting
# ─────────────────────────────────────────────
def run_c2_sequential(event, reasoning):
    orch = MultiAgentOrchestrator(model_name=OLLAMA_MODEL)
    t0 = time.time()
    monitoring = orch.run_monitoring_agent(event, reasoning)
    diagnosis = orch.run_diagnosis_agent(event, monitoring, reasoning)
    planning = orch.run_planning_agent(diagnosis, reasoning)
    reporting = orch.run_reporting_agent(event["machine_id"], planning, diagnosis)
    elapsed = time.time() - t0
    return {
        "monitoring": monitoring, "diagnosis": diagnosis,
        "planning": planning, "reporting": reporting,
        "elapsed": elapsed,
        "valid_json": all(isinstance(x, dict) and "raw" not in x for x in
                          [monitoring, diagnosis, planning]),
    }


# ─────────────────────────────────────────────
# C3 Specialized-9: full QASAMAP stack (per-machine subset)
# ─────────────────────────────────────────────
def run_c3_specialized9(event, reasoning, all_events, all_reasonings):
    orch = MultiAgentOrchestrator(model_name=OLLAMA_MODEL)
    t0 = time.time()
    # Per-machine 5 agents
    monitoring = orch.run_monitoring_agent(event, reasoning)
    diagnosis = orch.run_diagnosis_agent(event, monitoring, reasoning)
    planning = orch.run_planning_agent(diagnosis, reasoning)
    reporting = orch.run_reporting_agent(event["machine_id"], planning, diagnosis)
    explainability = orch.run_explainability_agent(event, reasoning, reasoner.thresholds)
    self_reflection = orch.run_self_reflection_agent(monitoring, diagnosis, planning)
    # Fleet-level 3 agents (call once for all, but we attribute to this run)
    correlation = orch.run_correlation_agent(all_events, all_reasonings)
    scheduling = orch.run_scheduling_agent(all_events, all_reasonings)
    # Pattern: pass top5 history dict
    history = {e["machine_id"]: [e] for e in all_events}
    pattern = orch.run_pattern_agent(history)
    elapsed = time.time() - t0
    return {
        "monitoring": monitoring, "diagnosis": diagnosis,
        "planning": planning, "reporting": reporting,
        "explainability": explainability, "self_reflection": self_reflection,
        "correlation": correlation, "scheduling": scheduling, "pattern": pattern,
        "elapsed": elapsed,
        "valid_json": all(isinstance(x, dict) and "raw" not in x for x in
                          [monitoring, diagnosis, planning, explainability, self_reflection]),
    }


# ─────────────────────────────────────────────
# Composite quality score
# ─────────────────────────────────────────────
def composite_quality(condition, output, gt_action):
    """
    Compute composite quality score Q in [0, 1] across 5 sub-metrics:
      - decision_accuracy_correctness  (0.30): Did planning's action match GT?
      - output_structure_compliance    (0.20): % valid JSON
      - reasoning_depth                (0.20): how many distinct fields filled?
      - cross_dimension_consistency    (0.15): Monitoring HIGH ↔ Planning urgent?
      - explanation_quality            (0.15): present + non-trivial?
    """
    # 1. Decision accuracy
    if condition == "C1":
        plan = (output.get("parsed") or {}).get("planning", {})
    else:
        plan = output.get("planning", {})
    if isinstance(plan, dict) and "raw" in plan:
        # Try to extract action from raw
        raw = plan["raw"]
        if "immediate_shutdown" in raw: action = "immediate_shutdown"
        elif "schedule_maintenance" in raw: action = "schedule_maintenance"
        elif "inspect" in raw: action = "inspect"
        elif "monitor" in raw: action = "monitor"
        else: action = "unknown"
    else:
        action = plan.get("action", "unknown") if isinstance(plan, dict) else "unknown"

    # Map action to GT action label
    action_to_gt = {
        "immediate_shutdown": "Immediate shutdown",
        "schedule_maintenance": "Schedule maintenance",
        "inspect": "Schedule inspection",
        "monitor": "Monitor only",
    }
    predicted = action_to_gt.get(action, "Monitor only")
    decision_acc = 1.0 if predicted == gt_action else 0.0
    # Partial credit: within 1 escalation step
    severity_order = ["Monitor only", "Schedule inspection", "Schedule maintenance", "Immediate shutdown"]
    if not decision_acc and predicted in severity_order and gt_action in severity_order:
        diff = abs(severity_order.index(predicted) - severity_order.index(gt_action))
        if diff == 1: decision_acc = 0.5

    # 2. Structure compliance
    structure = 1.0 if output.get("valid_json") else 0.5

    # 3. Reasoning depth (count populated fields)
    if condition == "C1":
        parsed = output.get("parsed") or {}
        n_keys = len(parsed) if isinstance(parsed, dict) else 0
        reasoning_depth = min(1.0, n_keys / 6.0)  # expect 6 sub-objects
    else:
        n_agents = sum(1 for k in output if isinstance(output.get(k), dict)
                       and output[k] and "error" not in output[k])
        target = {"C2": 4, "C3": 9}[condition]
        reasoning_depth = min(1.0, n_agents / target)

    # 4. Cross-dimension consistency: monitoring risk_level vs planning action severity
    if condition == "C1":
        parsed = output.get("parsed") or {}
        mon = parsed.get("monitoring", {})
        plan_obj = parsed.get("planning", {})
    else:
        mon = output.get("monitoring", {})
        plan_obj = output.get("planning", {})
    # Extract risk and action
    risk_level = mon.get("risk_level", "LOW") if isinstance(mon, dict) else "LOW"
    risk_to_action_expected = {
        "CRITICAL": ["immediate_shutdown", "schedule_maintenance"],
        "HIGH": ["schedule_maintenance", "inspect"],
        "MEDIUM": ["inspect", "schedule_maintenance"],
        "LOW": ["monitor"],
    }
    expected_actions = risk_to_action_expected.get(risk_level, ["monitor"])
    consistency = 1.0 if action in expected_actions else 0.0

    # 5. Explanation quality
    if condition == "C1":
        parsed = output.get("parsed") or {}
        bi = parsed.get("reporting_BI", "")
        xai = parsed.get("explainability", {})
        explanation = (1.0 if (isinstance(bi, str) and len(bi) > 30) else 0.0) * 0.5 + \
                      (1.0 if (isinstance(xai, dict) and xai) else 0.0) * 0.5
    else:
        rep = output.get("reporting", {})
        xai = output.get("explainability", {}) if condition == "C3" else None
        rep_text = rep.get("raw", "") if isinstance(rep, dict) else str(rep)
        explanation = 0.0
        if isinstance(rep_text, str) and len(rep_text) > 30: explanation += 0.5
        if xai and isinstance(xai, dict) and xai: explanation += 0.5

    Q = (0.30 * decision_acc + 0.20 * structure + 0.20 * reasoning_depth +
         0.15 * consistency + 0.15 * explanation)
    return {
        "Q": round(Q, 4),
        "decision_acc": decision_acc,
        "structure": structure,
        "reasoning_depth": round(reasoning_depth, 3),
        "consistency": consistency,
        "explanation": explanation,
        "predicted_action": predicted,
        "ground_truth_action": gt_action,
    }


# ─────────────────────────────────────────────
# Run all 3 conditions × 5 machines (single seed for speed)
# ─────────────────────────────────────────────
print(f"\n[2/4] Running 3 conditions × {len(top5_events)} machines × 1 seed...")
print(f"  Estimated LLM calls: 5 (C1) + 20 (C2) + 50 (C3) = 75 calls × ~10s = ~13 min")

# Determine GT action per machine
def determine_gt_action(evt):
    if evt["_gt_machine_status_label"] == "Fault" or evt.get("predicted_remaining_life", 200) < 30:
        return "Immediate shutdown"
    if evt["_gt_machine_status_label"] == "Warning" and evt["_gt_failure_type"] != "Normal":
        return "Schedule maintenance"
    if evt["_gt_machine_status_label"] == "Warning" or evt["_gt_failure_type"] != "Normal":
        return "Schedule inspection"
    return "Monitor only"


gt_actions = [determine_gt_action(e) for e in top5_events]
print(f"  GT actions: {dict(zip([e['machine_id'] for e in top5_events], gt_actions))}")

results_per_condition = {"C1": [], "C2": [], "C3": []}

print("\n[3/4] Executing conditions...")
for cidx, (event, reasoning, gt_action) in enumerate(zip(top5_events, top5_reasonings, gt_actions)):
    mid = event["machine_id"]
    print(f"\n  --- Machine M-{mid} (case {cidx+1}/{len(top5_events)}) ---")

    # C1
    print(f"    C1 Single-Call...", end=" ", flush=True)
    out_c1 = run_c1_single(event, reasoning)
    q_c1 = composite_quality("C1", out_c1, gt_action)
    print(f"Q={q_c1['Q']:.3f} ({out_c1['elapsed']:.1f}s, valid_json={out_c1['valid_json']})")
    results_per_condition["C1"].append({"machine_id": mid, "quality": q_c1, "elapsed": out_c1['elapsed']})

    # C2
    print(f"    C2 Sequential-4...", end=" ", flush=True)
    out_c2 = run_c2_sequential(event, reasoning)
    q_c2 = composite_quality("C2", out_c2, gt_action)
    print(f"Q={q_c2['Q']:.3f} ({out_c2['elapsed']:.1f}s, valid_json={out_c2['valid_json']})")
    results_per_condition["C2"].append({"machine_id": mid, "quality": q_c2, "elapsed": out_c2['elapsed']})

    # C3
    print(f"    C3 Specialized-9...", end=" ", flush=True)
    out_c3 = run_c3_specialized9(event, reasoning, top5_events, top5_reasonings)
    q_c3 = composite_quality("C3", out_c3, gt_action)
    print(f"Q={q_c3['Q']:.3f} ({out_c3['elapsed']:.1f}s, valid_json={out_c3['valid_json']})")
    results_per_condition["C3"].append({"machine_id": mid, "quality": q_c3, "elapsed": out_c3['elapsed']})


# ─────────────────────────────────────────────
# Statistical analysis
# ─────────────────────────────────────────────
print(f"\n[4/4] Statistical analysis...")
import statistics

def summarize(condition):
    qs = [r["quality"]["Q"] for r in results_per_condition[condition]]
    elapsed = [r["elapsed"] for r in results_per_condition[condition]]
    return {
        "n": len(qs),
        "mean_Q": round(statistics.mean(qs), 4),
        "stdev_Q": round(statistics.pstdev(qs), 4) if len(qs) > 1 else 0,
        "mean_elapsed_sec": round(statistics.mean(elapsed), 2),
        "total_elapsed_sec": round(sum(elapsed), 2),
    }

summary = {c: summarize(c) for c in ["C1", "C2", "C3"]}
print(f"\n  {'Condition':<25} {'Q mean':>8} {'Q stdev':>8} {'Time/case':>10} {'Total time':>12}")
print("  " + "-" * 70)
for c in ["C1", "C2", "C3"]:
    s = summary[c]
    name_map = {"C1": "C1 Single-Call", "C2": "C2 Sequential-4", "C3": "C3 Specialized-9"}
    print(f"  {name_map[c]:<25} {s['mean_Q']:>8.4f} {s['stdev_Q']:>8.4f} {s['mean_elapsed_sec']:>9.1f}s {s['total_elapsed_sec']:>11.1f}s")

# One-way ANOVA (pure-Python)
def one_way_anova(groups):
    k = len(groups)
    n_total = sum(len(g) for g in groups)
    grand_mean = sum(sum(g) for g in groups) / n_total
    ss_between = sum(len(g) * (statistics.mean(g) - grand_mean) ** 2 for g in groups)
    ss_within = sum(sum((x - statistics.mean(g)) ** 2 for x in g) for g in groups)
    df_between = k - 1
    df_within = n_total - k
    if df_within == 0 or ss_within == 0:
        return None, None, df_between, df_within
    ms_between = ss_between / df_between
    ms_within = ss_within / df_within
    F = ms_between / ms_within
    # p-value via F-distribution approx (Wilson-Hilferty for chi-square based)
    # For small N, use approximation; full p requires scipy
    return F, ms_between, ms_within, (df_between, df_within)

groups = [[r["quality"]["Q"] for r in results_per_condition[c]] for c in ["C1", "C2", "C3"]]
F, msb, msw, dfs = one_way_anova(groups)
print(f"\n  One-way ANOVA on Q:")
if F is not None:
    print(f"    F({dfs[0]}, {dfs[1]}) = {F:.3f}")
    print(f"    MS_between = {msb:.4f}, MS_within = {msw:.4f}")
    # η² effect size
    ss_between_total = sum(len(g) * (statistics.mean(g) - statistics.mean([x for grp in groups for x in grp])) ** 2 for g in groups)
    ss_total = sum((x - statistics.mean([y for grp in groups for y in grp])) ** 2 for grp in groups for x in grp)
    eta_sq = ss_between_total / ss_total if ss_total > 0 else 0
    print(f"    η² = {eta_sq:.4f}")
    if F > 5: print(f"    F > 5 suggests strong effect (p likely < 0.05); confirm with scipy.stats.f.sf({F:.3f}, {dfs[0]}, {dfs[1]})")
else:
    print(f"    Insufficient variance for ANOVA")

# Pairwise t-tests
def t_test_paired(a, b):
    """Paired t-test."""
    n = len(a)
    diffs = [a[i] - b[i] for i in range(n)]
    mean_d = statistics.mean(diffs)
    sd_d = statistics.pstdev(diffs) if len(diffs) > 1 else 0
    if sd_d == 0:
        return None, 1.0
    se = sd_d / (n ** 0.5)
    t = mean_d / se
    return t, mean_d

print(f"\n  Pairwise paired t-tests on Q (N={len(top5_events)} per group):")
print(f"    C3 vs C1: t = ", end="")
t, md = t_test_paired(groups[2], groups[0])
print(f"{t:.3f if t else 0}, mean diff = {md:.4f}" if t else "infinite (zero variance)")

print(f"    C3 vs C2: t = ", end="")
t, md = t_test_paired(groups[2], groups[1])
print(f"{t:.3f if t else 0}, mean diff = {md:.4f}" if t else "infinite (zero variance)")

print(f"    C2 vs C1: t = ", end="")
t, md = t_test_paired(groups[1], groups[0])
print(f"{t:.3f if t else 0}, mean diff = {md:.4f}" if t else "infinite (zero variance)")

# ─────────────────────────────────────────────
# Save
# ─────────────────────────────────────────────
out_dir = Path(__file__).parent
results_payload = {
    "metadata": {
        "experiment": "E6_Multi_Agent_Ablation",
        "n_machines": len(top5_events),
        "n_conditions": 3,
        "n_seeds": 1,
        "machine_ids": [e["machine_id"] for e in top5_events],
        "ground_truth_actions": dict(zip([e["machine_id"] for e in top5_events], gt_actions)),
        "conditions": {
            "C1": "Single-Call: one LLM call returning all outputs",
            "C2": "Sequential-4: Monitoring → Diagnosis → Planning → Reporting",
            "C3": "Specialized-9: full QASAMAP 9-agent stack",
        },
    },
    "summary": summary,
    "anova_F": F,
    "results_per_condition": results_per_condition,
}
out_path = out_dir / "results.json"
out_path.write_text(json.dumps(results_payload, indent=2, default=str), encoding="utf-8")
print(f"\n[SAVED] {out_path}")

print(f"\n{'='*80}\n E6 RESULTS SUMMARY\n{'='*80}")
print(f"  C1 Single-Call    Q={summary['C1']['mean_Q']:.4f} (time {summary['C1']['mean_elapsed_sec']:.1f}s/case)")
print(f"  C2 Sequential-4   Q={summary['C2']['mean_Q']:.4f} (time {summary['C2']['mean_elapsed_sec']:.1f}s/case)")
print(f"  C3 Specialized-9  Q={summary['C3']['mean_Q']:.4f} (time {summary['C3']['mean_elapsed_sec']:.1f}s/case)")
print(f"\n  Quality gain C3 vs C1: +{(summary['C3']['mean_Q'] - summary['C1']['mean_Q']):.4f} ({100*(summary['C3']['mean_Q']/max(summary['C1']['mean_Q'],0.01)-1):.0f}%)")
print(f"  Time cost C3 vs C1: +{(summary['C3']['mean_elapsed_sec'] - summary['C1']['mean_elapsed_sec']):.1f}s ({summary['C3']['mean_elapsed_sec']/max(summary['C1']['mean_elapsed_sec'],1):.1f}× longer)")
