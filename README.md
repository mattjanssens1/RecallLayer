# TurboQuant Native Vector Database

Store billions of embeddings at much lower memory cost while keeping recall high and query latency low.

## Vision

This project explores a vector database architecture that uses **TurboQuant-style compressed representations** for first-pass retrieval, followed by **exact or higher-precision reranking** on a much smaller candidate set.

The central idea is simple:

1. Keep a compact **search representation** of each vector in hot memory.
2. Use that representation for fast candidate generation.
3. Rerank a short list using higher-precision vectors.
4. Support online ingestion without expensive retraining or reindexing.

This is designed for large-scale workloads such as:

- semantic document retrieval
- RAG retrieval stores
- recommendation candidate generation
- deduplication / near-duplicate search
- anomaly and fraud neighbor lookups

## Why this project exists

Modern vector systems hit a familiar wall:

- embeddings grow into the hundreds of millions or billions
- RAM and GPU memory become the bottleneck
- exact search is too expensive
- coarse quantization often hurts recall

A TurboQuant-inspired design aims to preserve search-relevant geometry while reducing memory pressure enough to keep large indexes hot and fast.

## Design principles

- **Compressed-first retrieval**: use a compact code path for candidate generation.
- **Precise reranking**: spend exact compute only where it matters.
- **Online ingestion**: support continuously arriving vectors.
- **Tiered storage**: hot compressed codes, warmer higher-precision vectors, colder archival originals.
- **Modular engine**: quantization, ANN retrieval, reranking, and compaction should be separable services.

## Repository map

- `docs/architecture.md` - system design and data flow
- `docs/roadmap.md` - phased implementation plan

## Initial architecture at a glance

```text
                +------------------+
                |  Embed Service   |
                +------------------+
                          |
                          v
                +------------------+
                | Quantize Service |
                +------------------+
                     |        |
                     |        +----------------------+
                     v                               v
          +----------------------+       +----------------------+
          | Compressed ANN Index |       | Higher Precision     |
          |  (hot memory)        |       | Vector Store         |
          +----------------------+       |  (SSD / object)      |
                     |                    +----------------------+
                     v
               top-N candidates
                     |
                     v
                +------------------+
                | Rerank Service   |
                +------------------+
                          |
                          v
                +------------------+
                | Query Results    |
                +------------------+
```

## First concrete milestone

Build a secondary compressed index beside a baseline vector store and evaluate:

- recall@10 / recall@100
- p95 latency
- ingestion throughput
- memory reduction
- rerank cost per query

## Near-term questions

- What compressed format should be the first implementation target?
- Should the first retrieval engine be brute-force compressed scan, IVF, or graph ANN?
- How should metadata filtering interact with compressed retrieval?
- What benchmark corpus should be the first proof point?

## Status

This repository is currently in **design and prototyping** mode.

The next step is to turn the system design into a concrete package layout and baseline benchmark harness.
