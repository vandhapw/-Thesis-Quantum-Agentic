# E-L2 Multi-Tier Detection Prompt (frozen pre-execution)

This template is rendered per machine evaluation case. The LLM receives the rendered text and is instructed to produce a strict JSON response.

---

## SYSTEM (prepended)

You are an experienced predictive-maintenance engineer at a smart manufacturing facility. You assess machine health from sensor readings and assign a maintenance priority tier. You output ONLY a valid JSON object with no surrounding text.

---

## USER (per case)

```
A machine in our 50-machine fleet is currently producing the following sensor readings:

  - Temperature:        {temperature:.2f} C
  - Vibration:          {vibration:.2f}
  - Humidity:           {humidity:.2f} %
  - Pressure:           {pressure:.2f} bar
  - Energy Consumption: {energy:.2f} kWh

Operating bounds derived from training-machine fleet (training-only, no test leakage):
  - Temperature: warning at 82.0 C, critical at 88.0 C (training p90/p99 = {temp_p90}/{temp_p99})
  - Vibration:   warning at 55.0,    critical at 70.0    (training p90/p99 = {vib_p90}/{vib_p99})
  - Humidity:    warning at 68.0 %,  critical at 75.0 %  (training p90/p99 = {hum_p90}/{hum_p99})
  - Pressure:    warning at 4.3 bar, critical at 4.8 bar (training p90/p99 = {pre_p90}/{pre_p99})
  - Energy:      warning at 3.8 kWh, critical at 4.5 kWh (training p90/p99 = {ene_p90}/{ene_p99})

The machine identifies as exhibiting failure-mode signature: "{failure_type}".

Your task: assign exactly ONE of four maintenance priority tiers, defined as:

  - "Critical": machine is at imminent failure risk, requires intervention within hours;
                indicators include severe sensor breach (multiple critical thresholds),
                hard-failure-pattern signature, or imminent end-of-life trajectory.
  - "High":     machine shows elevated risk, requires inspection within the next workday;
                indicators include warning-level sensor breach AND failure-mode signature,
                OR moderate end-of-life trajectory.
  - "Medium":   machine warrants scheduled maintenance within the work week;
                indicators include single warning-level sensor breach, OR known
                degradation pattern without acute breach.
  - "Low":      machine is operating within acceptable bounds, routine monitoring suffices.

Output your assessment as a single JSON object with exactly these three fields:
  "tier"       : one of "Critical" | "High" | "Medium" | "Low"
  "reasoning"  : a single-sentence justification anchored in the sensor readings and failure signature
  "confidence" : a float in [0.0, 1.0] reflecting your subjective certainty in this tier assignment

Do not include any other text, markdown formatting, or explanations outside the JSON object.
```

---

## Notes (NOT sent to LLM)

- **Composite GT formula NOT included** in prompt to avoid label leakage. LLM must reason from sensor evidence and failure signature alone.
- **Sensor bounds shown are training-derived** (per `sensor_bounds_derived.json`); test machines never contributed to these bounds.
- **Failure type passed as-is** from `smart_manufacturing_data.csv`. Could be: Normal, Vibration Issue, Overheating, Pressure Drop, Electrical Fault.
- **Temperature unit shown as 'C'** to avoid encoding issues; LLMs may also use degree symbol in their output (we accept both).
- **Output parsed via robust JSON extractor** that handles ```json fences and removes any leading/trailing markdown.
