from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models

async def on_transfer(
    ctx: HandlerContext,
    transfer: TezosTransaction,
) -> None:
    # FA2 transfers are a list: [{"from_": "...", "txs": [{"to_": "...", "token_id": "...", "amount": "..."}]}]
    # DipDup provides this as a list of objects or dicts depending on type generation.
    payload = transfer.parameter
    if not payload:
        return

    # Handle both list and object access (defensive until Types are generated)
    # The payload is typically a list of Transfer items
    items = payload if isinstance(payload, list) else [payload]

    for item in items:
        # Get from address (handles both attr and dict access)
        from_address = getattr(item, 'from_', None) or item.get('from_')
        if not from_address:
            continue
            
        from_holder, _ = await models.Holder.get_or_create(address=from_address)
        
        txs = getattr(item, 'txs', []) or item.get('txs', [])
        for tx in txs:
            to_address = getattr(tx, 'to_', None) or tx.get('to_')
            token_id = getattr(tx, 'token_id', None)
            if token_id is None:
                token_id = tx.get('token_id')
                
            amount = getattr(tx, 'amount', None)
            if amount is None:
                amount = tx.get('amount')

            if to_address is None or token_id is None:
                continue

            # Resolve Token
            token = await models.Token.get_or_none(
                contract=transfer.data.target_address,
                token_id=int(token_id)
            )
            if not token:
                # If we haven't seen the mint, skip or create stub? 
                # For transfers, we prefer having the Token record first.
                continue

            to_holder, _ = await models.Holder.get_or_create(address=to_address)

            await models.Transfer.create(
                token=token,
                from_holder=from_holder,
                from_address=from_address,
                to_holder=to_holder,
                to_address=to_address,
                amount=int(amount or 0),
                timestamp=transfer.data.timestamp,
                level=transfer.data.level
            )
