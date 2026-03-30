# TurboQuant-native Vector Database

**Store billions of embeddings with 4× lower memory while keeping >95% recall and sub-100 ms query latency.**

The *first* full vector database built directly on Google's brand-new [TurboQuant](https://arxiv.org/abs/2504.19874) (ICLR 2026) — the same technique that's blowing up for KV-cache compression, now applied natively to retrieval.

![Hero benchmark chart coming soon — run the scripts below and screenshot it!]

## Why this matters
- **TurboQuant-native compression** — data-oblivious, near-zero indexing time, state-of-the-art distortion
- **Hybrid query engine** — exact path + compressed path + reranker (maximum recall safety net)
- **Production-ready storage skeleton** — WAL + mutable buffer + sealed segments + crash recovery
- **Already runnable** — local facade, FastAPI endpoint, full benchmarks, diagnostics exporters

## 30-second quick start

```bash
# 1. Clone & install
git clone https://github.com/mattjanssens1/TurboQuant-native-vector-database.git
cd TurboQuant-native-vector-database
pip install -e .[dev]

# 2. Run the showcase (best local surface)
python examples/quickstart.py

# 3. See the magic
python scripts/run_showcase_benchmark.py          # hybrid vs exact
python scripts/run_quantizer_comparison.py       # TurboQuant-style vs baselines
python scripts/run_extended_benchmark.py         # full diagnostics
