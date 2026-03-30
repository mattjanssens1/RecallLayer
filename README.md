# TurboQuant-native Vector Database

An early vector-database prototype exploring TurboQuant-style compressed retrieval, hybrid mutable/sealed execution, reranking, benchmarkable storage-engine ideas, and diagnostics-rich API surfaces.

## Start here

If you want the clearest path through the repo, read these first:

- `docs/repository-status.md`
- `docs/current-surfaces.md`
- `docs/benchmark-proof-pack.md`

## Best current surfaces

- **Best local facade:** `turboquant_db.showcase.ShowcaseScoredDatabase`
- **Best API entrypoint:** `src/turboquant_db/api/app_best.py`
- **Best benchmark workflow:** `python scripts/run_canonical_flow.py`
- **Best report export:** `python scripts/export_full_ladder.py`
- **Best compact proof artifact:** `python scripts/export_proof_pack.py`

## Quick start

```bash
# 1. Clone & install
git clone https://github.com/mattjanssens1/TurboQuant-native-vector-database.git
cd TurboQuant-native-vector-database
pip install -e .[dev]

# 2. Run the showcase example
python examples/quickstart.py

# 3. Run the canonical benchmark flow
python scripts/run_canonical_flow.py

# 4. Export one compact proof table
python scripts/export_proof_pack.py
```

## What this repo is trying to prove

- hybrid query execution across mutable and sealed state can be made coherent
- compressed retrieval can be benchmarked honestly against exact and reranked paths
- diagnostics-rich APIs are useful during engine development
- a small local storage engine can support meaningful benchmark and architecture work

## Important note on TurboQuant wording

This repo includes TurboQuant-style and adapter-based work, but not a claim of full algorithmic fidelity. Where code is experimental or placeholder, it should be read that way.
