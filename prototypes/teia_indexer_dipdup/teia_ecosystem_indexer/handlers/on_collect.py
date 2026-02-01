from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction
from teia_ecosystem_indexer.types.hen_v2.tezos_parameters.collect import CollectParameter as HenCollect
from teia_ecosystem_indexer.types.teia_market.tezos_parameters.collect import CollectParameter as TeiaCollect

async def on_collect(
    ctx: HandlerContext,
    transaction: TezosTransaction[HenCollect | TeiaCollect, None],
) -> None:
    buyer = transaction.data.sender_address
    contract = transaction.data.target_address
    amount = transaction.data.amount
    
    # --- DEBUGGING SECTION ---
    # This will print the raw object so we can see if it's named 'swap_id', 'swap', 'id', etc.
    print(f"🔍 DEBUG RAW PARAM: {transaction.parameter}")
    # -------------------------

    swap_id = None
    token_id = None
    
    # Try all known variations for HEN/Teia
    if hasattr(transaction.parameter, 'swap_id'):
        swap_id = transaction.parameter.swap_id
    elif hasattr(transaction.parameter, 'swap'):  # Sometimes named just 'swap'
        swap_id = transaction.parameter.swap
        
    if hasattr(transaction.parameter, 'objkt_id'):
        token_id = transaction.parameter.objkt_id
    elif hasattr(transaction.parameter, 'objkt_amount'):
        token_id = transaction.parameter.objkt_amount

    if swap_id:
        print(f"💰 COLLECT: {buyer} bought Swap #{swap_id}")
    elif token_id:
        print(f"💰 COLLECT: {buyer} bought Token #{token_id}")
    else:
        print(f"⚠️  MISSING ID: {buyer} bought ??? on {contract} for {amount}")