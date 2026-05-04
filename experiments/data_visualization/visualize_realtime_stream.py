"""
Academic visualization: real-time streaming behaviour of the QASAMAP
Kafka-driven inference pipeline.

Complements the dual-mode architecture diagram (data_sources_architecture.png)
by zooming in on the streaming-only path. Generates a single multi-panel
figure suitable for inclusion in the thesis Methods chapter (subsection
'Data Sources and Characteristics').

Panel layout (3 rows):
  (A) Kafka topology  : producer -> broker (partitioned by machine_id) ->
                        consumer group with the sliding window buffer.
  (B) Event timeline  : 8 sample machines, 30-minute window, one marker per
                        Kafka event (1/min); marker colour = anomaly flag,
                        marker size = downtime_risk. Sourced from the real
                        100k-row CSV.
  (C) 60-s decision   : end-to-end latency budget from event arrival to
       budget          dispatched work order, broken into Layer 1 / Layer 2 /
                       Layer 3 components with the empirical p95 numbers
                       already reported in Chapters 4-6.
"""
import math
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle

DATA_CSV = r"D:/AI-LLM/Claude Experiment/Ver13/smart_manufacturing_data.csv"
OUT_DIR  = Path(r"D:/AI-LLM/Claude Experiment/Ver13/experiments/data_visualization")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Panel A: Kafka topology
# ---------------------------------------------------------------------------
def draw_kafka_topology(ax):
    ax.set_xlim(0, 16); ax.set_ylim(0, 6.2); ax.axis("off")
    ax.text(8, 5.85, "(A) Kafka real-time streaming topology",
            ha="center", va="center", fontsize=12, fontweight="bold")

    # Producers (left) - digital twin per machine
    prod_x = 1.6
    for k, y in enumerate([4.6, 3.7, 2.8, 1.9, 1.0]):
        c = Circle((prod_x, y), 0.22, facecolor="#10b981", edgecolor="black", lw=1.0)
        ax.add_patch(c)
        ax.text(prod_x, y, f"M{k+1}", ha="center", va="center",
                fontsize=7, color="white", fontweight="bold")
    ax.text(prod_x, 0.5, "...", ha="center", fontsize=12, fontweight="bold")
    ax.text(prod_x, 5.05, "Digital-twin\nproducers\n(50 machines\n× 1 evt/min)",
            ha="center", va="bottom", fontsize=8.5, color="#15803d", fontweight="bold")

    # Broker (middle) - 4 partitions
    broker_x0, broker_y0, broker_w, broker_h = 5.0, 0.7, 4.0, 4.2
    ax.add_patch(FancyBboxPatch((broker_x0, broker_y0), broker_w, broker_h,
                                 boxstyle="round,pad=0.08",
                                 facecolor="#fef3c7", edgecolor="#d97706", lw=1.6))
    ax.text(broker_x0 + broker_w/2, broker_y0 + broker_h + 0.15,
            "Kafka broker (localhost:9092)\ntopic: sensor_stream",
            ha="center", va="bottom", fontsize=9, color="#92400e", fontweight="bold")

    part_h = (broker_h - 0.4) / 4
    for k in range(4):
        py = broker_y0 + 0.2 + k * part_h
        ax.add_patch(Rectangle((broker_x0 + 0.25, py), broker_w - 0.5, part_h - 0.15,
                               facecolor="#fde68a", edgecolor="#92400e", lw=0.8))
        ax.text(broker_x0 + 0.45, py + (part_h - 0.15)/2,
                f"partition {3-k}", ha="left", va="center", fontsize=8,
                color="#92400e", fontweight="bold")
        # tiny event markers
        for j in range(8):
            ex = broker_x0 + 1.7 + j * 0.28
            ax.add_patch(Rectangle((ex, py + 0.10), 0.18, part_h - 0.35,
                                   facecolor="#16a34a" if (j + k) % 5 != 0 else "#dc2626",
                                   edgecolor="white", lw=0.4))
    ax.text(broker_x0 + broker_w/2, broker_y0 - 0.25,
            "partitioned by machine_id (hash mod 4); per-key ordering preserved",
            ha="center", va="top", fontsize=8, style="italic", color="#92400e")

    # Producer -> broker arrows
    for y in [4.6, 3.7, 2.8, 1.9, 1.0]:
        ax.add_patch(FancyArrowPatch((prod_x + 0.22, y), (broker_x0 - 0.05, y),
                                      arrowstyle="->", mutation_scale=12,
                                      lw=0.9, color="#16a34a", alpha=0.7))

    # Consumer group (right)
    cons_x0, cons_y0, cons_w, cons_h = 10.4, 0.7, 4.6, 4.2
    ax.add_patch(FancyBboxPatch((cons_x0, cons_y0), cons_w, cons_h,
                                 boxstyle="round,pad=0.08",
                                 facecolor="#dbeafe", edgecolor="#2563eb", lw=1.6))
    ax.text(cons_x0 + cons_w/2, cons_y0 + cons_h + 0.15,
            "Consumer group (group.id=qasamap)\nper-machine sliding buffer (W=10)",
            ha="center", va="bottom", fontsize=9, color="#1e3a8a", fontweight="bold")

    # Per-machine ring buffer schematic
    ring_y = cons_y0 + cons_h - 1.0
    for j in range(10):
        bx = cons_x0 + 0.35 + j * 0.40
        col = "#3b82f6" if j < 8 else ("#94a3b8" if j == 8 else "#e2e8f0")
        ax.add_patch(Rectangle((bx, ring_y), 0.32, 0.55,
                               facecolor=col, edgecolor="black", lw=0.6))
        ax.text(bx + 0.16, ring_y + 0.27, str(j + 1),
                ha="center", va="center", fontsize=7,
                color="white", fontweight="bold")
    # Direction arrow + endpoint annotations (replace the prior "t-9 ... t" lag
    # labels which were easily misread as negative sensor values)
    ax.annotate("", xy=(cons_x0 + 4.20, ring_y - 0.05),
                xytext=(cons_x0 + 0.35, ring_y - 0.05),
                arrowprops=dict(arrowstyle="->", color="#1e3a8a", lw=1.0))
    ax.text(cons_x0 + 0.35, ring_y - 0.30, "oldest event",
            ha="left", va="top", fontsize=7.5, color="#1e3a8a",
            style="italic")
    ax.text(cons_x0 + 4.20, ring_y - 0.30, "newest event",
            ha="right", va="top", fontsize=7.5, color="#1e3a8a",
            style="italic")
    ax.text(cons_x0 + cons_w/2, ring_y - 0.55,
            "ring buffer (W = 10) for one machine — slot index 1 .. 10\n"
            "(oldest-evicted FIFO; new event appended at slot 10)",
            ha="center", va="top", fontsize=8, style="italic", color="#1e3a8a")

    # MongoDB persistence sink
    mongo_y = cons_y0 + 0.55
    ax.add_patch(FancyBboxPatch((cons_x0 + 0.4, mongo_y), 1.6, 0.7,
                                 boxstyle="round,pad=0.05",
                                 facecolor="#7c3aed", edgecolor="black", lw=1.0))
    ax.text(cons_x0 + 1.2, mongo_y + 0.35, "MongoDB\nevent log",
            ha="center", va="center", fontsize=8, color="white", fontweight="bold")

    # Inference handoff
    ax.add_patch(FancyBboxPatch((cons_x0 + 2.4, mongo_y), 1.9, 0.7,
                                 boxstyle="round,pad=0.05",
                                 facecolor="#0ea5e9", edgecolor="black", lw=1.0))
    ax.text(cons_x0 + 3.35, mongo_y + 0.35, "Layer 1\nT-GCN + classifier",
            ha="center", va="center", fontsize=8, color="white", fontweight="bold")

    # Broker -> consumer arrow
    ax.add_patch(FancyArrowPatch((broker_x0 + broker_w + 0.05, broker_y0 + broker_h/2),
                                  (cons_x0 - 0.05, broker_y0 + broker_h/2),
                                  arrowstyle="->", mutation_scale=18, lw=1.6,
                                  color="#1e3a8a"))
    ax.text((broker_x0 + broker_w + cons_x0)/2, broker_y0 + broker_h/2 + 0.25,
            "poll(timeout=1s)", ha="center", fontsize=8, style="italic",
            color="#1e3a8a")


