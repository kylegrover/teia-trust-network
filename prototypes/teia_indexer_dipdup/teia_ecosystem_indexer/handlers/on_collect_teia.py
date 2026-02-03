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
        ctx.logger.error(f"Failed to parse swap_id from teia_market parameter at level {transaction.data.level}")
        return

    contract = await utils.get_contract(transaction.data.target_address, 'teia_market')
    swap = await models.Swap.get_or_none(swap_id=swap_id, contract=contract)

    if not swap:
        # ctx.logger.warning(f"Swap {swap_id} not found for Teia collect at level {transaction.data.level}")
        return

    # 2. Update Swap state
    amount_collected = 1  # Teia marketplace collect is usually 1 item per call
    swap.amount_left -= amount_collected
    if swap.amount_left <= 0:
        swap.status = 'finished'
    await swap.save()

    # 3. Record the Trade
    buyer_holder = await utils.get_holder(transaction.data.sender_address, transaction.data.timestamp)

    await models.Trade.create(
        swap=swap,
        buyer=buyer_holder,
        amount=amount_collected,
        price_mutez=swap.price_mutez,
        timestamp=transaction.data.timestamp,
    )
    ctx.logger.info(f"  [Teia] Trade created: 1 item from swap {swap_id}")

    # In Teia/HEN, collect usually implies 1 item unless batching (which isn't this entrypoint)
    amount_collected = 1

    swap.amount_left -= amount_collected
    if swap.amount_left <= 0:
        swap.status = 'finished'
    await swap.save()

    buyer_holder = await utils.get_holder(transaction.data.sender_address)

    await models.Trade.create(
        swap=swap,
        buyer=buyer_holder,
        amount=amount_collected,
        price_mutez=swap.price_mutez,
        timestamp=transaction.data.timestamp,
    )
    ctx.logger.info(f"  [Teia] Trade created for swap {swap_id}")
