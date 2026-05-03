"""
Visualizations for the multi-agent pipeline (Monitoring -> Diagnosing -> Planning -> Action).
Produces three figures:
  1. pipeline_architecture.png : block diagram of the 4-stage pipeline + LLM assignment
  2. latency_breakdown.png     : stacked bar of per-stage latency per machine
  3. trace_table.png           : sample-trace table image (ready for LaTeX include)
"""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

OUT_DIR = Path(r"D:/AI-LLM/Claude Experiment/Ver13/experiments/E-L2-MultiAgent_Pipeline")

with open(OUT_DIR / "trace.json") as f:
    traces = json.load(f)

AGENT_LLM = {
    "monitoring": "glm-5.1:cloud",
    "diagnosing": "deepseek-v4-pro:cloud",
    "planning":   "kimi-k2.6:cloud",
    "action":     "deepseek-v4-pro:cloud",
}

# -----------------------------------------------------------------------------
# Figure 1: Pipeline architecture
# -----------------------------------------------------------------------------
def fig_architecture():
    fig, ax = plt.subplots(figsize=(15, 6))
    ax.set_xlim(0, 16); ax.set_ylim(0, 6); ax.axis("off")

    stages = [
        ("Monitoring",  "glm-5.1:cloud",         "#3b82f6",  3.5,  "sensor + classifier\nevidence",       "status, severity,\nflagged_sensors"),
        ("Diagnosing",  "deepseek-v4-pro:cloud", "#10b981",  6.5,  "monitoring out +\nfailure type + RUL", "root_cause,\naffected_component"),
        ("Planning",    "kimi-k2.6:cloud",       "#f59e0b",  9.5,  "diagnosis +\ncontext",                "action, priority,\nemployees, duration"),
        ("Action",      "deepseek-v4-pro:cloud", "#8b5cf6", 12.5,  "plan + machine_id",                   "work_order_id,\napproval_required"),
    ]
    box_h = 1.4; box_w = 2.2

    for i, (name, llm, color, x, inputs, outputs) in enumerate(stages):
        box = FancyBboxPatch((x - box_w/2, 2.5), box_w, box_h,
                              boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor="black", linewidth=1.5, alpha=0.85)
        ax.add_patch(box)
        ax.text(x, 3.5, f"Stage {i+1}", ha="center", va="center", fontsize=10, color="white", fontweight="bold")
        ax.text(x, 3.05, name, ha="center", va="center", fontsize=14, color="white", fontweight="bold")
        ax.text(x, 2.65, llm, ha="center", va="center", fontsize=8, color="white", style="italic")

        ax.text(x, 4.55, inputs, ha="center", va="center", fontsize=8, color="black",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#f3f4f6", edgecolor="#9ca3af", alpha=0.9))
        ax.text(x, 1.75, outputs, ha="center", va="center", fontsize=8, color="black",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#fef3c7", edgecolor="#d97706", alpha=0.9))

        if i < len(stages) - 1:
            arrow = FancyArrowPatch((x + box_w/2 + 0.05, 3.2), (stages[i+1][3] - box_w/2 - 0.05, 3.2),
                                     arrowstyle="->", mutation_scale=20, lw=2, color="#374151")
            ax.add_patch(arrow)

    ax.text(8, 5.7, "Multi-Agent Pipeline for Monitoring → Diagnosing → Planning → Action",
            ha="center", va="center", fontsize=15, fontweight="bold")
    ax.text(8, 5.3, "Sequential 4-stage agentic pipeline with role-specialised LLM assignment",
            ha="center", va="center", fontsize=10, style="italic", color="#4b5563")

    # Input source (LEFT, well separated from Stage 1)
    ax.text(1.0, 3.2, "Layer 1\noutput\n(sensor +\nclassifier)", ha="center", va="center", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#dbeafe", edgecolor="#2563eb"))
    ax.add_patch(FancyArrowPatch((1.7, 3.2), (stages[0][3] - box_w/2 - 0.05, 3.2),
                                  arrowstyle="->", mutation_scale=15, lw=1.5, color="#374151"))

    # Output sink (RIGHT, well separated from Stage 4)
    ax.text(15.0, 3.2, "CMMS\nwork order\ndispatch", ha="center", va="center", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#ede9fe", edgecolor="#7c3aed"))
    ax.add_patch(FancyArrowPatch((stages[-1][3] + box_w/2 + 0.05, 3.2), (14.3, 3.2),
                                  arrowstyle="->", mutation_scale=15, lw=1.5, color="#374151"))

    legend_h = mpatches.Patch(facecolor="#f3f4f6", edgecolor="#9ca3af", label="Stage input")
    legend_o = mpatches.Patch(facecolor="#fef3c7", edgecolor="#d97706", label="Stage output (JSON)")
    ax.legend(handles=[legend_h, legend_o], loc="lower center", ncol=2, frameon=False,
              bbox_to_anchor=(0.5, 0.02))

    plt.tight_layout()
    out = OUT_DIR / "pipeline_architecture.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")

# -----------------------------------------------------------------------------
# Figure 2: Latency breakdown stacked bar
# -----------------------------------------------------------------------------
def fig_latency():
    machines = [f"M-{t['machine_id']}\n({t['gt_tier']})" for t in traces]
    stages_order = ["monitoring", "diagnosing", "planning", "action"]
    colors = {"monitoring":"#3b82f6","diagnosing":"#10b981","planning":"#f59e0b","action":"#8b5cf6"}

    data = {s: [t["stages"][s]["elapsed_s"] for t in traces] for s in stages_order}

    fig, ax = plt.subplots(figsize=(11, 5))
    bottom = np.zeros(len(machines))
    for s in stages_order:
        bars = ax.bar(machines, data[s], bottom=bottom, label=f"{s} ({AGENT_LLM[s]})",
                       color=colors[s], edgecolor="white", linewidth=0.5)
        # annotate per-bar
        for bar, v in zip(bars, data[s]):
            if v > 1.5:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_y() + bar.get_height()/2,
                        f"{v:.1f}s", ha="center", va="center", fontsize=8, color="white", fontweight="bold")
        bottom += np.array(data[s])

    # 60s budget line
    ax.axhline(y=60, color="red", linestyle="--", linewidth=1.5, label="60-s Kafka cycle budget")

    # totals annotated above each bar
    for i, m in enumerate(machines):
        total = bottom[i]
        ax.text(i, total + 1.5, f"{total:.1f}s", ha="center", fontsize=9, fontweight="bold")

    ax.set_xlabel("Machine (GT criticality tier)", fontsize=11)
    ax.set_ylabel("Wall-clock latency (s)", fontsize=11)
    ax.set_title("Per-stage latency breakdown across 5 demo machines", fontsize=13, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9, ncol=1)
    ax.set_ylim(0, max(70, bottom.max() * 1.15))
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    out = OUT_DIR / "latency_breakdown.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")

# -----------------------------------------------------------------------------
# Figure 3: Trace table (rendered as matplotlib image for LaTeX inclusion)
# -----------------------------------------------------------------------------
def fig_trace_table():
    rows = []
    for t in traces:
        m = t["machine_id"]; gt = t["gt_tier"]
        mon = t["stages"]["monitoring"]["parsed"] or {}
        diag = t["stages"]["diagnosing"]["parsed"] or {}
        plan = t["stages"]["planning"]["parsed"] or {}
        act = t["stages"]["action"]["parsed"] or {}
        rows.append([
            f"M-{m}", gt,
            f"{mon.get('status','?')}/{mon.get('severity','?')}",
            (diag.get("root_cause","")[:35]),
            f"{plan.get('action','?')}/{plan.get('priority','?')}",
            f"{plan.get('estimated_duration_hours','?')}h × {plan.get('employees_needed','?')}emp",
            ("Dispatch" if act.get("status") == "dispatched" else "Approval"),
            f"{t['total_elapsed_s']:.1f}s",
        ])
    headers = ["Machine", "GT tier", "Monitoring\n(status/sev)", "Diagnosing\n(root_cause)",
                "Planning\n(action/prio)", "Resource\n(dur × emp)", "Action\n(decision)", "Total\nlatency"]

    fig, ax = plt.subplots(figsize=(13.5, 0.65 * (len(rows)+2.5)))
    ax.axis("off")
    table = ax.table(cellText=rows, colLabels=headers, loc="center", cellLoc="left",
                      colWidths=[0.07, 0.08, 0.13, 0.27, 0.12, 0.13, 0.12, 0.08])
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.7)

    # color header row
    for i, _ in enumerate(headers):
        table[(0, i)].set_facecolor("#1f2937")
        table[(0, i)].set_text_props(color="white", fontweight="bold")
    # tier color coding
    tier_colors = {"Critical": "#fecaca", "High": "#fed7aa", "Medium": "#fef3c7", "Low": "#dcfce7"}
    for ri, row in enumerate(rows, start=1):
        c = tier_colors.get(row[1], "white")
        table[(ri, 1)].set_facecolor(c)
        # action coloring
        ac = row[6]
        table[(ri, 6)].set_facecolor("#fde68a" if ac == "Approval" else "#bbf7d0")

    plt.title("Sample pipeline trace across 5 demo machines (M-29 Critical → M-15 Low)",
              fontsize=12, fontweight="bold", pad=15)
    plt.tight_layout()
    out = OUT_DIR / "trace_table.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")

if __name__ == "__main__":
    fig_architecture()
    fig_latency()
    fig_trace_table()
