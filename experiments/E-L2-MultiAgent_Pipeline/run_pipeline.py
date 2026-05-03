"""
Multi-Agent Pipeline for Monitoring -> Diagnosing -> Planning -> Action
=======================================================================

Sequential 4-stage agentic pipeline. Each stage is an LLM specialized for its role:

  Stage 1  Monitoring : sensor + classifier evidence -> anomaly status + severity
  Stage 2  Diagnosing : monitoring out + evidence -> root cause + component
  Stage 3  Planning   : diagnosis -> action + priority + employees + duration
  Stage 4  Action     : plan -> formal CMMS-style work order dispatch

LLM assignment (heterogeneous, leveraging per-LLM strengths from E-L2 V3 ablation):
  Monitoring  -> glm-5.1:cloud         (fast pre-screen)
  Diagnosing  -> deepseek-v4-pro:cloud (best reasoning, kappa=0.728 in E-L2 V3)
  Planning    -> kimi-k2.6:cloud       (structured output)
  Action      -> deepseek-v4-pro:cloud (consistency for dispatch decisions)

Demo: 5 machines from test split. Records per-stage JSON output + per-stage
latency. Saves trace + summary CSV. Visualization in visualize.py.
"""
import json, time, hashlib, sys
from pathlib import Path
import numpy as np
import pandas as pd
from ollama import Client

sys.path.insert(0, r"D:/AI-LLM/Claude Experiment/Ver13")
from config import OLLAMA_API_KEY

