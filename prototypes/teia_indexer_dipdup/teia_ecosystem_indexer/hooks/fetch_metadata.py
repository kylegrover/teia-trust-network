import aiohttp
from dipdup.context import HookContext

from teia_ecosystem_indexer import models
from teia_ecosystem_indexer import utils

IPFS_GATEWAYS = [
    'https://ipfs.io/ipfs/',
    'https://cloudflare-ipfs.com/ipfs/',
    'https://gateway.pinata.cloud/ipfs/',
]


async def fetch_json_with_fallback(session: aiohttp.ClientSession, cid: str) -> dict | None:
    """Fetch JSON from IPFS using multiple gateways as fallbacks."""
    for gateway in IPFS_GATEWAYS:
        url = f'{gateway}{cid}'
        try:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    # Basic validation that we got a dict
                    if isinstance(data, dict):
                        return utils.clean_null_bytes(data)
        except Exception:
            continue
    return None


async def fetch_metadata(ctx: HookContext) -> None:
    # 1. Collect unsynced entities
    # Exclude CIDs that are already marked as ignored
    ignored_cids = await models.IgnoredCid.all().values_list('cid', flat=True)

    unsynced_tokens = (
        await models.Token.filter(metadata_synced=False, metadata_uri__startswith='ipfs://')
        .filter(metadata_uri__not_in=[f'ipfs://{cid}' for cid in ignored_cids])
        .limit(10)
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
        # --- Handle Tokens ---
        for token in unsynced_tokens:
            cid = token.metadata_uri.replace('ipfs://', '')
            data = await fetch_json_with_fallback(session, cid)

            if data:
                # Extract rich fields
                mime = ""
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

                # Extract Tags (Hicdex logic)
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

                token.metadata_synced = True
                await token.save()
                ctx.logger.info('Fetched metadata for Token %s', token.token_id)
            else:
                ctx.logger.warning('Failed all IPFS gateways for token %s (%s)', token.token_id, cid)

        # --- Handle Holders (User Profiles) ---
        for holder in unsynced_holders:
            cid = holder.metadata_uri.replace('ipfs://', '')
            data = await fetch_json_with_fallback(session, cid)

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
                holder.metadata_synced = True
                await holder.save()
                ctx.logger.info('Fetched metadata for Holder %s (%s)', holder.name, holder.address)
            else:
                ctx.logger.warning('Failed all IPFS gateways for holder %s', holder.address)
