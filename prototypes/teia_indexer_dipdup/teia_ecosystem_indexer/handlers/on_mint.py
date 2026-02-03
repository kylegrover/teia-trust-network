from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer import utils
from teia_ecosystem_indexer.types.hen_objkts.tezos_parameters.mint import MintParameter


async def on_mint(
    ctx: HandlerContext,
    transaction: TezosTransaction[MintParameter, None],
) -> None:
    # Convert '69706673...' hex to 'ipfs://...' string
    metadata_hex = transaction.parameter.token_info.get('')
    metadata_uri = bytes.fromhex(metadata_hex).decode('utf-8') if metadata_hex else None

    # Ensure the canonical identity exists
    creator_holder = await utils.get_holder(transaction.parameter.address)

    await models.Token.create(
        contract=transaction.data.target_address,
        token_id=transaction.parameter.token_id,
        creator=creator_holder,
        creator_address=transaction.parameter.address,
        supply=transaction.parameter.amount,
        metadata_uri=metadata_uri,
        metadata_synced=False,
        timestamp=transaction.data.timestamp,
    )

    # Fire the metadata fetcher hook for this new token
    await ctx.fire_hook('fetch_metadata')
