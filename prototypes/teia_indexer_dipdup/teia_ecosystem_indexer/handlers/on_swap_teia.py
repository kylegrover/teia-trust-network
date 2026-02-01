from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction
from teia_ecosystem_indexer.types.teia_market.tezos_parameters.swap import SwapParameter
from teia_ecosystem_indexer import models

async def on_swap_teia(
    ctx: HandlerContext,
    transaction: TezosTransaction,
) -> None:
    # 1. Parse Swap ID from BigMap diffs
    swap_id = None
    if transaction.data.diffs:
        for diff in transaction.data.diffs:
            # FIX: Use dot notation for Pydantic models
            if diff.action == 'add_key':
                swap_id = int(diff.key)
                break
    
    if swap_id is None:
        # Check if we can get it from storage (optional/fallback) or just return
        return

    # 2. Find or Create the Token
    token, _ = await models.Token.get_or_create(
        contract=transaction.parameter.fa2,
        token_id=transaction.parameter.objkt_id,
        defaults={
            "creator_address": transaction.parameter.creator,
            "supply": 0,
            "timestamp": transaction.data.timestamp
        }
    )

    # 3. Create Swap
    await models.Swap.create(
        swap_id=swap_id,
        contract_address=transaction.data.target_address,
        market_version=models.MarketVersion.TEIA,
        seller_address=transaction.data.sender_address,
        token=token,
        amount_initial=transaction.parameter.objkt_amount,
        amount_left=transaction.parameter.objkt_amount,
        price_mutez=transaction.parameter.xtz_per_objkt,
        royalties_permille=transaction.parameter.royalties,
        timestamp=transaction.data.timestamp
    )