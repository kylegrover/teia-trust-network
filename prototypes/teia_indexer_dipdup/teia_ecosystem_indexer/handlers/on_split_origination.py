from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosOperationData

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer import utils


async def on_split_origination(
    ctx: HandlerContext,
    origination_0: TezosOperationData,
) -> None:
    # 1. Resolve storage
    # In DipDup 8.x for generic originations, storage is in origination_0.storage
    storage = origination_0.storage
    if not storage:
        return

    # Extract fields from storage (Hicdex pattern)
    shares = getattr(storage, 'shares', {})
    administrator_address = getattr(storage, 'administrator', None)
    total_shares = int(getattr(storage, 'totalShares', 0) or getattr(storage, 'total_shares', 0))
    core_participants = getattr(storage, 'coreParticipants', [])

    if not administrator_address:
        return

    contract_address = origination_0.originated_contract_address
    if not contract_address:
        return

    # 2. Register the originated contract
    holder = await utils.get_holder(contract_address, origination_0.timestamp)
    holder.is_split = True
    await holder.save()

    # 3. Register administrator
    admin_holder = await utils.get_holder(administrator_address, origination_0.timestamp)

    # 4. Create SplitContract record
    split_contract, _ = await models.SplitContract.get_or_create(
        contract=holder,
        defaults={
            'administrator': admin_holder,
            'total_shares': total_shares,
        },
    )

    # 5. Create Shareholder records
    for address, share in shares.items():
        shareholder_holder = await utils.get_holder(address, origination_0.timestamp)

        holder_type = models.ShareholderStatus.BENEFACTOR
        if address in core_participants:
            holder_type = models.ShareholderStatus.CORE_PARTICIPANT

        await models.Shareholder.get_or_create(
            split_contract=split_contract,
            holder=shareholder_holder,
            defaults={
                'shares': int(share),
                'holder_type': holder_type,
            },
        )
