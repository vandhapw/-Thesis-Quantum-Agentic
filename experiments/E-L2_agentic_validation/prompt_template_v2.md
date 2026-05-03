# E-L2 Multi-Tier Detection Prompt V2 (Option A REMEDIATION DRAFT)

**Status:** DRAFT — NOT EXECUTED. Awaits supervisor approval.

**Changes vs V1:**
1. Tier definitions now use **concrete numeric thresholds** instead of vague "warning-level breach"
2. Added **4 worked examples** (one per tier) with explicit reasoning
3. Added **explicit anti-overcall instruction** ("default to Low unless evidence rules it out")
4. Added **decision-tree pseudocode** the LLM can follow

---

## SYSTEM (prepended)

You are a senior predictive-maintenance engineer. You are conservative: you only escalate machines when the evidence clearly supports it. You output ONLY a valid JSON object with no surrounding text.

---

## USER (per case)

```
Sensor readings for one machine in our 50-machine fleet:

  Temperature:        {temperature:.2f} C   (warning >= 82, critical >= 88)
  Vibration:          {vibration:.2f}        (warning >= 55, critical >= 70)
  Humidity:           {humidity:.2f} %       (warning >= 68, critical >= 75)
  Pressure:           {pressure:.2f} bar     (warning >= 4.3, critical >= 4.8)
  Energy Consumption: {energy:.2f} kWh       (warning >= 3.8, critical >= 4.5)

Failure-mode signature (from upstream classifier): "{failure_type}"
(Possible values: "Normal", "Vibration Issue", "Overheating", "Pressure Drop", "Electrical Fault")

Decide ONE of four maintenance priority tiers using this DECISION TREE
(evaluate top to bottom, return first match):

  IF (>=2 sensors past CRITICAL threshold)
     OR (>=1 sensor past CRITICAL threshold AND failure_type in {"Electrical Fault", "Pressure Drop"})
     OR (failure_type == "Electrical Fault" AND temperature >= 88):
       => "Critical"

  ELIF (>=1 sensor past CRITICAL threshold)
     OR (>=2 sensors past WARNING threshold AND failure_type != "Normal"):
       => "High"

  ELIF (>=1 sensor past WARNING threshold)
     OR (failure_type != "Normal"):
       => "Medium"

  ELSE:
       => "Low"

Important rules:
  - DO NOT escalate to Critical based on a single sensor warning.
  - DO NOT escalate to High when failure_type is "Normal" and only one sensor is at warning level.
  - "Low" is the correct answer when no sensor is past warning AND failure_type is "Normal".
  - When in doubt between two adjacent tiers, choose the LOWER tier (less aggressive).

WORKED EXAMPLES (study these patterns):

  Example 1 (Critical):
    temp=92.0 (>= critical 88), vib=72.0 (>= critical 70), failure_type="Electrical Fault"
    -> 2 critical breaches + electrical -> "Critical"

  Example 2 (High):
    temp=85.0 (warning), vib=60.0 (warning), failure_type="Vibration Issue"
    -> 2 warnings + non-normal failure -> "High"

  Example 3 (Medium):
    temp=85.0 (warning), vib=50.0 (ok), pressure=3.0 (ok), failure_type="Normal"
    -> 1 warning + normal failure -> "Medium"

  Example 4 (Low):
    temp=75.0 (ok), vib=50.0 (ok), humidity=55.0 (ok), pressure=2.5 (ok), energy=2.0 (ok), failure_type="Normal"
    -> all normal, no failure signature -> "Low"

OUTPUT FORMAT — output exactly this JSON object, nothing else:

{"tier": "Critical|High|Medium|Low", "reasoning": "<one short sentence citing the rule from decision tree>", "confidence": <float 0.0-1.0>}
```

---

## Expected improvements over V1

| Issue in V1 | Fix in V2 |
|---|---|
| Vague "warning-level breach" definition | Concrete threshold numbers per sensor |
| Safety-bias overcall | Explicit "DO NOT escalate" rules + "default to Low" |
| Mid-tier confusion (High vs Medium F1 < 0.10) | 4 worked examples make tier boundaries concrete |
| LLM had to invent tier mapping | Decision tree pseudocode removes interpretation room |

## Risks / what could still fail

- LLM may still over-trust the failure_type signature even when sensors are normal (Example 4 shows the correct behavior)
- Decision-tree compliance assumes LLM follows instructions — may not for kimi/qwen
- Worked examples may anchor LLM toward the specific numeric values shown (mitigated by varied numbers in examples)
- Pre-registration deviation: changing prompt mid-experiment requires explicit documentation. Will add `PRE_REG_DEVIATION_001.md` if executed.

## Execution plan if approved

1. Replace prompt template with V2
2. Clear cache for `prompt_v2` namespace (V1 cache preserved separately)
3. Re-run E-L2 against same 125 cases × 4 LLMs (or 3 if dropping qwen3.5)
4. If κ ≥ 0.6: proceed to E-L3A as originally planned, document deviation
5. If κ < 0.6: re-evaluate with supervisor — may need to defer Layer 3 (Option F)
