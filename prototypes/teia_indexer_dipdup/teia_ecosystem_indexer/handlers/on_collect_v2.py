from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models as models
from teia_ecosystem_indexer import utils
from teia_ecosystem_indexer.types.hen_market_v2.tezos_parameters.collect import CollectParameter
from teia_ecosystem_indexer.types.hen_market_v2.tezos_storage import HenMarketV2Storage


async def on_collect_v2(
    ctx: HandlerContext,
    collect: TezosTransaction[CollectParameter, HenMarketV2Storage],
) -> None:
    # 1. Resolve Swap
    # RootModel uses .root in Pydantic v2
    swap_id = int(collect.parameter.root)
    swap = await models.Swap.get_or_none(swap_id=swap_id, contract_address=collect.data.target_address)
    if not swap:
        return

    # 2. Update Swap state
    amount_collected = 1  # V2 collects are always 1 item per tx
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
