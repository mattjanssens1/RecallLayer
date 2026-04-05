from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

try:  # pragma: no cover - import shape is tested via adapter behavior instead.
    import psycopg
except ImportError:  # pragma: no cover - optional dependency.
    psycopg = None

from turboquant_db.engine.compaction_executor import CompactionExecutor
from turboquant_db.engine.compaction_planner import CompactionPlanner
from turboquant_db.engine.compactor import LocalSegmentCompactor
from turboquant_db.engine.manifest_store import ManifestStore
from turboquant_db.engine.segment_manifest_store import SegmentManifestStore
from turboquant_db.engine.showcase_scored_db import ShowcaseScoredDatabase


@dataclass(slots=True)
class HostDocument:
    """Canonical host-database record used by the sidecar demo."""

    document_id: str
    title: str
    body: str
    region: str
    status: str = "published"

    @property
    def vector_id(self) -> str:
        return f"document:{self.document_id}"


class HostDocumentRepository(Protocol):
    def upsert_document(
        self,
        *,
        document_id: str,
        title: str,
        body: str,
        region: str,
        status: str = "published",
    ) -> HostDocument: ...

    def set_status(self, *, document_id: str, status: str) -> HostDocument: ...

    def get_document(self, document_id: str) -> HostDocument | None: ...

    def delete_document(self, document_id: str) -> HostDocument | None: ...

    def hydrate_many(self, vector_ids: list[str]) -> list[dict[str, Any]]: ...

    def list_documents(self, *, include_unpublished: bool = True) -> list[HostDocument]: ...

    def list_document_ids(self, *, include_unpublished: bool = True) -> list[str]: ...


class InMemoryPostgresRepository:
    """In-memory repository shaped like a future Postgres adapter boundary."""

    def __init__(self) -> None:
        self._documents: dict[str, HostDocument] = {}

    def upsert_document(
        self,
        *,
        document_id: str,
        title: str,
        body: str,
        region: str,
        status: str = "published",
    ) -> HostDocument:
        document = HostDocument(
            document_id=document_id,
            title=title,
            body=body,
            region=region,
            status=status,
        )
        self._documents[document_id] = document
        return document

    def set_status(self, *, document_id: str, status: str) -> HostDocument:
        document = self._documents[document_id]
        updated = HostDocument(
            document_id=document.document_id,
            title=document.title,
            body=document.body,
            region=document.region,
            status=status,
        )
        self._documents[document_id] = updated
        return updated

    def get_document(self, document_id: str) -> HostDocument | None:
        return self._documents.get(document_id)

    def delete_document(self, document_id: str) -> HostDocument | None:
        return self._documents.pop(document_id, None)

    def list_documents(self, *, include_unpublished: bool = True) -> list[HostDocument]:
        documents = sorted(self._documents.values(), key=lambda document: document.document_id)
        if include_unpublished:
            return documents
        return [document for document in documents if document.status == "published"]

    def list_document_ids(self, *, include_unpublished: bool = True) -> list[str]:
        documents = self.list_documents(include_unpublished=include_unpublished)
        return [document.document_id for document in documents]

    def hydrate_many(self, vector_ids: list[str]) -> list[dict[str, Any]]:
        hydrated: list[dict[str, Any]] = []
        for vector_id in vector_ids:
            prefix, _, raw_id = vector_id.partition(":")
            if prefix != "document" or not raw_id:
                continue
            document = self.get_document(raw_id)
            if document is None or document.status != "published":
                continue
            hydrated.append(
                {
                    "document_id": document.document_id,
                    "vector_id": document.vector_id,
                    "title": document.title,
                    "body": document.body,
                    "region": document.region,
                    "status": document.status,
                }
            )
        return hydrated


InMemoryPostgres = InMemoryPostgresRepository


