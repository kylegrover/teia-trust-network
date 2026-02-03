import pytest

from teia_ecosystem_indexer.utils import resolve_address_async


class Dummy:
    def __init__(self, legacy=None, fk=None):
        self.creator_address = legacy
        self.creator = fk


class HolderLike:
    def __init__(self, address):
        self.address = address
        self.id = 1


@pytest.mark.asyncio
async def test_resolve_address_prefers_fk_instance():
    h = HolderLike('tz1foo')
    d = Dummy(legacy='tz1bar', fk=h)
    assert await resolve_address_async(d, 'creator', 'creator_address') == 'tz1foo'


@pytest.mark.asyncio
async def test_resolve_address_falls_back_to_legacy():
    d = Dummy(legacy='tz1bar', fk=None)
    assert await resolve_address_async(d, 'creator', 'creator_address') == 'tz1bar'
