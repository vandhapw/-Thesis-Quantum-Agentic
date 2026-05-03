# Pre-Registration Deviation #002 — Drop qwen3.5 from E-L2 Ensemble

**Date:** 2026-05-04
**Original protocol:** PHASE1_PROTOCOL_V2_ALIGNED_3LAYER.md §3.3 (4-LLM ensemble)
**Authorization:** Supervisor approval ("A2") on 2026-05-04 after V2 smoke test showed qwen3.5 60% empty-content rate

## What changed

| Aspect | Pre-reg V1 | After deviation #001 (V2) | After deviation #002 (V2 final) |
|---|---|---|---|
| LLM ensemble | 4 models | 4 models | **3 models** |
| Models | glm-5.1, qwen3.5, kimi-k2.6, deepseek-v4-pro | same | **glm-5.1, kimi-k2.6, deepseek-v4-pro** |
| qwen3.5 status | active member | active member | **dropped** |

All other parameters from PRE_REG_DEVIATION_001 unchanged (prompt V2, num_predict=800, primary metric κ, threshold 0.6, halt rule).

## Justification

qwen3.5:cloud demonstrated **technical incompatibility** with the experimental setup, not substantive disagreement:

| Run | qwen3.5 valid responses | Empty-content rate |
|---|---|---|
| V1 (prompt v1, num_predict=500) | 67/125 (53.6%) | 46.4% |
| V2 smoke (prompt v2, num_predict=800) | 2/5 (40%) | 60% |

Root cause: `think=False` parameter is not honored by qwen3.5 cloud endpoint. Reasoning tokens consume the `num_predict` budget, leaving zero tokens for the actual JSON output. Increasing budget did NOT resolve (smoke V2 still 60% empty even at 800 tokens).

This is a **technical issue specific to qwen3.5 cloud** that cannot be cleanly mitigated without:
- Setting `think=True` and parsing `thinking` field separately (different from other 3 LLMs which respect `think=False`)
- Using a much larger `num_predict` (e.g., 4000+) at high cost without guarantee
- Switching to a different qwen variant not in the original spec

Either path constitutes a more invasive deviation than dropping qwen3.5.

## Why this is methodologically defensible

1. **Documentation of failure**: qwen3.5 V1 + V2 results preserved and reported in thesis as honest evidence of technical-incompatibility, not buried.
2. **Same primary metric and threshold**: κ ≥ 0.6 still applies; we are not lowering the bar.
3. **Ensemble identity preserved**: 3 of 4 original LLMs remain — heterogeneous diversity intact.
4. **Halt rule preserved**: if 3-LLM ensemble V2 also yields κ < 0.6, halt rule still triggers.
5. **Pre-execution declaration**: this deviation is documented BEFORE re-execution.

## Risk acknowledgement

- A 3-LLM ensemble is technically smaller than 4-LLM but no analysis claim depends on the specific number; "ensemble" is the unit of analysis.
- Defense panel may ask why qwen3.5 was excluded; the answer is documented here with empirical evidence (60% empty-content rate, not an arbitrary choice).
- The decision to drop qwen3.5 is informed by smoke test data, not by post-hoc convenience.

## Files affected

- `run_el2_v2.py`: LLMS list reduced from 4 to 3
- All output files retain `_v2` suffix; per-LLM ablation will report 3 models (qwen3.5 excluded)
- V1 + smoke V2 cache preserved for archival; per-machine cases that were cached for qwen3.5 simply won't be referenced by the 3-LLM ensemble logic