class PsycopgPostgresRepository:
    """Optional real Postgres adapter boundary for the sidecar story.

    This intentionally keeps the contract small and honest:
    - it uses psycopg only if installed by the integrator
    - it expects a simple `documents` table shape
    - it is suitable for local integration wiring
    - it is not presented as production-ready ORM or migration tooling
    """

    def __init__(self, dsn: str, *, table_name: str = "documents") -> None:
        self.dsn = dsn
        self.table_name = table_name

    @classmethod
    def from_dsn(cls, dsn: str, *, table_name: str = "documents") -> "PsycopgPostgresRepository":
        return cls(dsn, table_name=table_name)

    def _connect(self):
        if psycopg is None:
            raise RuntimeError(
                "psycopg is not installed. "
                "Install psycopg[binary] to use the Postgres adapter path."
            )
        return psycopg.connect(self.dsn)

    def upsert_document(
        self,
        *,
        document_id: str,
        title: str,
        body: str,
        region: str,
        status: str = "published",
    ) -> HostDocument:
        sql = f"""
        insert into {self.table_name} (id, title, body, region, status)
        values (%s, %s, %s, %s, %s)
        on conflict (id) do update set
            title = excluded.title,
            body = excluded.body,
            region = excluded.region,
            status = excluded.status
        returning id, title, body, region, status
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (document_id, title, body, region, status))
            row = cur.fetchone()
        return self._row_to_document(row)

    def set_status(self, *, document_id: str, status: str) -> HostDocument:
        sql = f"""
        update {self.table_name}
        set status = %s
        where id = %s
        returning id, title, body, region, status
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (status, document_id))
            row = cur.fetchone()
        if row is None:
            raise KeyError(document_id)
        return self._row_to_document(row)

    def get_document(self, document_id: str) -> HostDocument | None:
        sql = f"select id, title, body, region, status from {self.table_name} where id = %s"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (document_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_document(row)

    def delete_document(self, document_id: str) -> HostDocument | None:
        sql = (
            f"delete from {self.table_name} "
            "where id = %s returning id, title, body, region, status"
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (document_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_document(row)

    def hydrate_many(self, vector_ids: list[str]) -> list[dict[str, Any]]:
        hydrated: list[dict[str, Any]] = []
        for vector_id in vector_ids:
            prefix, _, raw_id = vector_id.partition(":")
            if prefix != "document" or not raw_id:
                continue
            document = self.get_document(raw_id)
            if document is None or document.status != "published":
                continue
            hydrated.append(
                {
                    "document_id": document.document_id,
                    "vector_id": document.vector_id,
                    "title": document.title,
                    "body": document.body,
                    "region": document.region,
                    "status": document.status,
                }
            )
        return hydrated

    def list_documents(self, *, include_unpublished: bool = True) -> list[HostDocument]:
        sql = f"select id, title, body, region, status from {self.table_name}"
        params: tuple[Any, ...] = ()
        if not include_unpublished:
            sql += " where status = %s"
            params = ("published",)
        sql += " order by id"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [self._row_to_document(row) for row in rows]

    def list_document_ids(self, *, include_unpublished: bool = True) -> list[str]:
        documents = self.list_documents(include_unpublished=include_unpublished)
        return [document.document_id for document in documents]

    @staticmethod
    def _row_to_document(row: Any) -> HostDocument:
        if row is None:
            raise ValueError("expected a row")
        document_id, title, body, region, status = row
        return HostDocument(
            document_id=str(document_id),
            title=title,
            body=body,
            region=region,
            status=status,
        )


class RecallLayerSidecar:
    """Small coordinator showing the intended host-DB + sidecar contract."""

    def __init__(
        self,
        *,
        host_db: HostDocumentRepository,
        root_dir: str | Path,
        collection_id: str = "recalllayer-sidecar-demo",
    ) -> None:
        self.host_db = host_db
        self.root_dir = Path(root_dir)
        self.collection_id = collection_id
        self.recall_layer = ShowcaseScoredDatabase(
            collection_id=collection_id,
            root_dir=self.root_dir,
        )

    def upsert_and_sync_document(
        self,
        *,
        document_id: str,
        title: str,
        body: str,
        region: str,
        status: str = "published",
    ) -> str:
        self.write_source_record(
            document_id=document_id,
            title=title,
            body=body,
            region=region,
            status=status,
        )
        return self.sync_document(document_id)

    def write_source_record(
        self,
        *,
        document_id: str,
        title: str,
        body: str,
        region: str,
        status: str = "published",
    ) -> HostDocument:
        return self.host_db.upsert_document(
            document_id=document_id,
            title=title,
            body=body,
            region=region,
            status=status,
        )

    def sync_document(self, document_id: str) -> str:
        document = self.host_db.get_document(document_id)
        if document is None or document.status != "published":
            vector_id = f"document:{document_id}"
            self.recall_layer.delete(vector_id=vector_id)
            return vector_id

        embedding = self.embed_text(f"{document.title} {document.body}")
        self.recall_layer.upsert(
            vector_id=document.vector_id,
            embedding=embedding,
            metadata={
                "region": document.region,
                "status": document.status,
                "source_table": "documents",
            },
        )
        return document.vector_id

    def unpublish_document(self, document_id: str) -> str:
        self.host_db.set_status(document_id=document_id, status="unpublished")
        return self.sync_document(document_id)

    def delete_document(self, document_id: str) -> str:
        self.host_db.delete_document(document_id)
        return self.sync_document(document_id)

    def repair_documents(self, document_ids: list[str] | None = None) -> list[str]:
        if document_ids is None:
            document_ids = self.known_document_ids()
        return [self.sync_document(document_id) for document_id in document_ids]

    def backfill_from_host(self) -> list[str]:
        return [self.sync_document(document_id) for document_id in self.host_db.list_document_ids()]

    def flush(self, *, segment_id: str = "seg-1", generation: int = 1) -> None:
        self.recall_layer.flush_mutable(segment_id=segment_id, generation=generation)

    def compact(
        self,
        *,
        output_segment_id: str = "seg-compacted",
        generation: int = 1,
        min_segment_count: int = 2,
        max_total_rows: int = 1000,
        shard_id: str = "shard-0",
    ) -> dict[str, Any] | None:
        executor = CompactionExecutor(
            planner=CompactionPlanner(
                min_segment_count=min_segment_count,
                max_total_rows=max_total_rows,
            ),
            compactor=LocalSegmentCompactor(
                segments_root=self.root_dir / "segments",
                manifests_root=self.root_dir / "manifests",
            ),
            manifest_store=ManifestStore(self.root_dir / "manifests"),
            segment_manifest_store=SegmentManifestStore(self.root_dir / "segment-manifests"),
        )
        result = executor.compact_shard(
            collection_id=self.collection_id,
            shard_id=shard_id,
            output_segment_id=output_segment_id,
            generation=generation,
        )
        if result is None:
            return None
        return {
            "active_segment_ids": result.updated_shard_manifest.active_segment_ids,
            "replay_from_write_epoch": result.updated_shard_manifest.replay_from_write_epoch,
            "selected_source_segment_ids": result.selected_source_segment_ids,
            "output_segment_id": result.artifacts.segment_manifest.segment_id,
        }

    def restart(self) -> "RecallLayerSidecar":
        restarted = RecallLayerSidecar(
            host_db=self.host_db,
            root_dir=self.root_dir,
            collection_id=self.collection_id,
        )
        restarted.recall_layer.recover()
        return restarted

    def query_candidates(
        self,
        query_text: str,
        *,
        top_k: int = 3,
        region: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = {"status": {"eq": "published"}}
        if region is not None:
            filters["region"] = {"eq": region}

        hits = self.recall_layer.query_compressed_reranked_hybrid_hits(
            self.embed_text(query_text),
            top_k=top_k,
            candidate_k=max(top_k * 2, top_k),
            filters=filters,
        )
        return [
            {
                "vector_id": hit.vector_id,
                "score": hit.score,
                "metadata": hit.metadata,
            }
            for hit in hits
        ]

    def hydrate_results(self, candidate_ids: list[str]) -> list[dict[str, Any]]:
        return self.host_db.hydrate_many(candidate_ids)

    def search(
        self,
        query_text: str,
        *,
        top_k: int = 3,
        region: str | None = None,
    ) -> dict[str, Any]:
        candidates = self.query_candidates(query_text, top_k=top_k, region=region)
        candidate_ids = [candidate["vector_id"] for candidate in candidates]
        hydrated = self.hydrate_results(candidate_ids)
        return {
            "query": query_text,
            "candidate_ids": candidate_ids,
            "candidates": candidates,
            "hydrated_results": hydrated,
        }

    def known_document_ids(self) -> list[str]:
        host_ids = set(self.host_db.list_document_ids(include_unpublished=True))
        vector_ids = {
            vector_id.partition(":")[2]
            for vector_id in self._known_vector_ids()
            if vector_id.startswith("document:")
        }
        return sorted(host_ids | vector_ids)

    def _known_vector_ids(self) -> set[str]:
        mutable_ids = set(self.recall_layer.mutable_buffer._entries)
        sealed_ids = set(self.recall_layer._sealed_vector_map().keys())
        return mutable_ids | sealed_ids

    @staticmethod
    def embed_text(text: str) -> list[float]:
        lowered = text.lower()
        token_groups = {
            "postgres": {"postgres", "postgresql", "sql", "database"},
            "python": {"python", "pytest", "script", "sdk"},
            "music": {"music", "song", "audio", "playlist"},
            "shipping": {"shipping", "delivery", "warehouse", "order"},
        }
        vector = [0.0] * len(token_groups)
        for index, synonyms in enumerate(token_groups.values()):
            vector[index] = float(sum(lowered.count(token) for token in synonyms))
        if not any(vector):
            vector[0] = float(len(lowered.split())) or 1.0
        norm = sum(value * value for value in vector) ** 0.5
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]


def build_demo_state(root_dir: str | Path) -> RecallLayerSidecar:
    host_db = InMemoryPostgresRepository()
    app = RecallLayerSidecar(host_db=host_db, root_dir=root_dir)

    app.write_source_record(
        document_id="1",
        title="Postgres retrieval guide",
        body="How to hydrate ids from a sidecar search index.",
        region="us",
    )
    app.write_source_record(
        document_id="2",
        title="Python vector SDK",
        body="Pytest and scripts for vector sync workers.",
        region="us",
    )
    app.write_source_record(
        document_id="3",
        title="Music playlist",
        body="A calm audio mix for late-night coding.",
        region="ca",
    )

    for document_id in ["1", "2", "3"]:
        app.sync_document(document_id)

    return app
