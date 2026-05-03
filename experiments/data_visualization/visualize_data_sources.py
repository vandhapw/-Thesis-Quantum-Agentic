"""
Academic visualization: dual-mode data architecture for QASAMAP.
Shows the historical batch mode (offline CSV training) and the real-time
streaming mode (Kafka producer -> consumer -> inference) in one
comprehensive figure suitable for inclusion in the thesis Methods chapter
(subsection 'Data Sources and Characteristics').

Generates two complementary figures:
  1. data_sources_architecture.png : architecture / pipeline diagram
                                      (dual-mode batch + stream)
  2. data_sources_distribution.png : sensor distributions + class balance
                                      (descriptive statistics on the actual
                                       100k-row historical CSV)
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

DATA_CSV = r"D:/AI-LLM/Claude Experiment/Ver13/smart_manufacturing_data.csv"
OUT_DIR = Path(r"D:/AI-LLM/Claude Experiment/Ver13/experiments/data_visualization")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# Figure 1: Dual-mode architecture diagram
# -----------------------------------------------------------------------------
def fig_architecture():
    fig, ax = plt.subplots(figsize=(15, 9))
    ax.set_xlim(0, 16); ax.set_ylim(0, 10); ax.axis("off")

    # ===== Title =====
    ax.text(8, 9.55, "QASAMAP Dual-Mode Data Architecture",
            ha="center", va="center", fontsize=17, fontweight="bold")
    ax.text(8, 9.15,
            "Historical batch mode for model training "
            "(offline CSV) + Real-time streaming mode for production inference (Kafka)",
            ha="center", va="center", fontsize=11, style="italic", color="#4b5563")

    # ===== Top lane: Historical Batch (training) =====
    # Lane background
    lane1 = Rectangle((0.5, 5.4), 15.0, 2.9, facecolor="#dbeafe",
                      edgecolor="#2563eb", linewidth=1.5, alpha=0.35)
    ax.add_patch(lane1)
    ax.text(0.85, 8.05, "HISTORICAL BATCH MODE", fontsize=11, fontweight="bold",
            color="#1e40af", rotation=0)
    ax.text(0.85, 7.75, "(offline; used for model training & analysis)", fontsize=8,
            style="italic", color="#1e40af")

    # Boxes for historical mode
    boxes_hist = [
        (2.5,  "Historical CSV\n100k records\n50 machines\n2025-01-01 → 2025-03-11",
                                                         "#3b82f6", "13 variables\n(5 sensors +\n7 labels + ts)"),
        (5.5,  "Feature\nEngineering",
                                                         "#3b82f6", "rolling means\n+ differencing\n+ sliding\nwindow (W=10)"),
        (8.5,  "Model Training\n(GPU: A100 80GB)",
                                                         "#3b82f6", "T-GCN\n+ 5 ensemble\nclassifiers\n+ TabNet"),
        (11.5, "Trained\nArtifacts",
                                                         "#3b82f6", "T-GCN.pth\n+ classifier.pkl\n+ scaler/bounds"),
    ]
    box_w_h, box_h_h = 2.0, 1.5
    for x, label, color, sub in boxes_hist:
        box = FancyBboxPatch((x - box_w_h/2, 6.0), box_w_h, box_h_h,
                              boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor="black", linewidth=1.3, alpha=0.85)
        ax.add_patch(box)
        ax.text(x, 7.05, label, ha="center", va="center", fontsize=9.5,
                color="white", fontweight="bold")
        ax.text(x, 6.25, sub, ha="center", va="center", fontsize=7,
                color="white", style="italic")

    # arrows historical
    for i in range(len(boxes_hist) - 1):
        x1 = boxes_hist[i][0] + box_w_h/2 + 0.05
        x2 = boxes_hist[i+1][0] - box_w_h/2 - 0.05
        ax.add_patch(FancyArrowPatch((x1, 6.75), (x2, 6.75), arrowstyle="->",
                                      mutation_scale=18, lw=1.7, color="#1e3a8a"))

    # Hand-off label (historical → streaming via "deploy")
    ax.text(13.5, 5.55, "deploy trained\nmodels & bounds",
            ha="center", va="center", fontsize=8, style="italic",
            color="#1e3a8a",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#fef3c7",
                      edgecolor="#d97706"))
    ax.add_patch(FancyArrowPatch((11.5, 6.0), (11.5, 4.65),
                                  arrowstyle="->", mutation_scale=20,
                                  lw=2.0, color="#d97706"))

    # ===== Bottom lane: Real-time Streaming =====
    lane2 = Rectangle((0.5, 1.6), 15.0, 3.0, facecolor="#dcfce7",
                      edgecolor="#16a34a", linewidth=1.5, alpha=0.35)
    ax.add_patch(lane2)
    ax.text(0.85, 4.35, "REAL-TIME STREAMING MODE", fontsize=11, fontweight="bold",
            color="#15803d", rotation=0)
    ax.text(0.85, 4.05,
            "(production inference; 1 event / machine / minute via Apache Kafka)",
            fontsize=8, style="italic", color="#15803d")

    boxes_stream = [
        (2.0,  "Digital Twin\nSimulator",
                                                         "#10b981", "produces 1 event\nper machine per\nminute (50/min)"),
        (4.7,  "Kafka Topic\nsensor_stream",
                                                         "#10b981", "broker:\nlocalhost:9092\npartition by\nmachine_id"),
        (7.4,  "Kafka Consumer\n+ MongoDB",
                                                         "#10b981", "buffer last\n10 events per\nmachine; persist\nto MongoDB"),
        (10.1, "Layer 1\nT-GCN Forecast\n+ Classifier",
                                                         "#10b981", "30-min ahead\nforecast +\nanomaly_flag,\nRUL, downtime"),
        (13.0, "Layer 2 + 3\nLLM Ensemble\n+ Scheduler",
                                                         "#10b981", "tier classify\n→ schedule via\nclassical heur.\n(p95 < 60s)"),
    ]
    box_w_s, box_h_s = 2.1, 1.6
    for x, label, color, sub in boxes_stream:
        box = FancyBboxPatch((x - box_w_s/2, 2.2), box_w_s, box_h_s,
                              boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor="black", linewidth=1.3, alpha=0.85)
        ax.add_patch(box)
        ax.text(x, 3.40, label, ha="center", va="center", fontsize=9.5,
                color="white", fontweight="bold")
        ax.text(x, 2.55, sub, ha="center", va="center", fontsize=7,
                color="white", style="italic")

    for i in range(len(boxes_stream) - 1):
        x1 = boxes_stream[i][0] + box_w_s/2 + 0.05
        x2 = boxes_stream[i+1][0] - box_w_s/2 - 0.05
        ax.add_patch(FancyArrowPatch((x1, 3.0), (x2, 3.0), arrowstyle="->",
                                      mutation_scale=18, lw=1.7, color="#14532d"))

    # ===== Output box (right side) =====
    out_box = FancyBboxPatch((13.6, 0.55), 2.0, 0.95,
                              boxstyle="round,pad=0.08",
                              facecolor="#a78bfa", edgecolor="black", linewidth=1.3)
    ax.add_patch(out_box)
    ax.text(14.6, 1.20, "Maintenance\nDecision +\nWork Order",
            ha="center", va="center", fontsize=9, color="white", fontweight="bold")
    ax.add_patch(FancyArrowPatch((13.0, 2.2), (14.6, 1.55),
                                  arrowstyle="->", mutation_scale=18, lw=1.7,
                                  color="#7c3aed"))

    # ===== Continuous learning loop arrow =====
    ax.add_patch(FancyArrowPatch((13.0, 4.0), (8.5, 5.95),
                                  connectionstyle="arc3,rad=0.3",
                                  arrowstyle="->", mutation_scale=18,
                                  lw=1.5, color="#dc2626", linestyle="--"))
    ax.text(11.0, 5.05, "feedback loop\n(retrain trigger\nevery N records)",
            ha="center", va="center", fontsize=8, style="italic", color="#dc2626")

    # ===== Footnote / data summary at bottom =====
    ax.text(0.5, 0.45,
            "Historical CSV: 100,000 rows × 13 columns; "
            "anomaly_flag prevalence 8.92\\%; failure_type imbalance "
            "(Normal 91.9\\% vs Electrical Fault 1.0\\%); "
            "RUL near-uniform (mean 234.27 h, std 150.06 h).",
            ha="left", va="bottom", fontsize=8.5, color="#374151", wrap=True)
    ax.text(0.5, 0.10,
            "Streaming target throughput: 50 machines × 1 event/min = 3000 events/h; "
            "real-time deadline: end-to-end Layer 1 → Layer 3 within 60 s Kafka cycle.",
            ha="left", va="bottom", fontsize=8.5, color="#374151")

    plt.tight_layout()
    out = OUT_DIR / "data_sources_architecture.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")

# -----------------------------------------------------------------------------
# Figure 2: Sensor distributions + class balance (descriptive stats)
# -----------------------------------------------------------------------------
def fig_distribution():
    df = pd.read_csv(DATA_CSV)
    sensors = ["temperature", "vibration", "humidity", "pressure", "energy_consumption"]
    sensor_units = ["°C", "(units)", "%", "bar", "kWh"]

    fig = plt.figure(figsize=(14, 8.5))
    gs = fig.add_gridspec(3, 5, height_ratios=[1.4, 1.0, 1.0], hspace=0.55, wspace=0.45)

    fig.suptitle("Historical Dataset Descriptive Statistics (100,000 rows × 50 machines × 69 days)",
                 fontsize=14, fontweight="bold", y=0.995)

    # Row 1: per-sensor violin (anomaly vs normal)
    for j, (s, unit) in enumerate(zip(sensors, sensor_units)):
        ax = fig.add_subplot(gs[0, j])
        normal = df[df["anomaly_flag"] == 0][s].values
        anom   = df[df["anomaly_flag"] == 1][s].values
        # subsample for fast plotting
        rng = np.random.default_rng(42)
        if len(normal) > 5000: normal = rng.choice(normal, 5000, replace=False)
        if len(anom)   > 5000: anom   = rng.choice(anom,   5000, replace=False)
        parts = ax.violinplot([normal, anom], positions=[0, 1], showmedians=True,
                               widths=0.7)
        for pc, color in zip(parts["bodies"], ["#3b82f6", "#dc2626"]):
            pc.set_facecolor(color); pc.set_alpha(0.65)
        ax.set_xticks([0, 1]); ax.set_xticklabels(["Normal", "Anomaly"], fontsize=8)
        ax.set_title(f"{s}\n{unit}", fontsize=9.5, fontweight="bold")
        ax.tick_params(axis="y", labelsize=7.5)
        ax.grid(axis="y", alpha=0.25)

    # Row 2 (panel 0-2): failure type distribution
    ax_ft = fig.add_subplot(gs[1, 0:3])
    ft_counts = df["failure_type"].value_counts()
    colors = ["#3b82f6", "#f59e0b", "#10b981", "#8b5cf6", "#dc2626"]
    bars = ax_ft.bar(ft_counts.index, ft_counts.values,
                      color=colors[:len(ft_counts)], edgecolor="white")
    for bar, v in zip(bars, ft_counts.values):
        pct = 100 * v / len(df)
        ax_ft.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1500,
                   f"{v:,}\n({pct:.1f}%)", ha="center", fontsize=8.5, fontweight="bold")
    ax_ft.set_title("Failure Type Distribution (severe class imbalance)",
                     fontsize=11, fontweight="bold")
    ax_ft.set_ylabel("count", fontsize=9.5)
    ax_ft.tick_params(axis="x", labelsize=9, rotation=15)
    ax_ft.tick_params(axis="y", labelsize=8.5)
    ax_ft.grid(axis="y", alpha=0.3)

    # Row 2 (panel 3-4): RUL distribution
    ax_rul = fig.add_subplot(gs[1, 3:5])
    rul = df["predicted_remaining_life"].values
    ax_rul.hist(rul, bins=50, color="#10b981", alpha=0.75, edgecolor="white")
    ax_rul.axvline(50, color="orange", linestyle="--", lw=1.5, label="critical (<50h)")
    ax_rul.axvline(10, color="red",    linestyle="--", lw=1.5, label="imminent (<10h)")
    ax_rul.set_title(f"RUL Distribution  (mean {rul.mean():.0f}h, std {rul.std():.0f}h)",
                      fontsize=11, fontweight="bold")
    ax_rul.set_xlabel("predicted_remaining_life (hours)", fontsize=9.5)
    ax_rul.set_ylabel("count", fontsize=9.5)
    ax_rul.legend(fontsize=8.5)
    ax_rul.tick_params(labelsize=8.5)
    ax_rul.grid(alpha=0.3)

    # Row 3: time-series example (machine 40, sample sensor)
    ax_ts = fig.add_subplot(gs[2, :])
    sub = df[df["machine_id"] == 40].head(200)   # first 200 minutes for one machine
    sub_ts = pd.to_datetime(sub["timestamp"])
    for s, c in zip(sensors, ["#dc2626", "#f59e0b", "#10b981", "#8b5cf6", "#3b82f6"]):
        # normalize for visual comparison
        v = sub[s].values
        v_norm = (v - v.min()) / (v.max() - v.min() + 1e-9)
        ax_ts.plot(sub_ts, v_norm, label=s, color=c, lw=1.3, alpha=0.9)
    ax_ts.set_title("Sample Sensor Trace, Machine M-40, first 200 minutes (normalised to [0,1] for visual comparison)",
                     fontsize=11, fontweight="bold")
    ax_ts.set_xlabel("timestamp (1-minute Kafka cycle)", fontsize=9.5)
    ax_ts.set_ylabel("normalised value", fontsize=9.5)
    ax_ts.legend(loc="upper right", fontsize=8.5, ncol=5)
    ax_ts.tick_params(labelsize=8.5)
    ax_ts.grid(alpha=0.3)

    plt.tight_layout()
    out = OUT_DIR / "data_sources_distribution.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"saved {out}")

if __name__ == "__main__":
    fig_architecture()
    fig_distribution()
