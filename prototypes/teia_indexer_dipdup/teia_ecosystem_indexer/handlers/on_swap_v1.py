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
    # Use storage swap_id (V1 uses 'swap_id' field for swaps)
    try:
        swap_id = int(swap.storage.swap_id) - 1
    except (ValueError, TypeError, AttributeError):
        ctx.logger.error(f"Failed to get swap_id from V1 storage at level {swap.data.level}")
        return

    objkt_contract_address = 'KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton'
    objkt_contract = await utils.get_contract(objkt_contract_address, 'hen_objkts')
    market_contract = await utils.get_contract(swap.data.target_address, 'hen_minter_v1')

    # In V1, we don't have creator in the parameter.
    creator_holder = await utils.get_holder(swap.data.sender_address, swap.data.timestamp)

    token, _ = await models.Token.get_or_create(
        contract=objkt_contract,
        token_id=swap.parameter.objkt_id,
        defaults={
            'supply': 0,
            'timestamp': swap.data.timestamp,
            'metadata_synced': False,
            'creator': creator_holder,
        },
    )

    seller_holder = await utils.get_holder(swap.data.sender_address, swap.data.timestamp)

    await models.Swap.update_or_create(
        swap_id=swap_id,
        contract=market_contract,
        defaults={
            'market_version': models.MarketVersion.V1,
            'seller': seller_holder,
            'token': token,
            'amount_initial': swap.parameter.objkt_amount,
            'amount_left': swap.parameter.objkt_amount,
            'price_mutez': swap.parameter.xtz_per_objkt,
            'royalties_permille': 250,  # V1 hardcoded 25% royalties
            'timestamp': swap.data.timestamp,
        }
    )
    ctx.logger.info(f"  [V1] Swap {swap_id} created/updated for token {token.token_id}")
