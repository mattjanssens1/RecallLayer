from __future__ import annotations

import json
from pathlib import Path

from turboquant_db.benchmark.mini_harness import run_mini_harness
from turboquant_db.engine.showcase_db import ShowcaseLocalDatabase


def main() -> None:
    root_dir = Path(".turboquant_local")
    db = ShowcaseLocalDatabase(collection_id="demo", root_dir=root_dir)

    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us", "tier": "gold"})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca", "tier": "silver"})
    db.upsert(vector_id="c", embedding=[0.8, 0.2], metadata={"region": "us", "tier": "platinum"})
    db.flush_mutable(segment_id="seg-1", generation=1)

    result = run_mini_harness(db, [[0.9, 0.1], [0.1, 0.9]], top_k=2)
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
