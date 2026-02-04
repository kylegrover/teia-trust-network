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

    # Ensure the canonical identity and contract exist
    creator_holder = await utils.get_holder(transaction.parameter.address, transaction.data.timestamp)
    contract = await utils.get_contract(transaction.data.target_address, 'hen_objkts')

    token, _created = await models.Token.get_or_create(
        contract=contract,
        token_id=int(transaction.parameter.token_id),
        defaults={
            'creator': creator_holder,
            'supply': int(transaction.parameter.amount),
            'metadata_uri': metadata_uri,
            'metadata_synced': False,
            'timestamp': transaction.data.timestamp,
        },
    )

    # Initialize Creator Balance
    holder_holding, _ = await models.TokenHolder.get_or_create(token=token, holder=creator_holder)
    holder_holding.quantity += int(transaction.parameter.amount)
    await holder_holding.save()
