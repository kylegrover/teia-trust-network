from dipdup import fields
from dipdup.models import Model


class Swap(Model):
    """Represents a Listing. We need this to resolve 'Swap #500' -> 'Artist A'"""

    id = fields.IntField(pk=True)
    swap_id = fields.BigIntField(index=True)  # The ID used in the 'collect' call
    contract = fields.CharField(max_length=36)
    seller_address = fields.CharField(max_length=36)
    token_id = fields.BigIntField()
    price_mutez = fields.BigIntField()
    timestamp = fields.DatetimeField()


class TrustEdge(Model):
    """The core of your Trust Network: Who gave money to Whom?"""

    id = fields.IntField(pk=True)
    buyer_address = fields.CharField(max_length=36)
    seller_address = fields.CharField(max_length=36)  # Resolved from Swap
    contract = fields.CharField(max_length=36)
    token_id = fields.BigIntField(null=True)
    amount_paid_mutez = fields.BigIntField()
    swap_id = fields.BigIntField(null=True)
    timestamp = fields.DatetimeField()
