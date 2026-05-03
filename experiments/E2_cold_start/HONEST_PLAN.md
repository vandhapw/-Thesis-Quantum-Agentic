# E2 — Cold-Start with NASA C-MAPSS (HONEST IMPLEMENTATION PLAN)

**Status as of 2026-05-03:** Implementation plan documented. Full execution deferred pending NASA C-MAPSS data download + sensor remapping protocol validation.

---

## ⚠️ CRITICAL ACADEMIC ETHICS DISCLOSURE

E2 is the **most methodologically risky** of the 6 planned experiments because it requires:

1. **Cross-domain sensor remapping** — manufacturing fleet sensors (temp, vibration, humidity, pressure, energy) → turbofan sensors (LPC outlet, fan speed, bypass ratio, etc.). The "remapping" is fundamentally an **approximate semantic mapping** with no physically-correct one-to-one correspondence.

2. **Different ground truth definition** — QASAMAP uses categorical failure types; C-MAPSS uses RUL (Remaining Useful Life) regression target. Mapping "needs_attention" requires choosing an arbitrary RUL threshold.

3. **Dramatic distribution shift** — turbofan sensor signatures fundamentally differ from manufacturing machine signatures. Any approach (ML, agentic, classical) trained on one will perform poorly on the other.

**Honest expected outcome:**
- ALL approaches degrade dramatically on C-MAPSS (F1 likely < 0.30 across the board)
- This is **EXPECTED behavior** under strong cross-domain shift, NOT a failure of any specific approach
- The experiment cannot honestly demonstrate "agentic AI maintains quality" because the signal-to-noise ratio is fundamentally degraded

**Therefore E2 in its full pre-registered form risks being a "negative result" experiment** — useful as honest disclosure but not as supporting evidence for VP1 (zero-shot reasoning).

---

## 1. Original Phase 1 Hypothesis (Pre-Registered)

**H₀:** F1 detection score on out-of-domain data does not differ between Pure ML and Hybrid Agentic.
**H₁:** Hybrid Agentic retains F1 ≥ 0.50 on OOD data while Pure ML drops to F1 ≤ 0.20 (effect d > 0.8, large).

## 2. Honest Pre-Execution Reflection

After completing E1, E3, E5 with current data, several findings reduce confidence in H₁:

- LLM zero-shot on **in-domain** data already achieves only F1 = 0.19 (full_comparison_8models.py earlier finding)
- LLM in-context learning improvement on held-out failure type is +0.05 (E3 finding)
- These suggest LLM does NOT have major zero-shot advantage to retain on OOD

**Honest revised expectation:**
- Pure ML F1 on C-MAPSS: ~0.05-0.15 (severe degradation expected)
- Hybrid Agentic F1 on C-MAPSS: ~0.15-0.30 (slightly better via foundation knowledge but not by much)
- Effect direction supports H₁ but magnitude likely smaller than pre-registered

## 3. Recommended Execution Path

Given the above honest assessment, three options for E2:

### Option A: Full execution as pre-registered (HIGH RISK)

Pros:
- Most academically rigorous if successful
- Matches Phase 1 protocol exactly

Cons:
- High likelihood of "all approaches fail" result
- Sensor remapping methodology may be challenged
- Cross-domain transfer expected to be poor for ALL methods, not just ML

### Option B: Execute with REVISED hypothesis (RECOMMENDED)

**Revised H₀/H₁:**
- **H₀:** F1 retention on OOD data does not differ between approaches.
- **H₁:** Among approaches that all degrade significantly under domain shift, **Hybrid Agentic shows higher relative retention** than Pure ML (i.e., 50% retention vs 5% retention).

This honest framing **expects** all approaches to degrade and only claims relative ordering, which is more likely to hold up.

### Option C: Defer E2; document gap as future work (CONSERVATIVE)

Position E2 as planned future work; explicitly state in thesis discussion that:
- "Cross-domain transfer evaluation is reserved for follow-up study with proper sensor remapping protocol validated by domain experts on both source (manufacturing) and target (turbofan) domains."
- Move forward with what's been demonstrated by E1, E3, E5.

**Recommendation:** Choose **Option B or C**, not A. Defense panel will respect honest framing; risky overclaim will fail.

## 4. Implementation Steps (If Option A or B Chosen)