DATA_CSV    = r"D:/AI-LLM/Claude Experiment/Ver13/smart_manufacturing_data.csv"
BOUNDS_JSON = r"D:/AI-LLM/Claude Experiment/Ver13/sensor_bounds_derived.json"
OUT_DIR     = Path(r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-L2-MultiAgent_Pipeline")
CACHE_DIR   = OUT_DIR / "llm_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

AGENT_LLM = {
    "monitoring": "glm-5.1:cloud",
    "diagnosing": "deepseek-v4-pro:cloud",
    "planning":   "kimi-k2.6:cloud",
    "action":     "deepseek-v4-pro:cloud",
}
N_DEMO_MACHINES = 5
SEED = 42
NUM_PREDICT = 800

client = Client(host="https://ollama.com",
                headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"})

# -----------------------------------------------------------------------------
# Per-agent prompt templates
# -----------------------------------------------------------------------------
SYSTEM_BASE = (
    "You are a specialized agent in a 4-stage industrial maintenance pipeline. "
    "You perform exactly one role and output only a single valid JSON object."
)

def prompt_monitoring(evidence):
    return (
        "ROLE: Monitoring Agent (Stage 1 of 4). Task: assess whether the machine is in normal, warning, or anomalous state.\n\n"
        f"Sensor readings:\n"
        f"  Temperature        : {evidence['temperature']:.2f} C  (warning>=82, critical>=88)\n"
        f"  Vibration          : {evidence['vibration']:.2f}        (warning>=55, critical>=70)\n"
        f"  Humidity           : {evidence['humidity']:.2f} %       (warning>=68, critical>=75)\n"
        f"  Pressure           : {evidence['pressure']:.2f} bar     (warning>=4.3, critical>=4.8)\n"
        f"  Energy Consumption : {evidence['energy']:.2f} kWh       (warning>=3.8, critical>=4.5)\n\n"
        f"Upstream classifier:\n"
        f"  failure_type           = \"{evidence['failure_type']}\"\n"
        f"  anomaly_flag           = {evidence['anomaly_flag']}\n"
        f"  downtime_risk          = {evidence['downtime_risk']:.2f}\n"
        f"  maintenance_required   = {evidence['maintenance_required']}\n"
        f"  predicted_remaining_life = {evidence['rul']:.0f} hours\n\n"
        "Output ONLY this JSON (no other text):\n"
        "{\"status\": \"normal|warning|anomaly\", \"severity\": \"low|medium|high|critical\", "
        "\"flagged_sensors\": [list of sensor names that exceeded threshold], "
        "\"reasoning\": \"<one sentence>\", \"confidence\": <float 0.0-1.0>}"
    )

def prompt_diagnosing(evidence, mon_out):
    return (
        "ROLE: Diagnosing Agent (Stage 2 of 4). Task: given the Monitoring assessment, identify the most likely root cause and affected component.\n\n"
        f"Sensor readings: temp={evidence['temperature']:.2f}, vib={evidence['vibration']:.2f}, "
        f"hum={evidence['humidity']:.2f}, press={evidence['pressure']:.2f}, energy={evidence['energy']:.2f}\n"
        f"Failure-type signature: \"{evidence['failure_type']}\"\n"
        f"RUL forecast: {evidence['rul']:.0f} hours\n\n"
        f"Monitoring Agent output (Stage 1):\n"
        f"  status           = {mon_out.get('status', 'unknown')}\n"
        f"  severity         = {mon_out.get('severity', 'unknown')}\n"
        f"  flagged_sensors  = {mon_out.get('flagged_sensors', [])}\n"
        f"  reasoning        = {mon_out.get('reasoning', '')}\n\n"
        "Output ONLY this JSON (no other text):\n"
        "{\"root_cause\": \"<short phrase, e.g. bearing wear, seal degradation, electrical short>\", "
        "\"affected_component\": \"<short, e.g. spindle bearing, cooling fan, hydraulic seal>\", "
        "\"failure_progression\": \"<one sentence on how this failure mode is likely to evolve>\", "
        "\"evidence\": [list of evidence supporting diagnosis], "
        "\"confidence\": <float 0.0-1.0>}"
    )

def prompt_planning(diag_out, evidence):
    return (
        "ROLE: Planning Agent (Stage 3 of 4). Task: given the Diagnosing output, propose a concrete maintenance action with priority and resource estimate.\n\n"
        f"Diagnosis (Stage 2):\n"
        f"  root_cause          = {diag_out.get('root_cause', 'unknown')}\n"
        f"  affected_component  = {diag_out.get('affected_component', 'unknown')}\n"
        f"  failure_progression = {diag_out.get('failure_progression', 'unknown')}\n"
        f"  evidence            = {diag_out.get('evidence', [])}\n\n"
        f"Context: failure_type={evidence['failure_type']}, RUL={evidence['rul']:.0f}h\n\n"
        "Plan a maintenance action. Choose action from: \"monitor\" | \"inspect\" | \"repair\" | \"replace\" | \"shutdown\".\n"
        "Choose priority from: \"P1\" (critical, <=4h) | \"P2\" (high, <=24h) | \"P3\" (medium, <=1week) | \"P4\" (routine, next window).\n\n"
        "Output ONLY this JSON (no other text):\n"
        "{\"action\": \"monitor|inspect|repair|replace|shutdown\", "
        "\"priority\": \"P1|P2|P3|P4\", "
        "\"estimated_duration_hours\": <integer>, "
        "\"employees_needed\": <integer 1-5>, "
        "\"skills_needed\": [list of skill labels], "
        "\"scheduled_within_hours\": <integer, deadline window>, "
        "\"justification\": \"<one sentence>\"}"
    )

def prompt_action(plan_out, machine_id):
    return (
        f"ROLE: Action Agent (Stage 4 of 4). Task: convert the Planning output into a formal CMMS-style work order dispatch decision.\n\n"
        f"Machine ID: M-{machine_id}\n"
        f"Planning output (Stage 3):\n"
        f"  action                  = {plan_out.get('action', 'monitor')}\n"
        f"  priority                = {plan_out.get('priority', 'P4')}\n"
        f"  estimated_duration_h    = {plan_out.get('estimated_duration_hours', 1)}\n"
        f"  employees_needed        = {plan_out.get('employees_needed', 1)}\n"
        f"  skills_needed           = {plan_out.get('skills_needed', [])}\n"
        f"  scheduled_within_hours  = {plan_out.get('scheduled_within_hours', 168)}\n"
        f"  justification           = {plan_out.get('justification', '')}\n\n"
        "Decide whether this action requires human supervisor approval before dispatch (P1 actions of type repair/replace/shutdown ALWAYS require approval; P2-P4 monitor/inspect can dispatch automatically).\n\n"
        "Output ONLY this JSON (no other text):\n"
        f"{{\"work_order_id\": \"WO-M{machine_id}-<8-char-suffix-from-current-time>\", "
        "\"action_type\": \"<copied from planning action>\", "
        "\"dispatched_to\": \"<team identifier, e.g. Maintenance-Team-A>\", "
        "\"scheduled_time\": \"<ISO datetime within scheduled_within_hours from now>\", "
        "\"approval_required\": <true|false>, "
        "\"status\": \"dispatched|pending_approval\", "
        "\"audit_note\": \"<one sentence summary for the audit log>\"}"
    )

# -----------------------------------------------------------------------------
# JSON extraction
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# Cached LLM call
# -----------------------------------------------------------------------------
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
                            messages=[{"role":"system","content":SYSTEM_BASE},
                                       {"role":"user","content":prompt}],
                            options={"temperature":0, "num_predict":NUM_PREDICT},
                            think=False)
            elapsed = time.time() - t0
            content = r["message"].get("content", "")
            data = {"model": model, "content": content, "elapsed_s": elapsed, "ts": time.time()}
            with open(cf, "w") as f: json.dump(data, f)
            return data
        except Exception as e:
            last_err = str(e)[:300]
            if "503" in last_err or "overloaded" in last_err:
                time.sleep(3 + attempt*2); continue
            break
    return {"model": model, "content": "", "error": last_err, "elapsed_s": 0, "ts": time.time()}

# -----------------------------------------------------------------------------
# Sample evidence
# -----------------------------------------------------------------------------
def composite_gt(row):
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

def build_demo_set():
    with open(BOUNDS_JSON) as f: bounds = json.load(f)
    test_ids = bounds["test_machine_ids"]
    df = pd.read_csv(DATA_CSV)
    rng = np.random.default_rng(SEED)
    # Pick machines spanning different GT tiers for richer demonstration
    pool = df[df["machine_id"].isin(test_ids)].reset_index(drop=True)
    pool = pool.assign(gt_tier=pool.apply(composite_gt, axis=1))
    cases = []
    # Sample 1 case per tier where possible, plus extras to reach N_DEMO_MACHINES
    tiers_to_pick = ["Critical", "High", "Medium", "Low", "Low"]   # 1+1+1+2 to get richness
    for t in tiers_to_pick:
        sub = pool[pool.gt_tier == t]
        if len(sub) == 0: sub = pool
        row = sub.sample(1, random_state=int(rng.integers(0, 2**31-1))).iloc[0]
        cases.append({
            "machine_id":  int(row["machine_id"]),
            "timestamp":   str(row["timestamp"]),
            "temperature": float(row["temperature"]),
            "vibration":   float(row["vibration"]),
            "humidity":    float(row["humidity"]),
            "pressure":    float(row["pressure"]),
            "energy":      float(row["energy_consumption"]),
            "failure_type": str(row["failure_type"]),
            "rul":          float(row["predicted_remaining_life"]),
            "anomaly_flag": int(row["anomaly_flag"]),
            "downtime_risk": float(row["downtime_risk"]),
            "maintenance_required": int(row["maintenance_required"]),
            "gt_tier":     row["gt_tier"],
        })
    return cases

# -----------------------------------------------------------------------------
# Pipeline runner
# -----------------------------------------------------------------------------
def run_pipeline_one(case):
    """Run all 4 stages sequentially for one machine."""
    trace = {"machine_id": case["machine_id"], "gt_tier": case["gt_tier"], "stages": {}}
    t_start = time.time()

    # Stage 1: Monitoring
    p1 = prompt_monitoring(case)
    r1 = call_llm(AGENT_LLM["monitoring"], p1)
    j1 = extract_json(r1["content"])
    trace["stages"]["monitoring"] = {"llm": AGENT_LLM["monitoring"], "elapsed_s": r1["elapsed_s"],
                                      "raw": r1["content"][:300], "parsed": j1}
    if not j1:
        trace["error"] = "monitoring stage failed to parse JSON"
        trace["total_elapsed_s"] = time.time() - t_start
        return trace

    # Stage 2: Diagnosing
    p2 = prompt_diagnosing(case, j1)
    r2 = call_llm(AGENT_LLM["diagnosing"], p2)
    j2 = extract_json(r2["content"])
    trace["stages"]["diagnosing"] = {"llm": AGENT_LLM["diagnosing"], "elapsed_s": r2["elapsed_s"],
                                      "raw": r2["content"][:300], "parsed": j2}
    if not j2:
        trace["error"] = "diagnosing stage failed to parse JSON"
        trace["total_elapsed_s"] = time.time() - t_start
        return trace

    # Stage 3: Planning
    p3 = prompt_planning(j2, case)
    r3 = call_llm(AGENT_LLM["planning"], p3)
    j3 = extract_json(r3["content"])
    trace["stages"]["planning"] = {"llm": AGENT_LLM["planning"], "elapsed_s": r3["elapsed_s"],
                                    "raw": r3["content"][:300], "parsed": j3}
    if not j3:
        trace["error"] = "planning stage failed to parse JSON"
        trace["total_elapsed_s"] = time.time() - t_start
        return trace

    # Stage 4: Action
    p4 = prompt_action(j3, case["machine_id"])
    r4 = call_llm(AGENT_LLM["action"], p4)
    j4 = extract_json(r4["content"])
    trace["stages"]["action"] = {"llm": AGENT_LLM["action"], "elapsed_s": r4["elapsed_s"],
                                  "raw": r4["content"][:300], "parsed": j4}
    if not j4:
        trace["error"] = "action stage failed to parse JSON"

    trace["total_elapsed_s"] = time.time() - t_start
    return trace

def main():
    print("[Multi-Agent Pipeline] building demo set ...", flush=True)
    cases = build_demo_set()
    print(f"  {len(cases)} machines selected (spanning GT tiers):")
    for c in cases:
        print(f"    M-{c['machine_id']:3d}  GT_tier={c['gt_tier']:8s}  ft={c['failure_type']:20s}  RUL={c['rul']:.0f}h  anomaly={c['anomaly_flag']}")

    print("\n[Multi-Agent Pipeline] LLM assignment per role:")
    for role, llm in AGENT_LLM.items():
        print(f"    {role:11s} -> {llm}")
    print()

    traces = []
    t0 = time.time()
    for i, case in enumerate(cases):
        print(f"[{i+1}/{len(cases)}] M-{case['machine_id']} (GT={case['gt_tier']}) running pipeline ...", flush=True)
        tr = run_pipeline_one(case)
        traces.append(tr)
        # Compact summary print
        for stage, sd in tr["stages"].items():
            parsed_summary = ""
            if sd.get("parsed"):
                if stage == "monitoring":
                    parsed_summary = f"status={sd['parsed'].get('status')}, severity={sd['parsed'].get('severity')}"
                elif stage == "diagnosing":
                    parsed_summary = f"cause={sd['parsed'].get('root_cause','')[:40]}"
                elif stage == "planning":
                    parsed_summary = f"action={sd['parsed'].get('action')}, priority={sd['parsed'].get('priority')}, dur={sd['parsed'].get('estimated_duration_hours')}h"
                elif stage == "action":
                    parsed_summary = f"status={sd['parsed'].get('status')}, approval={sd['parsed'].get('approval_required')}"
            print(f"    {stage:11s} ({sd['elapsed_s']:.1f}s)  {parsed_summary}")
        print(f"    TOTAL: {tr['total_elapsed_s']:.1f}s\n")

    print(f"[Multi-Agent Pipeline] all {len(cases)} machines done in {time.time()-t0:.1f}s")

    # Save trace
    with open(OUT_DIR / "trace.json", "w") as f:
        json.dump(traces, f, indent=2, default=str)

    # Build summary CSV
    rows = []
    for tr in traces:
        row = {"machine_id": tr["machine_id"], "gt_tier": tr["gt_tier"], "total_s": tr["total_elapsed_s"]}
        for stage in ["monitoring", "diagnosing", "planning", "action"]:
            sd = tr["stages"].get(stage, {})
            row[f"{stage}_s"] = sd.get("elapsed_s")
            row[f"{stage}_llm"] = sd.get("llm")
            p = sd.get("parsed") or {}
            if stage == "monitoring":
                row["mon_status"]   = p.get("status")
                row["mon_severity"] = p.get("severity")
            elif stage == "diagnosing":
                row["diag_root_cause"] = (p.get("root_cause") or "")[:60]
                row["diag_component"]  = (p.get("affected_component") or "")[:50]
            elif stage == "planning":
                row["plan_action"]   = p.get("action")
                row["plan_priority"] = p.get("priority")
                row["plan_dur_h"]    = p.get("estimated_duration_hours")
                row["plan_emp"]      = p.get("employees_needed")
            elif stage == "action":
                row["act_status"]    = p.get("status")
                row["act_approval"]  = p.get("approval_required")
                row["act_workorder"] = (p.get("work_order_id") or "")[:30]
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT_DIR / "summary.csv", index=False)

    # Aggregate metrics
    n = len(traces)
    n_complete = sum(1 for t in traces if all(t["stages"].get(s, {}).get("parsed") for s in ["monitoring","diagnosing","planning","action"]))
    total_lat = [t["total_elapsed_s"] for t in traces]
    print(f"\n=== AGGREGATE ===")
    print(f"  Cases: {n}; complete-pipeline (all 4 stages parsed): {n_complete}/{n}")
    print(f"  Total per-case latency: median={np.median(total_lat):.1f}s, max={np.max(total_lat):.1f}s")
    for stage in ["monitoring", "diagnosing", "planning", "action"]:
        ls = [t["stages"][stage]["elapsed_s"] for t in traces if stage in t["stages"]]
        if ls:
            print(f"  Stage {stage:11s} ({AGENT_LLM[stage]:25s}): median={np.median(ls):.1f}s, max={np.max(ls):.1f}s")

    print(f"\n[Multi-Agent Pipeline] saved trace.json + summary.csv to {OUT_DIR}")

if __name__ == "__main__":
    main()
