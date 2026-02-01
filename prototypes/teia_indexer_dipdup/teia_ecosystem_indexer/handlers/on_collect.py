from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer.types.hen_v2.tezos_parameters.collect import CollectParameter as HenCollect
from teia_ecosystem_indexer.types.teia_market.tezos_parameters.collect import CollectParameter as TeiaCollect


async def on_collect(
    ctx: HandlerContext,
    transaction: TezosTransaction[HenCollect | TeiaCollect, None],
) -> None:
    buyer = transaction.data.sender_address
    contract = transaction.data.target_address
    amount = transaction.data.amount
    timestamp = transaction.data.timestamp

    # 1. Resolve Swap ID robustly and ensure it's an int (or None)
    def _normalize_swap_id(param) -> int | None:
        if param is None:
            return None
        if isinstance(param, int):
            return param
        if isinstance(param, str):
            try:
                return int(param)
            except Exception:
                return None
        if isinstance(param, dict):
            for key in ('__root__', 'root', 'swap_id'):
                if key in param:
                    try:
                        return int(param[key])
                    except Exception:
                        return None
            return None
        for attr in ('__root__', 'root', 'swap_id'):
            if hasattr(param, attr):
                try:
                    return int(getattr(param, attr))
                except Exception:
                    return None
        return None

    swap_id = _normalize_swap_id(transaction.parameter)

    seller_address = 'Unknown'
    token_id = None

    # 2. Look up the Swap in OUR Database to find the Seller
    if swap_id is not None:
        # We try to find the swap we saved in on_swap
        swap = await models.Swap.get_or_none(swap_id=swap_id, contract=contract)
        if swap:
            seller_address = swap.seller_address
            token_id = swap.token_id
        else:
            # This happens if the Swap was created BEFORE we started indexing (Historical)
            # For a perfect graph, we'd need to backfill further.
            seller_address = 'Historical_Seller'

    # 3. Save the Trust Edge
    await models.TrustEdge.create(
        buyer_address=buyer,
        seller_address=seller_address,
        contract=contract,
        token_id=token_id,
        amount_paid_mutez=amount,
        swap_id=swap_id,
        timestamp=timestamp,
    )

    print(f'💰 EDGE CREATED: {buyer} -> {seller_address} ({amount} mutez)')
