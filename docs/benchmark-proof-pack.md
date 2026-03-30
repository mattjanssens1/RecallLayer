# Benchmark Proof Pack

This guide adds one small, reproducible benchmark table intended to improve credibility.

## Command

```bash
python scripts/export_proof_pack.py
```

## Output

The command writes:

- `reports/proof_pack.md`

## What the table includes

- an exact-hybrid baseline row for each fixture
- compressed-hybrid rows for a scalar quantizer baseline
- compressed-reranked-hybrid rows for the same scalar baseline
- compressed and reranked rows for the current TurboQuant adapter path

## Why this is useful

This gives readers one compact artifact that is:

- reproducible
- benchmark-oriented
- explicit about adapter-based versus baseline paths
- easier to evaluate than broad narrative claims

## Important note

Rows that use `turboquant-adapter` should be read as adapter-based prototype measurements, not as proof of full TurboQuant fidelity.
