import aiohttp
from dipdup.context import HookContext

from teia_ecosystem_indexer import models


async def fetch_metadata(ctx: HookContext) -> None:
    # 1. Find tokens with unsynced metadata
    unsynced_tokens = (
        await models.Token.filter(metadata_synced=False, metadata_uri__startswith='ipfs://').limit(10).all()
    )

    if not unsynced_tokens:
        return

    ipfs_gateway = 'https://ipfs.io/ipfs/'

    async with aiohttp.ClientSession() as session:
        for token in unsynced_tokens:
            cid = token.metadata_uri.replace('ipfs://', '')
            url = f'{ipfs_gateway}{cid}'

            try:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        token.metadata = data
                        token.metadata_synced = True
                        await token.save()
                        ctx.logger.info('Fetched metadata for Token %s', token.token_id)
            except Exception as e:
                ctx.logger.warning('Failed to fetch IPFS for token %s: %s', token.token_id, e)
