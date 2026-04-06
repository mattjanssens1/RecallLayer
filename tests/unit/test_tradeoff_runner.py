from __future__ import annotations

from recalllayer.benchmark.tradeoff_runner import (
    render_tradeoff_markdown,
    run_quantizer_tradeoff_benchmark,
)


def test_tradeoff_benchmark_reports_rows(tmp_path) -> None:
    rows = run_quantizer_tradeoff_benchmark(root_prefix=tmp_path / "tradeoffs")

    assert rows
    assert any(row.search_budget is None for row in rows)
    assert any(row.search_budget == 16 for row in rows)
    assert all(row.storage_bytes > 0 for row in rows)
    assert all(row.bytes_per_vector > 0 for row in rows)
    assert all(0.0 <= row.compressed_recall_at_1 <= 1.0 for row in rows)
    assert all(0.0 <= row.compressed_recall_at_10 <= 1.0 for row in rows)


def test_tradeoff_markdown_includes_tradeoff_columns(tmp_path) -> None:
    rows = run_quantizer_tradeoff_benchmark(root_prefix=tmp_path / "tradeoffs")
    markdown = render_tradeoff_markdown(rows)

    assert "| Quantizer | Search budget | Exact ms | Compressed ms |" in markdown
    assert "Bytes/vector" in markdown