# ---------------------------------------------------------------------------
# Panel B: Event timeline (real CSV slice)
# ---------------------------------------------------------------------------
def draw_event_timeline(ax, df):
    # Use the historical CSV slice for the first 24 h on the first 8
    # machine_ids. The CSV cadence is irregular (the digital-twin records
    # only state-change events), and the panel title makes that explicit
    # rather than misrepresenting a regular 1-min cadence.
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    machines = sorted(df["machine_id"].unique())[:8]
    t0 = df["timestamp"].min().normalize()
    t1 = t0 + pd.Timedelta(hours=24)
    sub = df[(df["timestamp"] >= t0) & (df["timestamp"] < t1) &
             (df["machine_id"].isin(machines))]

    ax.set_title("(B) Per-machine event arrivals over the first 24-hour "
                 "training-CSV window (8 sample machines)",
                 fontsize=11, fontweight="bold", pad=10)

    for row_idx, m in enumerate(machines):
        s = sub[sub["machine_id"] == m].sort_values("timestamp")
        if s.empty:
            continue
        anom = s["anomaly_flag"].values
        dr   = s["downtime_risk"].fillna(0).clip(0, 1).values
        colors = ["#dc2626" if a == 1 else "#3b82f6" for a in anom]
        sizes  = 30 + 220 * dr
        ax.scatter(s["timestamp"], np.full(len(s), row_idx),
                   c=colors, s=sizes, alpha=0.80,
                   edgecolors="black", linewidths=0.4)

    ax.set_yticks(range(len(machines)))
    ax.set_yticklabels([f"M-{m:02d}" for m in machines], fontsize=8.5)
    ax.set_xlabel("event timestamp (irregular cadence; "
                  "digital-twin records state-change events)",
                  fontsize=9.5)
    ax.set_ylabel("machine_id (Kafka partition key)", fontsize=9.5)
    ax.set_xlim(t0, t1)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    ax.grid(axis="x", alpha=0.3)
    ax.tick_params(labelsize=8.5)

    # Legend (manual)
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", label="anomaly_flag = 0 (normal)",
                   markerfacecolor="#3b82f6", markersize=8, markeredgecolor="black"),
        plt.Line2D([0], [0], marker="o", color="w", label="anomaly_flag = 1 (anomaly)",
                   markerfacecolor="#dc2626", markersize=8, markeredgecolor="black"),
        plt.Line2D([0], [0], marker="o", color="w", label="marker size ∝ downtime_risk",
                   markerfacecolor="grey", markersize=12, markeredgecolor="black"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8.5, framealpha=0.92)


