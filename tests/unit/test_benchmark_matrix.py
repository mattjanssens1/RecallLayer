from __future__ import annotations

from pathlib import Path

from recalllayer.benchmark.matrix_runner import (
    BenchmarkScenario,
    generate_scenario_dataset,
    render_matrix_markdown,
    run_benchmark_matrix,
    run_benchmark_scenario,
)


def test_generate_scenario_dataset_respects_shape_and_deletes() -> None:
    scenario = BenchmarkScenario(
        name="shape-check",
        size=20,
        dimensions=8,
        query_count=5,
        shard_count=2,
        delete_ratio=0.2,
        enable_ivf=True,
        ivf_n_clusters=4,
    )

    dataset = generate_scenario_dataset(scenario)

    assert len(dataset.items) == 20
    assert len(dataset.queries) == 5
    assert all(len(query) == 8 for query in dataset.queries)
    assert len(dataset.deleted_ids) >= 1
    assert {shard_id for *_rest, shard_id in dataset.items} == {"shard-0", "shard-1"}


def test_run_benchmark_scenario_returns_storage_and_recall(tmp_path: Path) -> None:
    scenario = BenchmarkScenario(
        name="single-scenario",
        size=48,
        dimensions=8,
        query_count=6,
        top_k=5,
        shard_count=2,
        delete_ratio=0.125,
        enable_ivf=True,
        ivf_n_clusters=8,
        ivf_probe_k=2,
        rerank_probe_k=4,
    )

    result = run_benchmark_scenario(scenario, root_dir=tmp_path)

    assert result.scenario.name == "single-scenario"
    assert result.live_rows == scenario.size - result.deleted_rows
    assert result.storage_bytes > 0
    assert 0.0 <= result.compressed.recall_at_1 <= 1.0
    assert 0.0 <= result.compressed.recall_at_10 <= 1.0
    assert result.reranked is not None
    assert 0.0 <= result.reranked.recall_at_10 <= 1.0


def test_run_benchmark_matrix_and_render_markdown(tmp_path: Path) -> None:
    scenarios = [
        BenchmarkScenario(
            name="tiny-a",
            size=24,
            dimensions=4,
            query_count=4,
            shard_count=1,
            delete_ratio=0.0,
            enable_ivf=False,
        ),
        BenchmarkScenario(
            name="tiny-b",
            size=24,
            dimensions=4,
            query_count=4,
            shard_count=2,
            delete_ratio=0.25,
            enable_ivf=True,
            ivf_n_clusters=4,
            ivf_probe_k=1,
            rerank_probe_k=2,
        ),
    ]

    results = run_benchmark_matrix(scenarios, root_prefix=tmp_path / "matrix")
    markdown = render_matrix_markdown(results)

    assert len(results) == 2
    assert "| Scenario | Size | Dim | Shards | Delete % |" in markdown
    assert "tiny-a" in markdown
    assert "tiny-b" in markdown
