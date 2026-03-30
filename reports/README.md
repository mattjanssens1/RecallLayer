# Reports Directory

This directory is intended to hold generated benchmark and diagnostics artifacts.

## Common generators

- `python scripts/export_showcase_bundle.py`
- `python scripts/export_quantizer_bundle.py`
- `python scripts/export_extended_diagnostics.py`
- `python scripts/export_quantizer_summary.py`
- `python scripts/export_quantizer_details.py`
- `python scripts/export_all_reports.py`

## Common outputs

- showcase bundle Markdown and JSON
- quantizer bundle Markdown and JSON
- extended benchmark diagnostics Markdown and JSON
- quantizer summary Markdown and JSON
- per-quantizer JSON details under `reports/quantizers/`

## Current best workflow

```bash
python scripts/run_canonical_flow.py
python scripts/export_all_reports.py
```
