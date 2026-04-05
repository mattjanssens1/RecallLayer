from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from turboquant_db.engine.manifest_store import ManifestStore
from turboquant_db.engine.manifest_validation import raise_for_manifest_issues, validate_manifest_set
from turboquant_db.engine.mutable_buffer import MutableBuffer
from turboquant_db.engine.query_executor import QueryExecutor
from turboquant_db.engine.recovery_manager import RecoveryManager
from turboquant_db.engine.sealed_segments import LocalSegmentStore, SegmentBuilder
from turboquant_db.engine.segment_gc_executor import SegmentGarbageCollectionExecution, SegmentGarbageCollectionExecutor
from turboquant_db.engine.segment_manifest_store import SegmentManifestStore
from turboquant_db.engine.write_log import WriteLog
from turboquant_db.model.manifest import SegmentState, ShardManifest
from turboquant_db.quantization.base import Quantizer
from turboquant_db.quantization.scalar import ScalarQuantizer


class LocalVectorDatabase:
    """A tiny single-node database facade for local development."""

    def __init__(
        self,
        *,
        collection_id: str,
        root_dir: str | Path,
        embedding_version: str = "embed-v1",
        quantizer_version: str = "tq-v0",
        quantizer: Quantizer | None = None,
        flush_threshold: int | None = None,
    ) -> None:
        self.collection_id = collection_id
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_version = embedding_version
        self.quantizer_version = quantizer_version
        self.quantizer = quantizer or ScalarQuantizer()

        self.mutable_buffer = MutableBuffer(collection_id=collection_id)
        self.write_log = WriteLog(self.root_dir / collection_id / "write_log.jsonl")
        self.manifest_store = ManifestStore(self.root_dir / "manifests")
        self.segment_manifest_store = SegmentManifestStore(self.root_dir / "segment-manifests")
        self.segment_store = LocalSegmentStore(self.root_dir / "segments")
        self.segment_builder = SegmentBuilder(self.root_dir / "segments", quantizer=self.quantizer)
        self.recovery_manager = RecoveryManager(write_log=self.write_log, mutable_buffer=self.mutable_buffer)
        self.query_executor = QueryExecutor(mutable_buffer=self.mutable_buffer, quantizer=self.quantizer)
        self.flush_threshold = flush_threshold

        self._write_epoch = self.mutable_buffer.watermark()
        self._auto_flush_segment_counter = 0

    def upsert(self, *, vector_id: str, embedding: list[float], metadata: dict[str, object] | None = None) -> int:
        self._write_epoch += 1
        self.write_log.append_upsert(
            collection_id=self.collection_id,
            vector_id=vector_id,
            write_epoch=self._write_epoch,
            embedding=embedding,
            metadata=metadata or {},
        )
        self.mutable_buffer.upsert(
            vector_id=vector_id,
            embedding=embedding,
            metadata=metadata or {},
            embedding_version=self.embedding_version,
            quantizer_version=self.quantizer_version,
            write_epoch=self._write_epoch,
        )
        self._maybe_auto_flush()
        return self._write_epoch

    def delete(self, *, vector_id: str) -> int:
        self._write_epoch += 1
        self.write_log.append_delete(
            collection_id=self.collection_id,
            vector_id=vector_id,
            write_epoch=self._write_epoch,
        )
        self.mutable_buffer.delete(
            vector_id=vector_id,
            embedding_version=self.embedding_version,
            quantizer_version=self.quantizer_version,
            write_epoch=self._write_epoch,
        )
        return self._write_epoch

    def _maybe_auto_flush(self) -> None:
        if self.flush_threshold is None:
            return
        mutable_count = len(self.mutable_buffer.all_entries())
        if mutable_count >= self.flush_threshold:
            self._auto_flush_segment_counter += 1
            self.flush_mutable(
                segment_id=f"seg-auto-{self._auto_flush_segment_counter}",
                generation=self._auto_flush_segment_counter,
            )

    def shard_live_row_fraction(self, *, shard_id: str = "shard-0") -> float | None:
        """Return live / total rows across sealed segments for this shard.

        Returns None when there are no sealed segments.
        """
        segment_manifests = self.segment_manifest_store.list_manifests(
            collection_id=self.collection_id, shard_id=shard_id
        )
        shard_manifest = self.manifest_store.load(collection_id=self.collection_id, shard_id=shard_id)
        if shard_manifest is None:
            return None
        active_ids = set(shard_manifest.active_segment_ids)
        active_manifests = [m for m in segment_manifests if m.segment_id in active_ids]
        if not active_manifests:
            return None
        total_rows = sum(m.row_count for m in active_manifests)
        live_rows = sum(m.live_row_count for m in active_manifests)
        if total_rows == 0:
            return 1.0
        return live_rows / total_rows

    def shard_delete_ratio(self, *, shard_id: str = "shard-0") -> float | None:
        """Return fraction of rows that are deleted (1 - live_row_fraction).

        Returns None when there are no sealed segments.
        """
        fraction = self.shard_live_row_fraction(shard_id=shard_id)
        if fraction is None:
            return None
        return 1.0 - fraction

    def query_exact(self, query_vector: list[float], *, top_k: int) -> list[str]:
        return [item.vector_id for item in self.query_executor.search_exact(query_vector, top_k=top_k)]

    def query_compressed(self, query_vector: list[float], *, top_k: int) -> list[str]:
        return [item.vector_id for item in self.query_executor.search_compressed(query_vector, top_k=top_k)]

    def flush_mutable(self, *, shard_id: str = "shard-0", segment_id: str = "seg-0", generation: int = 1) -> ShardManifest | None:
        entries = self.mutable_buffer.all_entries()
        if not entries:
            return None

        segment_manifest, _paths = self.segment_builder.build(
            collection_id=self.collection_id,
            shard_id=shard_id,
            segment_id=segment_id,
            generation=generation,
            embedding_version=self.embedding_version,
            quantizer_version=self.quantizer_version,
            entries=entries,
        )
        now = datetime.now(timezone.utc)
        segment_manifest.state = SegmentState.ACTIVE
        segment_manifest.sealed_at = segment_manifest.sealed_at or now
        segment_manifest.activated_at = segment_manifest.activated_at or now
        self.segment_manifest_store.save(segment_manifest)

        previous_shard_manifest = self.manifest_store.load(collection_id=self.collection_id, shard_id=shard_id)
        prior_active_segment_ids = previous_shard_manifest.active_segment_ids if previous_shard_manifest is not None else []
        shard_manifest = ShardManifest(
            shard_id=shard_id,
            collection_id=self.collection_id,
            active_segment_ids=[*prior_active_segment_ids, segment_manifest.segment_id],
            replay_from_write_epoch=segment_manifest.max_write_epoch,
        )
        existing_segment_manifests = self.segment_manifest_store.list_manifests(
            collection_id=self.collection_id,
            shard_id=shard_id,
        )
        issues = validate_manifest_set(
            shard_manifest=shard_manifest,
            segment_manifests=existing_segment_manifests,
        )
        raise_for_manifest_issues(issues)
        self.manifest_store.save(shard_manifest)
        self.mutable_buffer.remove_many(entry.record.vector_id for entry in entries)
        return shard_manifest

    def load_manifest_set(self, *, shard_id: str = "shard-0") -> tuple[ShardManifest | None, list]:
        shard_manifest = self.manifest_store.load(collection_id=self.collection_id, shard_id=shard_id)
        segment_manifests = self.segment_manifest_store.list_manifests(collection_id=self.collection_id, shard_id=shard_id)
        if shard_manifest is not None:
            issues = validate_manifest_set(shard_manifest=shard_manifest, segment_manifests=segment_manifests)
            raise_for_manifest_issues(issues)
        return shard_manifest, segment_manifests

    def collect_retired_segments(self, *, shard_id: str = "shard-0") -> SegmentGarbageCollectionExecution:
        executor = SegmentGarbageCollectionExecutor(
            segment_manifest_store=self.segment_manifest_store,
            segments_root=self.root_dir / "segments",
            manifests_root=self.root_dir / "manifests",
        )
        return executor.collect_shard(collection_id=self.collection_id, shard_id=shard_id)

    def recover(self, *, shard_id: str = "shard-0") -> int:
        shard_manifest = self.manifest_store.load(collection_id=self.collection_id, shard_id=shard_id)
        replay_from_write_epoch = shard_manifest.replay_from_write_epoch if shard_manifest is not None else 0
        applied = self.recovery_manager.replay(
            embedding_version=self.embedding_version,
            quantizer_version=self.quantizer_version,
            after_write_epoch=replay_from_write_epoch,
        )
        self._write_epoch = max(self._write_epoch, self.mutable_buffer.watermark(), replay_from_write_epoch)
        return applied
