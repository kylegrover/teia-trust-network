"""Small helpers used by handlers during the interning migration.

- resolve_address_async(obj, fk_attr, legacy_attr): prefer the FK (Holder), fall back to legacy string.
- resolve_holder_async(address_or_id): convenience to get Holder by id or address.

Keep helpers minimal and defensive so they can be applied repo-wide without risk.
"""
from __future__ import annotations

from typing import Any, Optional

from dipdup import fields

from teia_ecosystem_indexer import models


async def resolve_holder_async(value: Any) -> Optional[models.Holder]:
    """Return a Holder from an id or address or model instance (or None)."""
    if value is None:
        return None
    # already a model instance
    if hasattr(value, 'address') and hasattr(value, 'id'):
        return value
    # integer PK
    if isinstance(value, int):
        return await models.Holder.get_or_none(id=value)
    # address string
    if isinstance(value, str):
        return await models.Holder.get_or_none(address=value)
    return None


async def resolve_address_async(obj: Any, fk_attr: str, legacy_attr: str) -> Optional[str]:
    """Resolve an address for a model instance.

    Strategy (defensive):
    - If FK is present and resolved, return holder.address
    - If FK is an int PK, fetch Holder by id
    - Otherwise return legacy string column (if present)
    - Return None if nothing found
    """
    # 1) try FK attribute without extra queries
    fk = getattr(obj, fk_attr, None)
    # If fk is a model instance with 'address', prefer it
    if fk is not None and hasattr(fk, 'address'):
        return getattr(fk, 'address')
    # If fk is an int (stored PK), fetch Holder
    if isinstance(fk, int):
        holder = await models.Holder.get_or_none(id=fk)
        return holder.address if holder else None
    # If fk is a string (unlikely), treat as address
    if isinstance(fk, str):
        return fk
    # 2) fallback to legacy string column (no extra DB hits)
    legacy = getattr(obj, legacy_attr, None)
    return legacy
