from pathlib import Path

from turboquant_db.engine.mutable_buffer import MutableBuffer
from turboquant_db.engine.sealed_segments import SegmentBuilder, SegmentReader
from turboquant_db.quantization.scalar import ScalarQuantizer


def test_segment_builder_and_reader_round_trip(tmp_path: Path) -> None:
    buffer = MutableBuffer(collection_id="documents")
    buffer.upsert(
        vector_id="doc-1",
        embedding=[1.0, 0.0],
        metadata={"region": "us"},
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=1,
    )

    builder = SegmentBuilder(tmp_path, quantizer=ScalarQuantizer())
    manifest, paths = builder.build(
        collection_id="documents",
        shard_id="shard-0",
        segment_id="seg-1",
        generation=1,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        entries=buffer.live_entries(),
    )

    reader = SegmentReader(paths.segment_path)
    rows = list(reader.iter_indexed_vectors())

    assert manifest.row_count == 1
    assert paths.segment_path.exists()
    assert len(rows) == 1
    assert rows[0].vector_id == "doc-1"
