# Benchmark Proof Story

This is the canonical benchmark narrative for the current RecallLayer repo.

It exists to answer a narrow question honestly:

> What do the current benchmark artifacts actually prove about RecallLayer today?

Short answer:

- the exact, compressed, and compressed+rereanked query paths all run end to end
- compressed retrieval is already meaningfully faster than exact search on the synthetic tiers in this repo
- reranking can recover quality when compressed-only search drops recall
- the current benchmark work supports the **sidecar retrieval architecture** story
- the current benchmark work does **not** yet prove broad production authority, real-world workload dominance, or final quantizer superiority

## What to run

For the current benchmark surfaces, use:

```bash
python scripts/run_benchmark_matrix.py
python scripts/run_quantizer_tradeoffs.py
python scripts/run_sprint5_benchmark.py
python scripts/export_proof_pack.py
```

The most important artifacts are:

- `reports/benchmark-matrix.md`
- `reports/quantizer-tradeoffs.md`
- `reports/sprint5_benchmark.md`
- `reports/proof_pack.md`

## The three query modes in plain language

### Exact

The exact path scores against the full-precision retrieval state and acts as the quality reference.

What it means in practice:

- slowest path in the current synthetic benchmarks
- used as the recall truth baseline
- helpful for understanding whether approximation changed result quality

What it does **not** mean:

- it is not automatically the right production path
- it is not the sidecar's main scaling story

### Compressed

The compressed path searches over quantized or otherwise compressed retrieval payloads first.

What it means in practice:

- usually the fastest or near-fastest retrieval path in the current repo benchmarks
- gives the engine a realistic way to reduce scoring cost over sealed state
- is the core reason RecallLayer can be interesting as a retrieval sidecar instead of just another exact scan wrapper

Tradeoff:

- compressed search can lose ranking quality relative to exact search
- how much quality it loses depends on the fixture, quantizer, and search budget

### Compressed + reranked

The reranked path first gets a candidate set from compressed retrieval, then rescoring happens on a smaller shortlist using higher-precision data.

What it means in practice:

- usually a little slower than compressed-only because it does extra work
- often recovers recall that compressed-only search gave up
- gives RecallLayer a practical middle ground: cheaper candidate generation without fully giving up quality

Tradeoff:

- reranking is not free
- if compressed-only already has full recall on a workload, reranking may add little value
- if the candidate set is too small or the compressed stage misses the right items entirely, reranking cannot magically recover them

## What the benchmark matrix already shows

`reports/benchmark-matrix.md` is the best single artifact for understanding path behavior across a few different synthetic shapes.

Current matrix highlights:

| Scenario | Exact ms | Compressed ms | Comp R@10 | Reranked ms | Reranked R@10 |
|---|---:|---:|---:|---:|---:|
| small-2d-single-shard | 7.346 | 7.165 | 1.000 | 5.793 | 1.000 |
| medium-16d-ivf | 20.595 | 12.225 | 0.969 | 22.059 | 0.988 |
| medium-16d-ivf-deletes | 8.610 | 5.550 | 0.925 | 10.610 | 1.000 |
| large-32d-ivf-multishard | 14.813 | 7.667 | 0.854 | 14.883 | 1.000 |

What this supports:

- compressed search is already materially faster than exact on the more interesting IVF-backed scenarios
- reranking improves result quality when compressed-only search drops recall
- deletes and multi-shard layouts do not break the basic quality-recovery story
- the engine now has a benchmarkable tradeoff curve instead of a single best-case number

What this does **not** support yet:

- that every dataset will show the same curve
- that reranking is always worth the latency cost
- that these synthetic tiers predict production latency with high confidence

## What the quantizer tradeoff report already shows

`reports/quantizer-tradeoffs.md` is useful because it prevents overclaiming.

The current signal is not "every approximation family works great." It is closer to this:

- some quantizer paths are clearly stronger than others
- the normalized scalar baseline is currently the most credible benchmarked path in this report
- several adapter-style paths still underperform badly on recall in this fixture

