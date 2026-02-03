from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models as models
from teia_ecosystem_indexer import utils
from teia_ecosystem_indexer.types.hen_split_signer.tezos_parameters.sign import SignParameter
from teia_ecosystem_indexer.types.hen_split_signer.tezos_storage import HenSplitSignerStorage


async def on_split_sign(
    ctx: HandlerContext,
    sign: TezosTransaction[SignParameter, HenSplitSignerStorage],
) -> None:
    sender_address = sign.data.sender_address
    payload = sign.parameter
    # In some versions it's a root parameter, in others it's an attribute
    token_id_raw = payload.root if hasattr(payload, 'root') else payload

    try:
        token_id = int(token_id_raw)
    except (ValueError, TypeError):
        ctx.logger.error('Invalid token_id %s in split sign at level %s', token_id_raw, sign.data.level)
        return

    # OBJKT contract address
    objkt_contract = 'KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton'
    token = await utils.get_token(objkt_contract, token_id)
    if not token:
        # ctx.logger.warning(f"Token {token_id} not found for split sign")
        return

    sender_holder = await utils.get_holder(sender_address, sign.data.timestamp)

    # 1. Record the signature
    await models.Signature.get_or_create(token=token, holder=sender_holder)

    # 2. Check if all core participants have signed
    # The creator of the token should be a SplitContract
    split_contract = await models.SplitContract.get_or_none(contract_id=token.creator_id)
    if not split_contract:
        return

    try:
        # Get required core participants
        core_participants = await models.Shareholder.filter(
            split_contract=split_contract, holder_type=models.ShareholderStatus.CORE_PARTICIPANT
        ).all()

        if not core_participants:
            return

        sig_required = {sh.holder_id for sh in core_participants}

        # Get existing signatures for this token
        signers = await models.Signature.filter(token=token).all()
        sig_created = {s.holder_id for s in signers}

        # If all core participants have signed, mark as signed
        if sig_required.issubset(sig_created):
            token.is_signed = True
            await token.save()

    except Exception as exc:
        ctx.logger.error('Failed to update signed status for token %s: %s', token.id, exc)
