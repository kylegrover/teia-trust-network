from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models as models
from teia_ecosystem_indexer.types.hen_market_v2.tezos_parameters.cancel_swap import CancelSwapParameter
from teia_ecosystem_indexer.types.hen_market_v2.tezos_storage import HenMarketV2Storage


async def on_cancel_swap_v2(
    ctx: HandlerContext,
    cancel_swap: TezosTransaction[CancelSwapParameter, HenMarketV2Storage],
) -> None:
    swap_id = int(cancel_swap.parameter.root)

    await models.Swap.filter(
        swap_id=swap_id,
        contract_address=cancel_swap.data.target_address,
    ).update(status='canceled')
