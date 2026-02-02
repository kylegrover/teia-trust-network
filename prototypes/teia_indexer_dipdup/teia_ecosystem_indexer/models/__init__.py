from enum import Enum

from dipdup import fields
from dipdup.models import Model


class MarketVersion(str, Enum):
    V1 = 'v1'
    V2 = 'v2'
    TEIA = 'teia'


class Holder(Model):
    """Canonical identity registry (address is stored ONCE).
    - Backwards-compatible: handlers will continue writing legacy string columns until migration completes.
    - Small: keeps the hot index compact (INT PK, unique address).
    """

    id = fields.IntField(pk=True)
    address = fields.CharField(max_length=36, unique=True)
    first_seen = fields.DatetimeField(null=True)
    last_seen = fields.DatetimeField(null=True)


class Token(Model):
    id = fields.BigIntField(pk=True)
    # The FA2 contract address (e.g. KT1RJ6...)
    contract = fields.CharField(max_length=36)
    token_id = fields.BigIntField()
    # New canonical FK to the Identity registry (nullable until migration completes)
    creator: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField(
        'models.Holder', related_name='tokens', null=True
    )
    # Legacy string (kept during rollout/backfill) — will be removed in a later migration
    creator_address = fields.CharField(max_length=36, null=True)
    supply = fields.BigIntField()
    # IPFS URI (e.g. ipfs://Qm...)
    metadata_uri = fields.TextField(null=True)
    # The actual JSON content, fetched later
    metadata = fields.JSONField(null=True)
    metadata_synced = fields.BooleanField(default=False)
    timestamp = fields.DatetimeField()

    class Meta:
        unique_together = ('contract', 'token_id')


class Swap(Model):
    id = fields.BigIntField(pk=True)
    # The ID inside the smart contract storage
    swap_id = fields.BigIntField()
    contract_address = fields.CharField(max_length=36)
    market_version = fields.EnumField(MarketVersion)

    # Canonical FK to `Holder` (nullable until migration completes)
    seller: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField('models.Holder', related_name='swaps', null=True)
    # Legacy string retained for compatibility/backfill
    seller_address = fields.CharField(max_length=36, null=True)
    token = fields.ForeignKeyField('models.Token', related_name='swaps')

    amount_initial = fields.BigIntField()
    amount_left = fields.BigIntField()
    price_mutez = fields.BigIntField()
    royalties_permille = fields.IntField()  # 100 = 10%

    status = fields.CharField(max_length=20, default='active')  # active, finished, canceled
    timestamp = fields.DatetimeField()

    class Meta:
        # Swap IDs are unique PER CONTRACT, not globally
        unique_together = ('contract_address', 'swap_id')


class Trade(Model):
    id = fields.BigIntField(pk=True)
    swap = fields.ForeignKeyField('models.Swap', related_name='trades')
    # FK to Holder for compact storage
    buyer: fields.ForeignKeyField['Holder'] = fields.ForeignKeyField(
        'models.Holder', related_name='purchases', null=True
    )
    # Legacy string (nullable during rollout)
    buyer_address = fields.CharField(max_length=36, null=True)
    amount = fields.BigIntField()
    price_mutez = fields.BigIntField()  # Snapshot price at time of sale
    timestamp = fields.DatetimeField()
