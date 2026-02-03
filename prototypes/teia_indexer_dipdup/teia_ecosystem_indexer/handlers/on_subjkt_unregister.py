from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer import utils


async def on_subjkt_unregister(
    ctx: HandlerContext,
    unregistry: TezosTransaction,
) -> None:
    holder = await utils.get_holder(unregistry.data.sender_address, unregistry.data.timestamp)
    
    # 1. Clear handle
    holder.name = None
    holder.metadata_uri = None
    holder.metadata_synced = False
    await holder.save()

    # 2. Delete sidecar metadata if it exists
    await models.HolderMetadata.filter(holder=holder).delete()

    ctx.logger.info(f"Unregistered subjkt for {unregistry.data.sender_address}")
