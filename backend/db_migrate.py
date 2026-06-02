from __future__ import annotations

from mongo import ensure_indexes


def ensure_schema(_: object = None) -> None:
    # MongoDB migration strategy is index-first in this codebase.
    ensure_indexes()
