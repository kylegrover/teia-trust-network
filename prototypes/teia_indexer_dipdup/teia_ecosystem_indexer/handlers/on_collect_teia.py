from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer import utils
from teia_ecosystem_indexer.types.teia_market.tezos_parameters.collect import CollectParameter


async def on_collect_teia(
    ctx: HandlerContext,
    transaction: TezosTransaction[CollectParameter, None],
) -> None:
    # 1. Resolve Swap ID
    try:
        # Pydantic models in DipDup often use .root for simple types
        swap_id = int(transaction.parameter.root)
    except (AttributeError, ValueError, TypeError):
        ctx.logger.error('Failed to parse swap_id from teia_market parameter at level %s', transaction.data.level)
        return

    contract = await utils.get_contract(transaction.data.target_address, 'teia_market')
    swap = await models.Swap.get_or_none(swap_id=swap_id, contract=contract).prefetch_related('token')

    if not swap:
        # ctx.logger.warning(f"Swap {swap_id} not found for Teia collect at level {transaction.data.level}")
        return

    # 2. Update Swap state
    amount_collected = 1  # Teia marketplace collect is usually 1 item per call
    swap.amount_left -= amount_collected
    if swap.amount_left <= 0:
        swap.status = models.SwapStatus.FINISHED
    await swap.save()

    # 3. Record the Trade
    buyer_holder = await utils.get_holder(transaction.data.sender_address, transaction.data.timestamp)

    await models.Trade.create(
        swap=swap,
        token=swap.token,
        seller_id=swap.seller_id,
        creator_id=swap.token.creator_id,
        buyer=buyer_holder,
        amount=amount_collected,
        price_mutez=swap.price_mutez,
        timestamp=transaction.data.timestamp,
        is_primary_market=(swap.seller_id == swap.token.creator_id),
    )
    # ctx.logger.info(f"  [Teia] Trade created: 1 item from swap {swap_id}")
