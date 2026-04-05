from recalllayer.api.showcase_notes import build_collection_notes


def test_build_collection_notes_includes_collection_id_and_extra_fields() -> None:
    notes = build_collection_notes(collection_id='showcase', extra={'surface': 'measured'})

    assert notes == {'collection_id': 'showcase', 'surface': 'measured'}
