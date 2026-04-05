from recalllayer.benchmark.cluster_runner import run_cluster_benchmark


def test_cluster_benchmark_runner_returns_rows() -> None:
    artifacts = run_cluster_benchmark(root_prefix=".test_cluster_benchmark")
    assert artifacts.rows
    assert artifacts.fixture_name.startswith("clustered_fixture")
