from __future__ import annotations

from pprint import pprint

from turboquant_db.sidecar import build_demo_state


def main() -> None:
    app = build_demo_state(root_dir=".postgres_sidecar_demo")

    print("== initial query: candidate ids from RecallLayer, hydrated from host DB ==")
    initial = app.search("postgres search sidecar", top_k=2, region="us")
    pprint(initial)

    print("\n== flush mutable state into a sealed segment ==")
    app.flush(segment_id="seg-1", generation=1)
    flushed = app.search("postgres search sidecar", top_k=2, region="us")
    pprint(flushed)

    print("\n== unpublish document 1 in host DB and mirror delete into RecallLayer ==")
    app.unpublish_document("1")
    after_unpublish = app.search("postgres search sidecar", top_k=2, region="us")
    pprint(after_unpublish)

    print("\n== restart RecallLayer and recover post-flush tail writes ==")
    restarted = app.restart()
    after_restart = restarted.search("postgres search sidecar", top_k=2, region="us")
    pprint(after_restart)


if __name__ == "__main__":
    main()