# ---------------------------------------------------------------------------
# Panel C: 60-second decision budget
# ---------------------------------------------------------------------------
def draw_latency_budget(ax):
    ax.set_xlim(0, 60); ax.set_ylim(-0.6, 3.6); ax.axis("on")
    ax.set_title("(C) Per-cycle 60-s decision budget — empirical p95 latencies "
                 "from Chapters 4–6",
                 fontsize=11, fontweight="bold", pad=10)

    # Horizontal bar segments showing how latency is consumed
    segments = [
        ("Layer 1: T-GCN forecast\n+ supervised classifier",
            0.0, 0.4, "#0ea5e9", "<1 s"),
        ("Layer 2: 4-stage Multi-Agent Pipeline\n(Monitoring → Diagnosing → Planning → Action)",
            0.4, 32.7 - 0.4, "#10b981", "p95 ≈ 32.7 s"),
        ("Layer 3: scheduling solver\n(GA / SA / TS / Greedy)",
            32.7, 1.5, "#f59e0b", "p95 < 1.5 s"),
        ("Slack (margin to Kafka cycle deadline)",
            34.2, 60 - 34.2, "#e5e7eb", "≥ 25.8 s margin"),
    ]
    y = 1.4
    for label, x0, w, color, annot in segments:
        ax.add_patch(Rectangle((x0, y), w, 0.9,
                               facecolor=color, edgecolor="black", lw=1.0,
                               alpha=0.92))
        if w >= 4.0:
            ax.text(x0 + w/2, y + 0.45, annot,
                    ha="center", va="center", fontsize=9,
                    color="white" if color != "#e5e7eb" else "#374151",
                    fontweight="bold")
    # Stage labels above the bar
    label_positions = [(0.2, "L1"), (16.5, "Layer 2 — Multi-Agent Pipeline"),
                       (33.5, "L3"), (47.0, "headroom")]
    for x, t in label_positions:
        ax.text(x, y + 1.05, t, ha="center", va="bottom", fontsize=9,
                fontweight="bold", color="#374151")

    # Tick marks at second-level stages
    ax.axvline(60, color="#dc2626", linestyle="--", lw=1.5)
    ax.text(60, 0.85, "Kafka cycle deadline (60 s)",
            ha="right", va="bottom", fontsize=9, color="#dc2626",
            fontweight="bold", rotation=0)
    ax.set_xticks([0, 10, 20, 30, 40, 50, 60])
    ax.set_xlabel("seconds since event arrival at Kafka consumer",
                  fontsize=9.5)
    ax.set_yticks([])
    ax.tick_params(labelsize=8.5)
    ax.grid(axis="x", alpha=0.3)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)

    # Footnote referencing where the numbers come from
    ax.text(0, -0.45,
            "Source: Layer 2 latency from Chapter 5 §Multi-Agent Pipeline Demonstration "
            "(5-machine demo, max observed 53.1 s; p95 ≈ 32.7 s); "
            "Layer 3 from Chapter 6 §V2 Follow-Up dynamic re-scheduling (p95 < 1.5 s).",
            fontsize=8, color="#6b7280", style="italic", ha="left", va="top")


# ---------------------------------------------------------------------------
# Composite figure
# ---------------------------------------------------------------------------
def main():
    df = pd.read_csv(DATA_CSV, parse_dates=["timestamp"])

    fig = plt.figure(figsize=(15, 13.5))
    gs = fig.add_gridspec(3, 1, height_ratios=[2.0, 1.7, 1.1],
                          hspace=0.55)

    fig.suptitle("Real-Time Streaming Behaviour of the QASAMAP Kafka Pipeline",
                 fontsize=15, fontweight="bold", y=0.995)

    ax_top = fig.add_subplot(gs[0]); draw_kafka_topology(ax_top)
    ax_mid = fig.add_subplot(gs[1]); draw_event_timeline(ax_mid, df)
    ax_bot = fig.add_subplot(gs[2]); draw_latency_budget(ax_bot)

    plt.tight_layout(rect=[0, 0, 1, 0.985])
    out = OUT_DIR / "data_sources_realtime_stream.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")


if __name__ == "__main__":
    main()
