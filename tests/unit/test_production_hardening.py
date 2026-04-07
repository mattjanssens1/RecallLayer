"""Tests for the five production-hardening features:

1. Rate limiting (SlidingWindowRateLimiter)
2. TLS configuration (docker-entrypoint.sh passthrough — tested indirectly)
3. Multi-tenancy (per-key collection isolation)
4. Auto-flush scheduler (AutoFlushScheduler background thread)
5. Dynamic IVF (ivf_auto_threshold in LocalVectorDatabase)
"""
from __future__ import annotations

import math
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 1. Rate Limiter
# ---------------------------------------------------------------------------


class TestSlidingWindowRateLimiter:
    def test_allows_requests_within_limit(self):
        from recalllayer.api.rate_limiter import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60.0)
        for _ in range(5):
            allowed, retry_after = limiter.check("key-a")
            assert allowed is True
            assert retry_after == 0.0

    def test_blocks_requests_over_limit(self):
        from recalllayer.api.rate_limiter import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60.0)
        for _ in range(3):
            limiter.check("key-b")
        allowed, retry_after = limiter.check("key-b")
        assert allowed is False
        assert retry_after > 0.0

    def test_different_keys_are_independent(self):
        from recalllayer.api.rate_limiter import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0)
        allowed_a, _ = limiter.check("key-a")
        allowed_a2, _ = limiter.check("key-a")  # should be blocked
        allowed_b, _ = limiter.check("key-b")  # different key — should pass

        assert allowed_a is True
        assert allowed_a2 is False
        assert allowed_b is True

    def test_window_expiry_allows_new_requests(self):
        from recalllayer.api.rate_limiter import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=0.1)
        limiter.check("key-c")
        time.sleep(0.15)
        allowed, _ = limiter.check("key-c")
        assert allowed is True


# ---------------------------------------------------------------------------
# 2. TLS — app config parses env vars (actual SSL binding is an infra concern)
# ---------------------------------------------------------------------------


class TestTLSConfig:
    def test_entrypoint_script_exists(self):
        """The docker-entrypoint.sh that wires TLS into uvicorn must exist."""
        script = Path(__file__).parent.parent.parent / "docker-entrypoint.sh"
        assert script.exists(), "docker-entrypoint.sh is missing"
        content = script.read_text()
        assert "ssl-certfile" in content
        assert "ssl-keyfile" in content
        assert "RECALLLAYER_TLS_CERT" in content
        assert "RECALLLAYER_TLS_KEY" in content

    def test_dockerfile_exposes_tls_env_vars(self):
        dockerfile = Path(__file__).parent.parent.parent / "Dockerfile"
        content = dockerfile.read_text()
        assert "RECALLLAYER_TLS_CERT" in content
        assert "RECALLLAYER_TLS_KEY" in content


# ---------------------------------------------------------------------------
# 3. Multi-tenancy
# ---------------------------------------------------------------------------


class TestMultiTenancy:
    def _make_config(self, tenants_str: str):
        from recalllayer.api.recalllayer_sidecar_app import (
            SidecarAppConfig,
            _parse_tenants,
        )

        cfg = SidecarAppConfig(root_dir=".tmp_test_mt")
        cfg.tenants = _parse_tenants(tenants_str)
        return cfg

    def test_parse_tenants(self):
        from recalllayer.api.recalllayer_sidecar_app import _parse_tenants

        tenants = _parse_tenants("keyA:col-a,keyB:col-b")
        assert len(tenants) == 2
        assert tenants[0].api_key == "keyA"
        assert tenants[0].collection_id == "col-a"
        assert tenants[1].api_key == "keyB"
        assert tenants[1].collection_id == "col-b"

    def test_parse_tenants_invalid_format(self):
        from recalllayer.api.recalllayer_sidecar_app import _parse_tenants

        with pytest.raises(ValueError, match="api_key:collection_id"):
            _parse_tenants("bad-entry-no-colon")

    def test_each_tenant_gets_own_sidecar(self, tmp_path):
        from recalllayer.api.recalllayer_sidecar_app import (
            SidecarAppConfig,
            _parse_tenants,
            create_recalllayer_sidecar_app,
        )

        cfg = SidecarAppConfig(root_dir=str(tmp_path))
        cfg.tenants = _parse_tenants("key1:col-1,key2:col-2")
        cfg.auto_flush_interval_sec = 0  # disable scheduler for test

        app = create_recalllayer_sidecar_app(config=cfg)
        tenant_sidecars = app.state.tenant_sidecars

        assert "key1" in tenant_sidecars
        assert "key2" in tenant_sidecars
        # Each tenant has a distinct sidecar pointing at a distinct collection
        assert tenant_sidecars["key1"] is not tenant_sidecars["key2"]
        assert tenant_sidecars["key1"].collection_id == "col-1"
        assert tenant_sidecars["key2"].collection_id == "col-2"

    @pytest.mark.anyio
    async def test_missing_api_key_rejected_in_multi_tenant_mode(self, tmp_path):
        from httpx import ASGITransport, AsyncClient

        from recalllayer.api.recalllayer_sidecar_app import (
            SidecarAppConfig,
            _parse_tenants,
            create_recalllayer_sidecar_app,
        )

        cfg = SidecarAppConfig(root_dir=str(tmp_path))
        cfg.tenants = _parse_tenants("secretkey:my-collection")
        cfg.auto_flush_interval_sec = 0

        app = create_recalllayer_sidecar_app(config=cfg)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                "/v1/documents/doc1",
                json={"title": "t", "body": "b", "region": "us", "status": "published"},
            )
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_valid_api_key_accepted_in_multi_tenant_mode(self, tmp_path):
        from httpx import ASGITransport, AsyncClient

        from recalllayer.api.recalllayer_sidecar_app import (
            SidecarAppConfig,
            _parse_tenants,
            create_recalllayer_sidecar_app,
        )

        cfg = SidecarAppConfig(root_dir=str(tmp_path))
        cfg.tenants = _parse_tenants("secretkey:my-collection")
        cfg.auto_flush_interval_sec = 0

        app = create_recalllayer_sidecar_app(config=cfg)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                "/v1/documents/doc1",
                json={"title": "t", "body": "b", "region": "us", "status": "published"},
                headers={"x-api-key": "secretkey"},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. Auto-flush scheduler
