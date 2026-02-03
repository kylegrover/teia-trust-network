from enum import Enum

from dipdup import fields
from dipdup.models import Model


class MarketVersion(str, Enum):
    V1 = 'v1'
    V2 = 'v2'
    TEIA = 'teia'


class SwapStatus(str, Enum):
    ACTIVE = 'active'
    FINISHED = 'finished'
    CANCELED = 'canceled'


class ShareholderStatus(str, Enum):
    BENEFACTOR = 'benefactor'
    CORE_PARTICIPANT = 'core_participant'


class Contract(Model):
    """Canonical contract registry.
    Saves massive space by storing KT1... addresses once.
    """

    id = fields.IntField(pk=True)
    address = fields.CharField(max_length=36, unique=True)
    typename = fields.CharField(max_length=50, null=True)


class Holder(Model):
    """Canonical identity registry (address is stored ONCE).
    Small and efficient: keeps the hot index compact (INT PK, unique address).
    """

    id = fields.IntField(pk=True)
    address = fields.CharField(max_length=36, unique=True)
    name = fields.TextField(null=True, index=True)
    
    metadata_uri = fields.TextField(null=True)
    metadata_synced = fields.BooleanField(default=False, index=True)

    is_split = fields.BooleanField(default=False, index=True)

    first_seen = fields.DatetimeField(null=True)
    last_seen = fields.DatetimeField(null=True)


class HolderMetadata(Model):
    """Sidecar table for User Profiles (Bios, Avatars, etc)."""

    holder = fields.OneToOneField('models.Holder', pk=True, related_name='metadata_sidecar')

    # Raw JSON and extracted fields
    content = fields.JSONField(null=True)
    bio = fields.TextField(null=True)
    alias = fields.TextField(null=True)
    logo = fields.TextField(null=True)  # Avatar URI

    class Meta:
        table = 'holder_metadata'


class Token(Model):
    id = fields.BigIntField(pk=True)
    contract: fields.ForeignKeyField['Contract'] = fields.ForeignKeyField('models.Contract', related_name='tokens')
    token_id = fields.BigIntField(index=True)

    creator: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField('models.Holder', related_name='tokens')

    supply = fields.BigIntField()
    metadata_uri = fields.TextField(null=True)
    metadata_synced = fields.BooleanField(default=False, index=True)
    timestamp = fields.DatetimeField(index=True)

    is_signed = fields.BooleanField(default=False, index=True)

    class Meta:
        unique_together = ('contract', 'token_id')


class TokenHolder(Model):
    """Tracks the current quantity of a token held by an address."""
    id = fields.BigIntField(pk=True)
    token = fields.ForeignKeyField('models.Token', related_name='holders')
    holder = fields.ForeignKeyField('models.Holder', related_name='holdings')
    quantity = fields.BigIntField(default=0)

    class Meta:
        unique_together = ('token', 'holder')
        table = 'token_holder'


class TokenMetadata(Model):
    """Sidecar table for heavy IPFS data.
    Keeping this separate ensures 'Token' table scans remain blindingly fast.
    """

    token = fields.OneToOneField('models.Token', pk=True, related_name='metadata_sidecar')

    # Store the raw JSON once
    content = fields.JSONField(null=True)

    # Extract searchable fields for indexing
    name = fields.TextField(null=True, index=True)
    description = fields.TextField(null=True)
    
    # MIME type and rich URIs
    mime = fields.TextField(null=True, index=True)
    artifact_uri = fields.TextField(null=True)
    display_uri = fields.TextField(null=True)
    thumbnail_uri = fields.TextField(null=True)

    # Optional: If you want Full Text Search, we can add triggers later.
    class Meta:
        table = 'token_metadata'


class Tag(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, unique=True, index=True)

class TokenTag(Model):
    id = fields.BigIntField(pk=True)
    token = fields.ForeignKeyField('models.Token', related_name='tags')
    tag = fields.ForeignKeyField('models.Tag', related_name='tokens')

    class Meta:
        unique_together = ('token', 'tag')


class IgnoredCid(Model):
    """CIDs that are known bad or have failed too many times."""
    cid = fields.CharField(max_length=100, pk=True)
    reason = fields.TextField(null=True)
    timestamp = fields.DatetimeField(auto_now_add=True)


class Swap(Model):
    id = fields.BigIntField(pk=True)
    # The ID inside the smart contract storage
    swap_id = fields.BigIntField(index=True)
    contract: fields.ForeignKeyField['Contract'] = fields.ForeignKeyField('models.Contract', related_name='swaps')
    market_version = fields.EnumField(MarketVersion, index=True)

    seller: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField('models.Holder', related_name='swaps')

    token = fields.ForeignKeyField('models.Token', related_name='swaps')

    amount_initial = fields.BigIntField()
    amount_left = fields.BigIntField()
    price_mutez = fields.BigIntField()
    royalties_permille = fields.IntField()  # 100 = 10%

    status = fields.EnumField(SwapStatus, default=SwapStatus.ACTIVE, index=True)
    timestamp = fields.DatetimeField()

    class Meta:
        unique_together = ('contract', 'swap_id')


class Trade(Model):
    id = fields.BigIntField(pk=True)
    swap = fields.ForeignKeyField('models.Swap', related_name='trades')

    buyer: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField('models.Holder', related_name='purchases')

    amount = fields.BigIntField()
    price_mutez = fields.BigIntField()
    timestamp = fields.DatetimeField()


class Transfer(Model):
    id = fields.BigIntField(pk=True)
    token = fields.ForeignKeyField('models.Token', related_name='transfers')

    # Identifiers (ForeignKeys to Holder table)
    # Using only FKs saves ~1.5GB of space on 10M+ transfers by removing redundant address strings
    from_holder: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField(
        'models.Holder', related_name='transfers_sent'
    )
    to_holder: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField(
        'models.Holder', related_name='transfers_received'
    )

    amount = fields.BigIntField()
    timestamp = fields.DatetimeField(index=True)
    level = fields.IntField()


class SplitContract(Model):
    id = fields.IntField(pk=True)
    contract = fields.OneToOneField('models.Holder', related_name='split_contract_sidecar')
    administrator = fields.ForeignKeyField('models.Holder', related_name='managed_splits')
    total_shares = fields.BigIntField()

    class Meta:
        table = 'split_contract'


class Shareholder(Model):
    id = fields.BigIntField(pk=True)
    split_contract = fields.ForeignKeyField('models.SplitContract', related_name='shareholders')
    holder = fields.ForeignKeyField('models.Holder', related_name='shares')
    shares = fields.BigIntField()
    holder_type = fields.EnumField(ShareholderStatus, default=ShareholderStatus.BENEFACTOR)

    class Meta:
        unique_together = ('split_contract', 'holder')


class Signature(Model):
    id = fields.BigIntField(pk=True)
    token = fields.ForeignKeyField('models.Token', related_name='signatures')
    holder = fields.ForeignKeyField('models.Holder', related_name='signatures')

    class Meta:
        unique_together = ('token', 'holder')
