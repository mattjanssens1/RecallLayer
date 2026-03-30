# Filter Indexes

This note adds small exact metadata indexes and a planner primitive.

## New modules

- `src/turboquant_db/filters/indexes.py`
- `src/turboquant_db/filters/planner.py`

## What they do

- build exact lookup sets for keyword and boolean metadata
- support numeric `gte` and `lte` range scans
- estimate selectivity for a filter bundle
- choose a simple `pre-filter` versus `post-filter` strategy

## Why this split

The current engine already evaluates exact filters correctly. These primitives make
it easier to decide when a selective filter should narrow the candidate pool before
compressed retrieval or rerank.

## Current scope

This is intentionally small:

- exact metadata behavior only
- no ANN coupling yet
- no on-disk posting lists yet
- no background maintenance yet

It is a stepping stone toward the filter-index milestone in the implementation plan.
