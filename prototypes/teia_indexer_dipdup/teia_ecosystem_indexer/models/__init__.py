from enum import Enum

from dipdup import fields
from dipdup.models import Model


class MarketVersion(str, Enum):
    V1 = 'v1'
    V2 = 'v2'
    TEIA = 'teia'


class Holder(Model):
    """Canonical identity registry (address is stored ONCE).
    Small and efficient: keeps the hot index compact (INT PK, unique address).
    """

    id = fields.IntField(pk=True)
    address = fields.CharField(max_length=36, unique=True)
    first_seen = fields.DatetimeField(null=True)
    last_seen = fields.DatetimeField(null=True)


class Token(Model):
    id = fields.BigIntField(pk=True)
    contract = fields.CharField(max_length=36, index=True)
    token_id = fields.BigIntField(index=True)

    creator: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField('models.Holder', related_name='tokens')
    creator_address = fields.CharField(max_length=36, index=True)

    supply = fields.BigIntField()
    metadata_uri = fields.TextField(null=True)
    metadata_synced = fields.BooleanField(default=False, index=True)
    timestamp = fields.DatetimeField(index=True)

    class Meta:
        unique_together = ('contract', 'token_id')


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
    # Store 'image' or 'artifact' URI explicitly for UI display without parsing JSON
    display_uri = fields.TextField(null=True)

    # Optional: If you want Full Text Search, we can add triggers later.
    class Meta:
        table = 'token_metadata'


class Swap(Model):
    id = fields.BigIntField(pk=True)
    # The ID inside the smart contract storage
    swap_id = fields.BigIntField(index=True)
    contract_address = fields.CharField(max_length=36, index=True)
    market_version = fields.EnumField(MarketVersion, index=True)

    # Hybrid Identity
    seller: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField('models.Holder', related_name='swaps')
    seller_address = fields.CharField(max_length=36, index=True)

    token = fields.ForeignKeyField('models.Token', related_name='swaps')

    amount_initial = fields.BigIntField()
    amount_left = fields.BigIntField()
    price_mutez = fields.BigIntField()
    royalties_permille = fields.IntField()  # 100 = 10%

    status = fields.CharField(max_length=20, default='active', index=True)  # active, finished, canceled
    timestamp = fields.DatetimeField()

    class Meta:
        unique_together = ('contract_address', 'swap_id')


class Trade(Model):
    id = fields.BigIntField(pk=True)
    swap = fields.ForeignKeyField('models.Swap', related_name='trades')

    # Hybrid Identity
    buyer: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField('models.Holder', related_name='purchases')
    buyer_address = fields.CharField(max_length=36, index=True)

    amount = fields.BigIntField()
    price_mutez = fields.BigIntField()
    timestamp = fields.DatetimeField()


class Transfer(Model):
    id = fields.BigIntField(pk=True)
    token = fields.ForeignKeyField('models.Token', related_name='transfers')

    # Hybrid Identity for sender and receiver
    from_holder: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField(
        'models.Holder', related_name='transfers_sent'
    )
    from_address = fields.CharField(max_length=36, index=True)

    to_holder: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField(
        'models.Holder', related_name='transfers_received'
    )
    to_address = fields.CharField(max_length=36, index=True)

    amount = fields.BigIntField()
    timestamp = fields.DatetimeField(index=True)
    level = fields.IntField()
