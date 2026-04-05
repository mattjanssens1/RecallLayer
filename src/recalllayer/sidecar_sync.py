from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from recalllayer.sidecar import RecallLayerSidecar


@dataclass(slots=True)
class OutboxEvent:
    event_id: int
    document_id: str
    operation: str
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    attempts: int = 0


class SidecarSyncOutbox(Protocol):
    def enqueue(
        self,
        *,
        document_id: str,
        operation: str,
        payload: dict[str, Any] | None = None,
    ) -> OutboxEvent: ...

    def pending(self) -> list[OutboxEvent]: ...

    def mark_processed(self, event_id: int) -> None: ...

    def mark_failed(self, event_id: int) -> None: ...


class InMemorySidecarSyncOutbox:
    """Small local outbox used to make the sidecar sync story concrete in tests/docs."""

    def __init__(self) -> None:
        self._events: list[OutboxEvent] = []
        self._next_id = 1

    def enqueue(
        self,
        *,
        document_id: str,
        operation: str,
        payload: dict[str, Any] | None = None,
    ) -> OutboxEvent:
        event = OutboxEvent(
            event_id=self._next_id,
            document_id=document_id,
            operation=operation,
            payload=payload or {},
        )
        self._next_id += 1
        self._events.append(event)
        return event

    def pending(self) -> list[OutboxEvent]:
        return [event for event in self._events if event.status == "pending"]

    def mark_processed(self, event_id: int) -> None:
        event = self._get(event_id)
        event.status = "processed"

    def mark_failed(self, event_id: int) -> None:
        event = self._get(event_id)
        event.status = "failed"

    def _get(self, event_id: int) -> OutboxEvent:
        for event in self._events:
            if event.event_id == event_id:
                return event
        raise KeyError(event_id)


class RecallLayerSyncWorker:
    """Consumes durable-ish host events and applies them to RecallLayer.

    This is intentionally lightweight. It demonstrates the recommended path:
    host DB truth -> outbox event -> RecallLayer sync/repair.
    """

    def __init__(self, *, sidecar: RecallLayerSidecar, outbox: SidecarSyncOutbox) -> None:
        self.sidecar = sidecar
        self.outbox = outbox

    def process_pending(self) -> list[str]:
        synced_vector_ids: list[str] = []
        for event in self.outbox.pending():
            event.attempts += 1
            try:
                if event.operation in {"upsert", "repair", "backfill"}:
                    synced_vector_ids.append(self.sidecar.sync_document(event.document_id))
                elif event.operation in {"delete", "unpublish"}:
                    synced_vector_ids.append(self.sidecar.sync_document(event.document_id))
                else:
                    raise ValueError(f"unsupported outbox operation: {event.operation}")
                self.outbox.mark_processed(event.event_id)
            except Exception:
                self.outbox.mark_failed(event.event_id)
                raise
        return synced_vector_ids


def apply_host_write_with_outbox(
    *,
    sidecar: RecallLayerSidecar,
    outbox: SidecarSyncOutbox,
    document_id: str,
    title: str,
    body: str,
    region: str,
    status: str = "published",
) -> OutboxEvent:
    sidecar.write_source_record(
        document_id=document_id,
        title=title,
        body=body,
        region=region,
        status=status,
    )
    return outbox.enqueue(document_id=document_id, operation="upsert", payload={"status": status})


def apply_host_unpublish_with_outbox(
    *,
    sidecar: RecallLayerSidecar,
    outbox: SidecarSyncOutbox,
    document_id: str,
) -> OutboxEvent:
    sidecar.host_db.set_status(document_id=document_id, status="unpublished")
    return outbox.enqueue(document_id=document_id, operation="unpublish")


__all__ = [
    "OutboxEvent",
    "SidecarSyncOutbox",
    "InMemorySidecarSyncOutbox",
    "RecallLayerSyncWorker",
    "apply_host_write_with_outbox",
    "apply_host_unpublish_with_outbox",
]
