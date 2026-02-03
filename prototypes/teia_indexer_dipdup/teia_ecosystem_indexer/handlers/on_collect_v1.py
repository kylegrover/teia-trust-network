from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models as models
from teia_ecosystem_indexer import utils
from teia_ecosystem_indexer.types.hen_minter_v1.tezos_parameters.collect import CollectParameter
from teia_ecosystem_indexer.types.hen_minter_v1.tezos_storage import HenMinterV1Storage


async def on_collect_v1(
    ctx: HandlerContext,
    collect: TezosTransaction[CollectParameter, HenMinterV1Storage],
) -> None:
    # 1. Resolve Swap
    swap_id = int(collect.parameter.swap_id)
    swap = await models.Swap.get_or_none(swap_id=swap_id, contract_address=collect.data.target_address)
    if not swap:
        return

    # 2. Update Swap state
    amount_collected = int(collect.parameter.objkt_amount)
    swap.amount_left -= amount_collected
    if swap.amount_left <= 0:
        swap.status = 'finished'
    await swap.save()

    # 3. Record the Trade (Hybrid Identity)
    buyer_holder = await utils.get_holder(collect.data.sender_address)

    await models.Trade.create(
        swap=swap,
        buyer=buyer_holder,
        buyer_address=collect.data.sender_address,
        amount=amount_collected,
        price_mutez=swap.price_mutez,
        timestamp=collect.data.timestamp,
    )
