from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer.types.hen_v2.tezos_parameters.swap import SwapParameter as HenSwap
from teia_ecosystem_indexer.types.teia_market.tezos_parameters.swap import SwapParameter as TeiaSwap


async def on_swap(
    ctx: HandlerContext,
    transaction: TezosTransaction[HenSwap | TeiaSwap, None],
) -> None:
    seller = transaction.data.sender_address
    contract = transaction.data.target_address

    # 1. Get Details from Params
    token_id = transaction.parameter.objkt_id
    price = transaction.parameter.xtz_per_objkt

    # 2. Find the Swap ID from the BigMap Diff
    swap_id = None

    if transaction.data.diffs:
        for diff in transaction.data.diffs:
            # FIX: Check if it's a dict or an object to be safe
            action = diff.get('action') if isinstance(diff, dict) else getattr(diff, 'action', None)
            key = diff.get('key') if isinstance(diff, dict) else getattr(diff, 'key', None)

            if action == 'add_key' or action == 'update':
                try:
                    swap_id = int(key)
                    break
                except Exception:
                    continue

    if swap_id is None:
        # Warn but don't crash. Some swaps might not emit standard diffs.
        # print(f"⚠️  SWAP WITHOUT ID: {seller} listed {token_id}")
        return

    # 3. Save to Database — ensure we populate the canonical identity registry (safe, non-breaking)
    seller_holder, _ = await models.Holder.get_or_create(address=seller)

    await models.Swap.create(
        swap_id=swap_id,
        contract=contract,
        seller=seller_holder,
        seller_address=seller,
        token_id=token_id,
        price_mutez=price,
        timestamp=transaction.data.timestamp,
    )

    print(f'🏷️  SAVED SWAP #{swap_id}: {seller} listed Item {token_id}')
