from turboquant_db.benchmark.proof_pack import build_proof_rows, render_proof_markdown


def test_proof_pack_builds_rows_with_exact_baselines() -> None:
    rows = build_proof_rows(root_prefix=".proof_pack_test")

    assert rows
    exact_rows = [row for row in rows if row.query_path == "exact-hybrid"]
    assert exact_rows
    assert all(row.recall_at_1 == 1.0 for row in exact_rows)
    assert all(row.recall_at_10 == 1.0 for row in exact_rows)

    markdown = render_proof_markdown(rows)
    assert "| Fixture | Query path | Backend | Latency ms | Recall@1 | Recall@10 | Note |" in markdown
    assert "turboquant-adapter" in markdown
