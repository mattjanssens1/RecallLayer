from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RetrievalPlan:
    mode: str
    top_k: int
    use_rerank: bool


class RetrievalPlanner:
    def choose(self, *, top_k: int, approximate: bool = True, rerank: bool = False) -> RetrievalPlan:
        mode = "compressed" if approximate else "exact"
        return RetrievalPlan(mode=mode, top_k=top_k, use_rerank=rerank)
