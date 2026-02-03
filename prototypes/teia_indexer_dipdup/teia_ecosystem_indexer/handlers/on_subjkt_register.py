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
    # 1. Decode subjkts name (it's in 'metadata', 'subjkt' is the IPFS link)
    name_raw = registry.parameter.metadata
    profile_raw = registry.parameter.subjkt
    
    def _clean_hex(val: str) -> str:
        try:
            # Try to convert hex to string if it looks like hex
            if len(val) > 0 and all(c in '0123456789abcdefABCDEF' for c in val):
                return bytes.fromhex(val).decode('utf-8', errors='ignore')
            return val
        except Exception:
            return val

    name = _clean_hex(name_raw)
    profile_uri = _clean_hex(profile_raw)

    # 2. Update Holder
    holder = await utils.get_holder(registry.data.sender_address, registry.data.timestamp)
    
    # Store the cleaned name
    holder.name = name
    # We might want to store profile_uri in the future, for now we log it
    await holder.save()

    ctx.logger.info(f"Registered subjkt: {name} profile: {profile_uri} for {registry.data.sender_address}")
