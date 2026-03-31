from __future__ import annotations

import warnings
from typing import Any


def build_alias_warning(*, module_name: str, preferred_module: str, purpose: str) -> str:
    return (
        f"{module_name} is a soft-deprecated compatibility alias for {purpose}; "
        f"prefer {preferred_module} for new entrypoints."
    )


def emit_alias_warning(*, module_name: str, preferred_module: str, purpose: str) -> None:
    warnings.warn(
        build_alias_warning(module_name=module_name, preferred_module=preferred_module, purpose=purpose),
        DeprecationWarning,
        stacklevel=2,
    )
