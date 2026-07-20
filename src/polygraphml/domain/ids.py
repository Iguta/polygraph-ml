from __future__ import annotations

import ulid


def new_id(prefix: str) -> str:
    """Return a sortable public identifier with a stable type prefix."""
    return f"{prefix}_{ulid.new()}"
