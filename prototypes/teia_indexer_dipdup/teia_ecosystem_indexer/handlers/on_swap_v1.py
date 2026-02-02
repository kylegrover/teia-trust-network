from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models as models
from teia_ecosystem_indexer.types.hen_minter_v1.tezos_parameters.swap import SwapParameter
from teia_ecosystem_indexer.types.hen_minter_v1.tezos_storage import HenMinterV1Storage


async def on_swap_v1(
    ctx: HandlerContext,
    swap: TezosTransaction[SwapParameter, HenMinterV1Storage],
) -> None:
    swap_id = None
    if swap.data.diffs:
        for diff in swap.data.diffs:
            action = diff.get('action') if isinstance(diff, dict) else getattr(diff, 'action', None)
            key = diff.get('key') if isinstance(diff, dict) else getattr(diff, 'key', None)
            if action in ('add_key', 'update'):
                try:
                    swap_id = int(key)
                    break
                except Exception:
                    continue

    if swap_id is None:
        return

    objkt_contract = 'KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton'
    
    # In V1, we don't have creator in the parameter. 
    # We find the Token record which should have been created by on_mint.
    token = await models.Token.get_or_none(
        contract=objkt_contract,
        token_id=swap.parameter.objkt_id
    )
    if not token:
        # Fallback if mint was missed (not ideal)
        return

    seller_holder, _ = await models.Holder.get_or_create(address=swap.data.sender_address)

    await models.Swap.create(
        swap_id=swap_id,
        contract_address=swap.data.target_address,
        market_version=models.MarketVersion.V1,
        seller=seller_holder,
        seller_address=swap.data.sender_address,
        token=token,
        amount_initial=swap.parameter.objkt_amount,
        amount_left=swap.parameter.objkt_amount,
        price_mutez=swap.parameter.xtz_per_objkt,
        royalties_permille=250,  # V1 hardcoded 25% royalties
        timestamp=swap.data.timestamp,
    )

