from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ComparisonRow:
    name: str
    latency_ms: float
    recall_at_1: float
    recall_at_10: float


def render_markdown_table(rows: list[ComparisonRow]) -> str:
    lines = [
        "| Backend | Latency ms | Recall@1 | Recall@10 |",
        "|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.name} | {row.latency_ms:.3f} | {row.recall_at_1:.3f} | {row.recall_at_10:.3f} |"
        )
    return "\n".join(lines)
