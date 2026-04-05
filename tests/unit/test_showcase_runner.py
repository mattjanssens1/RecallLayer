from recalllayer.benchmark.showcase_runner import run_showcase_benchmark


def test_showcase_benchmark_runner_returns_rows() -> None:
    artifacts = run_showcase_benchmark(root_dir=".test_showcase_benchmark_db")
    assert artifacts.rows
    assert artifacts.rows[0].name == "showcase-scored-db:exact-hybrid"
