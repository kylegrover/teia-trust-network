from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models as models
from teia_ecosystem_indexer.types.hen_market_v2.tezos_parameters.collect import CollectParameter
from teia_ecosystem_indexer.types.hen_market_v2.tezos_storage import HenMarketV2Storage


async def on_collect_v2(
    ctx: HandlerContext,
    collect: TezosTransaction[CollectParameter, HenMarketV2Storage],
) -> None: ...
