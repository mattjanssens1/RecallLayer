from turboquant_db.filters.indexes import FilterIndexes, MetadataRow
from turboquant_db.filters.planner import FilterPlanner


def main() -> None:
    rows = [
        MetadataRow(vector_id="a", metadata={"region": "us", "active": True, "score": 10}),
        MetadataRow(vector_id="b", metadata={"region": "us", "active": False, "score": 6}),
        MetadataRow(vector_id="c", metadata={"region": "ca", "active": True, "score": 8}),
        MetadataRow(vector_id="d", metadata={"region": "uk", "active": True, "score": 2}),
    ]

    indexes = FilterIndexes(rows)
    planner = FilterPlanner(prefilter_threshold=0.30)

    selective = planner.plan(filters={"region": {"eq": "uk"}}, indexes=indexes)
    broad = planner.plan(filters={"active": {"eq": True}}, indexes=indexes)

    print({
        "selective_strategy": selective.strategy,
        "selective_ids": sorted(selective.candidate_ids),
        "broad_strategy": broad.strategy,
        "broad_ids": sorted(broad.candidate_ids),
    })


if __name__ == "__main__":
    main()
