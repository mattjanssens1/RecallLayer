from __future__ import annotations

import os
from pprint import pprint

from recalllayer.sidecar import build_postgres_demo_state


def main() -> None:
    dsn = os.environ["RECALLLAYER_POSTGRES_DSN"]
    table_name = os.environ.get("RECALLLAYER_POSTGRES_TABLE", "documents")
    app = build_postgres_demo_state(
        dsn=dsn,
        root_dir=".postgres_sidecar_live_demo",
        table_name=table_name,
        bootstrap_schema=True,
        reset_table=True,
    )

    print("== live Postgres query: candidate ids from RecallLayer, hydrated from host DB ==")
    pprint(app.search("postgres search sidecar", top_k=2, region="us"))

    print("\n== unpublish document 1 in Postgres and mirror visibility into RecallLayer ==")
    app.unpublish_document("1")
    pprint(app.search("postgres search sidecar", top_k=2, region="us"))

    print("\n== backfill from Postgres host truth ==")
    app.write_source_record(
        document_id="4",
        title="Postgres backfill worker",
        body="Backfill can rebuild RecallLayer state from host truth.",
        region="us",
    )
    app.backfill_from_host()
    pprint(app.search("postgres backfill worker", top_k=2, region="us"))


if __name__ == "__main__":
    main()
