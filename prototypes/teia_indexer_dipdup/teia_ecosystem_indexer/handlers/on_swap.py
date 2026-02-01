from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction  # <--- The correct import

from teia_ecosystem_indexer.types.hen_v2.tezos_parameters.swap import SwapParameter as HenSwap
from teia_ecosystem_indexer.types.teia_market.tezos_parameters.swap import SwapParameter as TeiaSwap

async def on_swap(
    ctx: HandlerContext,
    transaction: TezosTransaction[HenSwap | TeiaSwap, None],
) -> None:
    seller = transaction.data.sender_address
    contract = transaction.data.target_address
    
    token_id = None
    price = None
    
    # 1. Extract info (handling both contract types)
    if hasattr(transaction.parameter, 'objkt_id'):
        token_id = transaction.parameter.objkt_id
        price = transaction.parameter.xtz_per_objkt
    elif hasattr(transaction.parameter, 'objkt_amount'):
        # Some older contracts used different names
        token_id = transaction.parameter.objkt_amount
        price = transaction.parameter.xtz_per_objkt
        
    # 2. Log it
    print(f"🏷️  SWAP: {seller} listed Item {token_id} for {price} mutez on {contract}")