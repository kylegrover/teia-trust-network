from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer import utils


async def on_swap_v2(
    ctx: HandlerContext,
    transaction: TezosTransaction,
) -> None:
    # Use storage counter (V2 uses 'counter' field for swaps)
    try:
        swap_id = int(transaction.storage.counter) - 1
    except (ValueError, TypeError, AttributeError):
        ctx.logger.error(f"Failed to get swap_id from V2 storage at level {transaction.data.level}")
        return

    objkt_contract_address = 'KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton'
    objkt_contract = await utils.get_contract(objkt_contract_address, 'hen_objkts')
    market_contract = await utils.get_contract(transaction.data.target_address, 'hen_market_v2')

    # Ensure creator identity exists
    creator_holder = await utils.get_holder(transaction.parameter.creator, transaction.data.timestamp)

    token, _ = await models.Token.get_or_create(
        contract=objkt_contract,
        token_id=transaction.parameter.objkt_id,
        defaults={
            'creator': creator_holder,
            'supply': 0,
            'timestamp': transaction.data.timestamp,
        },
    )

    seller_holder = await utils.get_holder(transaction.data.sender_address, transaction.data.timestamp)

    await models.Swap.update_or_create(
        swap_id=swap_id,
        contract=market_contract,
        defaults={
            'market_version': models.MarketVersion.V2,
            'seller': seller_holder,
            'token': token,
            'amount_initial': transaction.parameter.objkt_amount,
            'amount_left': transaction.parameter.objkt_amount,
            'price_mutez': transaction.parameter.xtz_per_objkt,
            'royalties_permille': transaction.parameter.royalties,
            'timestamp': transaction.data.timestamp,
            'status': models.SwapStatus.ACTIVE,
        }
    )
    # ctx.logger.info(f"  [V2] Swap {swap_id} created/updated for token {token.token_id}")
