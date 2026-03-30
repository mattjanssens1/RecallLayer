from __future__ import annotations

from typing import Iterable

from turboquant_db.engine.sealed_segments import SegmentReader
from turboquant_db.quantization.base import Quantizer
from turboquant_db.retrieval.base import Candidate, IndexedVector
from turboquant_db.retrieval.exact import ExactRetriever
from turboquant_db.retrieval.scan import CompressedScanRetriever


def search_sealed_segments_compressed(
    *,
    query_vector: list[float],
    top_k: int,
    quantizer: Quantizer,
    segment_paths: Iterable[str],
) -> list[Candidate]:
    retriever = CompressedScanRetriever(quantizer=quantizer)
    for path in segment_paths:
        reader = SegmentReader(path)
        for indexed in reader.iter_indexed_vectors():
            retriever.add(indexed)
    return retriever.search(query_vector=query_vector, top_k=top_k)


def search_sealed_segments_exactish(
    *,
    query_vector: list[float],
    top_k: int,
    segment_paths: Iterable[str],
) -> list[Candidate]:
    retriever = ExactRetriever()
    for path in segment_paths:
        reader = SegmentReader(path)
        for indexed in reader.iter_indexed_vectors():
            reconstructed = (indexed.encoded.codes.astype("float32") * indexed.encoded.scale).tolist()
            retriever.add(vector_id=indexed.vector_id, values=reconstructed, metadata=indexed.metadata)
    return retriever.search(query_vector=query_vector, top_k=top_k)


def merge_candidates(*candidate_lists: list[Candidate], top_k: int) -> list[Candidate]:
    merged: dict[str, Candidate] = {}
    for candidate_list in candidate_lists:
        for candidate in candidate_list:
            current = merged.get(candidate.vector_id)
            if current is None or candidate.score > current.score:
                merged[candidate.vector_id] = candidate
    ranked = sorted(merged.values(), key=lambda item: item.score, reverse=True)
    return ranked[:top_k]
