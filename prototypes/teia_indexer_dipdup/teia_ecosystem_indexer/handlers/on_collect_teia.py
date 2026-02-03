from dipdup.context import HandlerContext
from dipdup.models.tezos import TezosTransaction

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer import utils
from teia_ecosystem_indexer.types.teia_market.tezos_parameters.collect import CollectParameter


async def on_collect_teia(
    ctx: HandlerContext,
    transaction: TezosTransaction[CollectParameter, None],
) -> None:
    # Normalize swap id from a variety of generated parameter shapes (int, str, dict, pydantic)
    def _normalize_swap_id(param) -> int | None:
        if param is None:
            return None
        # already primitive
        if isinstance(param, int):
            return param
        if isinstance(param, str):
            try:
                return int(param)
            except Exception:
                return None
        # dict-like (RPC)
        if isinstance(param, dict):
            for key in ('__root__', 'root', 'swap_id'):
                if key in param:
                    try:
                        return int(param[key])
                    except Exception:
                        return None
            return None
        # pydantic / model-like
        for attr in ('__root__', 'root', 'swap_id'):
            if hasattr(param, attr):
                try:
                    return int(getattr(param, attr))
                except Exception:
                    return None
        return None

    swap_id = _normalize_swap_id(transaction.parameter)

    if swap_id is None:
        return

    contract = await utils.get_contract(transaction.data.target_address, 'teia_market')
    swap = await models.Swap.filter(
        swap_id=swap_id,
        contract=contract,
    ).get_or_none()

    if not swap:
        return

    # In Teia/HEN, collect usually implies 1 item unless batching (which isn't this entrypoint)
    amount_collected = 1

    swap.amount_left -= amount_collected
    if swap.amount_left <= 0:
        swap.status = 'finished'
    await swap.save()

    buyer_holder = await utils.get_holder(transaction.data.sender_address)

    await models.Trade.create(
        swap=swap,
        buyer=buyer_holder,
        amount=amount_collected,
        price_mutez=swap.price_mutez,
        timestamp=transaction.data.timestamp,
    )
    ctx.logger.info(f"  [Teia] Trade created for swap {swap_id}")
