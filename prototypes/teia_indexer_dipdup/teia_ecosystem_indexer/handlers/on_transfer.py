from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models, utils


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
        from_holder = await utils.get_holder(from_address)

        for tx in item.txs:
            to_address = tx.to_
            token_id = int(tx.token_id)
            amount = int(tx.amount)

            # Resolve Token
            token = await models.Token.get_or_none(contract=transfer.data.target_address, token_id=token_id)
            if not token:
                continue

            to_holder = await utils.get_holder(to_address)

            await models.Transfer.create(
                token=token,
                from_holder=from_holder,
                from_address=from_address,
                to_holder=to_holder,
                to_address=to_address,
                amount=amount,
                timestamp=transfer.data.timestamp,
                level=transfer.data.level,
            )


