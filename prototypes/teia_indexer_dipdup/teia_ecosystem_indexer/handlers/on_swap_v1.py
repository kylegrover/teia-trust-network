from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models as models
from teia_ecosystem_indexer import utils
from teia_ecosystem_indexer.types.hen_minter_v1.tezos_parameters.swap import SwapParameter
from teia_ecosystem_indexer.types.hen_minter_v1.tezos_storage import HenMinterV1Storage


async def on_swap_v1(
    ctx: HandlerContext,
    swap: TezosTransaction[SwapParameter, HenMinterV1Storage],
) -> None:
    # ctx.logger.info(f"on_swap_v1 called for level {swap.data.level}")
    swap_id = None
    
    # Try to find the swap_id from big_map diffs
    # ctx.logger.info(f"Diffs: {swap.data.diffs}")
    for diff in swap.data.diffs:
        # In DipDup 8.x diffs are typically Dicts for Tezos
        if diff.get('action') in ('add_key', 'update'):
            # V1 swaps big_map is usually at path 'swaps'
            try:
                swap_id = int(diff.get('key'))
                break
            except (ValueError, TypeError, KeyError):
                continue

    if swap_id is None:
        # ctx.logger.warning(f"No swap_id found in diffs for level {swap.data.level}")
        return

    objkt_contract_address = 'KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton'
    objkt_contract = await utils.get_contract(objkt_contract_address, 'hen_objkts')
    market_contract = await utils.get_contract(swap.data.target_address, 'hen_minter_v1')

    # In V1, we don't have creator in the parameter.
    # Use get_or_create to handle cases where market index is ahead of token index
    token, _ = await models.Token.get_or_create(
        contract=objkt_contract,
        token_id=swap.parameter.objkt_id,
        defaults={
            'supply': 0,
            'timestamp': swap.data.timestamp,
            'metadata_synced': False,
            'creator': await utils.get_holder(swap.data.sender_address), # Fallback creator
        },
    )

    seller_holder = await utils.get_holder(swap.data.sender_address)

    await models.Swap.create(
        swap_id=swap_id,
        contract=market_contract,
        market_version=models.MarketVersion.V1,
        seller=seller_holder,
        token=token,
        amount_initial=swap.parameter.objkt_amount,
        amount_left=swap.parameter.objkt_amount,
        price_mutez=swap.parameter.xtz_per_objkt,
        royalties_permille=250,  # V1 hardcoded 25% royalties
        timestamp=swap.data.timestamp,
    )
    ctx.logger.info(f"  [V1] Swap {swap_id} created at level {swap.data.level}")
