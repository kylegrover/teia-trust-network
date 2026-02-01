from enum import Enum

from dipdup import fields
from dipdup.models import Model


class MarketVersion(str, Enum):
    V1 = 'v1'
    V2 = 'v2'
    TEIA = 'teia'


class Token(Model):
    id = fields.BigIntField(pk=True)
    # The FA2 contract address (e.g. KT1RJ6...)
    contract = fields.CharField(max_length=36)
    token_id = fields.BigIntField()
    creator_address = fields.CharField(max_length=36)
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

    seller_address = fields.CharField(max_length=36)
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
    buyer_address = fields.CharField(max_length=36)
    amount = fields.BigIntField()
    price_mutez = fields.BigIntField()  # Snapshot price at time of sale
    timestamp = fields.DatetimeField()
