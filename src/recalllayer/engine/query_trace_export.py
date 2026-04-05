from dataclasses import asdict, is_dataclass


def build_query_trace_payload(*, inspection: object, plan: object | None = None, stats: object | None = None, notes: dict | None = None) -> dict:
    payload = {"inspection": _serialize(inspection)}
    if plan is not None:
        payload["plan"] = _serialize(plan)
    if stats is not None:
        payload["stats"] = _serialize(stats)
    if notes:
        payload["notes"] = dict(notes)
    return payload


def _serialize(value: object):
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value
