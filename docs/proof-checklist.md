# Proof Checklist

Use this file when you want to answer the question:

> Can this repository prove that it works today from a clean state?

The goal is not hype. The goal is a repeatable, honest proof run.

## Canonical entrypoints

Use these paths unless you are intentionally testing an experimental or compatibility surface:

- **Best API:** `src/turboquant_db/api/app_best.py`
- **Run best API:** `python scripts/run_best_api.py`
- **Best local facade:** `turboquant_db.showcase.ShowcaseScoredDatabase`
- **Canonical benchmark workflow:** `python scripts/run_canonical_flow.py`
- **Compact proof artifact:** `python scripts/export_proof_pack.py`

Treat `app_observed.py` and `run_observed_api.py` as compatibility aliases, not the preferred named path.

## Proof gates

### Gate 1 — correctness baseline

From a clean state:

1. install dependencies
2. run the full test suite
3. confirm all tests pass

Expected command:

```bash
pip install -e .[dev]
pytest -q
```

Expected outcome:

- full suite passes
- no empty-index tests are polluted by persisted local state
- any warnings are understood and documented

### Gate 2 — API smoke proof

Run the best API or the in-process best API demo.

Expected commands:

```bash
python scripts/run_best_api.py
# or
python scripts/demo_best_api_flow.py
```

What this should prove:

- health endpoint responds
- vectors can be upserted
- flush succeeds
- exact / compressed / reranked paths respond
- trace diagnostics are present

### Gate 3 — benchmark proof

Run the canonical benchmark flow.

Expected command:

```bash
python scripts/run_canonical_flow.py
```

What this should prove:

- benchmark runners complete from a clean checkout
- report/export scripts execute successfully
- output files are written under `reports/`

### Gate 4 — compact artifact proof

Export the compact proof artifact.

Expected command:

```bash
python scripts/export_proof_pack.py
```

Expected output:

- `reports/proof_pack.md`

### Gate 5 — honest claims check

Before calling the repo "proved," verify that the claims match the current state.

Real claims this repo can support more comfortably:

- hybrid mutable + sealed query execution exists
- compressed, reranked, and exact paths are runnable
- diagnostics-rich API surfaces exist
- benchmark/report artifacts can be generated
- storage-engine lifecycle work exists beyond toy retrieval

Claims that should still stay careful:

- full TurboQuant algorithmic fidelity
- production readiness
- large-scale benchmark authority beyond the datasets in-repo

## Suggested clean proof run order

Use this order when validating the repo end to end:

1. `pytest -q`
2. `python examples/quickstart.py`
3. `python scripts/demo_best_api_flow.py`
4. `python scripts/run_canonical_flow.py`
5. `python scripts/export_proof_pack.py`

## Record the proof run

After a real proof run, write down:

- date/time
- branch and commit
- test result summary
- which benchmark scripts completed
- which files were generated in `reports/`
- warnings, caveats, and anything still experimental

## Why this file exists

A repo like this becomes much more convincing when it can be validated on command instead of only described well in conversation.
