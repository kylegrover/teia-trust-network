from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models as models
from teia_ecosystem_indexer.types.hen_minter_v1.tezos_parameters.cancel_swap import CancelSwapParameter
from teia_ecosystem_indexer.types.hen_minter_v1.tezos_storage import HenMinterV1Storage


from teia_ecosystem_indexer import utils

async def on_cancel_swap_v1(
    ctx: HandlerContext,
    cancel_swap: TezosTransaction[CancelSwapParameter, HenMinterV1Storage],
) -> None:
    swap_id = int(cancel_swap.parameter.root)
    contract = await utils.get_contract(cancel_swap.data.target_address, 'hen_minter_v1')

    await models.Swap.filter(
        swap_id=swap_id,
        contract=contract,
    ).update(status='canceled')