# ---------------------------------------------------------------------------


class TestAutoFlushScheduler:
    def test_scheduler_flushes_on_interval(self, tmp_path):
        """Scheduler calls flush within a short interval when buffer is non-empty."""
        from recalllayer.api.recalllayer_sidecar_app import AutoFlushScheduler
        from recalllayer.sidecar import InMemoryPostgresRepository, RecallLayerSidecar

        sidecar = RecallLayerSidecar(
            host_db=InMemoryPostgresRepository(),
            root_dir=tmp_path,
            collection_id="auto-flush-test",
        )
        # Pre-populate the mutable buffer so there is something to flush
        sidecar.upsert_and_sync_document(
            document_id="d1", title="Hello", body="World", region="us"
        )

        buf_before = sum(
            len(buf.all_entries())
            for buf in sidecar.recall_layer._shard_buffers.values()
        )
        assert buf_before > 0

        scheduler = AutoFlushScheduler(
            sidecars={"auto-flush-test": sidecar},
            interval_sec=0.05,  # very short for test
            upsert_threshold=999_999,  # threshold won't trigger
            poll_sec=0.02,
        )
        scheduler.start()
        time.sleep(0.3)
        scheduler.stop()

        buf_after = sum(
            len(buf.all_entries())
            for buf in sidecar.recall_layer._shard_buffers.values()
        )
        assert buf_after == 0, "buffer should have been flushed by the scheduler"

    def test_scheduler_flushes_on_threshold(self, tmp_path):
        """Scheduler flushes when upsert_threshold is reached before interval."""
        from recalllayer.api.recalllayer_sidecar_app import AutoFlushScheduler
        from recalllayer.sidecar import InMemoryPostgresRepository, RecallLayerSidecar

        sidecar = RecallLayerSidecar(
            host_db=InMemoryPostgresRepository(),
            root_dir=tmp_path,
            collection_id="threshold-flush-test",
        )
        sidecar.upsert_and_sync_document(
            document_id="d1", title="A", body="B", region="us"
        )

        scheduler = AutoFlushScheduler(
            sidecars={"threshold-flush-test": sidecar},
            interval_sec=3600.0,  # very long — won't trigger by time
            upsert_threshold=1,  # trigger immediately
            poll_sec=0.02,
        )
        scheduler.start()
        time.sleep(0.3)
        scheduler.stop()

        buf_after = sum(
            len(buf.all_entries())
            for buf in sidecar.recall_layer._shard_buffers.values()
        )
        assert buf_after == 0


# ---------------------------------------------------------------------------
# 5. Dynamic IVF
# ---------------------------------------------------------------------------


class TestDynamicIVF:
    def test_ivf_disabled_below_threshold(self, tmp_path):
        from recalllayer.engine.local_db import LocalVectorDatabase

        db = LocalVectorDatabase(
            collection_id="ivf-test",
            root_dir=tmp_path,
            ivf_auto_threshold=100,
        )
        # Only 5 vectors — well below threshold
        for i in range(5):
            db.upsert(vector_id=f"v{i}", embedding=[float(i)] * 4)

        result = db._resolve_ivf_clusters(shard_id="shard-0")
        assert result is None, "IVF should be disabled below threshold"

    def test_ivf_enabled_above_threshold(self, tmp_path):
        from recalllayer.engine.local_db import LocalVectorDatabase

        db = LocalVectorDatabase(
            collection_id="ivf-test-large",
            root_dir=tmp_path,
            ivf_auto_threshold=10,
        )
        for i in range(20):
            db.upsert(vector_id=f"v{i}", embedding=[float(i)] * 4)

        result = db._resolve_ivf_clusters(shard_id="shard-0")
        assert result is not None, "IVF should be enabled above threshold"
        expected = max(8, min(4096, math.isqrt(20)))
        assert result == expected

    def test_ivf_clusters_scale_with_corpus(self, tmp_path):
        from recalllayer.engine.local_db import LocalVectorDatabase

        db = LocalVectorDatabase(
            collection_id="ivf-scale",
            root_dir=tmp_path,
            ivf_auto_threshold=0,  # always on
        )
        for i in range(10_000):
            db.upsert(vector_id=f"v{i}", embedding=[float(i % 128)] * 4)

        result = db._resolve_ivf_clusters(shard_id="shard-0")
        assert result is not None
        assert result == max(8, min(4096, math.isqrt(10_000)))  # == 100

    def test_manual_enable_ivf_overrides_auto(self, tmp_path):
        from recalllayer.engine.local_db import LocalVectorDatabase

        db = LocalVectorDatabase(
            collection_id="ivf-manual",
            root_dir=tmp_path,
            enable_ivf=True,
            ivf_n_clusters=32,
            ivf_auto_threshold=999_999,
        )
        db.upsert(vector_id="v0", embedding=[1.0, 2.0, 3.0, 4.0])
        result = db._resolve_ivf_clusters(shard_id="shard-0")
        assert result == 32, "manual enable_ivf should use the explicit cluster count"
