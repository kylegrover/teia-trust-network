from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer import utils

BURN_ADDRESS = 'tz1burnburnburnburnburnburnburjAYjjX'


async def on_transfer(
    ctx: HandlerContext,
    transfer: TezosTransaction,
) -> None:
    # FA2 transfers are a list: [{"from_": "...", "txs": [{"to_": "...", "token_id": "...", "amount": "..."}]}]
    payload = transfer.parameter
    if not payload:
        return

    # Handle the RootModel or direct list
    items = payload.root if hasattr(payload, 'root') else payload

    for item in items:
        # Use simple dot notation for generated Pydantic models
        from_address = item.from_
        from_holder = await utils.get_holder(from_address, transfer.data.timestamp)

        for tx in item.txs:
            to_address = tx.to_
            token_id = int(tx.token_id)
            amount = int(tx.amount)

            # Resolve Token from cache/DB
            token = await utils.get_token(transfer.data.target_address, token_id)
            if not token:
                # If we don't have the token yet (e.g. indexing out of order), 
                # we should still track the holder timestamps
                await utils.get_holder(to_address, transfer.data.timestamp)
                continue

            to_holder = await utils.get_holder(to_address, transfer.data.timestamp)

            # Record the transaction
            await models.Transfer.create(
                token=token,
                from_holder=from_holder,
                to_holder=to_holder,
                amount=amount,
                timestamp=transfer.data.timestamp,
                level=transfer.data.level,
            )

            # Update Balances (TokenHolder ledger)
            sender_holding, _ = await models.TokenHolder.get_or_create(token=token, holder=from_holder)
            sender_holding.quantity -= amount
            await sender_holding.save()

            receiver_holding, _ = await models.TokenHolder.get_or_create(token=token, holder=to_holder)
            receiver_holding.quantity += amount
            await receiver_holding.save()

            # Supply tracking for burns
            if to_address == BURN_ADDRESS:
                token.supply -= amount
                await token.save()
