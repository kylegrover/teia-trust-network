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
    # 1. Decode subjkts name/metadata
    field_a = registry.parameter.metadata
    field_b = registry.parameter.subjkt
    
    def _clean_val(val: str) -> str:
        if not val:
            return ""
        # 1. Try to decode hex if it looks like hex
        decoded = utils.from_hex(val)
        # 2. Ensure null bytes are stripped (postgres protection)
        return utils.clean_null_bytes(decoded or val)

    val_a = _clean_val(field_a)
    val_b = _clean_val(field_b)

    # 2. Logic to distinguish Handle from IPFS URI
    # Typically metadata = name and subjkt = ipfs, but it can be reversed 
    # depending on the wallet/app used to register.
    name = None
    uri = None

    for v in [val_a, val_b]:
        if v.startswith('ipfs://') or v.startswith('Qm'):
            uri = v if v.startswith('ipfs://') else f'ipfs://{v}'
        elif v and not name:
            name = v

    # 3. Update Holder
    holder = await utils.get_holder(registry.data.sender_address, registry.data.timestamp)
    
    holder.name = name
    if uri:
        holder.metadata_uri = uri
        holder.metadata_synced = False
    
    await holder.save()

    # ctx.logger.info(f"Registered subjkt: {name} URI: {uri} for {registry.data.sender_address}")
