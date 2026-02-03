"""Small helpers used by handlers during the interning migration.

- resolve_address_async(obj, fk_attr, legacy_attr): prefer the FK (Holder), fall back to legacy string.
- resolve_holder_async(address_or_id): convenience to get Holder by id or address.

Keep helpers minimal and defensive so they can be applied repo-wide without risk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from teia_ecosystem_indexer import models

if TYPE_CHECKING:
    from datetime import datetime

# High-speed memory cache for Holder identities to skip heavy DB IO during deep sync
_HOLDER_CACHE: dict[str, models.Holder] = {}
_TOKEN_CACHE: dict[str, models.Token] = {}
_MAX_CACHE_SIZE = 100000


async def get_holder(address: str, timestamp: datetime | None = None) -> models.Holder:
    """Fetch holder from memory cache or DB, ensuring it exists."""
    holder = _HOLDER_CACHE.get(address)

    if not holder:
        holder, created = await models.Holder.get_or_create(address=address)
        if created and timestamp:
            holder.first_seen = timestamp
            holder.last_seen = timestamp
            await holder.save()

        # Simple cache eviction
        if len(_HOLDER_CACHE) > _MAX_CACHE_SIZE:
            key_to_del = next(iter(_HOLDER_CACHE))
            del _HOLDER_CACHE[key_to_del]
        _HOLDER_CACHE[address] = holder

    # Update activity timestamps if provided (Historical sync tracking)
    if timestamp:
        changed = False
        if holder.first_seen is None or timestamp < holder.first_seen:
            holder.first_seen = timestamp
            changed = True
        if holder.last_seen is None or timestamp > holder.last_seen:
            holder.last_seen = timestamp
            changed = True

        if changed:
            await holder.save()

    return holder


async def get_token(contract: str, token_id: int) -> models.Token | None:
    """Fetch token from memory cache or DB."""
    cache_key = f'{contract}:{token_id}'
    if cache_key in _TOKEN_CACHE:
        return _TOKEN_CACHE[cache_key]

    token = await models.Token.get_or_none(contract=contract, token_id=token_id)
    if token:
        if len(_TOKEN_CACHE) > _MAX_CACHE_SIZE:
            key_to_del = next(iter(_TOKEN_CACHE))
            del _TOKEN_CACHE[key_to_del]
        _TOKEN_CACHE[cache_key] = token

    return token


async def resolve_holder_async(value: Any) -> models.Holder | None:
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


async def resolve_address_async(obj: Any, fk_attr: str, legacy_attr: str) -> str | None:
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
        return fk.address
    # If fk is an int (stored PK), fetch Holder
    if isinstance(fk, int):
        holder = await models.Holder.get_or_none(id=fk)
        return holder.address if holder else None
    # If fk is a string (unlikely), treat as address
    if isinstance(fk, str):
        return fk
    # 2) fallback to legacy string column (no extra DB hits)
    return getattr(obj, legacy_attr, None)
