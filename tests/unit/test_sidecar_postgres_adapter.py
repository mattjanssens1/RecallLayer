import pytest

import recalllayer.sidecar as sidecar_module
from recalllayer.sidecar import PsycopgPostgresRepository


def test_psycopg_postgres_repository_requires_optional_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = PsycopgPostgresRepository("postgresql://example")
    monkeypatch.setattr(sidecar_module, "psycopg", None)

    with pytest.raises(RuntimeError, match="psycopg is not installed"):
        repo.get_document("1")


def test_psycopg_postgres_repository_row_mapping_is_honest_and_simple() -> None:
    row = ("1", "Postgres retrieval guide", "Hydrate from host truth.", "us", "published")

    document = PsycopgPostgresRepository._row_to_document(row)

    assert document.document_id == "1"
    assert document.vector_id == "document:1"
    assert document.region == "us"


def test_psycopg_postgres_repository_rejects_unsafe_table_names() -> None:
    with pytest.raises(ValueError, match="unsafe identifier"):
        PsycopgPostgresRepository("postgresql://example", table_name="documents; drop table")
