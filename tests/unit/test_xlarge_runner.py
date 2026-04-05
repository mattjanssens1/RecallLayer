from recalllayer.benchmark.xlarge_runner import run_xlarge_benchmark


def test_xlarge_benchmark_runner_returns_rows() -> None:
    artifacts = run_xlarge_benchmark(root_prefix=".test_xlarge_benchmark")
    assert artifacts.rows
    assert artifacts.fixture_name.startswith("xlarge_synthetic")
