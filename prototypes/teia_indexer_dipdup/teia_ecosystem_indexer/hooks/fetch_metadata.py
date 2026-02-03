import aiohttp
from dipdup.context import HookContext

from teia_ecosystem_indexer import models


async def fetch_metadata(ctx: HookContext) -> None:
    # 1. Collect unsynced entities (limit to 10 each per run)
    unsynced_tokens = await models.Token.filter(
        metadata_synced=False, 
        metadata_uri__startswith='ipfs://'
    ).limit(10).all()
    
    unsynced_holders = await models.Holder.filter(
        metadata_synced=False, 
        metadata_uri__startswith='ipfs://'
    ).limit(10).all()

    if not unsynced_tokens and not unsynced_holders:
        return

    ipfs_gateway = 'https://ipfs.io/ipfs/'

    async with aiohttp.ClientSession() as session:
        # --- Handle Tokens ---
        for token in unsynced_tokens:
            cid = token.metadata_uri.replace('ipfs://', '')
            url = f'{ipfs_gateway}{cid}'
            try:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        await models.TokenMetadata.update_or_create(
                            token=token,
                            defaults={
                                'content': data,
                                'name': data.get('name'),
                                'description': data.get('description'),
                                'display_uri': data.get('displayUri') or data.get('artifactUri'),
                            },
                        )
                        token.metadata_synced = True
                        await token.save()
                        # ctx.logger.info('Fetched metadata for Token %s', token.token_id)
            except Exception as e:
                ctx.logger.warning('Failed IPFS for token %s: %s', token.token_id, e)

        # --- Handle Holders (User Profiles) ---
        for holder in unsynced_holders:
            cid = holder.metadata_uri.replace('ipfs://', '')
            url = f'{ipfs_gateway}{cid}'
            try:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        await models.HolderMetadata.update_or_create(
                            holder=holder,
                            defaults={
                                'content': data,
                                'bio': data.get('description'),
                                'alias': data.get('name') or data.get('alias'),
                                'logo': data.get('logo') or data.get('avatar'),
                            },
                        )
                        holder.metadata_synced = True
                        await holder.save()
                        # ctx.logger.info('Fetched metadata for Holder %s (%s)', holder.name, holder.address)
            except Exception as e:
                ctx.logger.warning('Failed IPFS for holder %s: %s', holder.address, e)