That honesty matters.

A representative example from the current report:

- `normalized-scalar-int8-127` at `auto` budget keeps `Recall@10 = 1.000`
- several adapter rows show `Recall@10 = 0.000` or `0.500`

So the right interpretation is:

- RecallLayer's **benchmark harness** is doing its job because it distinguishes stronger and weaker retrieval families
- the repo has a credible baseline path already
- the more ambitious adapter paths are still experimental and should remain clearly labeled that way

## What the sprint 5 benchmark already shows

`reports/sprint5_benchmark.md` is the strongest "single number" benchmark in the repo right now, but it should be read carefully.

On the 5,000-vector, 128-dim synthetic fixture with scalar int8 quantization and cache enabled:

- exact-hybrid: `288.611 ms`
- compressed-hybrid with IVF: `47.380 ms`
- compressed-reranked-hybrid with IVF: `49.785 ms`
- all three show `Recall@10 = 1.000` in that fixture

That means the current repo can already demonstrate:

- compressed retrieval can be much faster than exact on a nontrivial synthetic workload
- IVF materially changes the cost profile of compressed search
- reranking can stay close to compressed-only latency when the candidate shortlist is bounded

This is a strong result for the engine.

It is **not** a license to claim:

- universal 6x wins
- production latency guarantees
- that all quantizers or datasets behave this way

## Why this matters for the sidecar architecture

The sidecar story is not "RecallLayer beats every vector database."

The sidecar story is:

- the application database stays the source of truth
- RecallLayer owns retrieval-optimized state
- RecallLayer returns candidate ids and scores
- the application hydrates final records from the source database

For that architecture to make sense, RecallLayer needs to show three things:

1. it has a real quality reference path
2. it has a cheaper candidate-generation path
3. it has a practical way to recover quality when approximation is too lossy

The current benchmark work now supports all three:

- **exact** provides the reference
- **compressed** provides the cheaper candidate-generation path
- **reranked** provides the quality-recovery step

That is why the benchmark work matters. It is not just performance theater. It is evidence that the sidecar's two-stage retrieval shape is technically coherent.

## What is already strong

The current benchmark story is already strong enough to support these bounded claims:

- RecallLayer has repeatable benchmark artifacts in-repo
- the repo exposes exact, compressed, and reranked behavior separately
- compressed retrieval is already faster than exact on several meaningful synthetic scenarios
- reranking improves quality on scenarios where compressed-only retrieval drops recall
- the benchmark harness is useful for comparing quantizers instead of hiding weak paths
- IVF-backed compressed retrieval is now a credible part of the engine story

## What is not claimed yet

These claims should still stay out of bounds for now:

- production-readiness on real customer workloads
- broad authority on large real-world corpora
- final quantizer design victory
- full TurboQuant fidelity
- guaranteed wins across every workload shape
- end-to-end application latency claims beyond the retrieval portion measured here

## Practical interpretation for readers

If you are evaluating RecallLayer today, the honest read is:

- this repo already demonstrates a real retrieval tradeoff story
- the compressed-first sidecar design is no longer just conceptual
- the synthetic benchmark evidence is useful and reproducible
- the benchmark evidence is still narrower than a production validation program

That puts RecallLayer in a better place than "interesting architecture notes," but still short of "fully proven product."

## Recommended doc reading order

1. `docs/benchmark-proof-story.md`
2. `docs/prove-it-works.md`
3. `docs/postgres-recalllayer-architecture.md`
4. `docs/benchmark-proof-pack.md`
5. `reports/benchmark-matrix.md`
6. `reports/quantizer-tradeoffs.md`
7. `reports/sprint5_benchmark.md`

## Bottom line

The benchmark work now proves something specific and important:

> RecallLayer has a measurable exact-vs-compressed-vs-reranked retrieval story, and that story is directly relevant to the repo's intended role as a vector retrieval sidecar.

That is the canonical benchmark proof today.
