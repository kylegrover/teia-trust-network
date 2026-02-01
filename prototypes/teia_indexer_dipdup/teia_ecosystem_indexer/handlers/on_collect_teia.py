from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction
from teia_ecosystem_indexer.types.teia_market.tezos_parameters.collect import CollectParameter
from teia_ecosystem_indexer import models

async def on_collect_teia(
    ctx: HandlerContext,
    transaction: TezosTransaction[CollectParameter, None],
) -> None:
    # Handle both wrapped (.__root__) and direct parameter types
    # This depends on the exact generated type structure
    raw_param = transaction.parameter
    swap_id = getattr(raw_param, "__root__", raw_param)

    # Ensure swap_id is an integer
    try:
        swap_id = int(swap_id)
    except (ValueError, TypeError):
        # Fallback if it's an object with a swap_id field (unlikely for this contract but safe)
        if hasattr(swap_id, 'swap_id'):
            swap_id = int(swap_id.swap_id)

    swap = await models.Swap.filter(
        swap_id=swap_id, 
        contract_address=transaction.data.target_address
    ).get_or_none()

    if not swap:
        # It's possible we missed the swap if it happened before we started indexing
        return

    # In Teia/HEN, collect usually implies 1 item unless batching (which isn't this entrypoint)
    amount_collected = 1 

    swap.amount_left -= amount_collected
    if swap.amount_left <= 0:
        swap.status = "finished"
    await swap.save()

    await models.Trade.create(
        swap=swap,
        buyer_address=transaction.data.sender_address,
        amount=amount_collected,
        price_mutez=swap.price_mutez,
        timestamp=transaction.data.timestamp
    )