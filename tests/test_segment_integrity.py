"""Tests for segment checksum verification and crash-recovery integrity."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from recalllayer.engine.local_db import LocalVectorDatabase


def _make_db(root_dir: str) -> LocalVectorDatabase:
    return LocalVectorDatabase(
        collection_id="integrity-test",
        root_dir=root_dir,
    )


def _sample_embedding(seed: int = 0) -> list[float]:
    import math
    n = 16
    vec = [math.sin(seed + i) for i in range(n)]
    norm = sum(v * v for v in vec) ** 0.5
    return [v / norm for v in vec]


# ---------------------------------------------------------------------------
# Checksum written at flush time
# ---------------------------------------------------------------------------

class TestChecksumWritten:
    def test_flush_writes_checksum(self, tmp_path):
        db = _make_db(str(tmp_path))
        db.upsert(vector_id="v1", embedding=_sample_embedding(1), metadata={"x": 1})
        db.flush_mutable(segment_id="seg-0", generation=1)

        _, seg_manifests = db.load_manifest_set()
        assert len(seg_manifests) == 1
        m = seg_manifests[0]
        assert m.content_sha256 is not None, "flush must record content_sha256"
        assert len(m.content_sha256) == 64, "sha256 hex digest is 64 chars"

    def test_checksum_is_correct(self, tmp_path):
        import hashlib
        db = _make_db(str(tmp_path))
        db.upsert(vector_id="v1", embedding=_sample_embedding(1))
        db.flush_mutable(segment_id="seg-0", generation=1)

        _, seg_manifests = db.load_manifest_set()
        m = seg_manifests[0]
        segment_files = list((tmp_path / "segments").rglob("*.segment.jsonl"))
        assert segment_files, "segment file should exist on disk"
        actual = hashlib.sha256(segment_files[0].read_bytes()).hexdigest()
        assert actual == m.content_sha256

    def test_multiple_flushes_each_have_checksum(self, tmp_path):
        db = _make_db(str(tmp_path))
        for i in range(3):
            db.upsert(vector_id=f"v{i}", embedding=_sample_embedding(i))
            db.flush_mutable(segment_id=f"seg-{i}", generation=i + 1)

        _, seg_manifests = db.load_manifest_set()
        assert len(seg_manifests) == 3
        for m in seg_manifests:
            assert m.content_sha256 is not None


# ---------------------------------------------------------------------------
# verify_segment_integrity()
# ---------------------------------------------------------------------------

class TestVerifySegmentIntegrity:
    def test_passes_when_files_are_intact(self, tmp_path):
        db = _make_db(str(tmp_path))
        db.upsert(vector_id="v1", embedding=_sample_embedding(1))
        db.flush_mutable(segment_id="seg-0", generation=1)

        errors = db.verify_segment_integrity()
        assert errors == [], f"expected no errors, got: {errors}"

    def test_detects_corrupted_segment_file(self, tmp_path):
        db = _make_db(str(tmp_path))
        db.upsert(vector_id="v1", embedding=_sample_embedding(1))
        db.flush_mutable(segment_id="seg-0", generation=1)

        # Corrupt the segment file
        segment_files = list((tmp_path / "segments").rglob("*.segment.jsonl"))
        assert segment_files
        seg_path = segment_files[0]
        original = seg_path.read_bytes()
        seg_path.write_bytes(original + b"\ncorrupted-line\n")

        errors = db.verify_segment_integrity()
        assert len(errors) == 1
        assert "checksum mismatch" in errors[0]

    def test_returns_empty_for_no_segments(self, tmp_path):
        db = _make_db(str(tmp_path))
        errors = db.verify_segment_integrity()
        assert errors == []

    def test_skips_segments_without_checksum(self, tmp_path):
        """Legacy segments (no content_sha256) should not cause errors."""
        db = _make_db(str(tmp_path))
        db.upsert(vector_id="v1", embedding=_sample_embedding(1))
        db.flush_mutable(segment_id="seg-0", generation=1)

        # Simulate a legacy manifest by nulling out the checksum
        _, seg_manifests = db.load_manifest_set()
        m = seg_manifests[0]
        patched = m.model_copy(update={"content_sha256": None})
        db.segment_manifest_store.save(patched)

        errors = db.verify_segment_integrity()
        assert errors == [], "legacy segments without checksum should be skipped"


# ---------------------------------------------------------------------------
# Crash recovery: restart after simulated unclean shutdown
# ---------------------------------------------------------------------------

class TestCrashRecovery:
    def test_recovery_restores_unflushed_writes(self, tmp_path):
        """WAL replay should restore vectors written but not yet flushed."""
        db = _make_db(str(tmp_path))
        db.upsert(vector_id="v1", embedding=_sample_embedding(1))
        db.upsert(vector_id="v2", embedding=_sample_embedding(2))
        # Intentionally do NOT flush — simulate crash before flush

        db2 = _make_db(str(tmp_path))
        applied = db2.recover()
        assert applied == 2, f"expected 2 replayed entries, got {applied}"
        ids = db2.query_exact([0.0] * 16, top_k=10)
        assert "v1" in ids or "v2" in ids, "recovered entries should be queryable"

    def test_recovery_respects_flush_watermark(self, tmp_path):
        """After a flush, recovery should only replay post-flush entries."""
        db = _make_db(str(tmp_path))
        db.upsert(vector_id="v1", embedding=_sample_embedding(1))
        db.flush_mutable(segment_id="seg-0", generation=1, truncate_write_log=True)
        db.upsert(vector_id="v2", embedding=_sample_embedding(2))
        # Crash before second flush

        db2 = _make_db(str(tmp_path))
        applied = db2.recover()
        # Only v2 should be replayed (v1 is already in sealed segment)
        assert applied == 1, f"expected 1 replayed entry (post-flush), got {applied}"

    def test_recovery_integrity_after_flush_then_crash(self, tmp_path):
        """Sealed segment checksums should pass after recovery."""
        db = _make_db(str(tmp_path))
        db.upsert(vector_id="v1", embedding=_sample_embedding(1))
        db.upsert(vector_id="v2", embedding=_sample_embedding(2))
        db.flush_mutable(segment_id="seg-0", generation=1)
        db.upsert(vector_id="v3", embedding=_sample_embedding(3))
        # Crash — v3 is in WAL only

        db2 = _make_db(str(tmp_path))
        db2.recover()

        errors = db2.verify_segment_integrity()
        assert errors == [], f"segment integrity failed after recovery: {errors}"

    def test_repeated_recovery_is_idempotent(self, tmp_path):
        """Running recover() twice should not duplicate entries."""
        db = _make_db(str(tmp_path))
        db.upsert(vector_id="v1", embedding=_sample_embedding(1))
        # No flush

        db2 = _make_db(str(tmp_path))
        db2.recover()
        db2.recover()  # second call

        ids = db2.query_exact([0.0] * 16, top_k=10)
        # v1 should appear at most once
        assert ids.count("v1") <= 1


# ---------------------------------------------------------------------------
# Filter index written alongside segment
# ---------------------------------------------------------------------------

class TestFilterIndexWritten:
    def test_filter_index_file_created_at_flush(self, tmp_path):
        db = _make_db(str(tmp_path))
        db.upsert(vector_id="v1", embedding=_sample_embedding(1), metadata={"region": "us"})
        db.flush_mutable(segment_id="seg-0", generation=1)

        filter_files = list((tmp_path / "segments").rglob("*.filter_index.json"))
        assert len(filter_files) == 1, "expected one filter index file alongside the segment"

    def test_filter_index_contains_metadata(self, tmp_path):
        db = _make_db(str(tmp_path))
        db.upsert(vector_id="v1", embedding=_sample_embedding(1), metadata={"region": "us"})
        db.upsert(vector_id="v2", embedding=_sample_embedding(2), metadata={"region": "eu"})
        db.flush_mutable(segment_id="seg-0", generation=1)

        filter_files = list((tmp_path / "segments").rglob("*.filter_index.json"))
        payload = json.loads(filter_files[0].read_text(encoding="utf-8"))
        assert payload["format_version"] == "v1"
        vector_ids = {r["vector_id"] for r in payload["rows"]}
        assert "v1" in vector_ids
        assert "v2" in vector_ids

    def test_filter_index_excludes_tombstones(self, tmp_path):
        db = _make_db(str(tmp_path))
        db.upsert(vector_id="v1", embedding=_sample_embedding(1), metadata={"region": "us"})
        db.upsert(vector_id="v2", embedding=_sample_embedding(2), metadata={"region": "eu"})
        db.delete(vector_id="v1")
        db.flush_mutable(segment_id="seg-0", generation=1)

        filter_files = list((tmp_path / "segments").rglob("*.filter_index.json"))
        payload = json.loads(filter_files[0].read_text(encoding="utf-8"))
        vector_ids = {r["vector_id"] for r in payload["rows"]}
        # v1 was deleted before flush; it should NOT be in the filter index
        assert "v1" not in vector_ids
        assert "v2" in vector_ids
