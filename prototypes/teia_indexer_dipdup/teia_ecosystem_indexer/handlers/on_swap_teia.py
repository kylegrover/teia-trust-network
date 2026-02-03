from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer import utils


async def on_swap_teia(
    ctx: HandlerContext,
    transaction: TezosTransaction,
) -> None:
    # Use storage counter minus 1 (Hicdex logic)
    try:
        swap_id = int(transaction.storage.counter) - 1
    except (ValueError, TypeError, AttributeError):
        ctx.logger.error(f"Failed to get swap_id from storage at level {transaction.data.level}")
        return

    objkt_contract = await utils.get_contract(transaction.parameter.fa2, 'hen_objkts')
    market_contract = await utils.get_contract(transaction.data.target_address, 'teia_market')

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
            'market_version': models.MarketVersion.TEIA,
            'seller': seller_holder,
            'token': token,
            'amount_initial': transaction.parameter.objkt_amount,
            'amount_left': transaction.parameter.objkt_amount,
            'price_mutez': transaction.parameter.xtz_per_objkt,
            'royalties_permille': transaction.parameter.royalties,
            'timestamp': transaction.data.timestamp,
        }
    )
    ctx.logger.info(f"  [Teia] Swap {swap_id} created/updated for token {token.token_id}")
