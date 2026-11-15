from uuid import UUID
from decimal import Decimal
from pydantic import Field, model_validator
from .schemas import StrictInput, ID, TabPayment


class SplitLine(StrictInput):
    sales_order_line_id: ID
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)


class SplitBill(StrictInput):
    request_key: UUID
    expected_revision: ID
    expected_total: Decimal = Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    lines: list[SplitLine] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_lines(self):
        if len({line.sales_order_line_id for line in self.lines}) != len(self.lines):
            raise ValueError('Choose each original line once per bill')
        return self


class SplitPayment(TabPayment):
    expected_balance: Decimal = Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
