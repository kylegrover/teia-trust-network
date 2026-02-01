from teia_trust_indexer import models
from teia_trust_indexer.types.teia_market.parameter.collect import CollectParameter
from teia_trust_indexer.types.hen_v2.parameter.collect import CollectParameter as HenCollectParameter
from dipdup.context import HandlerContext
from dipdup.models import Transaction

async def on_collect(
    ctx: HandlerContext,
    transaction: Transaction[CollectParameter, None], # <--- Typed!
) -> None:
    
    # DipDup guarantees this transaction was successful (status="applied")
    # and handles reorgs (rollback) automatically.

    buyer_address = transaction.data.sender_address
    contract_address = transaction.data.target_address
    
    # ACCESSING DATA
    # No more `val.get()`. If the field doesn't exist, this code won't even start.
    # Note: different contracts might have slightly different parameter names
    # which DipDup handles via different Type classes.
    if hasattr(transaction.parameter, 'objkt_id'):
        token_id = transaction.parameter.objkt_id
    elif hasattr(transaction.parameter, 'objkt_amount'):
         token_id = transaction.parameter.objkt_amount # Handle legacy param names
    
    # YOUR TRUST LOGIC
    # We can still use optimized SQL here if ORM is too slow for you.
    # But usually, the ORM is fine for writing.
    
    await models.Edge.create(
        source=buyer_address,
        target=contract_address, # You'd resolve this to artist in a real helper
        token_id=token_id,
        weight=transaction.data.amount, # Tezos value sent
        timestamp=transaction.data.timestamp
    )