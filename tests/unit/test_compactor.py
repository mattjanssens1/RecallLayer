import json
from pathlib import Path

from turboquant_db.engine.compactor import LocalSegmentCompactor
from turboquant_db.engine.manifest_store import ManifestStore
from turboquant_db.engine.sealed_segments import SegmentReader


def _write_segment(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")))
            handle.write("\n")


def test_local_segment_compactor_merges_latest_rows(tmp_path: Path) -> None:
    segments_root = tmp_path / "segments"
    manifests_root = tmp_path / "manifests"
    shard_dir = segments_root / "documents" / "shard-0"

    _write_segment(
        shard_dir / "seg-1.segment.jsonl",
        [
            {"local_docno": 0, "vector_id": "a", "codes": [1, 0], "scale": 1.0, "metadata": {"region": "us"}, "write_epoch": 1},
            {"local_docno": 1, "vector_id": "b", "codes": [0, 1], "scale": 1.0, "metadata": {"region": "ca"}, "write_epoch": 2},
        ],
    )
    _write_segment(
        shard_dir / "seg-2.segment.jsonl",
        [
            {"local_docno": 0, "vector_id": "a", "codes": [2, 0], "scale": 1.0, "metadata": {"region": "uk"}, "write_epoch": 3},
            {"local_docno": 1, "vector_id": "c", "codes": [0, 2], "scale": 1.0, "metadata": {"region": "us"}, "write_epoch": 4},
        ],
    )

    compactor = LocalSegmentCompactor(segments_root=segments_root, manifests_root=manifests_root)
    artifacts = compactor.compact(collection_id="documents", output_segment_id="seg-merged", generation=7)

    reader = SegmentReader(artifacts.segment_path)
    rows = {row.vector_id: row for row in reader.iter_indexed_vectors()}

    assert set(rows) == {"a", "b", "c"}
    assert rows["a"].metadata["region"] == "uk"
    assert artifacts.segment_manifest.row_count == 3
    assert artifacts.segment_manifest.min_write_epoch == 1
    assert artifacts.segment_manifest.max_write_epoch == 4
    assert artifacts.shard_manifest.active_segment_ids == ["seg-merged"]


def test_local_segment_compactor_publishes_segment_manifest_artifact(tmp_path: Path) -> None:
    segments_root = tmp_path / "segments"
    manifests_root = tmp_path / "manifests"
    shard_dir = segments_root / "events" / "shard-0"

    _write_segment(
        shard_dir / "seg-1.segment.jsonl",
        [
            {"local_docno": 0, "vector_id": "evt-1", "codes": [1], "scale": 1.0, "metadata": {"kind": "click"}, "write_epoch": 10},
        ],
    )

    compactor = LocalSegmentCompactor(segments_root=segments_root, manifests_root=manifests_root)
    artifacts = compactor.compact(collection_id="events", output_segment_id="seg-compacted", generation=2)

    manifest = ManifestStore(manifests_root).load(collection_id="events", shard_id="shard-0")
    assert manifest is None
    assert artifacts.manifest_path.exists()
    assert artifacts.segment_path.exists()


def test_local_segment_compactor_can_limit_sources(tmp_path: Path) -> None:
    segments_root = tmp_path / "segments"
    manifests_root = tmp_path / "manifests"
    shard_dir = segments_root / "documents" / "shard-0"

    _write_segment(shard_dir / "seg-1.segment.jsonl", [{"local_docno": 0, "vector_id": "a", "codes": [1], "scale": 1.0, "metadata": {}, "write_epoch": 1}])
    _write_segment(shard_dir / "seg-2.segment.jsonl", [{"local_docno": 0, "vector_id": "b", "codes": [2], "scale": 1.0, "metadata": {}, "write_epoch": 2}])
    _write_segment(shard_dir / "seg-3.segment.jsonl", [{"local_docno": 0, "vector_id": "c", "codes": [3], "scale": 1.0, "metadata": {}, "write_epoch": 3}])

    compactor = LocalSegmentCompactor(segments_root=segments_root, manifests_root=manifests_root)
    artifacts = compactor.compact(
        collection_id="documents",
        output_segment_id="seg-merged",
        generation=4,
        source_segment_ids=["seg-1", "seg-3"],
    )

    rows = {row.vector_id for row in SegmentReader(artifacts.segment_path).iter_indexed_vectors()}
    assert rows == {"a", "c"}
    assert artifacts.source_segment_ids == ["seg-1", "seg-3"]
