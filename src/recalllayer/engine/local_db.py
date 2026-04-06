from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from recalllayer.engine.manifest_store import ManifestStore
from recalllayer.engine.manifest_validation import raise_for_manifest_issues, validate_manifest_set
from recalllayer.engine.mutable_buffer import MutableBuffer
from recalllayer.engine.query_executor import QueryExecutor
from recalllayer.engine.recovery_manager import RecoveryManager
from recalllayer.engine.sealed_segments import LocalSegmentStore, SegmentBuilder, SegmentReadStats
from recalllayer.engine.segment_cache import SegmentReadCache
from recalllayer.engine.segment_gc_executor import (
    SegmentGarbageCollectionExecution,
    SegmentGarbageCollectionExecutor,
)
from recalllayer.engine.segment_manifest_store import SegmentManifestStore
from recalllayer.engine.write_log import DurabilityMode, WriteLog
from recalllayer.model.manifest import SegmentState, ShardManifest
from recalllayer.quantization.base import Quantizer
from recalllayer.quantization.scalar import ScalarQuantizer


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
        durability_mode: DurabilityMode = DurabilityMode.MEMORY,
        segment_cache_size: int = 8,
        enable_segment_cache: bool = True,
        enable_ivf: bool = False,
        ivf_n_clusters: int = 8,
        ivf_probe_k: int = 2,
    ) -> None:
        self.collection_id = collection_id
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_version = embedding_version
        self.quantizer_version = quantizer_version
        self.quantizer = quantizer or ScalarQuantizer()
        self.enable_segment_cache = enable_segment_cache
        self.enable_ivf = enable_ivf
        self.ivf_n_clusters = ivf_n_clusters
        self.ivf_probe_k = ivf_probe_k

        self.mutable_buffer = MutableBuffer(collection_id=collection_id)
        self.write_log = WriteLog(
            self.root_dir / collection_id / "write_log.jsonl", durability_mode=durability_mode
        )
        self.durability_mode = durability_mode
        self.manifest_store = ManifestStore(self.root_dir / "manifests")
        self.segment_manifest_store = SegmentManifestStore(self.root_dir / "segment-manifests")
        self.segment_store = LocalSegmentStore(self.root_dir / "segments")
        self.segment_builder = SegmentBuilder(self.root_dir / "segments", quantizer=self.quantizer)
        self.recovery_manager = RecoveryManager(
            write_log=self.write_log, mutable_buffer_provider=self._get_mutable_buffer
        )
        self.query_executor = QueryExecutor(
            mutable_buffer=self.mutable_buffer, quantizer=self.quantizer
        )
        self.segment_cache = SegmentReadCache(segment_cache_size)
        self.decoded_segment_cache = SegmentReadCache(segment_cache_size)
        self.segment_read_stats = SegmentReadStats()
        self.flush_threshold = flush_threshold

        # Multi-shard support: per-shard mutable buffers and query executors.
        # shard-0 uses the default mutable_buffer / query_executor for backward compat.
        self._shard_buffers: dict[str, MutableBuffer] = {"shard-0": self.mutable_buffer}
        self._shard_query_executors: dict[str, QueryExecutor] = {"shard-0": self.query_executor}
        self._shard_auto_flush_counters: dict[str, int] = {"shard-0": 0}

        self._write_epoch = self.mutable_buffer.watermark()
        self._auto_flush_segment_counter = 0

    def upsert(
        self,
        *,
        vector_id: str,
        embedding: list[float],
        metadata: dict[str, object] | None = None,
        shard_id: str = "shard-0",
    ) -> int:  # noqa: E501
        self._write_epoch += 1
        self.write_log.append_upsert(
            collection_id=self.collection_id,
            vector_id=vector_id,
            shard_id=shard_id,
            write_epoch=self._write_epoch,
            embedding=embedding,
            metadata=metadata or {},
        )
        self._get_mutable_buffer(shard_id).upsert(
            vector_id=vector_id,
            embedding=embedding,
            metadata=metadata or {},
            embedding_version=self.embedding_version,
            quantizer_version=self.quantizer_version,
            write_epoch=self._write_epoch,
            shard_id=shard_id,
        )
        self._maybe_auto_flush(shard_id=shard_id)
        return self._write_epoch

    def delete(self, *, vector_id: str, shard_id: str = "shard-0") -> int:
        self._write_epoch += 1
        self.write_log.append_delete(
            collection_id=self.collection_id,
            vector_id=vector_id,
            shard_id=shard_id,
            write_epoch=self._write_epoch,
        )
        self._get_mutable_buffer(shard_id).delete(
            vector_id=vector_id,
            embedding_version=self.embedding_version,
            quantizer_version=self.quantizer_version,
            write_epoch=self._write_epoch,
            shard_id=shard_id,
        )
        return self._write_epoch

    def _get_mutable_buffer(self, shard_id: str) -> MutableBuffer:
        if shard_id not in self._shard_buffers:
            buf = MutableBuffer(collection_id=self.collection_id)
            self._shard_buffers[shard_id] = buf
            self._shard_query_executors[shard_id] = QueryExecutor(
                mutable_buffer=buf, quantizer=self.quantizer
            )
            self._shard_auto_flush_counters[shard_id] = 0
        return self._shard_buffers[shard_id]

    def _get_query_executor(self, shard_id: str) -> QueryExecutor:
        self._get_mutable_buffer(shard_id)  # ensure initialized
        return self._shard_query_executors[shard_id]

    def _maybe_auto_flush(self, shard_id: str = "shard-0") -> None:
        if self.flush_threshold is None:
            return
        buf = self._get_mutable_buffer(shard_id)
        mutable_count = len(buf.all_entries())
        if mutable_count >= self.flush_threshold:
            self._shard_auto_flush_counters[shard_id] = (
                self._shard_auto_flush_counters.get(shard_id, 0) + 1
            )
            counter = self._shard_auto_flush_counters[shard_id]
            self._auto_flush_segment_counter = counter  # keep compat attr in sync for shard-0
            self.flush_mutable(
                shard_id=shard_id,
                segment_id=f"seg-auto-{counter}",
                generation=counter,
            )

    def shard_live_row_fraction(self, *, shard_id: str = "shard-0") -> float | None:
        """Return live / total rows across sealed segments for this shard.

        Returns None when there are no sealed segments.
        """
        segment_manifests = self.segment_manifest_store.list_manifests(
            collection_id=self.collection_id, shard_id=shard_id
        )
        shard_manifest = self.manifest_store.load(
            collection_id=self.collection_id, shard_id=shard_id
        )
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

    def query_exact(
        self, query_vector: list[float], *, top_k: int, shard_id: str = "shard-0"
    ) -> list[str]:
        return [
            item.vector_id
            for item in self._get_query_executor(shard_id).search_exact(query_vector, top_k=top_k)
        ]

    def query_compressed(
        self, query_vector: list[float], *, top_k: int, shard_id: str = "shard-0"
    ) -> list[str]:
        return [
            item.vector_id
            for item in self._get_query_executor(shard_id).search_compressed(
                query_vector, top_k=top_k
            )
        ]

    def flush_mutable(
        self,
        *,
        shard_id: str = "shard-0",
        segment_id: str = "seg-0",
        generation: int = 1,
        truncate_write_log: bool = False,
    ) -> ShardManifest | None:  # noqa: E501
        buf = self._get_mutable_buffer(shard_id)
        entries = buf.all_entries()
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
            n_ivf_clusters=self.ivf_n_clusters if self.enable_ivf else None,
        )
        self.segment_cache.invalidate(_paths.segment_path)
        self.decoded_segment_cache.invalidate(_paths.segment_path)
        if hasattr(self, "_segment_ivf_indexes"):
            self._segment_ivf_indexes.pop(str(_paths.segment_path), None)
        now = datetime.now(timezone.utc)
        segment_manifest.state = SegmentState.ACTIVE
        segment_manifest.sealed_at = segment_manifest.sealed_at or now
        segment_manifest.activated_at = segment_manifest.activated_at or now
        self.segment_manifest_store.save(segment_manifest)

        previous_shard_manifest = self.manifest_store.load(
            collection_id=self.collection_id, shard_id=shard_id
        )
        prior_active_segment_ids = (
            previous_shard_manifest.active_segment_ids
            if previous_shard_manifest is not None
            else []
        )
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
        buf.remove_many(entry.record.vector_id for entry in entries)
        if truncate_write_log:
            self.truncate_write_log_before(shard_manifest.replay_from_write_epoch)
        return shard_manifest

    def load_manifest_set(self, *, shard_id: str = "shard-0") -> tuple[ShardManifest | None, list]:
        shard_manifest = self.manifest_store.load(
            collection_id=self.collection_id, shard_id=shard_id
        )
        segment_manifests = self.segment_manifest_store.list_manifests(
            collection_id=self.collection_id, shard_id=shard_id
        )
        if shard_manifest is not None:
            issues = validate_manifest_set(
                shard_manifest=shard_manifest, segment_manifests=segment_manifests
            )
            raise_for_manifest_issues(issues)
        return shard_manifest, segment_manifests

    def collect_retired_segments(
        self, *, shard_id: str = "shard-0"
    ) -> SegmentGarbageCollectionExecution:
        executor = SegmentGarbageCollectionExecutor(
            segment_manifest_store=self.segment_manifest_store,
            segments_root=self.root_dir / "segments",
            manifests_root=self.root_dir / "manifests",
        )
        return executor.collect_shard(collection_id=self.collection_id, shard_id=shard_id)

    def recover(self, *, shard_id: str = "shard-0") -> int:
        shard_manifest = self.manifest_store.load(
            collection_id=self.collection_id, shard_id=shard_id
        )
        replay_from_write_epoch = (
            shard_manifest.replay_from_write_epoch if shard_manifest is not None else 0
        )
        applied = self.recovery_manager.replay(
            embedding_version=self.embedding_version,
            quantizer_version=self.quantizer_version,
            after_write_epoch=replay_from_write_epoch,
            shard_id=shard_id,
        )
        self._write_epoch = max(
            self._write_epoch,
            max((buffer.watermark() for buffer in self._shard_buffers.values()), default=0),
            replay_from_write_epoch,
        )
        return applied

    # ------------------------------------------------------------------
    # Write-log truncation
    # ------------------------------------------------------------------

    def truncate_write_log_before(self, write_epoch: int) -> int:
        """Remove write-log entries with write_epoch <= *write_epoch*.

        Returns the number of entries removed.  The log file is rewritten
        atomically (write to tmp, rename).
        """
        return self.write_log.truncate_before(write_epoch)

    # ------------------------------------------------------------------
    # Collection-level stats
    # ------------------------------------------------------------------

    def collection_stats(self) -> dict[str, object]:
        """Return a summary of the collection across all shards."""
        import os

        # Gather all shard IDs known via manifests
        known_shards: set[str] = set()
        manifests_dir = self.root_dir / "manifests" / self.collection_id
        if manifests_dir.exists():
            for p in manifests_dir.iterdir():
                if p.name.endswith(".manifest.json"):
                    known_shards.add(p.name.replace(".manifest.json", ""))
        # Also include shards with live buffer data
        known_shards.update(self._shard_buffers.keys())

        total_segment_count = 0
        total_live_rows = 0
        total_rows_all = 0

        for shard_id in known_shards:
            shard_manifest = self.manifest_store.load(
                collection_id=self.collection_id, shard_id=shard_id
            )
            if shard_manifest is None:
                continue
            active_ids = set(shard_manifest.active_segment_ids)
            segment_manifests = self.segment_manifest_store.list_manifests(
                collection_id=self.collection_id, shard_id=shard_id
            )
            active = [m for m in segment_manifests if m.segment_id in active_ids]
            total_segment_count += len(active)
            total_live_rows += sum(m.live_row_count for m in active)
            total_rows_all += sum(m.row_count for m in active)

        delete_ratio = (1.0 - total_live_rows / total_rows_all) if total_rows_all > 0 else 0.0

        # Mutable buffer size = total entries across all shard buffers
        mutable_buffer_size = sum(len(buf.all_entries()) for buf in self._shard_buffers.values())

        # Storage size: sum of all files under collection segments dir
        segments_dir = self.root_dir / "segments" / self.collection_id
        storage_bytes = 0
        if segments_dir.exists():
            for p in segments_dir.rglob("*"):
                if p.is_file():
                    storage_bytes += os.path.getsize(p)

        return {
            "collection_id": self.collection_id,
            "shard_count": len(known_shards),
            "total_segment_count": total_segment_count,
            "total_live_rows": total_live_rows,
            "total_delete_ratio": delete_ratio,
            "mutable_buffer_size": mutable_buffer_size,
            "storage_bytes": storage_bytes,
        }

    def segment_cache_stats(self) -> dict[str, object]:
        return {
            "indexed_cache": asdict(self.segment_cache.stats()),
            "decoded_cache": asdict(self.decoded_segment_cache.stats()),
            "segment_reads": self.segment_read_stats.snapshot(),
        }

    def reset_segment_cache_stats(self) -> None:
        self.segment_cache.reset_stats()
        self.decoded_segment_cache.reset_stats()
        self.segment_read_stats.reset()

    def clear_segment_caches(self) -> None:
        self.segment_cache.clear()
        self.decoded_segment_cache.clear()
