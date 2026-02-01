from dipdup import fields
from dipdup.models import Model


class Swap(Model):
    id = fields.IntField(pk=True)
    swap_id = fields.BigIntField(index=True)
    contract_address = fields.CharField(max_length=36)
    seller_address = fields.CharField(max_length=36)
    token_id = fields.BigIntField()
    price = fields.BigIntField()
    amount_left = fields.IntField()


class Trade(Model):
    id = fields.IntField(pk=True)
    swap = fields.ForeignKeyField('models.Swap', related_name='trades')
    buyer_address = fields.CharField(max_length=36)
    amount = fields.IntField()
    timestamp = fields.DatetimeField()
