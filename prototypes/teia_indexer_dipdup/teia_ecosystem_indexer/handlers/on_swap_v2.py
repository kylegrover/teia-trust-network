from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer import utils


async def on_swap_v2(
    ctx: HandlerContext,
    transaction: TezosTransaction,
) -> None:
    swap_id = None
    # Try to find the swap_id from big_map diffs
    for diff in transaction.data.diffs:
        if diff.get('action') in ('add_key', 'update') and diff.get('path') == 'swaps':
            try:
                swap_id = int(diff.get('key'))
                break
            except (ValueError, TypeError):
                continue

    if swap_id is None:
        return

    objkt_contract_address = 'KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton'
    objkt_contract = await utils.get_contract(objkt_contract_address, 'hen_objkts')
    market_contract = await utils.get_contract(transaction.data.target_address, 'hen_market_v2')

    # Ensure creator identity exists
    creator_holder = await utils.get_holder(transaction.parameter.creator)

    token, _ = await models.Token.get_or_create(
        contract=objkt_contract,
        token_id=transaction.parameter.objkt_id,
        defaults={
            'creator': creator_holder,
            'supply': 0,
            'timestamp': transaction.data.timestamp,
        },
    )

    seller_holder = await utils.get_holder(transaction.data.sender_address)

    await models.Swap.create(
        swap_id=swap_id,
        contract=market_contract,
        market_version=models.MarketVersion.V2,
        seller=seller_holder,
        token=token,
        amount_initial=transaction.parameter.objkt_amount,
        amount_left=transaction.parameter.objkt_amount,
        price_mutez=transaction.parameter.xtz_per_objkt,
        royalties_permille=transaction.parameter.royalties,
        timestamp=transaction.data.timestamp,
    )
    ctx.logger.info(f"  [V2] Swap {swap_id} created at level {transaction.data.level}")
