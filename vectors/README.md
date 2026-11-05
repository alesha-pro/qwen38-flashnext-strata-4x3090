# Refusal vectors for Qwen3.8-Flash-Next

Control vector GGUF files (`direction.1` ... `direction.47`, 2560 values each) for Strata's projection mode. Projection
removes the component along the direction from the residual stream on every layer in the range, it does not add anything.

| File | What | AdvBench / JailbreakBench / harmless | KL prose / code |
|---|---|---|---|
| `qwen38-flashnext-refusal-mix-r1.gguf` | my direction mixed per layer with huihui-ai's refusal direction, renormalized. **Use this one** | 0 / 0 / 0 | 0.029 / 0.011 |
| `qwen38-flashnext-refusal-own-NX.gguf` | my direction only | 0 / 1 / 1 | 0.039 / 0.018 |

Counts are refusals out of 64 / 82 / 64 on UD-IQ4_XS without thinking. KL is against the same model without the vector.
Full table in the main [README](../README.md#refusal-vector).

```text
--control-vector-scaled qwen38-flashnext-refusal-mix-r1.gguf:1.0
--control-vector-layer-range 1 47 --cvec-mode project --cvec-dir per-layer
```

Turn it off for one request with `"experimental_speed_projection": false` in the request body.
The direction was taken on UD-Q4_K_XL and works on UD-IQ4_XS as measured above. Checksums in `SHA256SUMS`.
