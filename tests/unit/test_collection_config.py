from recalllayer.model.collection import CollectionConfig, CollectionState, DistanceMetric


def test_collection_config_defaults() -> None:
    config = CollectionConfig(
        collection_id="documents",
        metric=DistanceMetric.COSINE,
        embedding_dim=768,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        rerank_precision="fp16",
    )

    assert config.collection_id == "documents"
    assert config.state == CollectionState.ACTIVE
    assert config.write_epoch == 0


def test_collection_id_is_trimmed() -> None:
    config = CollectionConfig(
        collection_id="  docs  ",
        metric=DistanceMetric.DOT_PRODUCT,
        embedding_dim=256,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        rerank_precision="fp32",
    )

    assert config.collection_id == "docs"
