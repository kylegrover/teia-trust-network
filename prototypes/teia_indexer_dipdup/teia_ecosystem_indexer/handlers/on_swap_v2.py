from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models


async def on_swap_v2(
    ctx: HandlerContext,
    transaction: TezosTransaction,
) -> None:
    swap_id = None
    if transaction.data.diffs:
        for diff in transaction.data.diffs:
            # Support both dict-style diffs (RPC responses) and object-style diffs
            # (DipDup may provide model objects). Be defensive like `on_swap`.
            action = diff.get('action') if isinstance(diff, dict) else getattr(diff, 'action', None)
            key = diff.get('key') if isinstance(diff, dict) else getattr(diff, 'key', None)

            if action == 'add_key' or action == 'update':
                try:
                    swap_id = int(key)
                    break
                except Exception:
                    continue

    if swap_id is None:
        return

    # Note: V2 contract hardcodes the OBJKT contract (KT1RJ6...)
    # We must match the address used in 'contracts' section of dipdup.yaml for hen_objkts
    objkt_contract = 'KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton'

    # Ensure creator identity exists and attach FK in the Token row (defaults)
    creator_holder, _ = await models.Holder.get_or_create(address=transaction.parameter.creator)

    token, _ = await models.Token.get_or_create(
        contract=objkt_contract,
        token_id=transaction.parameter.objkt_id,
        defaults={
            'creator': creator_holder,
            'creator_address': transaction.parameter.creator,
            'supply': 0,
            'timestamp': transaction.data.timestamp,
        },
    )

    seller_holder, _ = await models.Holder.get_or_create(address=transaction.data.sender_address)

    await models.Swap.create(
        swap_id=swap_id,
        contract_address=transaction.data.target_address,
        market_version=models.MarketVersion.V2,
        seller=seller_holder,
        seller_address=transaction.data.sender_address,
        token=token,
        amount_initial=transaction.parameter.objkt_amount,
        amount_left=transaction.parameter.objkt_amount,
        price_mutez=transaction.parameter.xtz_per_objkt,
        royalties_permille=transaction.parameter.royalties,
        timestamp=transaction.data.timestamp,
    )
