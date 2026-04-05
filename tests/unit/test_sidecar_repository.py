from turboquant_db.sidecar import InMemoryPostgres, InMemoryPostgresRepository


def test_in_memory_postgres_repository_lists_and_hydrates_published_rows() -> None:
    repo = InMemoryPostgresRepository()
    repo.upsert_document(
        document_id="1",
        title="Postgres retrieval guide",
        body="Hydrate ids from the host repository.",
        region="us",
    )
    repo.upsert_document(
        document_id="2",
        title="Draft only",
        body="Should not hydrate while unpublished.",
        region="us",
        status="unpublished",
    )

    assert repo.list_document_ids() == ["1", "2"]
    assert repo.list_document_ids(include_unpublished=False) == ["1"]
    assert [row["document_id"] for row in repo.hydrate_many(["document:1", "document:2"])] == ["1"]


def test_in_memory_postgres_alias_keeps_backward_compatible_name() -> None:
    repo = InMemoryPostgres()
    assert isinstance(repo, InMemoryPostgresRepository)
