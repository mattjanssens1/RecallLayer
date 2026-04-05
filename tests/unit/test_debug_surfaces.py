from recalllayer.engine.debug_surfaces import DebugEngineSurface
from recalllayer.engine.local_db import LocalVectorDatabase


def test_debug_engine_surface_exposes_recovery_audit_and_wal_snapshot(tmp_path) -> None:
    db = LocalVectorDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'region': 'us'})
    db.delete(vector_id='a')

    surface = DebugEngineSurface(root_dir=tmp_path, collection_id='documents')
    audit_rows = surface.recovery_audit()
    snapshot = surface.wal_snapshot()

    assert audit_rows[0]['collection_id'] == 'documents'
    assert audit_rows[0]['delete_count'] == 1
    assert snapshot['total_entries'] == 2
    assert snapshot['deleted_vector_count'] == 1
