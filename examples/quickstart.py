from recalllayer.engine.showcase_db import ShowcaseLocalDatabase


def main() -> None:
    db = ShowcaseLocalDatabase(collection_id="quickstart", root_dir=".quickstart_db")
    db.upsert(vector_id="doc-1", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="doc-2", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.flush_mutable(segment_id="seg-1", generation=1)

    print("exact hybrid:", db.query_exact_hybrid([0.9, 0.1], top_k=1))
    print("compressed hybrid:", db.query_compressed_hybrid([0.9, 0.1], top_k=1))
    print("filtered:", db.query_compressed_hybrid([0.9, 0.1], top_k=2, filters={"region": {"eq": "us"}}))


if __name__ == "__main__":
    main()
