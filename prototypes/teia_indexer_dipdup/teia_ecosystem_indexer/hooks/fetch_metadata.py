import asyncio
import aiohttp
from dipdup.context import HookContext

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer import utils

IPFS_GATEWAYS = [
    'https://cloudflare-ipfs.com/ipfs/',
    'https://gateway.pinata.cloud/ipfs/',
    'https://ipfs.io/ipfs/',
]


async def fetch_json_with_fallback(session: aiohttp.ClientSession, cid: str) -> dict | None:
    """Fetch JSON from IPFS using multiple gateways as fallbacks."""
    for gateway in IPFS_GATEWAYS:
        url = f'{gateway}{cid}'
        try:
            # Lower timeout to prevent watchdog triggers
            async with session.get(url, timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, dict):
                        return utils.clean_null_bytes(data)
        except Exception:
            continue
    return None


async def process_token_metadata(session: aiohttp.ClientSession, token: models.Token, ctx: HookContext):
    cid = token.metadata_uri.replace('ipfs://', '')
    data = await fetch_json_with_fallback(session, cid)
    return token, cid, data


async def process_holder_metadata(session: aiohttp.ClientSession, holder: models.Holder, ctx: HookContext):
    cid = holder.metadata_uri.replace('ipfs://', '')
    data = await fetch_json_with_fallback(session, cid)
    return holder, cid, data


async def fetch_metadata(ctx: HookContext) -> None:
    # 1. Collect unsynced entities
    ignored_cids = await models.IgnoredCid.all().values_list('cid', flat=True)

    unsynced_tokens = (
        await models.Token.filter(metadata_synced=False, metadata_uri__startswith='ipfs://')
        .filter(metadata_uri__not_in=[f'ipfs://{cid}' for cid in ignored_cids])
        .limit(20)
        .all()
    )

    unsynced_holders = (
        await models.Holder.filter(metadata_synced=False, metadata_uri__startswith='ipfs://')
        .filter(metadata_uri__not_in=[f'ipfs://{cid}' for cid in ignored_cids])
        .limit(10)
        .all()
    )

    if not unsynced_tokens and not unsynced_holders:
        return

    async with aiohttp.ClientSession() as session:
        # Phase 1: Parallel IPFS Fetch (The slow part)
        # We gather everything at once so all coroutines are awaited even if some fail.
        tasks = []
        tasks.extend([process_token_metadata(session, t, ctx) for t in unsynced_tokens])
        tasks.extend([process_holder_metadata(session, h, ctx) for h in unsynced_holders])
        
        if not tasks:
            return

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        token_results = [r for r in all_results if isinstance(r, tuple) and isinstance(r[0], models.Token)]
        holder_results = [r for r in all_results if isinstance(r, tuple) and isinstance(r[0], models.Holder)]

        # Phase 2: Sequential DB Write (The safe part)
        # We do this one-by-one to avoid asyncpg 'another operation in progress' errors
        for token, cid, data in token_results:
            if data:
                mime = ''
                formats = data.get('formats', [])
                if formats and isinstance(formats, list) and len(formats) > 0 and 'mimeType' in formats[0]:
                    mime = formats[0]['mimeType']

                await models.TokenMetadata.update_or_create(
                    token=token,
                    defaults={
                        'content': data,
                        'name': data.get('name'),
                        'description': data.get('description'),
                        'mime': mime,
                        'artifact_uri': data.get('artifactUri'),
                        'display_uri': data.get('displayUri'),
                        'thumbnail_uri': data.get('thumbnailUri'),
                    },
                )

                raw_tags = data.get('tags', [])
                if isinstance(raw_tags, list):
                    for tag_name in raw_tags:
                        if not isinstance(tag_name, str) or len(tag_name) > 255:
                            continue
                        tag_name = tag_name.lower().strip()
                        if not tag_name:
                            continue
                        tag_obj, _ = await models.Tag.get_or_create(name=tag_name)
                        await models.TokenTag.get_or_create(token=token, tag=tag_obj)
            else:
                ctx.logger.warning('Failed IPFS gateways for token %s (%s). Skipping.', token.token_id, cid)
                await models.IgnoredCid.get_or_create(cid=cid, defaults={'reason': 'Gateway timeout'})

            token.metadata_synced = True
            await token.save()

        for holder, cid, data in holder_results:
            if data:
                await models.HolderMetadata.update_or_create(
                    holder=holder,
                    defaults={
                        'content': data,
                        'bio': data.get('description'),
                        'alias': data.get('name') or data.get('alias'),
                        'logo': data.get('logo') or data.get('avatar'),
                    },
                )
            else:
                ctx.logger.warning('Failed IPFS gateways for holder %s (%s). Skipping.', holder.address, cid)
                await models.IgnoredCid.get_or_create(cid=cid, defaults={'reason': 'Gateway timeout'})

            holder.metadata_synced = True
            await holder.save()
