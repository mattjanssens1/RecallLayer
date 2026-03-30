from turboquant_db.benchmark.highdim_runner import run_highdim_benchmark


def test_highdim_benchmark_runner_returns_rows() -> None:
    artifacts = run_highdim_benchmark(root_prefix=".test_highdim_benchmark")
    assert artifacts.rows
    assert artifacts.fixture_name.startswith("highdim_fixture")
