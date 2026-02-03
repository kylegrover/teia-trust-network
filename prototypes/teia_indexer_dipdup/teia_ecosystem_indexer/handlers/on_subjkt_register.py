from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models as models
from teia_ecosystem_indexer import utils
from teia_ecosystem_indexer.types.hen_subjkts.tezos_parameters.registry import RegistryParameter
from teia_ecosystem_indexer.types.hen_subjkts.tezos_storage import HenSubjktsStorage


async def on_subjkt_register(
    ctx: HandlerContext,
    registry: TezosTransaction[RegistryParameter, HenSubjktsStorage],
) -> None:
    # Decode the subjkt (bytes to string if necessary, but Pydantic might have handled it)
    name = registry.parameter.subjkt
    # The contract sometimes receives hex-encoded names, but DipDup usually handles strings
    # We'll just store it as is for now.

    holder = await utils.get_holder(registry.data.sender_address)
    holder.name = name
    await holder.save()
