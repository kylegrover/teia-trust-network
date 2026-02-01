from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models as models
from teia_ecosystem_indexer.types.hen_minter_v1.tezos_parameters.swap import SwapParameter
from teia_ecosystem_indexer.types.hen_minter_v1.tezos_storage import HenMinterV1Storage


async def on_swap_v1(
    ctx: HandlerContext,
    swap: TezosTransaction[SwapParameter, HenMinterV1Storage],
) -> None: ...
