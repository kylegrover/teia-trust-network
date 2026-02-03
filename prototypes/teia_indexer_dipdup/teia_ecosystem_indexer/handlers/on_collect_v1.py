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
    try:
        swap_id = int(collect.parameter.swap_id)
    except (ValueError, TypeError, AttributeError):
        ctx.logger.error('Failed to parse swap_id from parameter at level %s', collect.data.level)
        return

    contract = await utils.get_contract(collect.data.target_address, 'hen_minter_v1')
    swap = await models.Swap.get_or_none(swap_id=swap_id, contract=contract).prefetch_related('token')

    if not swap:
        # ctx.logger.warning(f"Swap {swap_id} not found for collect at level {collect.data.level}")
        return

    # 2. Update Swap state
    amount_collected = int(collect.parameter.objkt_amount)
    swap.amount_left -= amount_collected
    if swap.amount_left <= 0:
        swap.status = models.SwapStatus.FINISHED
    await swap.save()

    # 3. Record the Trade
    buyer_holder = await utils.get_holder(collect.data.sender_address, collect.data.timestamp)

    await models.Trade.create(
        swap=swap,
        token=swap.token,
        seller_id=swap.seller_id,
        creator_id=swap.token.creator_id,
        buyer=buyer_holder,
        amount=amount_collected,
        price_mutez=swap.price_mutez,
        timestamp=collect.data.timestamp,
        is_primary_market=(swap.seller_id == swap.token.creator_id),
    )
    # ctx.logger.info(f"  [V1] Trade created: {amount_collected} items from swap {swap_id}")