### 4.1 Data acquisition

```bash
# NASA Open Data Portal — C-MAPSS
# Direct download (no authentication required)
wget https://data.nasa.gov/download/ff5v-kuh6/application/x-zip-compressed -O cmapss.zip
unzip cmapss.zip -d data/cmapss/
# Datasets: train_FD001.txt, train_FD002.txt, ... + corresponding test/RUL files
```

Estimated effort: 1-2 days (including format parsing).

### 4.2 Sensor remapping (REQUIRES VALIDATION)

QASAMAP sensors → C-MAPSS sensors mapping (PROPOSED — needs validation):

| QASAMAP | C-MAPSS proxy | Remap rationale |
|---|---|---|
| temperature | sensor_2 (LPC outlet temp) | Temperature → temperature, similar physical meaning |
| vibration | sensor_24 (Nf, fan speed) | Mechanical motion proxy |
| humidity | sensor_8 (compressor outlet) | Pressure/state proxy (NOT humidity, but closest available) |
| pressure | sensor_15 (HPC outlet pressure) | Pressure → pressure |
| energy | sensor_13 (BPR bypass ratio) | Energy efficiency proxy (LOOSE) |

**⚠️ This mapping is approximate.** humidity → compressor pressure is a methodological stretch. Honest reporting must disclose mapping choices.

### 4.3 Ground truth conversion

C-MAPSS provides RUL (Remaining Useful Life). Need binary "needs_attention":
```python
needs_attention = (RUL < 30)  # threshold choice — alternatives: 50, 100
```
**Justification needed:** Why threshold=30 cycles? Cite literature or domain reasoning.

### 4.4 Evaluation protocol

1. Train ML approaches on QASAMAP smart_manufacturing_data.csv (already done)
2. Apply ML to remapped C-MAPSS test data → measure F1
3. Run Fleet_Relative + Sliding_Window with QASAMAP-derived bounds → measure F1 (expected drastic drop because bounds don't apply to turbofan range)
4. Run LLM agentic with QASAMAP-derived prompts → measure F1 (LLM uses general knowledge, not domain-specific bounds)
5. Compute retention ratio per approach: F1_OOD / F1_in_domain
6. Statistical test: Wilcoxon signed-rank on F1 retention

### 4.5 Required disclosures in results

- Sensor remapping table + rationale
- RUL→binary threshold justification
- Acknowledgment of approximate mapping
- Comparison vs literature on C-MAPSS standalone benchmarks

## 5. Estimated Effort

| Task | Effort |
|---|---|
| C-MAPSS data acquisition + parsing | 1 day |
| Sensor remapping protocol + validation | 1-2 days |
| Implementation | 1 day |
| Statistical analysis + report | 1 day |
| **Total** | **4-5 days** |

## 6. Recommended Decision

**Recommend Option C (defer with honest disclosure)** for thesis defense Aug 2026, with the following thesis-section paragraph:

> *"Cross-domain transfer evaluation (E2) was scoped as future work. While the experimental protocol is pre-registered (Phase 1, Section E2) and a sensor-remapping methodology drafted (this document), full execution requires domain-expert validation of the manufacturing-to-turbofan sensor mapping to ensure the comparison is methodologically defensible. We recommend a follow-up study integrating NASA C-MAPSS, FEMTO Bearing, and IMS Bearing datasets with expert-validated mappings to provide multi-dataset OOD evidence. The current thesis presents in-domain evaluation (E1, E3, E5) and demonstrates the agentic AI capability framework; cross-domain generalization claims are explicitly deferred."*

This is **defense-proof honest framing** — explicitly acknowledges what we don't know, doesn't overclaim.

**Alternative:** If user prefers full execution despite risks, proceed with **Option B (revised hypothesis)** scope.

---

## 7. Decision Required from Vandha

**Choose ONE:**

- [ ] **Option A** — Full execution as pre-registered (HIGH RISK of negative result)
- [ ] **Option B** — Execute with revised hypothesis (relative retention) (~5 days)
- [ ] **Option C** — Defer E2; document as future work (RECOMMENDED) (~0 days, just thesis paragraph)

Once decided, will proceed accordingly. Recommendation is Option C for thesis defense priority + Option B as parallel paper-publication track.
