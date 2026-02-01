from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

# Import BOTH contract parameter types
from teia_ecosystem_indexer.types.hen_v2.tezos_parameters.collect import CollectParameter as HenCollect
from teia_ecosystem_indexer.types.teia_market.tezos_parameters.collect import CollectParameter as TeiaCollect

async def on_collect(
    ctx: HandlerContext,
    # This type hint tells DipDup: "Expect either a HEN or a Teia collect"
    transaction: TezosTransaction[HenCollect | TeiaCollect, None],
) -> None:
    
    # 1. Standard Info
    buyer = transaction.data.sender_address
    contract = transaction.data.target_address
    amount = transaction.data.amount
    
    # 2. Extract Data (Handling both contract styles)
    # HEN V2 and Teia mostly use 'swap_id', but direct sales might use 'objkt_id'
    
    swap_id = None
    token_id = None
    
    # Check for Swap ID (The most common case for Marketplaces)
    if hasattr(transaction.parameter, 'swap_id'):
        swap_id = transaction.parameter.swap_id
        
    # Check for Token ID (Direct sales or older contracts)
    if hasattr(transaction.parameter, 'objkt_id'):
        token_id = transaction.parameter.objkt_id
    elif hasattr(transaction.parameter, 'objkt_amount'):
        token_id = transaction.parameter.objkt_amount

    # 3. Log it
    if swap_id:
        print(f"💰 COLLECT: {buyer} bought Swap #{swap_id} on {contract} for {amount} mutez")
    else:
        print(f"💰 COLLECT: {buyer} bought Token #{token_id} on {contract} for {amount} mutez")