from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models as models
from teia_ecosystem_indexer.types.hen_minter_v1.tezos_parameters.collect import CollectParameter
from teia_ecosystem_indexer.types.hen_minter_v1.tezos_storage import HenMinterV1Storage


async def on_collect_v1(
    ctx: HandlerContext,
    collect: TezosTransaction[CollectParameter, HenMinterV1Storage],
) -> None: ...
