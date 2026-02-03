from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models as models
from teia_ecosystem_indexer.types.teia_market.tezos_parameters.cancel_swap import CancelSwapParameter
from teia_ecosystem_indexer.types.teia_market.tezos_storage import TeiaMarketStorage


from teia_ecosystem_indexer import utils

async def on_cancel_swap_teia(
    ctx: HandlerContext,
    cancel_swap: TezosTransaction[CancelSwapParameter, TeiaMarketStorage],
) -> None:
    swap_id = int(cancel_swap.parameter.root)
    contract = await utils.get_contract(cancel_swap.data.target_address, 'teia_market')

    await models.Swap.filter(
        swap_id=swap_id,
        contract=contract,
    ).update(status='canceled')
